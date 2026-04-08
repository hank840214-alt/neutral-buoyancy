"""Basic usage of Neutral Buoyancy."""

from buoyancy import Buoyancy

# Create a buoyancy instance (defaults to ~/.buoyancy/memory.db)
b = Buoyancy()

# Simulate several documentation tasks
print("=== Recording documentation tasks ===")
for i in range(10):
    tokens = 150 + (i % 3) * 30  # Varies between 150-210
    score = b.record_task(
        name=f"doc-fix-{i}",
        task_type="documentation",
        complexity="trivial",
        tokens_used=tokens,
        succeeded=True,
    )
    print(f"  Task {i}: {tokens} tokens → {score.symbol} score={score.score:+.2f}")

print()

# Simulate some bugfix tasks
print("=== Recording bugfix tasks ===")
for i in range(8):
    tokens = 800 + (i % 4) * 100  # Varies between 800-1100
    score = b.record_task(
        name=f"bugfix-{i}",
        task_type="bugfix",
        complexity="moderate",
        tokens_used=tokens,
        succeeded=i != 5,  # One failure
    )
    status = "FAILED" if i == 5 else "OK"
    print(f"  Task {i}: {tokens} tokens [{status}] → {score.symbol} score={score.score:+.2f}")

print()

# Now check estimates
print("=== Calibrated Estimates ===")
for task_type, complexity in [("documentation", "trivial"), ("bugfix", "moderate")]:
    budget = b.estimate(task_type, complexity)
    print(f"  {task_type}/{complexity}: {budget}")

print()

# Full report
print(b.report())

b.close()
