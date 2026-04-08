"""Persistent effort memory using SQLite."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from buoyancy.task import Complexity, ModelTier, TaskRecord


DEFAULT_DB_PATH = Path.home() / ".buoyancy" / "memory.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    complexity TEXT NOT NULL,
    fingerprint TEXT NOT NULL,

    estimated_tokens INTEGER DEFAULT 0,
    estimated_model_tier TEXT DEFAULT 'medium',

    actual_tokens INTEGER DEFAULT 0,
    actual_model_tier TEXT DEFAULT 'medium',
    actual_tool_calls INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,

    succeeded BOOLEAN DEFAULT 1,
    quality_score REAL DEFAULT 1.0,
    buoyancy_delta REAL DEFAULT 0.0,

    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calibration (
    task_type TEXT NOT NULL,
    complexity TEXT NOT NULL,
    optimal_tokens INTEGER NOT NULL,
    optimal_model_tier TEXT NOT NULL,
    buoyancy_score REAL DEFAULT 0.0,
    confidence REAL DEFAULT 0.0,
    sample_count INTEGER DEFAULT 0,
    last_updated TEXT NOT NULL,
    PRIMARY KEY (task_type, complexity)
);

CREATE INDEX IF NOT EXISTS idx_task_type_complexity
    ON task_records(task_type, complexity);
"""


class Memory:
    """SQLite-backed persistent effort memory."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._lock = threading.Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.db_path.parent, 0o700)
        except OSError:
            pass  # May fail on some filesystems, non-critical
        is_new_db = not self.db_path.exists()
        self._conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._conn.executescript(_SCHEMA)
        if is_new_db:
            try:
                os.chmod(self.db_path, 0o600)
            except OSError:
                pass

    def record(self, task: TaskRecord) -> int:
        """Store a task execution record. Returns the record ID."""
        task.task_name = task.task_name[:200] if task.task_name else ""
        task.task_type = task.task_type[:50] if task.task_type else "unknown"
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """INSERT INTO task_records
                (task_name, task_type, complexity, fingerprint,
                 estimated_tokens, estimated_model_tier,
                 actual_tokens, actual_model_tier, actual_tool_calls, duration_ms,
                 succeeded, quality_score, buoyancy_delta, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.task_name,
                    task.task_type,
                    task.complexity.value,
                    task.fingerprint,
                    task.estimated_tokens,
                    task.estimated_model_tier.value,
                    task.actual_tokens,
                    task.actual_model_tier.value,
                    task.actual_tool_calls,
                    task.duration_ms,
                    task.succeeded,
                    task.quality_score,
                    task.buoyancy_delta,
                    task.timestamp.isoformat(),
                ),
            )
        return cursor.lastrowid  # type: ignore[return-value]

    def get_history(
        self,
        task_type: str,
        complexity: Optional[Complexity] = None,
        limit: int = 100,
    ) -> list[TaskRecord]:
        """Get historical records for a task type."""
        if complexity:
            rows = self._conn.execute(
                """SELECT * FROM task_records
                WHERE task_type = ? AND complexity = ?
                ORDER BY timestamp DESC LIMIT ?""",
                (task_type, complexity.value, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT * FROM task_records
                WHERE task_type = ?
                ORDER BY timestamp DESC LIMIT ?""",
                (task_type, limit),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_calibration(
        self, task_type: str, complexity: Complexity
    ) -> Optional[dict]:
        """Get current calibration for a (task_type, complexity) pair."""
        row = self._conn.execute(
            """SELECT * FROM calibration
            WHERE task_type = ? AND complexity = ?""",
            (task_type, complexity.value),
        ).fetchone()
        return dict(row) if row else None

    def update_calibration(
        self,
        task_type: str,
        complexity: Complexity,
        optimal_tokens: int,
        optimal_model_tier: ModelTier,
        buoyancy_score: float,
        confidence: float,
        sample_count: int,
    ) -> None:
        """Upsert calibration data."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO calibration
                (task_type, complexity, optimal_tokens, optimal_model_tier,
                 buoyancy_score, confidence, sample_count, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_type, complexity) DO UPDATE SET
                    optimal_tokens = excluded.optimal_tokens,
                    optimal_model_tier = excluded.optimal_model_tier,
                    buoyancy_score = excluded.buoyancy_score,
                    confidence = excluded.confidence,
                    sample_count = excluded.sample_count,
                    last_updated = excluded.last_updated""",
                (
                    task_type,
                    complexity.value,
                    optimal_tokens,
                    optimal_model_tier.value,
                    buoyancy_score,
                    confidence,
                    sample_count,
                    now,
                ),
            )

    def get_all_calibrations(self) -> list[dict]:
        """Get all calibration entries."""
        rows = self._conn.execute(
            "SELECT * FROM calibration ORDER BY task_type, complexity"
        ).fetchall()
        return [dict(r) for r in rows]

    def convergence_data(
        self, task_type: str, complexity: str
    ) -> list[int]:
        """Return time series of actual_tokens for a (task_type, complexity) pair.

        Records are returned in chronological order (oldest first).
        """
        rows = self._conn.execute(
            """SELECT actual_tokens FROM task_records
            WHERE task_type = ? AND complexity = ?
            ORDER BY timestamp ASC""",
            (task_type, complexity),
        ).fetchall()
        return [r[0] for r in rows]

    def get_stats(self) -> dict:
        """Get summary statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) FROM task_records"
        ).fetchone()[0]
        types = self._conn.execute(
            "SELECT COUNT(DISTINCT task_type) FROM task_records"
        ).fetchone()[0]
        calibrated = self._conn.execute(
            "SELECT COUNT(*) FROM calibration WHERE confidence >= 0.5"
        ).fetchone()[0]
        return {
            "total_records": total,
            "unique_task_types": types,
            "calibrated_pairs": calibrated,
        }


    def prune(self, older_than_days: int = 90) -> int:
        """Delete task records older than N days. Returns count deleted."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "DELETE FROM task_records WHERE timestamp < ?", (cutoff,)
            )
            return cursor.rowcount

    def reset(self, task_type: str | None = None) -> int:
        """Reset calibration data. If task_type given, only reset that type. Returns count deleted."""
        with self._lock, self._conn:
            if task_type:
                c1 = self._conn.execute("DELETE FROM calibration WHERE task_type = ?", (task_type,))
                c2 = self._conn.execute("DELETE FROM task_records WHERE task_type = ?", (task_type,))
                return c1.rowcount + c2.rowcount
            else:
                c1 = self._conn.execute("DELETE FROM calibration")
                c2 = self._conn.execute("DELETE FROM task_records")
                return c1.rowcount + c2.rowcount

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _row_to_record(self, row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            task_name=row["task_name"],
            task_type=row["task_type"],
            complexity=Complexity(row["complexity"]),
            fingerprint=row["fingerprint"],
            estimated_tokens=row["estimated_tokens"],
            estimated_model_tier=ModelTier(row["estimated_model_tier"]),
            actual_tokens=row["actual_tokens"],
            actual_model_tier=ModelTier(row["actual_model_tier"]),
            actual_tool_calls=row["actual_tool_calls"],
            duration_ms=row["duration_ms"],
            succeeded=bool(row["succeeded"]),
            quality_score=row["quality_score"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
