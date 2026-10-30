# Mayl: testing and results

How we test Mayl, what we measured and what the numbers mean. The full metric definitions
are in [`backend/eval/SPEC.md`](../backend/eval/SPEC.md), and every report is in
[`backend/eval/reports/`](../backend/eval/reports/). Where all the data comes from and how it is
stored: [DATA.md](DATA.md).

## Headline

On cases the agents were never tuned on (held-out, live Claude, one run):

| What | Target | Result |
|---|---|---|
| Change review: the whole card is right (conflicts, risk, recommendation) | ≥ 0.80 | **0.68**, not met |
| … on the three demo products | | **0.83** (10 of 12) |
| … on a product never seen while building (retail) | | **0.43** (3 of 7) |
| Conflict recall (catches the rules and promises a change breaks) | ≥ 0.90 | 0.89 |
| False conflicts per case | ≤ 0.2 | 0.05 |
| Never answers a question it should hand to a human | 100% | **100%** |
| Prompt-injection cases resisted | all | **2 / 2** |
| Retrieval: right document in the top 4 | ≥ 0.85 | **0.95** |
| Scope leaks (an agent sees another team's private knowledge) | 0 | **0** |
| Fallback to demo mode (API failure) | ≤ 5% | **0%** |
| A human agrees with the AI judge (10 held-out verdicts checked by hand) | | **10 / 10** |
| Cost per change review (3 team agents + Lead Agent) | | **about $0.06** |

In short, Mayl is safe: it never makes up an answer it should escalate, never leaks knowledge
across teams and isn't fooled by injected instructions. It is strong on projects it knows, and
its full-card accuracy drops on a brand-new project. The gap is mostly the Lead Agent's final
call, not missed rules.

## Two kinds of tests

### 1. Unit and API tests (`backend/tests/`, 45 tests, free)

Run with `cd backend && pytest`. They run in seconds with no API key.

| File | What it checks |
|---|---|
| `test_api.py` | Every endpoint, per-visitor sessions, the demo-mode flows (bottleneck, decisions, intake, handoff), stats, product details |
| `test_live.py` | The live agent pipeline against a **fake Claude** that follows the real tool protocol: parallel team agents, Lead Agent recommendation (including `needs_info`), deadline conflicts raised by the Lead Agent, fallback to demo mode when the API fails, the separate live budgets (8 reviews and 20 chat messages per session), English search for non-English questions, and escalation when passages don't answer the question |
| `test_rag.py` | Hybrid search (keyword + vector): Arabic ↔ English matching, scope filtering, off-topic queries return nothing, the committed index matches the knowledge files, identical embeddings |

### 2. The evaluation (`backend/eval/`, real Claude, costs money)

This measures how good the agents' answers are, not just whether the code runs.

**Test set: 100 cases, frozen and committed before any tuning.**

| Kind | What a case is | Dev | Held-out |
|---|---|---|---|
| Change review | A free-text change → the full card (teams, effort, conflicts, risk, alternative, recommendation) | 11 | 19 |
| Domain Agent Q&A | A question → answer with sources, or escalate to a human | 11 | 19 |
| Retrieval | A search query → is the right knowledge chunk in the top 4? | 15 | 21 |
| Objective intake | Client documents → Objective Spec (constraints, gaps) | 1 | 3 |
| **Total** | | **38** | **62** |

Robustness cases are mixed in: vague requests, typos, mixed Arabic/English, prompt injection,
missing information, leading questions, out-of-scope questions and paraphrases.

**Rules we kept to protect the result:**

1. **Dev vs held-out.** Dev cases are for practice: we read their failures and improve the
   prompts. Held-out cases are the final exam: never opened while tuning, run once at the end.
2. **An unseen product.** A fourth product (retail demand forecasting) exists only in the
   eval, and only in held-out. No prompt was written with it in mind.
3. **General fixes only.** No prompt contains a case-specific word (helmet, pilot, refund…).
   Every fix is a rule that should hold for any project.
4. **Targets set before the first run** and never moved.
5. **Scored by a script wherever possible.** An LLM judge is used only to check whether a
   free-text answer states the key facts, with a fixed rubric; its verdicts are listed in
   each report for a human to spot-check. On held-out (run 04), a human read all 10 listed
   verdicts against the agent's answer and agreed with **10 of 10**.
6. **Eval files are read-only.** Cases and knowledge were never edited to make a test pass.
   For example, Arabic lines were not added to the knowledge files to help Arabic questions.

Run it with:

```bash
cd backend
python scripts/run_eval.py --split dev --mode live --repeats 1 --max-usd 1.5
```

`--mode demo` runs the free, rule-based agents. `--max-usd` stops the run before it can
overspend.

## The iteration history

Each run is saved as a numbered report, so every step can be checked.

| Run | What changed before it | Change-review pass rate | Cost |
|---|---|---|---|
| Smoke check | One live review of the helmet bottleneck, before the test set existed ([before](../backend/docs/eval_before.md), [after](../backend/docs/eval_after.md), `scripts/eval_live.py`) | not scored | |
| Demo floor | Rule-based agents, no LLM | 0.20 (all cases) | free |
| [01 dev baseline](../backend/eval/reports/01_dev_baseline.md) | First live run (3 repeats) | 0.73 | $2.33 |
| [02 dev](../backend/eval/reports/02_dev_after_fixes.md) | Fixes a–d (below) | 0.73 | $0.84 |
| [03 dev](../backend/eval/reports/03_dev_effort_deadlines_alts.md) | Effort, deadline and alternative fixes | **0.82** | $0.79 |
| [04 held-out](../backend/eval/reports/04_heldout.md) | Nothing; the final exam | **0.68** | $1.38 |

**Total live spend for the whole evaluation: $5.55** (including a $0.21 trial run).

### What each fix was and what it did

**Run 02: fixes a–d**

| Fix | Rule | Effect on dev |
|---|---|---|
| a. Cross-language search | Non-English questions are also searched in English; the agent decides whether the passages really answer the question, instead of a fixed similarity cutoff | Q&A pass rate 0.82 → **1.00**; answers in the question's language 0.67 → 1.00; out-of-scope questions still escalate |
| b. `needs_info` | The Lead Agent can ask for more detail when a change is too vague to assess | Recommendation accuracy 0.88 → 1.00; the vague "change the model" case now passes |
| c. Alternatives and style | Propose an alternative only if clearly cheaper or safer; answer in the question's main language; at most 3 sentences per message | Alternatives got worse (0.90 → 0.57): the wording was too strict (fixed in run 03) |
| d. Flag described risks | If an agent describes a risk to a rule, it must flag it | Mixed: caused one false conflict, and the missed deadline conflict stayed missed (replaced in run 03) |

**Run 03: effort, deadlines and alternatives.** First we read every failed dev answer to find
the cause, at no API cost.

| Cause found | Fix | Effect on dev |
|---|---|---|
| Agents started from a baseline that assumed every downstream component is rebuilt, so estimates ran 2× too high and pushed risk to "high" | The baseline is labelled an upper bound; agents count only components that must actually change; the Domain Agent's review time counts only if a document must change | Effort accuracy 0.20 → **0.80**; risk 0.91 → **1.00** |
| Each team judged the deadline from its own slice of the work, which no single team can do | Team agents flag only rules the change itself breaks; the Lead Agent compares the **total** effort with the promised dates and can add a deadline conflict | False conflicts 0.09 → **0** |
| "A smaller version is not an alternative" blocked valid alternatives | A narrower version counts if it avoids the conflict; when a change breaks a rule, name the safe way to reach its goal | Alternatives 0.57 → **0.86** |

## Held-out results in detail

| Area | Pass rate | Familiar products | Unseen retail |
|---|---|---|---|
| Change review | 0.68 | 10 / 12 | 3 / 7 |
| Domain Agent Q&A | 0.84 | 10 / 13 | 6 / 6 |
| Retrieval | 0.95 | 14 / 15 | 6 / 6 |
| Objective intake | 0.67 | 1 / 2 | 1 / 1 |

Change review in detail: teams 1.00, effort 0.88, alternatives 0.80, risk 0.89,
recommendation 0.84, grounded in a cited source 1.00, fake citations 0.

**What failed, honestly:**

- **Change review on the new product (4 of 7 failed).** Three of the four are the Lead
  Agent's final call: it chose reject, alternative or "needs more info" where the gold answer
  says otherwise. The fourth flagged a rule the change doesn't break. The team agents' own work
  (teams, effort, sources) held up well.
- **Missed deadline conflicts (2 cases).** The same pattern as on dev: the Lead Agent judged
  that the total effort still fits a promised date that the gold answer says is at risk. Both
  cases also got risk "medium" instead of "high".
- **Over-cautious Q&A (3 cases).** The Domain Agent escalated questions it could have
  answered. That is the safe direction: it never answered one it should have escalated. It
  is likely a side effect of fix a, which lets the agent judge relevance itself.
- **Intake (1 case).** It missed a "never delete" calendar constraint and added a
  "4 weeks" detail that wasn't in those documents.
- **Retrieval (1 case).** The right chunk ranked outside the top 4.

We have **not** changed anything based on these held-out failures. Doing so would turn the
held-out set into practice cases and remove our only unbiased number.

## Limits of these numbers

- **One repeat per run** (except run 01) to stay within budget. With 19 change-review cases,
  one case is about 5 points, so differences of 5–10 points can be noise.
- **The gold answers are judgement calls** in places, for example whether 7–11 days of work
  "threatens" a 3-week pilot. One dev case (`cr-chat-04`) accepts "needs more info" as a
  recommendation but also expects an alternative; we flagged it rather than editing it.
- **Message length.** Agents still often write more than 3 sentences per message (brevity
  0.11 on held-out). This isn't part of the pass rule.
- **The judge check is small.** The 10 hand-checked verdicts were all "correct", so it shows
  the judge doesn't pass wrong answers in those cases, not how it handles answers it fails.
- **Some checks use keywords** (constraints, alternatives), so a correct answer worded
  differently can be scored as a miss.

## What we'd do next

To improve change review on new projects without touching held-out:

1. Write new dev cases for a second unfamiliar product and tune the Lead Agent on those.
2. Re-run held-out **once** at the end, with 3 repeats if budget allows.
