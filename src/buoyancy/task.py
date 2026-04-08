"""Task data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import hashlib


class Complexity(str, Enum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EPIC = "epic"


class ModelTier(str, Enum):
    LOW = "low"        # Haiku-class
    MEDIUM = "medium"  # Sonnet-class
    HIGH = "high"      # Opus-class


@dataclass
class Budget:
    """Recommended budget for a task."""
    max_tokens: int
    model_tier: ModelTier
    confidence: float  # 0.0 to 1.0, how reliable this estimate is
    based_on_n: int    # number of historical data points

    def __repr__(self) -> str:
        return (
            f"Budget(max_tokens={self.max_tokens}, "
            f"model_tier={self.model_tier.value!r}, "
            f"confidence={self.confidence:.2f}, "
            f"based_on_n={self.based_on_n})"
        )


@dataclass
class TaskRecord:
    """A single recorded task execution."""
    task_name: str
    task_type: str
    complexity: Complexity
    fingerprint: str = ""

    # Budget (before execution)
    estimated_tokens: int = 0
    estimated_model_tier: ModelTier = ModelTier.MEDIUM

    # Actual (after execution)
    actual_tokens: int = 0
    actual_model_tier: ModelTier = ModelTier.MEDIUM
    actual_tool_calls: int = 0
    duration_ms: int = 0

    # Outcome
    succeeded: bool = True
    quality_score: float = 1.0  # 0.0 to 1.0

    # Metadata
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: Optional[int] = None

    def __post_init__(self):
        if isinstance(self.complexity, str):
            self.complexity = Complexity(self.complexity)
        if isinstance(self.estimated_model_tier, str):
            self.estimated_model_tier = ModelTier(self.estimated_model_tier)
        if isinstance(self.actual_model_tier, str):
            self.actual_model_tier = ModelTier(self.actual_model_tier)
        if not self.fingerprint:
            self.fingerprint = self._compute_fingerprint()

    def _compute_fingerprint(self) -> str:
        raw = f"{self.task_type}:{self.complexity.value}:{self.task_name}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    @property
    def buoyancy_delta(self) -> float:
        """How buoyant was this task execution?

        Positive = too much effort (wasted tokens)
        Negative = too little effort (task struggled/failed)
        Zero = neutral buoyancy (just right)
        """
        if not self.succeeded:
            return -0.5  # Clearly not enough effort

        if self.estimated_tokens == 0:
            return 0.0  # No estimate, can't compute

        ratio = self.estimated_tokens / max(self.actual_tokens, 1)

        if ratio > 1.5:
            # Estimated way more than needed → too much air
            return min(0.8, (ratio - 1.0) * 0.5)
        elif ratio > 1.1:
            # Slightly over-budgeted
            return (ratio - 1.0) * 0.5
        elif ratio < 0.7:
            # Used way more than estimated → not enough air
            return max(-0.8, (ratio - 1.0) * 0.5)
        elif ratio < 0.9:
            # Slightly under-budgeted
            return (ratio - 1.0) * 0.5
        else:
            return 0.0  # Within 10% → neutral


# Default budgets when no calibration data exists
DEFAULT_BUDGETS: dict[Complexity, Budget] = {
    Complexity.TRIVIAL: Budget(max_tokens=300, model_tier=ModelTier.LOW, confidence=0.1, based_on_n=0),
    Complexity.SIMPLE: Budget(max_tokens=800, model_tier=ModelTier.LOW, confidence=0.1, based_on_n=0),
    Complexity.MODERATE: Budget(max_tokens=2000, model_tier=ModelTier.MEDIUM, confidence=0.1, based_on_n=0),
    Complexity.COMPLEX: Budget(max_tokens=4000, model_tier=ModelTier.HIGH, confidence=0.1, based_on_n=0),
    Complexity.EPIC: Budget(max_tokens=8000, model_tier=ModelTier.HIGH, confidence=0.1, based_on_n=0),
}
