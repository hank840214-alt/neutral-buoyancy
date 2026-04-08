# Red Team Security Analysis

**Date:** 2026-04-08
**Risk Level:** MEDIUM (no remote attack surface; data integrity, privacy, reliability issues)

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 0 | — |
| HIGH | 3 | ✅ All fixed |
| MEDIUM | 7 | ✅ 5 fixed, 2 accepted |
| LOW | 5 | ✅ 3 fixed, 2 accepted |

## HIGH — Fixed

### H1. Calibration Poisoning (No Input Validation)

**Problem:** `record_task()` accepted any values — negative tokens, quality > 1.0, extreme values. A single `tokens_used=-999999` could permanently skew all future estimates via EMA.

**Fix:** Added `ValueError` for `tokens_used < 0`, `> 1,000,000`, and `quality_score` outside `[0.0, 1.0]` in both `TaskContext.record()` and `Buoyancy.record_task()`.

### H2. SQLite Concurrent Write Failures

**Problem:** Default SQLite config with no WAL, no busy timeout, no thread safety. Multi-agent environments (OMC ultrawork) would get `database is locked` errors.

**Fix:** WAL mode + `busy_timeout=30000` + `threading.Lock` on all write operations + `check_same_thread=False`.

### H3. Database File World-Readable

**Problem:** `~/.buoyancy/` directory and `memory.db` created with default umask (0o755/0o644), exposing task names and usage patterns to other users.

**Fix:** `os.chmod(directory, 0o700)` and `os.chmod(db_file, 0o600)` on creation.

## MEDIUM — Fixed

### M2. Failed Task Budget Infinite Growth

**Problem:** Failed tasks increased budget by 20% with no cap. 10 consecutive failures = 6.19x original budget.

**Fix:** Added `MAX_TOKENS_CAP = 100_000` limit.

### M3. Context Manager Exception Records Success

**Problem:** If code inside `with b.task(...)` threw an exception, the auto-record logic recorded `succeeded=True`.

**Fix:** Wrapped `yield ctx` in `try/except BaseException`, recording `succeeded=False` on exception.

### M7. No Data Expiration or Cleanup

**Problem:** `task_records` table grew forever with no TTL, no archival, no reset mechanism.

**Fix:** Added `Memory.prune(older_than_days)` and `Memory.reset(task_type)` with CLI commands `buoyancy prune` and `buoyancy reset`.

### L1. No String Length Limits

**Problem:** `task_name` and `task_type` accepted unbounded strings.

**Fix:** Truncation to 200 and 50 characters respectively in `Memory.record()`.

### L5. `close()` Not Idempotent

**Problem:** Double-calling `close()` raised `ProgrammingError`.

**Fix:** Guard with `if self._conn` check.

## MEDIUM — Accepted Risk

### M1. EMA Cold Start Bias

First 3 records are stored but ignored by `estimate()` (falls back to defaults). When the 4th record activates calibration, EMA may be skewed by early outliers. **Accepted** because the safety margin (1.15x) provides buffer, and confidence is low (0.1) during this phase.

### M4. BuoyantClaude Success Detection

`succeeded = response.stop_reason != "max_tokens"` doesn't account for `tool_use` stop reason. **Accepted** as adapter is clearly documented as optional and users can override.

## LOW — Accepted Risk

### M6. Classifier Keyword Conflicts

"fix a typo in README" matches `bugfix` before `docs`. Priority ordering mitigates most cases but imperfect. **Accepted** — misclassification slightly blurs calibration data but doesn't break it. Score-based classification is a future improvement.

### L2. Fingerprint Dead Code

SHA-256 fingerprint is computed but never used for queries. **Accepted** — reserved for future similarity matching.

## OWASP Top 10 Assessment

| Category | Rating | Notes |
|----------|--------|-------|
| A01 Broken Access Control | ✅ FIXED | DB now owner-only (0o600) |
| A02 Cryptographic Failures | PASS | No encryption needed |
| A03 Injection | PASS | All SQL parameterized |
| A04 Insecure Design | ✅ FIXED | Input validation, exception handling |
| A05 Security Misconfiguration | PASS | Secure defaults |
| A06 Vulnerable Components | PASS | stdlib only, no CVEs |
| A07 Auth Failures | N/A | Local SDK, no auth |
| A08 Integrity Failures | ✅ FIXED | Input bounds, budget caps |
| A09 Logging Failures | ✅ FIXED | prune/reset lifecycle |
| A10 SSRF | N/A | No outbound requests |
