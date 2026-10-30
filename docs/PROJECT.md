# Mayl: agentic platform for AI product teams

## The problem

Building an AI product takes several teams: data scientists, AI engineers and domain
experts, led by an AI lead. When one of them changes something, such as relabeling data,
swapping the model or adding a rule, the effects ripple into the others' work. Usually nobody
sees the full picture until something breaks: a client deadline slips, a domain rule gets
violated, or a cheaper fix was missed.

## What Mayl does

Every team has an **AI agent** that knows that team's work. When anyone proposes a change, in
plain language, each affected team's agent checks it **in parallel and in seconds**:

- **What it touches:** which of my components are affected?
- **How long it takes:** an effort range, anchored to similar past changes.
- **What it breaks:** domain rules and client promises on record.
- **A better way:** a cheaper or safer alternative, if the knowledge supports one.

The **Lead Agent** then reads every team's assessment, checks the total effort against
promised deadlines and recommends one option: **approve**, **use the alternative**,
**reject** or **ask for more detail**.

**Humans decide. Agents do the legwork.**

## The four agents

| Agent | Represents | Knows about |
|---|---|---|
| **Lead Agent** | The AI lead | The Objective Spec (goal, priorities in order, deadline), every team's assessment, rules and promises. Reads client documents into the Objective Spec. |
| **DS Agent** | Data science | Data, annotations, models, experiments, evaluation |
| **Engineer Agent** | AI engineering | The engine, APIs, apps, hardware, the engine contract (latency, limits), change history with actual effort |
| **Domain Agent** | The domain expert (an "expert twin") | Domain rules, safety, client promises. Answers domain questions with sources, and **hands the question to a human** when the documents don't cover it |

Each team's agent only sees its own knowledge plus the shared project memory. The tests
confirm there are no leaks between teams.

## The demo projects

| Project | State | What it shows |
|---|---|---|
| Arabic customer-service chatbot | Healthy | The calm view: everything green, ask the agents anything |
| Helmet compliance detection (PPE) | Bottleneck | A domain rule (a carried helmet doesn't count) → impact on every team → conflict with a client deadline → a 1-day alternative instead of a retrain → one decision |
| Smart clinic receptionist (triage) | New | Client documents → Objective Spec with the open questions → agents design the system → handoff |

## The app

| Screen | What you do there |
|---|---|
| **Overview** | Projects at a glance, the decisions waiting for you, recent activity |
| **Projects** | Each project's map (a graph of components owned by each team), its data and solution, its knowledge files and its results against the goals. Tap any component to propose a change and watch the agents respond. |
| **Agents** | Who the agents are, what they know and what they have done |
| **Chat** | Ask the Lead, DS, Engineer or Domain Agent, or the project memory. Arabic and English both work. |

Switch roles at the top (AI Lead, Data Scientist, AI Engineer, Domain Expert) to see the same
project through each team's eyes, including that role's inbox of changes to review. Every
visitor gets an isolated session, and **Reset demo** starts over. The layout works on a phone.

## How it works

```
 Proposal (free text)
        │
        ▼
 Project graph (NetworkX) ── which components, and which teams, are affected?
        │
        ▼
 LangGraph ─┬─ DS Agent ───────┐   each agent uses tools:
            ├─ Engineer Agent ─┤   • graph impact on my team
            └─ Domain Agent ───┘   • hybrid search over my knowledge
        │                          • rules and promises on record
        ▼
 Platform (code): risk, verdict, approvers, cheapest alternative
        │
        ▼
 Lead Agent: total effort vs deadlines → recommendation + reason
        │
        ▼
 Card in each approver's inbox → a human decides
```

**Key design choices:**

- **Claude Sonnet 5.5** for every agent. Agents end with a strict, schema-checked answer
  (effort range, verdict, conflicts, evidence, alternative), so the output is always usable.
- **Risk is computed in code, not by the LLM**, from conflicts, blocked verdicts and total
  effort. It is predictable and explainable.
- **Deadlines are the Lead Agent's job.** Only the Lead Agent sees the total effort across
  teams, so only it judges whether a promised date is at risk.
- **Never breaks on stage.** Without an API key, or if a call fails, deterministic demo agents
  answer instead. Each session gets 8 live reviews and 20 live chat messages, to cap cost.

### Knowledge search (RAG)

All knowledge lives in one committed SQLite file, which needs no external database:

- **Keyword search:** SQLite FTS5 with BM25 ranking.
- **Meaning search:** sqlite-vec with `multilingual-e5-small` embeddings, which match Arabic
  and English by meaning. It runs on CPU through ONNX, with no PyTorch.
- **Fusion:** the two rankings are merged with Reciprocal Rank Fusion.
- **Cross-language:** in chat, a non-English question is also searched with an English
  translation, and the agent decides whether the passages actually answer it. If they don't,
  it escalates to a human instead of guessing.
- **Live project memory** (activity, decisions, rules) is searched the same way and stays in
  memory, never written to the database.

## Quality

Full details are in [TESTING.md](TESTING.md).

- **44 automated tests**, including the live pipeline against a fake Claude.
- **A 100-case evaluation set**, frozen before tuning, with a held-out "final exam" and a
  product the agents never saw during development.
- **Held-out results:** change-review pass rate **0.68** (0.83 on familiar projects, 0.43 on
  the unseen one), 100% correct escalation, injection-proof, retrieval 0.95, no scope leaks,
  and about **$0.06 per change review**.

## Tech stack

| Layer | Tools |
|---|---|
| Backend | Python, FastAPI, NetworkX, LangGraph, Anthropic SDK |
| Search | SQLite FTS5 + sqlite-vec, multilingual-e5-small (ONNX + sentencepiece) |
| Frontend | React 19, Vite, React Router, React Flow (`@xyflow/react`), plain CSS |
| Hosting (planned) | Render (API) and Vercel (web), configured in `render.yaml` |

## Repository layout

```
backend/
  app/          API, agents, prompts, graph, RAG, LLM client
  knowledge/    each demo product's knowledge files (per team + shared)
  data/         mayl.db (search index) and sample data
  eval/         SPEC, frozen cases, eval-only retail product, numbered reports
  scripts/      build_index.py (rebuild the search index), run_eval.py (evaluation)
  tests/        44 automated tests
frontend/       React app
docs/           design, this file, TESTING.md
```

## Run it locally

```bash
# API: put ANTHROPIC_API_KEY in backend/.env for live agents (optional)
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000

# Web, in a new terminal
cd frontend && npm install && npm run dev
```

Tests: `cd backend && pytest`. After editing anything in `backend/knowledge/`, rebuild
the search index with `python scripts/build_index.py`.

## What's next

- Better Lead Agent judgement on brand-new projects, measured on new practice cases.
- Build the engine side of the project graph from a real code repository.
- Deploy publicly with a QR code for the demo.
