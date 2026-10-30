# 02_dev_after_fixes

Definitions and targets: `eval/SPEC.md`. Commit `c6338fa`. Compared with `01_dev_baseline` (commit `eb6fd0c`).

Pass definitions: change review as in the spec (conflict recall 1, no false conflicts, risk and recommendation correct). Domain Q&A: escalation correct and, when it should answer, a gold source, the key facts and the question's language. Retrieval: a gold chunk in the top 4 and no scope leak. Intake: every constraint and gap group found and nothing invented.

## dev · live · 20261030-165107

38 cases × 1 repeat(s) · kinds: change_review, domain_qa, retrieval, intake · model `claude-sonnet-5-5` · judge `claude-sonnet-5-5` · seeded bottleneck cleared · results `eval/results/20261030-165107_dev_live.json`

### Targets

| Metric | Target | Before (01_dev_baseline, 3 rep.) | Result | |
|---|---|---|---|---|
| Change-review pass rate (held-out) (this run: dev) | >= 0.8 | 0.73 | 0.73 | **not met** |
| Conflict recall | >= 0.9 | 0.86 | 0.86 | **not met** |
| False conflicts per case | <= 0.2 | 0 | 0.0909 | met |
| Escalation recall | == 1.0 | 1.00 | 1.00 | met |
| Answered-when-should-escalate | == 0 | 0 | 0 | met |
| Retrieval Recall@4 | >= 0.85 | 0.93 | 0.93 | met |
| Scope leaks | == 0 | 0 | 0 | met |
| Fallback rate | <= 0.05 | 0.00 | 0.00 | met |

**Cases fixed** (failed every repeat before, pass now): cr-chat-07, qa-chat-01, qa-tri-01  
**Cases broken** (passed every repeat before, fail now): cr-ppe-05, in-tri-01

### A. Change review

| Metric | Before (01_dev_baseline, 3 rep.) | Mean ± std |
|---|---|---|
| pass rate | 0.73 | 0.73 |
| conflict recall | 0.86 | 0.86 |
| false conflicts per case | 0 | 0.0909 |
| teams f1 | 0.93 ± 0.02 | 0.92 |
| effort hit | 0.20 | 0.20 |
| alternative | 0.90 ± 0.08 | 0.57 |
| risk | 0.91 | 0.91 |
| recommendation | 0.88 ± 0.05 | 1.00 |
| must mention | 1.00 | 1.00 |
| grounding | 1.00 | 1.00 |
| fake citations per case | 0 | 0 |
| brevity | 0.03 ± 0.05 | 0.00 |

### B. Domain Agent Q&A

| Metric | Before (01_dev_baseline, 3 rep.) | Mean ± std |
|---|---|---|
| pass rate | 0.82 | 1.00 |
| escalation precision | 0.80 | 1.00 |
| escalation recall | 1.00 | 1.00 |
| answered when should escalate | 0 | 0 |
| source hit | 0.86 | 1.00 |
| language match | 0.67 | 1.00 |
| fact accuracy | 0.86 | 1.00 |

### C. Retrieval

| Metric | Before (01_dev_baseline, 3 rep.) | Mean ± std |
|---|---|---|
| pass rate | 0.93 | 0.93 |
| recall at 4 | 0.93 | 0.93 |
| mrr | 0.80 | 0.80 |
| scope leaks | 0 | 0 |

### D. Objective intake

| Metric | Before (01_dev_baseline, 3 rep.) | Mean ± std |
|---|---|---|
| pass rate | 1.00 | 0.00 |
| constraint recall | 1.00 | 0.83 |
| gap recall | 1.00 | 1.00 |
| invented facts | 0 | 0 |

### E. System

| Metric | Before (01_dev_baseline, 3 rep.) | Mean ± std |
|---|---|---|
| fallback rate | 0.00 | 0.00 |
| cost per case usd | $0.0204 ± 0.00 | $0.0221 |
| cost per repeat usd | $0.7765 ± 0.00 | $0.8400 |
| latency change review p50 / p95 | 11.76 s / 29.69 s | 11.28 s / 46.38 s |
| latency domain qa p50 / p95 | 1.94 s / 2.75 s | 1.80 s / 4.31 s |
| latency retrieval p50 / p95 | 0.02 s / 0.03 s | 0.02 s / 0.02 s |
| latency intake p50 / p95 | 19.54 s / 20.52 s | 18.59 s / 18.59 s |
| cost per change review case | – | $0.0682 (20,925 in / 2,632 out tokens) |
| cost per domain qa case | – | $0.0042 (1,357 in / 153 out tokens) |
| cost per intake case | – | $0.0434 (9,775 in / 2,385 out tokens) |

