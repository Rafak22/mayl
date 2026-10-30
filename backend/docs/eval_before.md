# Live eval (before): Relabel carried helmets as a new class and retrain

Product `ppe`, node *Rule: helmet must be worn*, proposed by Domain Expert. Model `claude-sonnet-5-5`. Run 2026-10-30 09:03 UTC.

| | |
|---|---|
| Risk | high |
| Verdict | conflict |
| Conflicts | `p-pilot` |
| Total effort (max) | 15 days |
| Alternative | Keep the current classes and treat 'helmet' with no head overlap as a violation. This is a rule in the compliance logic, with the carried-helmet cases added to the evaluation set only. No retrain before the pilot. (0.5 days) |
| Approvers | ds, engineer, lead |
| Time | 14.4 s |
| LLM calls | 8 |
| Tokens | 18,715 input + 2,474 output = 21,189 |

## DS Agent

- **Effort:** 5–7 days (range 5–7)
- **Verdict:** works_with_changes
- **Tools used:** get_impact_on_my_team → search_knowledge → get_rules_and_promises → search_knowledge → search_knowledge
- **Evidence:**
  - ds/dataset-card.md › Label statistics
  - ds/experiment-log.md › Error analysis on model v3
  - ds/experiment-log.md › Idea not tested yet
  - ds/dataset-card.md › Classes (current annotation guide v1)

> Doable in about 6 days: we would find and relabel roughly 1,900 carried-helmet boxes (9% of 21,000), update the annotation guide, retrain YOLOv8n and re-review the 400-image eval set. It supports the "worn only" rule and fits the 3-week pilot, but the AI Engineer must update the compliance logic for the new class. A cheaper first step is an untested post-processing rule that only counts a helmet if its box overlaps the top of a head box. It needs no retraining and takes about 1.5 days.

## AI Engineer Agent

- **Effort:** 4–6 days (range 4–6)
- **Verdict:** works_with_changes
- **Tools used:** get_impact_on_my_team → get_rules_and_promises → search_knowledge
- **Evidence:**
  - engineer/change-history.md › Sep 2026: added a new class to the model output (person)
  - engineer/engine-contract.md › Interfaces
  - shared/meeting-notes.md › Decision pending

> The change fits the rule that a helmet counts only when worn (r-worn). We need to update the compliance logic and the app reason text for the new class. The baseline is 3 days, but a similar class change in Sep 2026 took 4 days against a 2-day estimate, so plan for 4-6 days, plus the Data Scientist's relabel and retrain time. A cheaper option is a head-position check on the existing helmet box, with no retrain.

## Domain Expert Agent

- **Effort:** 1–2 days (range 1–2)
- **Verdict:** works_with_changes
- **Tools used:** get_impact_on_my_team → get_rules_and_promises → search_knowledge → search_knowledge
- **Evidence:**
  - shared/meeting-notes.md › Site visit with the safety officer (Oct 2026)
  - shared/project-brief.md › Success metrics agreed with the client
  - project graph › annot
  - shared/project-brief.md › Status

> The change matches rule r-worn: a helmet counts only when worn on the head. My side only needs about 1–2 days to update the rule wording and define "carried helmet" as a violation. The larger work (annotation guide, relabeling about 9% of helmet boxes, retraining, the evaluation set, and compliance logic) sits with the Data Scientist and AI Engineer, and it puts the 3-week pilot at risk.
