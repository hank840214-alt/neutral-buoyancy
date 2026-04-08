"""Tests for the calibration algorithm."""

import tempfile
from pathlib import Path

from buoyancy.calibrator import Calibrator
from buoyancy.memory import Memory
from buoyancy.task import Complexity, ModelTier, TaskRecord


def make_calibrator() -> Calibrator:
    tmp = tempfile.mktemp(suffix=".db")
    mem = Memory(Path(tmp))
    return Calibrator(mem)


def test_first_calibration():
    cal = make_calibrator()
    record = TaskRecord(
        task_name="first-task",
        task_type="bugfix",
        complexity=Complexity.SIMPLE,
        estimated_tokens=800,
        actual_tokens=400,
        succeeded=True,
    )
    cal.memory.record(record)
    score = cal.update(record)

    assert score.task_type == "bugfix"
    assert score.sample_count == 1
    assert score.optimal_tokens == 400  # First record = actual tokens
    assert score.confidence > 0
    cal.memory.close()


def test_convergence_over_multiple_tasks():
    cal = make_calibrator()
    tokens_series = [500, 480, 510, 490, 500, 505, 495, 500, 498, 502]

    for i, tokens in enumerate(tokens_series):
        record = TaskRecord(
            task_name=f"task-{i}",
            task_type="code-review",
            complexity=Complexity.MODERATE,
            estimated_tokens=2000,  # default estimate
            actual_tokens=tokens,
            succeeded=True,
        )
        cal.memory.record(record)
        score = cal.update(record)

    # After 10 similar tasks, should converge near 500
    assert 450 < score.optimal_tokens < 550
    assert score.confidence >= 0.3  # At least 5 samples
    assert score.sample_count == 10
    cal.memory.close()


def test_failed_task_increases_budget():
    cal = make_calibrator()

    # First, establish a baseline
    for i in range(5):
        record = TaskRecord(
            task_name=f"task-{i}",
            task_type="feature",
            complexity=Complexity.COMPLEX,
            estimated_tokens=4000,
            actual_tokens=3000,
            succeeded=True,
        )
        cal.memory.record(record)
        cal.update(record)

    baseline = cal.memory.get_calibration("feature", Complexity.COMPLEX)
    baseline_tokens = baseline["optimal_tokens"]

    # Now a failed task
    failed = TaskRecord(
        task_name="failed-task",
        task_type="feature",
        complexity=Complexity.COMPLEX,
        estimated_tokens=4000,
        actual_tokens=4000,
        succeeded=False,
    )
    cal.memory.record(failed)
    score = cal.update(failed)

    # Budget should have increased
    assert score.optimal_tokens > baseline_tokens
    assert score.score < 0  # Negative buoyancy (sinking)
    cal.memory.close()


def test_estimate_with_no_data_returns_default():
    cal = make_calibrator()
    budget = cal.estimate("unknown-type", Complexity.TRIVIAL)
    assert budget.max_tokens == 300  # default for trivial
    assert budget.confidence == 0.1
    assert budget.based_on_n == 0
    cal.memory.close()


def test_estimate_with_calibration_data():
    cal = make_calibrator()

    # Build up calibration
    for i in range(5):
        record = TaskRecord(
            task_name=f"task-{i}",
            task_type="docs",
            complexity=Complexity.SIMPLE,
            estimated_tokens=800,
            actual_tokens=300,
            succeeded=True,
        )
        cal.memory.record(record)
        cal.update(record)

    budget = cal.estimate("docs", Complexity.SIMPLE)
    # Should be calibrated value * safety margin
    assert budget.based_on_n == 5
    assert budget.confidence >= 0.3
    assert budget.max_tokens < 800  # Much less than default
    cal.memory.close()


def test_buoyancy_score_direction():
    cal = make_calibrator()

    # Over-budgeted task (estimated 2000, used 500)
    record = TaskRecord(
        task_name="over-budget",
        task_type="test",
        complexity=Complexity.TRIVIAL,
        estimated_tokens=2000,
        actual_tokens=500,
        succeeded=True,
    )
    assert record.buoyancy_delta > 0  # Positive = too much air

    # Under-budgeted task (estimated 200, used 500)
    record2 = TaskRecord(
        task_name="under-budget",
        task_type="test",
        complexity=Complexity.TRIVIAL,
        estimated_tokens=200,
        actual_tokens=500,
        succeeded=True,
    )
    assert record2.buoyancy_delta < 0  # Negative = sinking

    # Just right (estimated 500, used 480)
    record3 = TaskRecord(
        task_name="just-right",
        task_type="test",
        complexity=Complexity.TRIVIAL,
        estimated_tokens=500,
        actual_tokens=480,
        succeeded=True,
    )
    assert abs(record3.buoyancy_delta) < 0.1  # Neutral
    cal.memory.close()