### Robustness tags

| Tag | Cases | Pass rate |
|---|---|---|
| mixed_language | 1 | 1.00 |
| out_of_scope | 1 | 1.00 |
| vague | 1 | 1.00 |

### Effort and teams misses (diagnosis, repeat 1: 4 of 11 change reviews)

| Case | Effort predicted (sum of midpoints) | Gold range | Effort | Teams with work | Required | Teams |
|---|---|---|---|---|---|---|
| cr-chat-01 | 4.38 d | 0.25–2 d | over | domain, ds, engineer | ds | extra domain |
| cr-chat-04 | 9 d | 1–6 d | over | ds, engineer | ds | ok |
| cr-ppe-03 | 8.25 d | 2–8 d | over | domain, ds, engineer | ds, engineer | extra domain |
| cr-ppe-07 | 9.75 d | 1–5 d | over | domain, ds, engineer | ds | extra domain |

### Failed cases (5 of 38)

- **cr-ppe-01** (change review): missed conflicts ['p-pilot']
- **cr-ppe-05** (change review): false conflicts ['p-pilot']
- **cr-ppe-07** (change review): risk high not in ['low', 'medium']
- **rt-ppe-05** (retrieval): no gold chunk in top 4
- **in-tri-01** (intake): missed constraints ['delete']

### Judge verdicts to hand-check (7 distinct cases; answer and reason from repeat 1)

| Case | Verdict per repeat | Keyword pre-check | Judge reason | Answer |
|---|---|---|---|---|
| qa-chat-01 | correct | hit | The answer says yes and that any message containing 'شكوى رسمية' must be handed to a human, matching the reference; the extra 30-second detail is additional and does not contradict the key facts. | Yes. Any message containing "شكوى رسمية" (formal complaint) must be handed over to a human, and formal complaints in general go to a human agent. Handover shoul |
| qa-chat-03 | correct | hit | The answer states that 'ابي' is Gulf dialect meaning 'أريد' (I want), which matches the reference key fact, and the extra remark about the bot does not contradict it. | كلمة "ابي" من اللهجة الخليجية وتعني "أريد" (I want). يجب أن يفهمها البوت وأن يرد بعربية واضحة. |
| qa-ppe-01 | correct | hit | The answer says no, a helmet counts only when worn on the head and one clipped to a belt is a violation, matching the reference; the extra detail about the strap and other carrying positions does not contradict it. | No. A helmet only counts when it is worn on the head with the strap fastened where visible; one clipped to a belt, carried in the hand, hanging on equipment or  |
| qa-ppe-03 | correct | hit | The answer lists the same high-priority zones as the reference (active work zones: under cranes, at height, near heavy machinery) and its added note that other areas are normal priority does not contradict the key facts. | High priority applies to no-helmet alerts in active work zones: under cranes, at height, and near heavy machinery. Everywhere else on site is normal priority. |
| qa-ppe-08 | correct | hit | The answer says no, a helmet on the ground next to the worker is a violation and not compliant, which matches the reference; the extra detail about the helmet needing to be worn with the strap fastened does not contradict it. | لا، الخوذة الموضوعة على الأرض بجانب العامل تعتبر مخالفة (violation) وليست compliant. القاعدة تقول إن الخوذة تُحتسب فقط إذا كانت على الرأس مع ربط الحزام حيث يكون |
| qa-tri-01 | correct | hit | The answer states the core conclusion from the reference: treat shortness of breath as an emergency, advise calling 997 or going to the emergency department immediately, and alert the nurse, with no contradiction. | ضيق النفس (صعوبة التنفس) يُصنَّف دائماً كحالة طوارئ: انصح المريض بالاتصال بالرقم 997 أو التوجه إلى قسم الطوارئ فوراً، ونبّه الممرضة. ولا تعرض عليه موعداً عادياً |
| qa-tri-03 | correct | hit | The answer states the core conclusion of a same-day appointment for fever under 3 days with ear pain, and the added exception for children under 2 does not contradict the reference. | Fever under 3 days with ear pain falls under a same-day appointment. Neither symptom is on the always-emergency list, but if the patient is a child under 2 year |
