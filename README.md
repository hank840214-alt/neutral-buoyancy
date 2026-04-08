# 🫧 Neutral Buoyancy

**Find the exact right amount of AI effort — not too much, not too little.**

Like a diver adjusting buoyancy: too much air and you waste energy fighting to stay down; too little and you sink. Neutral Buoyancy learns the optimal token budget for each type of task, remembers it, and applies that calibration to future tasks.

> 每個 AI 任務都有一個「中性浮力」點——用恰好夠的 token 完成任務，不多不少。透過記住過去的 effort 並持續校準，系統會自動收斂到這個最佳點。

## The Problem

Every AI agent wastes tokens. A trivial typo fix gets 2000 tokens of explanation. A complex refactor gets the same budget as a simple rename. Current solutions optimize at the **model level** (routing) or **prompt level** (compression), but nobody optimizes at the **task level** with persistent memory.

## The Metaphors

### Diving: Neutral Buoyancy

```
Too much air (positive buoyancy)  →  Waste tokens, over-engineered responses
Too little air (negative buoyancy) →  Task fails, incomplete responses
Neutral buoyancy                   →  Exactly the right amount of effort ✓
```

### Business: Sharpening (削尖)

```
Too dull    →  Can't cut (task fails)
Too sharp   →  Blade chips (wasted effort)
Just right  →  Remember this angle for next time
```

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

# Auto-classify from description (no manual type/complexity needed)
with b.auto_task("fix-btn", "fix the login button crash on mobile") as t:
    response = your_llm_call(max_tokens=t.budget.max_tokens)
    t.record(tokens_used=response.usage.output_tokens, succeeded=True)

# After several similar tasks, check calibration
print(b.estimate("documentation", "trivial"))
# → Budget(max_tokens=198, confidence=0.30, based_on_n=10)

# View convergence report
b.report()
```

## CLI

```bash
# Estimate budget for a task type
buoyancy estimate bugfix simple
# → max_tokens: 500, model_tier: low, confidence: 0.70

# Record a completed task
buoyancy record "fix-login-btn" bugfix simple 380

# Auto-classify from description
buoyancy classify "fix the login button crash"
# → task_type: bugfix, complexity: simple

# View calibration dashboard
buoyancy dashboard
# === Buoyancy Dashboard ===
# bugfix/moderate        ⚖️✅ [=====|=====··········] 1069/2000 tok  conf:0.30
# documentation/trivial  🫧↗️ [=====|======·········] 173/300 tok   conf:0.30

# View convergence chart
buoyancy convergence bugfix moderate

# Show summary stats
buoyancy stats

# Data lifecycle
buoyancy prune --days 90   # Delete records older than 90 days
buoyancy reset --type bugfix  # Reset calibration for a specific type
buoyancy reset             # Reset all calibration data
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

| Score | Meaning | Symbol | Action |
|-------|---------|--------|--------|
| `+0.5 to +1.0` | Way too much air | 🫧⬆️ | Significantly reduce budget |
| `+0.1 to +0.5` | Slightly positive | 🫧↗️ | Slightly reduce budget |
| `-0.1 to +0.1` | **Neutral buoyancy** | ⚖️✅ | Maintain current budget |
| `-0.5 to -0.1` | Slightly sinking | 🪨↘️ | Slightly increase budget |
| `-1.0 to -0.5` | Sinking fast | 🪨⬇️ | Significantly increase budget |

### Task Types & Complexity

**Auto-classification** from plain text (zero-cost, rule-based):

| Task Type | Keywords |
|-----------|----------|
| `bugfix` | fix, bug, error, crash, broken, patch |
| `feature` | add, new, implement, create, build |
| `refactor` | refactor, restructure, clean up |
| `docs` | doc, readme, comment, typo |
| `research` | research, investigate, explore, analyze |
| `code-review` | review, audit, check, inspect |
| `test` | test, spec, coverage |
| `deploy` | deploy, release, publish, ship |
| `config` | config, setup, install, env, ci |

| Complexity | Signals |
|------------|---------|
| `trivial` | One-liner, rename, ≤5 words |
| `simple` | 1-2 files, clear scope, ≤15 words |
| `moderate` | 3-5 files, some coordination |
| `complex` | Multi-system, design decisions |
| `epic` | Architecture changes, many unknowns |

## Demo: Calibration Convergence

