"""CLI for Neutral Buoyancy."""

from __future__ import annotations

import argparse
import sys

from buoyancy.classifier import classify
from buoyancy.core import Buoyancy
from buoyancy.task import Complexity, ModelTier


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="buoyancy",
        description="Neutral Buoyancy — adaptive token budget calibration",
    )
    sub = parser.add_subparsers(dest="command")

    # buoyancy report
    sub.add_parser("report", help="Show calibration report")

    # buoyancy estimate <task_type> <complexity>
    est = sub.add_parser("estimate", help="Get budget estimate")
    est.add_argument("task_type")
    est.add_argument("complexity", choices=[c.value for c in Complexity])

    # buoyancy record <name> <task_type> <complexity> <tokens> [--failed] [--quality Q]
    rec = sub.add_parser("record", help="Record a completed task")
    rec.add_argument("name")
    rec.add_argument("task_type")
    rec.add_argument("complexity", choices=[c.value for c in Complexity])
    rec.add_argument("tokens", type=int)
    rec.add_argument("--failed", action="store_true")
    rec.add_argument("--quality", type=float, default=1.0)
    rec.add_argument("--model-tier", choices=[m.value for m in ModelTier], default="medium")

    # buoyancy classify <description>
    cls = sub.add_parser("classify", help="Auto-classify a task description")
    cls.add_argument("description", help="Plain-text task description")

    # buoyancy stats
    sub.add_parser("stats", help="Show summary statistics")

    # buoyancy dashboard
    sub.add_parser("dashboard", help="Show buoyancy dashboard for all task types")

    # buoyancy convergence <task_type> <complexity>
    conv = sub.add_parser("convergence", help="Show convergence chart for a task type")
    conv.add_argument("task_type")
    conv.add_argument("complexity", choices=[c.value for c in Complexity])

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return

    b = Buoyancy()

    if args.command == "report":
        print(b.report())

    elif args.command == "estimate":
        budget = b.estimate(args.task_type, args.complexity)
        print(f"Task: {args.task_type} ({args.complexity})")
        print(f"  max_tokens:  {budget.max_tokens}")
        print(f"  model_tier:  {budget.model_tier.value}")
        print(f"  confidence:  {budget.confidence:.2f}")
        print(f"  based_on_n:  {budget.based_on_n}")

    elif args.command == "record":
        score = b.record_task(
            name=args.name,
            task_type=args.task_type,
            complexity=args.complexity,
            tokens_used=args.tokens,
            succeeded=not args.failed,
            quality_score=args.quality,
            model_tier=args.model_tier,
        )
        print(f"Recorded: {args.name}")
        print(f"  buoyancy: {score.score:+.2f} {score.symbol} {score.status}")
        print(f"  optimal_tokens: {score.optimal_tokens}")
        print(f"  confidence: {score.confidence:.2f} (n={score.sample_count})")

    elif args.command == "classify":
        task_type, complexity = classify(args.description)
        print(f"task_type: {task_type}, complexity: {complexity.value}")
        b.close()
        return

    elif args.command == "stats":
        stats = b._memory.get_stats()
        print("=== Neutral Buoyancy Stats ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif args.command == "dashboard":
        from buoyancy.viz import dashboard
        print(dashboard(b._memory, b._calibrator))

    elif args.command == "convergence":
        from buoyancy.viz import convergence_chart
        cal = b._memory.get_calibration(args.task_type, Complexity(args.complexity))
        print(convergence_chart(b._memory, args.task_type, args.complexity, calibration=cal))

    b.close()


if __name__ == "__main__":
    main()
