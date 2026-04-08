"""Tests for the viz module."""

from __future__ import annotations

import tempfile
from pathlib import Path

from buoyancy.calibrator import Calibrator
from buoyancy.memory import Memory
from buoyancy.task import Complexity, ModelTier, TaskRecord
from buoyancy.viz import convergence_chart, dashboard, sparkline


def make_memory() -> Memory:
    tmp = tempfile.mktemp(suffix=".db")
    return Memory(Path(tmp))


def make_calibrator(mem: Memory) -> Calibrator:
    return Calibrator(mem)


# ---------------------------------------------------------------------------
# convergence_chart tests
# ---------------------------------------------------------------------------

def test_convergence_chart_with_data():
    mem = make_memory()
    tokens_series = [500, 480, 510, 490, 500]
    for i, tokens in enumerate(tokens_series):
        mem.record(TaskRecord(
            task_name=f"task-{i}",
            task_type="bugfix",
            complexity=Complexity.MODERATE,
            actual_tokens=tokens,
        ))

    cal = {"confidence": 0.30, "optimal_tokens": 496}
    result = convergence_chart(mem, "bugfix", "moderate", calibration=cal)

    assert "bugfix/moderate convergence" in result
    assert "n=5" in result
    assert "conf=0.30" in result
    assert "← current optimal" in result
    # Should have at least a few lines
    lines = result.strip().splitlines()
    assert len(lines) >= 4
    mem.close()


def test_convergence_chart_empty_data():
    mem = make_memory()
    result = convergence_chart(mem, "nonexistent", "trivial", calibration=None)

    assert "nonexistent/trivial convergence" in result
    assert "n=0" in result
    assert "no data yet" in result
    mem.close()


def test_convergence_chart_single_record():
    mem = make_memory()
    mem.record(TaskRecord(
        task_name="only-task",
        task_type="docs",
        complexity=Complexity.TRIVIAL,
        actual_tokens=200,
    ))

    cal = {"confidence": 0.05, "optimal_tokens": 200}
    result = convergence_chart(mem, "docs", "trivial", calibration=cal)

    assert "docs/trivial convergence" in result
    assert "n=1" in result
    assert "200" in result
    mem.close()


def test_convergence_chart_no_calibration():
    mem = make_memory()
    for i in range(3):
        mem.record(TaskRecord(
            task_name=f"t-{i}",
            task_type="feature",
            complexity=Complexity.COMPLEX,
            actual_tokens=3000 + i * 100,
        ))

    result = convergence_chart(mem, "feature", "complex", calibration=None)
    assert "feature/complex convergence" in result
    assert "n=3" in result
    mem.close()


# ---------------------------------------------------------------------------
# dashboard tests
# ---------------------------------------------------------------------------

def test_dashboard_empty():
    mem = make_memory()
    cal = make_calibrator(mem)
    result = dashboard(mem, cal)

    assert "Buoyancy Dashboard" in result
    assert "No calibration data" in result
    mem.close()


def test_dashboard_with_data():
    mem = make_memory()
    cal = make_calibrator(mem)

    # Record enough tasks to get calibration entries
    for task_type, complexity, tokens in [
        ("documentation", Complexity.TRIVIAL, 173),
        ("bugfix", Complexity.MODERATE, 1069),
    ]:
        for i in range(4):
            record = TaskRecord(
                task_name=f"t-{i}",
                task_type=task_type,
                complexity=complexity,
                estimated_tokens=tokens * 2,
                actual_tokens=tokens + i * 10,
                succeeded=True,
            )
            mem.record(record)
            cal.update(record)

    result = dashboard(mem, cal)

    assert "Buoyancy Dashboard" in result
    assert "documentation/trivial" in result
    assert "bugfix/moderate" in result
    assert "tok" in result
    assert "conf:" in result
    # Bar format check
    assert "[" in result and "]" in result
    mem.close()


def test_dashboard_shows_symbol():
    mem = make_memory()
    cal = make_calibrator(mem)

    for i in range(4):
        record = TaskRecord(
            task_name=f"t-{i}",
            task_type="feature",
            complexity=Complexity.COMPLEX,
            estimated_tokens=4000,
            actual_tokens=3800,
            succeeded=True,
        )
        mem.record(record)
        cal.update(record)

    result = dashboard(mem, cal)
    # A buoyancy symbol should appear
    assert any(sym in result for sym in ["⚖️", "🫧", "🪨"])
    mem.close()


# ---------------------------------------------------------------------------
# sparkline tests
# ---------------------------------------------------------------------------

def test_sparkline_with_data():
    mem = make_memory()
    tokens_series = [800, 850, 900, 950, 1000, 1050, 1100, 1050, 1000, 950]
    for i, tokens in enumerate(tokens_series):
        mem.record(TaskRecord(
            task_name=f"t-{i}",
            task_type="bugfix",
            complexity=Complexity.MODERATE,
            actual_tokens=tokens,
        ))

    result = sparkline(mem, "bugfix", "moderate")

    assert "bugfix/moderate:" in result
    assert "800-1100 tokens" in result
    assert "avg 965" in result
    # Should contain spark characters
    assert any(ch in result for ch in "▁▂▃▄▅▆▇█")
    mem.close()


def test_sparkline_empty_data():
    mem = make_memory()
    result = sparkline(mem, "nonexistent", "trivial")

    assert "nonexistent/trivial:" in result
    assert "no data" in result
    mem.close()


def test_sparkline_single_value():
    mem = make_memory()
    mem.record(TaskRecord(
        task_name="solo",
        task_type="test",
        complexity=Complexity.SIMPLE,
        actual_tokens=500,
    ))

    result = sparkline(mem, "test", "simple")

    assert "test/simple:" in result
    assert "500-500 tokens" in result
    assert "avg 500" in result
    mem.close()


def test_sparkline_uniform_values():
    """All same values should not crash (span=0 edge case)."""
    mem = make_memory()
    for i in range(5):
        mem.record(TaskRecord(
            task_name=f"t-{i}",
            task_type="docs",
            complexity=Complexity.TRIVIAL,
            actual_tokens=300,
        ))

    result = sparkline(mem, "docs", "trivial")
    assert "300-300 tokens" in result
    assert "avg 300" in result
    mem.close()


# ---------------------------------------------------------------------------
# memory.convergence_data tests
# ---------------------------------------------------------------------------

def test_convergence_data_chronological_order():
    mem = make_memory()
    expected = [100, 200, 300, 400, 500]
    for i, tokens in enumerate(expected):
        mem.record(TaskRecord(
            task_name=f"t-{i}",
            task_type="review",
            complexity=Complexity.SIMPLE,
            actual_tokens=tokens,
        ))

    data = mem.convergence_data("review", "simple")
    assert data == expected
    mem.close()


def test_convergence_data_empty():
    mem = make_memory()
    data = mem.convergence_data("ghost", "epic")
    assert data == []
    mem.close()


def test_convergence_data_filters_by_pair():
    mem = make_memory()
    mem.record(TaskRecord(
        task_name="a", task_type="docs", complexity=Complexity.TRIVIAL, actual_tokens=100
    ))
    mem.record(TaskRecord(
        task_name="b", task_type="docs", complexity=Complexity.MODERATE, actual_tokens=999
    ))
    mem.record(TaskRecord(
        task_name="c", task_type="docs", complexity=Complexity.TRIVIAL, actual_tokens=110
    ))

    data = mem.convergence_data("docs", "trivial")
    assert data == [100, 110]
    mem.close()