```
=== Recording documentation tasks ===
  Task 0: 150 tokens → 🫧↗️ score=+0.15
  Task 1: 180 tokens → 🫧↗️ score=+0.21
  Task 5: 210 tokens → ⚖️✅ score=+0.10   ← converging
  Task 9: 150 tokens → 🫧↗️ score=+0.10

=== Calibrated Estimates ===
  documentation/trivial: Budget(max_tokens=198, confidence=0.30, based_on_n=10)
  bugfix/moderate:       Budget(max_tokens=1229, confidence=0.30, based_on_n=8)

=== Savings ===
  documentation: 300 → 173 tokens (42% reduction)
  bugfix:       2000 → 1069 tokens (47% reduction)
```

## Python API

```python
from buoyancy import Buoyancy, classify

b = Buoyancy()

# Context manager with manual classification
with b.task("fix-typo", task_type="docs", complexity="trivial") as t:
    response = llm_call(max_tokens=t.budget.max_tokens)
    t.record(tokens_used=response.usage.output_tokens, succeeded=True)

# Context manager with auto-classification
with b.auto_task("fix-btn", "fix the login button crash") as t:
    response = llm_call(max_tokens=t.budget.max_tokens)
    t.record(tokens_used=response.usage.output_tokens, succeeded=True)

# Direct recording (no context manager)
score = b.record_task("task-name", "bugfix", "simple", tokens_used=400)

# Standalone classification
task_type, complexity = classify("add unit tests for the parser")
# → ("test", Complexity.SIMPLE)

# Estimate without executing
budget = b.estimate("feature", "moderate")

# Check buoyancy score
score = b.buoyancy("bugfix", "simple")
print(f"{score.symbol} {score.status}")  # ⚖️✅ neutral (just right)

# Data lifecycle
b.prune(older_than_days=90)
b.reset(task_type="bugfix")  # or b.reset() for all

# Reports
print(b.report())
```

## Anthropic Claude Adapter

```python
from buoyancy.adapters.anthropic import BuoyantClaude

client = BuoyantClaude()  # wraps anthropic.Anthropic()

# Automatically tracks tokens, selects model tier, records results
response = client.message(
    task_type="code-review",
    complexity="moderate",
    prompt="Review this PR..."
)
# Budget was auto-calibrated from past code-review tasks
```

## Claude Code Integration

### Option 1: CLAUDE.md (behavioral, zero-cost)

Add to your `CLAUDE.md`:

```markdown
### Token Efficiency (Neutral Buoyancy)
- After completing any task, auto-record:
  `~/neutral-buoyancy/.venv/bin/buoyancy record "<name>" <type> <complexity> <tokens>`
- Token estimation: short ~200-400, single file ~500-1000, multi-file ~1500-3000
- Silently record, no need to ask user
```

### Option 2: Stop Hook (automatic reminder)

Add to `~/.claude/settings.json` under `hooks.Stop`:

```json
{
  "hooks": [{
    "type": "command",
    "command": "bash ~/.claude/hooks/buoyancy-auto-record.sh",
    "timeout": 5
  }]
}
```

The hook reminds Claude to record if it forgot, showing today's record count.

### Option 3: Skill (`/buoyancy`)

Install the skill at `~/.claude/skills/neutral-buoyancy/SKILL.md` for on-demand calibration reports via `/buoyancy`.

## Visualization

### Dashboard

```
=== Buoyancy Dashboard ===
bugfix/complex         ⚖️✅ [==========|==========] 4000/4000 tok  conf:0.10
bugfix/moderate        ⚖️✅ [=====|=====··········] 1069/2000 tok  conf:0.30
config/simple          ⚖️✅ [==========|==========] 800/800 tok    conf:0.10
documentation/trivial  🫧↗️ [=====|======·········] 173/300 tok    conf:0.30
feature/moderate       ⚖️✅ [==========|==========] 2350/2000 tok  conf:0.10
```

### Sparkline

```
bugfix/moderate: ▁▂▃▄▅▆▇█▇▆ (800-1100 tokens, avg 965)
```

### Convergence Chart

```
documentation/trivial convergence (n=10, conf=0.30)
tokens
  300 ┤████████
  250 ┤  ██████
  200 ┤    ████████
  173 ┤      ████████████████  ← current optimal
  150 ┤
      └──────────────────────
       1  2  3  4  5  6  7  8  9  10
```

## Where This Sits in the Research Landscape

