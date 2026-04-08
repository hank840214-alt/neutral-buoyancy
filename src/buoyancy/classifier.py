"""Auto-classifier for task type and complexity inference."""

from __future__ import annotations

import re

from buoyancy.task import Complexity

# Keyword maps for task type classification (ordered by priority)
TASK_KEYWORDS: dict[str, list[str]] = {
    "bugfix": ["fix", "bug", "error", "crash", "broken", "issue", "patch", "hotfix"],
    "docs": ["doc", "readme", "comment", "typo", "documentation"],
    "deploy": ["deploy", "release", "publish", "ship"],
    "refactor": ["refactor", "restructure", "reorganize", "clean up", "simplify"],
    "research": ["research", "investigate", "explore", "analyze", "compare"],
    "code-review": ["review", "audit", "check", "inspect"],
    "test": ["test", "spec", "coverage", "assert"],
    "config": ["config", "setup", "install", "env", "ci", "pipeline"],
    "feature": ["add", "new", "implement", "create", "build"],
}

# Keywords that push complexity up or down
_COMPLEXITY_LOW_KEYWORDS = ["simple", "quick", "trivial", "minor", "tiny", "small", "easy"]
_COMPLEXITY_HIGH_KEYWORDS = [
    "complex",
    "refactor entire",
    "migrate",
    "overhaul",
    "large",
    "major",
    "complete",
    "full",
    "entire",
]

# Rough file-mention pattern (e.g. "file.py", "src/foo.ts", "3 files")
_FILE_PATTERN = re.compile(
    r"\b(?:\d+\s+files?|[\w/.-]+\.(?:py|ts|js|go|rs|java|rb|css|html|json|yaml|yml|toml|md))\b"
)


def _count_files_mentioned(description: str) -> int:
    """Count distinct file references in the description."""
    return len(_FILE_PATTERN.findall(description))


def _estimate_complexity(description: str) -> Complexity:
    """Heuristic complexity estimation from a task description."""
    text = description.lower()
    word_count = len(description.split())
    files_mentioned = _count_files_mentioned(description)

    # Low-complexity signals win first
    for kw in _COMPLEXITY_LOW_KEYWORDS:
        if kw in text:
            return Complexity.SIMPLE

    # High-complexity signals
    for kw in _COMPLEXITY_HIGH_KEYWORDS:
        if kw in text:
            if word_count > 30 or files_mentioned >= 3:
                return Complexity.EPIC
            return Complexity.COMPLEX

    # Word count heuristic
    if word_count <= 5:
        return Complexity.TRIVIAL
    if word_count <= 15:
        return Complexity.SIMPLE
    if word_count <= 40:
        return Complexity.MODERATE

    # File count heuristic
    if files_mentioned >= 5:
        return Complexity.EPIC
    if files_mentioned >= 2:
        return Complexity.COMPLEX

    return Complexity.COMPLEX


def _classify_task_type(description: str) -> str:
    """Classify task type using keyword matching (returns first match)."""
    text = description.lower()
    for task_type, keywords in TASK_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return task_type
    return "feature"  # safe default


def classify(description: str) -> tuple[str, Complexity]:
    """Infer task_type and complexity from a plain-text description.

    Args:
        description: A human-readable task description, e.g.
            "fix the login button crash on mobile".

    Returns:
        A ``(task_type, complexity)`` tuple, e.g. ``("bugfix", Complexity.SIMPLE)``.
    """
    if not description or not description.strip():
        return "feature", Complexity.MODERATE

    task_type = _classify_task_type(description)
    complexity = _estimate_complexity(description)
    return task_type, complexity
