# 01_dev_baseline

Definitions and targets: `eval/SPEC.md`. Commit `eb6fd0c`.

Pass definitions: change review as in the spec (conflict recall 1, no false conflicts, risk and recommendation correct). Domain Q&A: escalation correct and, when it should answer, a gold source, the key facts and the question's language. Retrieval: a gold chunk in the top 4 and no scope leak. Intake: every constraint and gap group found and nothing invented.

## dev · live · 20261030-162955

38 cases × 3 repeat(s) · kinds: change_review, domain_qa, retrieval, intake · model `claude-sonnet-5-5` · judge `claude-sonnet-5-5` · seeded bottleneck cleared · results `eval/results/20261030-162955_dev_live.json`

### Targets

| Metric | Target | Result | |
|---|---|---|---|
| Change-review pass rate (held-out) (this run: dev) | >= 0.8 | 0.73 | **not met** |
| Conflict recall | >= 0.9 | 0.86 | **not met** |
| False conflicts per case | <= 0.2 | 0 | met |
| Escalation recall | == 1.0 | 1.00 | met |
| Answered-when-should-escalate | == 0 | 0 | met |
| Retrieval Recall@4 | >= 0.85 | 0.93 | met |
| Scope leaks | == 0 | 0 | met |
| Fallback rate | <= 0.05 | 0.00 | met |

### A. Change review

| Metric | Mean ± std |
|---|---|
| pass rate | 0.73 |
| conflict recall | 0.86 |
| false conflicts per case | 0 |
| teams f1 | 0.57 ± 0.03 |
| effort hit | 0.20 |
| alternative | 0.90 ± 0.08 |
| risk | 0.91 |
| recommendation | 0.88 ± 0.05 |
| must mention | 1.00 |
| grounding | 1.00 |
| fake citations per case | 0 |
| brevity | 0.03 ± 0.05 |

### B. Domain Agent Q&A

| Metric | Mean ± std |
|---|---|
| pass rate | 0.82 |
| escalation precision | 0.80 |
| escalation recall | 1.00 |
| answered when should escalate | 0 |
| source hit | 0.86 |
| language match | 0.67 |
| fact accuracy | 0.86 |

### C. Retrieval

| Metric | Mean ± std |
|---|---|
| pass rate | 0.93 |
| recall at 4 | 0.93 |
| mrr | 0.80 |
| scope leaks | 0 |

### D. Objective intake

| Metric | Mean ± std |
|---|---|
| pass rate | 1.00 |
| constraint recall | 1.00 |
| gap recall | 1.00 |
| invented facts | 0 |

### E. System

| Metric | Mean ± std |
|---|---|
| fallback rate | 0.00 |
| cost per case usd | $0.0204 ± 0.00 |
| cost per repeat usd | $0.7765 ± 0.00 |
| latency change review p50 / p95 | 11.76 s / 29.69 s |
| latency domain qa p50 / p95 | 1.94 s / 2.75 s |
| latency retrieval p50 / p95 | 0.02 s / 0.03 s |
| latency intake p50 / p95 | 19.54 s / 20.52 s |
| consistency (same recommendation in all repeats) | 0.64 |
| cost per change review case | $0.0637 (19,465 in / 2,477 out tokens) |
| cost per domain qa case | $0.0032 (956 in / 124 out tokens) |
| cost per intake case | $0.0411 (8,132 in / 2,484 out tokens) |

### Robustness tags

| Tag | Cases | Pass rate |
|---|---|---|
| mixed_language | 1 | 1.00 |
| out_of_scope | 1 | 1.00 |
| vague | 1 | 0.00 |

### Failed cases (6 of 38)

- **cr-chat-07** (change review, failed 3/3 repeats): recommendation reject not in ['needs_info']
- **cr-ppe-01** (change review, failed 3/3 repeats): missed conflicts ['p-pilot']
- **cr-ppe-07** (change review, failed 3/3 repeats): risk high not in ['low', 'medium']; recommendation alternative not in ['approve']
- **qa-chat-01** (domain qa, failed 3/3 repeats): wrong language
- **qa-tri-01** (domain qa, failed 3/3 repeats): escalated instead of answering; no gold source; wrong language
- **rt-ppe-05** (retrieval, failed 3/3 repeats): no gold chunk in top 4

### Judge verdicts to hand-check (6 distinct cases; answer and reason from repeat 1)

| Case | Verdict per repeat | Keyword pre-check | Judge reason | Answer |
|---|---|---|---|---|
| qa-chat-01 | correct / correct / correct | miss | The answer says yes, the bot must hand over to a human when the message contains 'شكوى رسمية', which matches the reference; the added 30-second detail does not contradict the key facts. | نعم، يجب على البوت التحويل إلى موظف بشري عندما تتضمن رسالة العميل عبارة "شكوى رسمية"، فهي من الحالات الإلزامية للتحويل حسب الإرشادات. كما يجب أن يتم التحويل في  |
| qa-chat-03 | correct / correct / correct | hit | The answer states that 'ابي' in the Gulf dialect means 'أريد' (I want), which matches the reference key fact, and the extra detail about the bot does not contradict it. | كلمة "ابي" في اللهجة الخليجية تعني "أريد" (I want)، وهي من العبارات التي يكتبها العملاء، ويجب على البوت فهمها والرد بعربية واضحة. |
| qa-ppe-01 | correct / correct / correct | hit | The answer says no, states that a helmet counts only when worn on the head, and calls a belt-clipped helmet a violation, which matches the reference; the extra detail about the strap and the compliance-logic caveat does not contradict it. | No. Under the site rules a helmet only counts when it is worn on the head with the strap fastened where visible, so a helmet clipped to a belt is a violation, n |
| qa-ppe-03 | correct / correct / correct | hit | The answer names the same high-priority zones as the reference (active work zones: under cranes, at height, near heavy machinery) and adds only a non-contradictory note that other areas are normal priority. | High priority applies to no-helmet violations in active work zones: under cranes, at height, and near heavy machinery. Everywhere else on site is normal priorit |
| qa-ppe-08 | correct / correct / correct | hit | The answer says no, it is not compliant, and states that a helmet lying on the ground is a violation, which matches the reference; the extra detail about the helmet being worn with the strap fastened does not contradict it. | لا، لا يعتبر compliant. حسب قاعدة الخوذة، الخوذة تُحتسب فقط إذا كانت على الرأس مع ربط الحزام حيث يكون ظاهراً، والخوذة الموضوعة على الأرض تُعد مخالفة. |
| qa-tri-03 | correct / correct / correct | hit | The answer states a same-day appointment, matching the reference's core conclusion, and its added rationale does not contradict it. | A same-day appointment. Fever under 3 days and ear pain are both listed under same-day appointment criteria. |
