"""Core Buoyancy API — the main entry point."""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from buoyancy.calibrator import BuoyancyScore, Calibrator
from buoyancy.classifier import classify
from buoyancy.memory import DEFAULT_DB_PATH, Memory
from buoyancy.task import Budget, Complexity, ModelTier, TaskRecord


class TaskContext:
    """Context for a single task execution. Used within `with b.task(...):`."""

    def __init__(
        self,
        name: str,
        task_type: str,
        complexity: Complexity,
        budget: Budget,
        calibrator: Calibrator,
    ):
        self.name = name
        self.task_type = task_type
        self.complexity = complexity
        self.budget = budget
        self._calibrator = calibrator
        self._start_time = time.monotonic_ns()
        self._recorded = False

    def record(
        self,
        tokens_used: int,
        succeeded: bool = True,
        quality_score: float = 1.0,
        model_tier: Optional[ModelTier] = None,
        tool_calls: int = 0,
    ) -> BuoyancyScore:
        """Record the outcome of this task execution."""
        elapsed_ms = (time.monotonic_ns() - self._start_time) // 1_000_000

        task_record = TaskRecord(
            task_name=self.name,
            task_type=self.task_type,
            complexity=self.complexity,
            estimated_tokens=self.budget.max_tokens,
            estimated_model_tier=self.budget.model_tier,
            actual_tokens=tokens_used,
            actual_model_tier=model_tier or self.budget.model_tier,
            actual_tool_calls=tool_calls,
            duration_ms=elapsed_ms,
            succeeded=succeeded,
            quality_score=quality_score,
        )

        # Store in memory
        self._calibrator.memory.record(task_record)

        # Update calibration
        score = self._calibrator.update(task_record)
        self._recorded = True
        return score


class Buoyancy:
    """Main API for Neutral Buoyancy.

    Usage:
        b = Buoyancy()

        with b.task("fix-typo", task_type="docs", complexity="trivial") as t:
            response = llm_call(max_tokens=t.budget.max_tokens)
            t.record(tokens_used=response.usage.output_tokens, succeeded=True)

        b.report()
    """

    def __init__(self, db_path: Optional[Path] = None):
        self._memory = Memory(db_path or DEFAULT_DB_PATH)
        self._calibrator = Calibrator(self._memory)

    @contextmanager
    def task(
        self,
        name: str,
        task_type: str,
        complexity: str | Complexity = Complexity.MODERATE,
    ) -> Generator[TaskContext, None, None]:
        """Context manager for wrapping a task execution."""
        if isinstance(complexity, str):
            complexity = Complexity(complexity)

        budget = self._calibrator.estimate(task_type, complexity)

        ctx = TaskContext(
            name=name,
            task_type=task_type,
            complexity=complexity,
            budget=budget,
            calibrator=self._calibrator,
        )

        yield ctx

        if not ctx._recorded:
            # Auto-record with budget as actual if user didn't call record()
            ctx.record(tokens_used=budget.max_tokens, succeeded=True)

    @contextmanager
    def auto_task(self, name: str, description: str) -> Generator[TaskContext, None, None]:
        """Context manager that auto-classifies the task from a description."""
        task_type, complexity = classify(description)
        yield from self.task(name, task_type, complexity)

    def estimate(
        self, task_type: str, complexity: str | Complexity = Complexity.MODERATE
    ) -> Budget:
        """Get calibrated budget estimate without starting a task."""
        if isinstance(complexity, str):
            complexity = Complexity(complexity)
        return self._calibrator.estimate(task_type, complexity)

    def record_task(
        self,
        name: str,
        task_type: str,
        complexity: str | Complexity,
        tokens_used: int,
        succeeded: bool = True,
        quality_score: float = 1.0,
        model_tier: str | ModelTier = ModelTier.MEDIUM,
    ) -> BuoyancyScore:
        """Record a task without using the context manager."""
        if isinstance(complexity, str):
            complexity = Complexity(complexity)
        if isinstance(model_tier, str):
            model_tier = ModelTier(model_tier)

        budget = self._calibrator.estimate(task_type, complexity)

        record = TaskRecord(
            task_name=name,
            task_type=task_type,
            complexity=complexity,
            estimated_tokens=budget.max_tokens,
            estimated_model_tier=budget.model_tier,
            actual_tokens=tokens_used,
            actual_model_tier=model_tier,
            succeeded=succeeded,
            quality_score=quality_score,
        )

        self._memory.record(record)
        return self._calibrator.update(record)

    def buoyancy(
        self, task_type: str, complexity: str | Complexity = Complexity.MODERATE
    ) -> Optional[BuoyancyScore]:
        """Get current buoyancy score for a task type."""
        if isinstance(complexity, str):
            complexity = Complexity(complexity)
        return self._calibrator.get_buoyancy(task_type, complexity)

    def report(self) -> str:
        """Generate a human-readable calibration report."""
        scores = self._calibrator.get_all_scores()
        stats = self._memory.get_stats()

        lines = [
            "=== Neutral Buoyancy Report ===",
            f"Total records: {stats['total_records']}",
            f"Task types: {stats['unique_task_types']}",
            f"Calibrated pairs: {stats['calibrated_pairs']}",
            "",
        ]

        if not scores:
            lines.append("No calibration data yet. Start recording tasks!")
            return "\n".join(lines)

        lines.append(
            f"{'Type':<20} {'Complexity':<10} {'Tokens':<8} "
            f"{'Model':<8} {'Score':<8} {'Conf':<6} {'N':<4} {'Status'}"
        )
        lines.append("-" * 90)

        for s in scores:
            lines.append(
                f"{s.task_type:<20} {s.complexity.value:<10} "
                f"{s.optimal_tokens:<8} {s.model_tier.value:<8} "
                f"{s.score:>+6.2f}  {s.confidence:<6.2f} "
                f"{s.sample_count:<4} {s.symbol} {s.status}"
            )

        return "\n".join(lines)

    def close(self):
        self._memory.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
