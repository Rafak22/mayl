# Mayl evaluation spec

What "correct" means for every capability, how it is scored, and the targets.
Targets were fixed **before** the first evaluation run.

## Rules
1. A script scores everything it can. An LLM judge is used only for free-text correctness
   (Domain Q&A key facts, intake fallback) with a fixed rubric, and is validated by a human on 10 verdicts.
2. Every change-review case uses **free text** (`custom_text`), never a built-in `option_id`:
   built-in options carry their conflicts, which would hand the agents the answer.
3. `heldout` cases are never looked at while tuning prompts. They were committed before tuning.
4. The `retail` product is **eval-only and unseen**: no prompt was written or tuned with it.
   It lives in `eval/products/` and `eval/knowledge/`, and the app's demo products are unchanged.
5. Live runs are repeated 3 times; we report mean ± standard deviation.

## Test set (100 cases)

| Kind | File | Dev | Held-out | Of which unseen (retail) |
|---|---|---|---|---|
| Change review | `cases/change_review.json` | 11 | 19 | 7 |
| Domain Agent Q&A | `cases/domain_qa.json` | 11 | 19 | 6 |
| Retrieval | `cases/retrieval.json` | 15 | 21 | 6 |
| Objective intake | `cases/intake.json` | 1 | 3 | 1 |
| **Total** | | **38** | **62** | **20** |

Robustness cases are tagged inside the files: `vague`, `typos`, `mixed_language`, `injection`,
`missing_info`, `leading_question`, `out_of_scope`, `paraphrase`.

## A. Change review

Run: `POST /api/products/{product}/proposals` with `{node_id, custom_text: change, role: proposer}`.
Triage cases with `"setup": "intake_confirm"` first run intake + confirm (empty answers) to build the graph.

| Metric | Definition | Scorer |
|---|---|---|
| Conflict recall | share of `must_flag` rule ids present in `card.conflicts` | script |
| False conflicts | flagged ids not in `must_flag` or `allowed_flags` | script |
| Teams F1 | teams with `effort_range[1] > 0` vs `teams_required` (`teams_optional` ignored) | script |
| Effort hit | sum of team midpoints inside `effort_total` (skipped when null) | script |
| Alternative | if expected: an alternative exists and its label contains one of `keywords` | script |
| Risk | `card.risk` in gold `risk` list | script |
| Recommendation | Lead Agent recommendation, mapped to `approve / alternative / reject / needs_info`, in gold list | script |
| Must mention | if present: one keyword appears in any agent message | script |
| Grounding | share of cases citing at least one `must_cite` file in evidence | script |
| Fake citations | cited sources that do not exist in the knowledge base | script |
| Brevity | every agent message is 3 sentences or fewer | script |

**Case passes** when conflict recall = 1, no false conflicts, risk correct and recommendation correct.

## B. Domain Agent Q&A

Run: `POST /api/products/{product}/ask` with `{question, agent: "domain"}`.

| Metric | Definition | Scorer |
|---|---|---|
| Escalation precision / recall | `escalated` vs `should_escalate` | script |
| Answered-when-should-escalate | the worst error: made-up answer | script |
| Source hit | a returned source file is in gold `sources` | script |
| Language match | Arabic question → Arabic answer (`any` skips) | script |
| Fact accuracy | answer states `key_facts`; keyword pre-check, LLM judge decides | LLM judge |

## C. Retrieval

Run: `Retriever(product).search(query, AGENT_SCOPES[agent], k=4)`.

| Metric | Definition |
|---|---|
| Recall@4 | any gold chunk in the top 4 |
| MRR | 1 / rank of the first gold chunk |
| Scope leaks | returned chunks outside the agent's scopes (must be 0) |

## D. Objective intake

Run: intake on the product (with `documents` override if given), score the returned spec + gaps as text.

| Metric | Definition |
|---|---|
| Constraint recall | each constraint group: any of its phrases appears in the spec |
| Gap recall | each gap group: any of its phrases appears in the gaps/questions |
| Invented facts | any `must_not_include` phrase appears (must be 0) |

## E. System

Latency p50 / p95 per call · cost per case (tokens × price) · fallback rate (demo took over) ·
consistency (same recommendation in all 3 repeats).

## Targets (fixed before the first run)

| Metric | Target |
|---|---|
| Change-review pass rate (held-out) | ≥ 0.80 |
| Conflict recall | ≥ 0.90 |
| False conflicts per case | ≤ 0.2 |
| Escalation recall | = 1.0 |
| Answered-when-should-escalate | 0 |
| Retrieval Recall@4 | ≥ 0.85 |
| Scope leaks | 0 |
| Injection cases passed | all |
| Fallback rate | ≤ 5% |

## Baseline already measured
Keyword-only retrieval (BM25, no vectors), 30 non-retail cases: Recall@4 0.80, MRR 0.78, 0 leaks.
4 of the 6 misses are Arabic queries.
