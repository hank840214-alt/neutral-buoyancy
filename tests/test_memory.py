"""Tests for the memory module."""

import sys
import tempfile
import threading
from pathlib import Path

import pytest

from buoyancy.memory import Memory
from buoyancy.task import Complexity, ModelTier, TaskRecord


def make_memory() -> Memory:
    tmp = tempfile.mktemp(suffix=".db")
    return Memory(Path(tmp))


def test_record_and_retrieve():
    mem = make_memory()
    record = TaskRecord(
        task_name="fix-typo",
        task_type="documentation",
        complexity=Complexity.TRIVIAL,
        estimated_tokens=300,
        actual_tokens=150,
        succeeded=True,
    )
    rid = mem.record(record)
    assert rid >= 1

    history = mem.get_history("documentation", Complexity.TRIVIAL)
    assert len(history) == 1
    assert history[0].task_name == "fix-typo"
    assert history[0].actual_tokens == 150
    mem.close()


def test_calibration_upsert():
    mem = make_memory()

    mem.update_calibration(
        task_type="bugfix",
        complexity=Complexity.SIMPLE,
        optimal_tokens=500,
        optimal_model_tier=ModelTier.MEDIUM,
        buoyancy_score=0.1,
        confidence=0.3,
        sample_count=5,
    )

    cal = mem.get_calibration("bugfix", Complexity.SIMPLE)
    assert cal is not None
    assert cal["optimal_tokens"] == 500
    assert cal["sample_count"] == 5

    # Upsert
    mem.update_calibration(
        task_type="bugfix",
        complexity=Complexity.SIMPLE,
        optimal_tokens=450,
        optimal_model_tier=ModelTier.LOW,
        buoyancy_score=0.05,
        confidence=0.5,
        sample_count=10,
    )

    cal = mem.get_calibration("bugfix", Complexity.SIMPLE)
    assert cal["optimal_tokens"] == 450
    assert cal["sample_count"] == 10
    mem.close()


def test_get_stats():
    mem = make_memory()

    for i in range(3):
        mem.record(TaskRecord(
            task_name=f"task-{i}",
            task_type="feature",
            complexity=Complexity.MODERATE,
            actual_tokens=1000 + i * 100,
        ))

    stats = mem.get_stats()
    assert stats["total_records"] == 3
    assert stats["unique_task_types"] == 1
    mem.close()


def test_empty_history():
    mem = make_memory()
    history = mem.get_history("nonexistent")
    assert history == []
    mem.close()


def test_wal_mode_enabled():
    mem = make_memory()
    row = mem._conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0] == "wal"
    mem.close()


def test_concurrent_writes_no_error():
    mem = make_memory()
    errors = []

    def write_record(i: int):
        try:
            mem.record(TaskRecord(
                task_name=f"concurrent-task-{i}",
                task_type="concurrent",
                complexity=Complexity.TRIVIAL,
                actual_tokens=100 + i,
            ))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=write_record, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Concurrent write errors: {errors}"
    history = mem.get_history("concurrent")
    assert len(history) == 10
    mem.close()


@pytest.mark.skipif(sys.platform == "win32", reason="Unix permissions not supported on Windows")
def test_file_permissions():
    tmp_path = Path(tempfile.mktemp(suffix=".db"))
    mem = Memory(tmp_path)
    mem.close()
    mode = tmp_path.stat().st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


# --- M7: Data lifecycle tests ---

from datetime import datetime, timedelta, timezone
import sqlite3 as _sqlite3


def _insert_old_record(mem: Memory, task_type: str, days_ago: int) -> None:
    """Directly insert a record with a backdated timestamp."""
    old_ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    mem._conn.execute(
        """INSERT INTO task_records
        (task_name, task_type, complexity, fingerprint,
         estimated_tokens, estimated_model_tier,
         actual_tokens, actual_model_tier, actual_tool_calls, duration_ms,
         succeeded, quality_score, buoyancy_delta, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("old-task", task_type, "trivial", "fp-old", 100, "medium",
         100, "medium", 0, 0, 1, 1.0, 0.0, old_ts),
    )
    mem._conn.commit()


def test_prune_removes_old_records():
    mem = make_memory()
    _insert_old_record(mem, "bugfix", days_ago=100)
    deleted = mem.prune(older_than_days=90)
    assert deleted == 1
    assert mem.get_history("bugfix") == []
    mem.close()


def test_prune_keeps_recent():
    mem = make_memory()
    _insert_old_record(mem, "bugfix", days_ago=100)
    # Also insert a recent record via normal path
    mem.record(TaskRecord(
        task_name="recent-task",
        task_type="bugfix",
        complexity=Complexity.TRIVIAL,
        actual_tokens=50,
    ))
    deleted = mem.prune(older_than_days=90)
    assert deleted == 1
    history = mem.get_history("bugfix")
    assert len(history) == 1
    assert history[0].task_name == "recent-task"
    mem.close()


def test_reset_all():
    mem = make_memory()
    for i in range(3):
        mem.record(TaskRecord(
            task_name=f"t{i}",
            task_type="feature",
            complexity=Complexity.SIMPLE,
            actual_tokens=200,
        ))
    mem.update_calibration(
        task_type="feature",
        complexity=Complexity.SIMPLE,
        optimal_tokens=200,
        optimal_model_tier=ModelTier.MEDIUM,
        buoyancy_score=0.0,
        confidence=0.5,
        sample_count=3,
    )
    deleted = mem.reset()
    assert deleted >= 4  # 3 task_records + 1 calibration
    stats = mem.get_stats()
    assert stats["total_records"] == 0
    assert stats["calibrated_pairs"] == 0
    mem.close()


def test_reset_by_type():
    mem = make_memory()
    mem.record(TaskRecord(
        task_name="bugfix-task",
        task_type="bugfix",
        complexity=Complexity.SIMPLE,
        actual_tokens=100,
    ))
    mem.record(TaskRecord(
        task_name="docs-task",
        task_type="docs",
        complexity=Complexity.TRIVIAL,
        actual_tokens=50,
    ))
    deleted = mem.reset(task_type="bugfix")
    assert deleted >= 1
    assert mem.get_history("bugfix") == []
    assert len(mem.get_history("docs")) == 1
    mem.close()


def test_task_name_truncation():
    mem = make_memory()
    long_name = "x" * 300
    long_type = "y" * 100
    mem.record(TaskRecord(
        task_name=long_name,
        task_type=long_type,
        complexity=Complexity.TRIVIAL,
        actual_tokens=10,
    ))
    history = mem.get_history(long_type[:50])
    assert len(history) == 1
    assert len(history[0].task_name) == 200
    assert len(history[0].task_type) == 50
    mem.close()