### Academic Foundations (2024-2026)

| Research | What it does | Persistent memory? | Task-level? |
|----------|-------------|-------------------|-------------|
| [RouteLLM](https://github.com/lm-sys/RouteLLM) (4.8K⭐) | Route queries to strong/weak models | ❌ | ❌ |
| [TALE](https://arxiv.org/abs/2412.18547) (ACL 2025) | Token budget per-prompt | ❌ | ❌ |
| [ARES](https://github.com/UCSB-NLP-Chang/Ares) | Per-step adaptive effort for agents | ❌ (offline training) | ✅ |
| [FrugalGPT](https://github.com/stanford-futuredata/FrugalGPT) (Stanford) | LLM cascade: cheap → expensive | ❌ | ❌ |
| [LLMLingua](https://github.com/microsoft/LLMLingua) (6K⭐) | Prompt compression up to 20x | ❌ | ❌ |
| [GPTCache](https://github.com/zilliztech/GPTCache) (8K⭐) | Semantic caching, zero tokens on hit | ✅ | ❌ |
| [Calibrate-Then-Act](https://arxiv.org/abs/2602.16699) | Cost-aware agent exploration | ❌ (single session) | ✅ |
| [Plan Caching](https://arxiv.org/html/2506.14852v1) | Cache successful execution plans | ✅ | ❌ |
| [Scaling Test-Time Compute](https://arxiv.org/abs/2408.03314) (DeepMind) | Compute-optimal inference | ❌ | ❌ |
| **Neutral Buoyancy** | **Effort per task type with memory** | **✅** | **✅** |

### The Gap We Fill

```
Existing research                     Neutral Buoyancy (the gap)
─────────────────                     ─────────────────────────
TALE (per-prompt budget)         ─┐
RouteLLM (model routing)         ─┤   Cross-session effort memory
Plan Caching (plan reuse)        ─┼→  + Continuous calibration loop
ARES (per-step routing)          ─┤   + task-type → optimal-effort mapping
Calibrate-Then-Act (cost-aware)  ─┘
```

Key academic search terms: **"adaptive test-time compute"**, **"token budget allocation"**, **"compute-optimal inference"**

### Industry Context

| Provider | Mechanism | Neutral Buoyancy adds |
|----------|-----------|----------------------|
| Anthropic | Claude `effort` parameter (low/med/high) | Learn which tasks need which level |
| OpenAI | o3/o4-mini reasoning intensity (3 tiers) | Persistent memory of past task costs |
| NVIDIA | `max_thinking_tokens` budget control | Cross-session calibration data |

## Security & Reliability

Hardened through [red team analysis](docs/red-team-report.md):

- **Input validation** — rejects negative/excessive tokens, clamps quality scores
- **SQLite WAL mode** — concurrent read/write safety with `busy_timeout=30s`
- **Threading lock** — safe for multi-threaded access
- **File permissions** — `0o700` directory, `0o600` database (owner-only)
- **Exception safety** — context manager records failure on exception, not success
- **Budget cap** — failed tasks can't inflate budget beyond 100K tokens
- **Data lifecycle** — `prune(days)` and `reset(task_type)` for cleanup
- **String sanitization** — task names truncated to 200 chars

## Architecture

```
neutral-buoyancy/
├── src/buoyancy/
│   ├── __init__.py          # Public API exports
│   ├── core.py              # Buoyancy class, TaskContext, context managers
│   ├── task.py              # TaskRecord, Budget, Complexity, ModelTier
│   ├── memory.py            # SQLite persistence with WAL + threading lock
│   ├── calibrator.py        # EMA convergence algorithm
│   ├── classifier.py        # Rule-based auto-classification (zero API cost)
│   ├── viz.py               # ASCII dashboard, convergence chart, sparkline
│   ├── cli.py               # CLI entry point
│   └── adapters/
│       ├── anthropic.py     # BuoyantClaude wrapper
│       └── __init__.py
├── tests/                   # 67 tests, <0.1s
├── examples/
│   └── basic_usage.py       # Demo convergence behavior
└── docs/
    └── red-team-report.md
```

## Philosophy

> "Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away." — Antoine de Saint-Exupéry

The goal isn't to minimize tokens. It's to find the **exact right amount** — where quality meets efficiency. Like sharpening a blade: too dull and it won't cut, too sharp and it chips. The sweet spot is learned, not guessed.

## License

MIT
