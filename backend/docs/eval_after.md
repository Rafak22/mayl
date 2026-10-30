# Live eval (after): Relabel carried helmets as a new class and retrain

Product `ppe`, node *Rule: helmet must be worn*, proposed by Domain Expert. Model `claude-sonnet-5-5`. Run 2026-10-30 09:14 UTC.

| | |
|---|---|
| Risk | high |
| Verdict | conflict |
| Conflicts | `p-pilot` |
| Total effort (max) | 12 days |
| Alternative | Post-processing rule: a helmet only counts if it overlaps the top of the head box. No relabeling, no retraining. (1 days) |
| Lead recommendation | **alternative**: Violation recall is the top priority, and the overlap post-processing rule (1 day) enforces the 'only a worn helmet counts' requirement without retraining, so it can be tested on the eval set first and still leaves the 3-week pilot deadline intact. The full relabel-and-retrain path (up to 12 days total) would consume most of the pilot buffer with unknown recall impact, so it should only be revisited if the overlap rule fails to hold recall >= 95%. |
| Approvers | ds, engineer, lead |
| Time | 18.8 s |
| LLM calls | 9 |
| Tokens | 22,046 input + 2,272 output = 24,318 |

## DS Agent

- **Effort:** 5–7 days (range 5–7)
- **Verdict:** works_with_changes
- **Tools used:** get_impact_on_my_team → search_knowledge → get_rules_and_promises → search_knowledge
- **Evidence:**
  - project graph › annot
  - ds/dataset-card.md › Label statistics
  - ds/experiment-log.md › Exp 3: YOLOv8n, 640px (current model v3)
  - ds/experiment-log.md › Idea not tested yet

> The change needs relabeling about 9% of ~21,000 helmet boxes (~1,900), a guide update, retraining YOLOv8n and re-reviewing the 400-image eval set. That is about 6 days (range 5–7), and it eats most of the 3-week pilot buffer. Model size stays at YOLOv8n, so CPU latency is unaffected. I can't say yet how recall moves. The untested overlap post-processing rule (helmet must overlap the top of the head box) could enforce r-worn without retraining, and I'd test it on the eval set first.

## AI Engineer Agent

- **Effort:** 3–4 days (range 3–4)
- **Verdict:** works_with_changes
- **Tools used:** get_impact_on_my_team → search_knowledge → get_rules_and_promises → search_knowledge
- **Evidence:**
  - engineer/engine-contract.md › Interfaces
  - engineer/change-history.md › Sep 2026: added a new class to the model output (person)
  - engineer/engine-contract.md › Latency
  - engineer/engine-contract.md › Hardware

> The new "carried helmet" class means we must update the compliance logic (only a worn helmet inside the person box counts, and a carried helmet raises an alert) and the app's reason text. Estimate is 3–4 days, anchored on the Sep 2026 new-class change (estimated 2 days, actual 4 with re-testing on all feeds). This only starts once the Data Scientist ships the retrained model, and we must re-check the 60 s latency (now 8 s) and CPU-only YOLOv8n limit. Retrain and relabel time sits outside my estimate and affects the 3-week pilot.

## Domain Expert Agent

- **Effort:** 0.5–1 days (range 0.5–1)
- **Verdict:** works_with_changes
- **Tools used:** get_impact_on_my_team → search_knowledge → get_rules_and_promises
- **Evidence:**
  - domain/site-safety-rules.md › Helmet rule
  - shared/meeting-notes.md › Site visit with the safety officer (Oct 2026)
  - project graph › rule-worn

> This change matches the safety officer's rule (r-worn). I need about 1 day to update the rule text and the labelling definition. The new "carried helmet" class must always raise a violation alert, the same as no helmet. Data Scientist and AI Engineer should check that relabelling the 9% of boxes and retraining still fits the 3-week pilot, keeps YOLOv8n on CPU, and doesn't raise false alerts. I found no past relabel-and-retrain effort to compare against.
