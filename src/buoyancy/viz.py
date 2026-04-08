"""Terminal-based visualizations for Neutral Buoyancy calibration data."""

from __future__ import annotations

from typing import Optional

from buoyancy.calibrator import BuoyancyScore, Calibrator
from buoyancy.memory import Memory
from buoyancy.task import Complexity


# Unicode block characters for sparkline
_SPARK_CHARS = "▁▂▃▄▅▆▇█"

# Bar fill character for convergence chart and dashboard
_BAR_CHAR = "█"
_FILL_CHAR = "="
_DOT_CHAR = "·"


def convergence_chart(
    memory: Memory,
    task_type: str,
    complexity: str,
    calibration: Optional[dict] = None,
    width: int = 22,
) -> str:
    """Render an ASCII convergence chart for a (task_type, complexity) pair.

    Shows how actual_tokens converged over recorded tasks.

    Example output::

        documentation/trivial convergence (n=10, confidence=0.30)
        tokens
          300 ┤████████
          250 ┤  ██████
          200 ┤    ████████
          173 ┤      ████████████████  ← current optimal
          150 ┤
              └──────────────────────
               1  2  3  4  5  6  7  8  9  10
    """
    series = memory.convergence_data(task_type, complexity)
    n = len(series)

    label = f"{task_type}/{complexity}"
    conf_str = f"conf={calibration['confidence']:.2f}" if calibration else "no calibration"
    header = f"{label} convergence (n={n}, {conf_str})"

    if n == 0:
        return f"{header}\n  (no data yet)\n"

    optimal = calibration["optimal_tokens"] if calibration else series[-1]
    max_val = max(max(series), optimal)
    min_val = min(min(series), optimal)

    # Choose ~5 y-axis ticks
    span = max_val - min_val
    if span == 0:
        span = max(1, max_val // 5)
    step = max(1, span // 4)
    ticks = sorted(set(
        list(range(min_val, max_val + 1, step)) + [max_val, optimal]
    ), reverse=True)

    # Width of the chart body (number of tasks = columns)
    chart_width = max(width, n * 2)

    def bar_at(level: int) -> str:
        """Return a row of characters for the given token level."""
        row = []
        for i, val in enumerate(series):
            col_pos = i * (chart_width // n) if n > 1 else 0
            # Fill from the value down to the level
            if val >= level:
                row.append(_BAR_CHAR)
            else:
                row.append(" ")
        # Pad to chart_width
        joined = "".join(row)
        return joined.ljust(chart_width)

    lines = [header, "tokens"]

    label_width = max(len(str(t)) for t in ticks) + 1

    for tick in ticks:
        bar = bar_at(tick)
        prefix = f"{tick:>{label_width}} ┤"
        suffix = ""
        if tick == optimal:
            suffix = "  ← current optimal"
        lines.append(f"{prefix}{bar}{suffix}")

    # X-axis
    axis_line = " " * (label_width + 1) + "└" + "─" * chart_width
    lines.append(axis_line)

    # X-axis labels (task indices)
    label_row = " " * (label_width + 2)
    step_x = max(1, n // 10)
    x_positions: list[tuple[int, str]] = []
    for i in range(0, n, step_x):
        x_positions.append((i, str(i + 1)))
    # Build sparse label row
    label_chars = [" "] * chart_width
    for idx, lbl in x_positions:
        pos = idx  # one char per task in bar_at
        for j, ch in enumerate(lbl):
            if pos + j < chart_width:
                label_chars[pos + j] = ch
    lines.append(" " * (label_width + 2) + "".join(label_chars))

    return "\n".join(lines)


def _buoyancy_bar(
    optimal_tokens: int,
    max_tokens: int,
    bar_width: int = 20,
) -> str:
    """Render a buoyancy progress bar.

    Format: [===|==========·····]
    The | marks the optimal point, === is usage, · is remaining headroom.
    """
    if max_tokens <= 0:
        return "[" + "?" * bar_width + "]"

    ratio = min(1.0, optimal_tokens / max_tokens)
    filled = int(ratio * bar_width)
    remaining = bar_width - filled

    # Split filled into two halves around the | marker
    half = filled // 2 if filled > 2 else filled
    left = _FILL_CHAR * half
    right = _FILL_CHAR * (filled - half)
    dots = _DOT_CHAR * remaining

    if filled > 0:
        return f"[{left}|{right}{dots}]"
    else:
        return f"[|{dots}]"


def dashboard(memory: Memory, calibrator: Calibrator) -> str:
    """Render the buoyancy dashboard for all calibrated task types.

    Example output::

        === Buoyancy Dashboard ===
        documentation/trivial  ⚖️  [===|=========·····] 173/300 tok  conf:0.30
        bugfix/moderate        ⚖️  [===|==========····] 1069/2000 tok  conf:0.30
        feature/complex        🫧⬆️ [===|==============] 3800/4000 tok  conf:0.15
    """
    scores = calibrator.get_all_scores()

    lines = ["=== Buoyancy Dashboard ==="]

    if not scores:
        lines.append("  No calibration data yet. Start recording tasks!")
        return "\n".join(lines)

    # Find label width for alignment
    labels = [f"{s.task_type}/{s.complexity.value}" for s in scores]
    max_label = max(len(l) for l in labels)

    from buoyancy.task import DEFAULT_BUDGETS

    for score, label in zip(scores, labels):
        # Max tokens: use default budget as ceiling reference
        complexity_enum = score.complexity
        default_budget = DEFAULT_BUDGETS.get(complexity_enum)
        max_tok = default_budget.max_tokens if default_budget else score.optimal_tokens * 2

        bar = _buoyancy_bar(score.optimal_tokens, max_tok)
        symbol = score.symbol
        conf = score.confidence

        line = (
            f"{label:<{max_label}}  {symbol} "
            f"{bar} {score.optimal_tokens}/{max_tok} tok  "
            f"conf:{conf:.2f}"
        )
        lines.append(line)

    return "\n".join(lines)


def sparkline(
    memory: Memory,
    task_type: str,
    complexity: str,
) -> str:
    """Render a compact sparkline of recent token usage.

    Example output::

        bugfix/moderate: ▁▂▃▄▅▆▇█▇▆ (800-1100 tokens, avg 950)
    """
    series = memory.convergence_data(task_type, complexity)
    label = f"{task_type}/{complexity}"

    if not series:
        return f"{label}: (no data)"

    min_val = min(series)
    max_val = max(series)
    avg_val = int(sum(series) / len(series))

    span = max_val - min_val
    chars = []
    for val in series:
        if span == 0:
            idx = len(_SPARK_CHARS) // 2
        else:
            idx = int((val - min_val) / span * (len(_SPARK_CHARS) - 1))
        chars.append(_SPARK_CHARS[idx])

    spark = "".join(chars)
    return f"{label}: {spark} ({min_val}-{max_val} tokens, avg {avg_val})"
