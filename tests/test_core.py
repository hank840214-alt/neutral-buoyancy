"""Tests for the core Buoyancy API."""

import tempfile
from pathlib import Path

from buoyancy.core import Buoyancy


def make_buoyancy() -> Buoyancy:
    tmp = tempfile.mktemp(suffix=".db")
    return Buoyancy(Path(tmp))


def test_context_manager_basic():
    b = make_buoyancy()

    with b.task("test-task", task_type="bugfix", complexity="simple") as t:
        assert t.budget.max_tokens > 0
        t.record(tokens_used=400, succeeded=True)

    # Should have calibration data now
    score = b.buoyancy("bugfix", "simple")
    assert score is not None
    assert score.sample_count == 1
    b.close()


def test_record_task_direct():
    b = make_buoyancy()

    score = b.record_task(
        name="direct-record",
        task_type="feature",
        complexity="moderate",
        tokens_used=1500,
        succeeded=True,
    )

    assert score.task_type == "feature"
    assert score.sample_count == 1
    b.close()


def test_report_empty():
    b = make_buoyancy()
    report = b.report()
    assert "No calibration data" in report
    b.close()


def test_report_with_data():
    b = make_buoyancy()

    for i in range(3):
        b.record_task(
            name=f"task-{i}",
            task_type="refactor",
            complexity="complex",
            tokens_used=3000 + i * 100,
        )

    report = b.report()
    assert "refactor" in report
    assert "complex" in report
    b.close()


def test_multiple_task_types():
    b = make_buoyancy()

    b.record_task("t1", "docs", "trivial", tokens_used=100)
    b.record_task("t2", "bugfix", "simple", tokens_used=500)
    b.record_task("t3", "feature", "complex", tokens_used=3000)

    # Each should have independent calibration
    d = b.buoyancy("docs", "trivial")
    f = b.buoyancy("feature", "complex")
    assert d.optimal_tokens != f.optimal_tokens
    b.close()


def test_context_manager_as_with():
    with make_buoyancy() as b:
        b.record_task("t1", "test", "simple", tokens_used=200)
        assert b.buoyancy("test", "simple") is not None


def test_record_task_negative_tokens_raises():
    b = make_buoyancy()
    import pytest
    with pytest.raises(ValueError, match="non-negative"):
        b.record_task("t1", "bugfix", "simple", tokens_used=-1)
    b.close()


def test_record_task_excessive_tokens_raises():
    b = make_buoyancy()
    import pytest
    with pytest.raises(ValueError, match="sanity limit"):
        b.record_task("t1", "bugfix", "simple", tokens_used=1_000_001)
    b.close()


def test_record_task_invalid_quality_raises():
    b = make_buoyancy()
    import pytest
    with pytest.raises(ValueError, match="quality_score"):
        b.record_task("t1", "bugfix", "simple", tokens_used=500, quality_score=1.5)
    b.close()


def test_context_manager_exception_records_failure():
    b = make_buoyancy()
    try:
        with b.task("failing-task", task_type="bugfix", complexity="simple") as t:
            raise RuntimeError("deliberate failure")
    except RuntimeError:
        pass

    score = b.buoyancy("bugfix", "simple")
    assert score is not None
    assert score.sample_count == 1
    # The task was recorded as failed; buoyancy score should reflect that
    b.close()


def test_double_close_is_safe():
    b = make_buoyancy()
    b.record_task("t1", "test", "simple", tokens_used=100)
    b.close()
    b.close()  # second close must not raise
