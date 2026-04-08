"""Tests for the memory module."""

import tempfile
from pathlib import Path

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
