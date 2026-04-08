"""Calibration algorithm — converge on neutral buoyancy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from buoyancy.memory import Memory
from buoyancy.task import Budget, Complexity, ModelTier, TaskRecord, DEFAULT_BUDGETS


# EMA smoothing factor — higher = more weight on recent data
ALPHA = 0.3

# Confidence thresholds
CONFIDENCE_LEVELS = {
    5: 0.3,   # rough estimate
    15: 0.7,  # good estimate
    30: 0.9,  # high confidence
}

# Safety margin on top of optimal estimate
SAFETY_MARGIN = 1.15


@dataclass
class BuoyancyScore:
    """Current buoyancy state for a (task_type, complexity) pair."""
    task_type: str
    complexity: Complexity
    score: float          # -1.0 to +1.0
    optimal_tokens: int
    model_tier: ModelTier
    confidence: float
    sample_count: int

    @property
    def status(self) -> str:
        if self.score > 0.3:
            return "positive (too much air — reduce budget)"
        elif self.score > 0.1:
            return "slightly positive (minor overuse)"
        elif self.score < -0.3:
            return "negative (sinking — increase budget)"
        elif self.score < -0.1:
            return "slightly negative (minor underuse)"
        else:
            return "neutral (just right)"

    @property
    def symbol(self) -> str:
        if self.score > 0.3:
            return "🫧⬆️"
        elif self.score > 0.1:
            return "🫧↗️"
        elif self.score < -0.3:
            return "🪨⬇️"
        elif self.score < -0.1:
            return "🪨↘️"
        else:
            return "⚖️✅"


class Calibrator:
    """Calibration engine that converges on optimal effort."""

    def __init__(self, memory: Memory, alpha: float = ALPHA):
        self.memory = memory
        self.alpha = alpha

    def estimate(
        self, task_type: str, complexity: Complexity
    ) -> Budget:
        """Get calibrated budget estimate for a task."""
        cal = self.memory.get_calibration(task_type, complexity)

        if cal and cal["sample_count"] >= 3:
            return Budget(
                max_tokens=int(cal["optimal_tokens"] * SAFETY_MARGIN),
                model_tier=ModelTier(cal["optimal_model_tier"]),
                confidence=cal["confidence"],
                based_on_n=cal["sample_count"],
            )

        # Fall back to defaults
        return DEFAULT_BUDGETS.get(
            complexity,
            DEFAULT_BUDGETS[Complexity.MODERATE],
        )

    def update(self, record: TaskRecord) -> BuoyancyScore:
        """Update calibration after a task completes. Returns new buoyancy score."""
        cal = self.memory.get_calibration(record.task_type, record.complexity)

        if cal:
            old_tokens = cal["optimal_tokens"]
            old_score = cal["buoyancy_score"]
            n = cal["sample_count"] + 1
        else:
            old_tokens = record.actual_tokens
            old_score = 0.0
            n = 1

        # Compute new optimal tokens via EMA
        if record.succeeded:
            new_tokens = int(
                self.alpha * record.actual_tokens
                + (1 - self.alpha) * old_tokens
            )
        else:
            # Failed task → increase budget by 20%
            new_tokens = int(old_tokens * 1.2)

        # Update buoyancy score via EMA
        new_score = (
            self.alpha * record.buoyancy_delta
            + (1 - self.alpha) * old_score
        )
        new_score = max(-1.0, min(1.0, new_score))

        # Determine model tier from history
        model_tier = self._determine_model_tier(record, cal)

        # Compute confidence from sample count
        confidence = self._compute_confidence(n)

        # Persist
        self.memory.update_calibration(
            task_type=record.task_type,
            complexity=record.complexity,
            optimal_tokens=new_tokens,
            optimal_model_tier=model_tier,
            buoyancy_score=new_score,
            confidence=confidence,
            sample_count=n,
        )

        return BuoyancyScore(
            task_type=record.task_type,
            complexity=record.complexity,
            score=new_score,
            optimal_tokens=new_tokens,
            model_tier=model_tier,
            confidence=confidence,
            sample_count=n,
        )

    def get_buoyancy(
        self, task_type: str, complexity: Complexity
    ) -> Optional[BuoyancyScore]:
        """Get current buoyancy score for a pair."""
        cal = self.memory.get_calibration(task_type, complexity)
        if not cal:
            return None
        return BuoyancyScore(
            task_type=task_type,
            complexity=complexity,
            score=cal["buoyancy_score"],
            optimal_tokens=cal["optimal_tokens"],
            model_tier=ModelTier(cal["optimal_model_tier"]),
            confidence=cal["confidence"],
            sample_count=cal["sample_count"],
        )

    def get_all_scores(self) -> list[BuoyancyScore]:
        """Get all buoyancy scores."""
        cals = self.memory.get_all_calibrations()
        return [
            BuoyancyScore(
                task_type=c["task_type"],
                complexity=Complexity(c["complexity"]),
                score=c["buoyancy_score"],
                optimal_tokens=c["optimal_tokens"],
                model_tier=ModelTier(c["optimal_model_tier"]),
                confidence=c["confidence"],
                sample_count=c["sample_count"],
            )
            for c in cals
        ]

    def _determine_model_tier(
        self, record: TaskRecord, cal: Optional[dict]
    ) -> ModelTier:
        """Pick model tier based on history."""
        if cal and cal["sample_count"] >= 3:
            # Use historical tier if well-calibrated
            return ModelTier(cal["optimal_model_tier"])
        return record.actual_model_tier

    def _compute_confidence(self, n: int) -> float:
        """Confidence grows with sample count."""
        for threshold, conf in sorted(
            CONFIDENCE_LEVELS.items(), reverse=True
        ):
            if n >= threshold:
                return conf
        return max(0.1, n * 0.05)
