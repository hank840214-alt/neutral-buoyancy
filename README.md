# 🫧 Neutral Buoyancy

**Find the exact right amount of AI effort — not too much, not too little.**

Like a diver adjusting buoyancy: too much air and you waste energy fighting to stay down; too little and you sink. Neutral Buoyancy learns the optimal token budget for each type of task, remembers it, and applies that calibration to future tasks.

## The Problem

Every AI agent wastes tokens. A trivial typo fix gets 2000 tokens of explanation. A complex refactor gets the same budget as a simple rename. Current solutions optimize at the **model level** (routing) or **prompt level** (compression), but nobody optimizes at the **task level** with persistent memory.

## The Insight

> Each task type has a "neutral buoyancy" point — the minimum effort that reliably produces good results. By remembering past task efforts and outcomes, we can converge on this point over time.

```
Effort →  ████████████████████░░░░░░░  Too much (wasteful)
          ████████████████░░░░░░░░░░░  Just right ← neutral buoyancy
          █████████░░░░░░░░░░░░░░░░░░  Too little (fails)
```

## Quick Start

```bash
pip install neutral-buoyancy
```

```python
from buoyancy import Buoyancy

b = Buoyancy()  # SQLite memory at ~/.buoyancy/memory.db

# Wrap any LLM task
with b.task("fix-typo", task_type="documentation", complexity="trivial") as t:
    response = your_llm_call(max_tokens=t.budget.max_tokens)
    t.record(tokens_used=response.usage.output_tokens, succeeded=True)

# After several similar tasks, check calibration
print(b.estimate("documentation", "trivial"))
# → Budget(max_tokens=180, confidence=0.82, model_tier="low")

# View convergence report
b.report()
```

## How It Works

### 1. Classify → 2. Estimate → 3. Execute → 4. Record → 5. Calibrate

```
┌─────────┐     ┌──────────┐     ┌─────────┐
│ New Task │────▶│ Estimate │────▶│ Execute │
└─────────┘     │ (lookup  │     │ (with   │
                │  memory) │     │  budget)│
                └──────────┘     └────┬────┘
                     ▲                │
                     │           ┌────▼────┐
                ┌────┴─────┐     │ Record  │
                │Calibrate │◀────│ (actual │
                │ (EMA     │     │  usage) │
                │  update) │     └─────────┘
                └──────────┘
                     │
                ┌────▼─────┐
                │ Memory   │  ← SQLite, persistent across sessions
                │ (task →  │
                │  effort) │
                └──────────┘
```

### The Calibration Algorithm

Uses **Exponential Moving Average (EMA)** to converge on optimal effort:

```
optimal_tokens = α × actual_sufficient_tokens + (1-α) × previous_optimal
```

- After ~5 similar tasks: rough estimate (confidence 0.3)
- After ~15 similar tasks: good estimate (confidence 0.7)
- After ~30 similar tasks: high confidence (confidence 0.9)

### Buoyancy Score

Each (task_type, complexity) pair gets a buoyancy score:

| Score | Meaning | Action |
|-------|---------|--------|
| `+0.5 to +1.0` | Way too much air | Significantly reduce budget |
| `+0.1 to +0.5` | Slightly positive | Slightly reduce budget |
| `-0.1 to +0.1` | **Neutral buoyancy** ✓ | Maintain current budget |
| `-0.5 to -0.1` | Slightly sinking | Slightly increase budget |
| `-1.0 to -0.5` | Sinking fast | Significantly increase budget |

## Adapters

Built-in wrappers for popular LLM SDKs:

```python
from buoyancy.adapters.anthropic import BuoyantClaude

client = BuoyantClaude()  # wraps anthropic.Anthropic()

# Automatically tracks tokens, adjusts effort parameter
response = client.message(
    task_type="code-review",
    complexity="moderate",
    prompt="Review this PR..."
)
# Budget was auto-calibrated from past code-review tasks
```

## Integration with Claude Code

Add to your `CLAUDE.md`:

```markdown
## Token Efficiency
Before starting any task, check ~/.buoyancy/memory.db for calibration data.
Use `buoyancy estimate <task_type> <complexity>` to get the recommended budget.
After completing, run `buoyancy record` to update calibration.
```

Or use the Claude Code skill (coming soon).

## Compared to Existing Work

| Approach | What it optimizes | Persistent memory? | Task-level? |
|----------|------------------|-------------------|-------------|
| RouteLLM | Model selection | ❌ | ❌ |
| TALE | Token budget per-prompt | ❌ | ❌ |
| FrugalGPT | Model cascade | ❌ | ❌ |
| LLMLingua | Prompt compression | ❌ | ❌ |
| GPTCache | Exact/semantic cache | ✅ | ❌ |
| **Neutral Buoyancy** | **Effort per task type** | **✅** | **✅** |

## Philosophy

> "Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away." — Antoine de Saint-Exupéry

The goal isn't to minimize tokens. It's to find the **exact right amount** — where quality meets efficiency. Like sharpening a blade: too dull and it won't cut, too sharp and it chips. The sweet spot is learned, not guessed.

## License

MIT
