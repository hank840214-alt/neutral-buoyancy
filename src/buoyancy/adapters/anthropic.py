"""Anthropic Claude adapter — wraps the Anthropic SDK with buoyancy tracking."""

from __future__ import annotations

from typing import Any, Optional

from buoyancy.core import Buoyancy
from buoyancy.task import Complexity, ModelTier

# Model name → tier mapping
_MODEL_TIERS: dict[str, ModelTier] = {
    "claude-haiku": ModelTier.LOW,
    "claude-haiku-4-5": ModelTier.LOW,
    "claude-sonnet": ModelTier.MEDIUM,
    "claude-sonnet-4-6": ModelTier.MEDIUM,
    "claude-opus": ModelTier.HIGH,
    "claude-opus-4-6": ModelTier.HIGH,
}


def _model_to_tier(model: str) -> ModelTier:
    for prefix, tier in _MODEL_TIERS.items():
        if model.startswith(prefix):
            return tier
    return ModelTier.MEDIUM


def _tier_to_model(tier: ModelTier) -> str:
    return {
        ModelTier.LOW: "claude-haiku-4-5-20251001",
        ModelTier.MEDIUM: "claude-sonnet-4-6-20250415",
        ModelTier.HIGH: "claude-opus-4-6-20250415",
    }[tier]


class BuoyantClaude:
    """Anthropic client with automatic buoyancy calibration.

    Usage:
        client = BuoyantClaude()
        response = client.message(
            task_type="code-review",
            complexity="moderate",
            prompt="Review this function...",
        )
    """

    def __init__(self, buoyancy: Optional[Buoyancy] = None, **anthropic_kwargs: Any):
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "Install anthropic SDK: pip install neutral-buoyancy[anthropic]"
            )

        self._client = anthropic.Anthropic(**anthropic_kwargs)
        self._buoyancy = buoyancy or Buoyancy()

    def message(
        self,
        task_type: str,
        complexity: str | Complexity,
        prompt: str,
        task_name: str = "",
        system: str = "",
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Send a message with auto-calibrated budget."""
        if isinstance(complexity, str):
            complexity = Complexity(complexity)

        budget = self._buoyancy.estimate(task_type, complexity)
        task_name = task_name or f"{task_type}-{complexity.value}"

        # Use calibrated model unless explicitly overridden
        if model is None:
            model = _tier_to_model(budget.model_tier)

        messages = [{"role": "user", "content": prompt}]
        create_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": budget.max_tokens,
            "messages": messages,
            **kwargs,
        }
        if system:
            create_kwargs["system"] = system

        response = self._client.messages.create(**create_kwargs)

        # Auto-record
        tokens_used = response.usage.output_tokens
        succeeded = response.stop_reason != "max_tokens"

        self._buoyancy.record_task(
            name=task_name,
            task_type=task_type,
            complexity=complexity,
            tokens_used=tokens_used,
            succeeded=succeeded,
            model_tier=_model_to_tier(model),
        )

        return response
