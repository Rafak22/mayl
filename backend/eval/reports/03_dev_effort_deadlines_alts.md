# 03_dev_effort_deadlines_alts

Definitions and targets: `eval/SPEC.md`. Commit `ed94133`. Compared with `02_dev_after_fixes` (commit `c6338fa`).

Pass definitions: change review as in the spec (conflict recall 1, no false conflicts, risk and recommendation correct). Domain Q&A: escalation correct and, when it should answer, a gold source, the key facts and the question's language. Retrieval: a gold chunk in the top 4 and no scope leak. Intake: every constraint and gap group found and nothing invented.

## dev · live · 20261030-171800

11 cases × 1 repeat(s) · kinds: change_review · model `claude-sonnet-5-5` · judge `claude-sonnet-5-5` · seeded bottleneck cleared · results `eval/results/20261030-171800_dev_live.json`

### Targets

| Metric | Target | Before (02_dev_after_fixes, 1 rep.) | Result | |
|---|---|---|---|---|
| Change-review pass rate (held-out) (this run: dev) | >= 0.8 | 0.73 | 0.82 | met |
| Conflict recall | >= 0.9 | 0.86 | 0.86 | **not met** |
| False conflicts per case | <= 0.2 | 0.0909 | 0 | met |
| Escalation recall | == 1.0 | 1.00 | – | – |
| Answered-when-should-escalate | == 0 | 0 | – | – |
| Retrieval Recall@4 | >= 0.85 | 0.93 | – | – |
| Scope leaks | == 0 | 0 | – | – |
| Fallback rate | <= 0.05 | 0.00 | 0.00 | met |

**Cases fixed** (failed every repeat before, pass now): cr-ppe-05  
**Cases broken** (passed every repeat before, fail now): none

### A. Change review

| Metric | Before (02_dev_after_fixes, 1 rep.) | Mean ± std |
|---|---|---|
| pass rate | 0.73 | 0.82 |
| conflict recall | 0.86 | 0.86 |
| false conflicts per case | 0.0909 | 0 |
| teams f1 | 0.92 | 0.91 |
| effort hit | 0.20 | 0.80 |
| alternative | 0.57 | 0.86 |
| risk | 0.91 | 1.00 |
| recommendation | 1.00 | 0.91 |
| must mention | 1.00 | 1.00 |
| grounding | 1.00 | 1.00 |
| fake citations per case | 0 | 0 |
| brevity | 0.00 | 0.00 |

### E. System

| Metric | Before (02_dev_after_fixes, 1 rep.) | Mean ± std |
|---|---|---|
| fallback rate | 0.00 | 0.00 |
| cost per case usd | $0.0221 | $0.0718 |
| cost per repeat usd | $0.8400 | $0.7896 |
| latency change review p50 / p95 | 11.28 s / 46.38 s | 16.77 s / 44.53 s |
| cost per change review case | – | $0.0718 (21,342 in / 2,910 out tokens) |

### Robustness tags

| Tag | Cases | Pass rate |
|---|---|---|
| vague | 1 | 1.00 |

### Effort and teams misses (diagnosis, repeat 1: 2 of 11 change reviews)

| Case | Effort predicted (sum of midpoints) | Gold range | Effort | Teams with work | Required | Teams |
|---|---|---|---|---|---|---|
| cr-ppe-07 | 5.5 d | 1–5 d | over | ds, engineer | ds | ok |
| cr-tri-03 | 0 d | not scored | – | none | ds | missing ds |

### Failed cases (2 of 11)

- **cr-ppe-01** (change review): missed conflicts ['p-pilot']
- **cr-ppe-07** (change review): recommendation needs_info not in ['approve']
