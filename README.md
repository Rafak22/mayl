<div align="center">

# Mayl

### See the ripple before you make the change.

**An agentic platform for AI product teams.** Every proposed change is checked by every team's
AI agent in seconds, so humans make one informed decision instead of discovering the damage later.

![Claude Sonnet 5.5](https://img.shields.io/badge/agents-Claude%20Sonnet%205.5-d97757)
![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-1c3c3c)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)
![React](https://img.shields.io/badge/frontend-React%2019-61dafb)
![Tests](https://img.shields.io/badge/tests-44%20passing-2ea44f)

</div>

---

## The problem

Building an AI product takes several teams: data scientists, AI engineers and domain experts,
led by an AI lead. When one of them changes something, such as relabeling data, swapping the
model or adding a rule, the effects ripple into everyone else's work. Usually nobody sees the
full picture until something breaks: a client deadline slips, a domain rule gets violated, or a
cheaper fix was missed.

## What Mayl does

Anyone proposes a change in plain language. Each affected team's agent checks it **in parallel**:

| Question | What the agent answers |
|---|---|
| **What does it touch?** | Which of my team's components are affected |
| **How long will it take?** | An effort range, anchored to similar past changes |
| **What does it break?** | Domain rules and client promises on record |
| **Is there a better way?** | A cheaper or safer alternative, backed by the team's knowledge |

The **Lead Agent** then reads every assessment, checks the total effort against promised
deadlines and recommends one option: **approve**, **use the alternative**, **reject** or
**ask for more detail**.

> **Humans decide. Agents do the legwork.**

## Meet the agents

| Agent | Represents | Knows about |
|---|---|---|
| 🧭 **Lead Agent** | The AI lead | The Objective Spec (goal, priorities in order, deadline), every team's assessment, rules and promises. Turns client documents into the Objective Spec. |
| 📊 **DS Agent** | Data science | Data, annotations, models, experiments, evaluation |
| ⚙️ **Engineer Agent** | AI engineering | The engine, APIs, apps, hardware, the engine contract (latency, limits), change history with actual effort |
| 🛡️ **Domain Agent** | The domain expert (an "expert twin") | Domain rules, safety, client promises. Answers domain questions with sources, and **hands the question to a human** when the documents don't cover it. |

Each agent sees only its own team's knowledge plus the shared project memory, and the tests
confirm that nothing leaks between teams.

## The demo

Three projects, each in a different state:

| Project | State | What it shows |
|---|---|---|
| 💬 Arabic customer-service chatbot | 🟢 Healthy | The calm view: everything green, ask the agents anything |
| ⛑️ Helmet compliance detection | 🟠 Bottleneck | A domain rule (a carried helmet doesn't count) → impact on every team → conflict with a client deadline → a 1-day alternative instead of a retrain → one decision |
| 🏥 Smart clinic receptionist | 🔵 New | Client documents → Objective Spec with open questions → agents design the system → handoff |

| Screen | What you do there |
|---|---|
| **Overview** | Projects at a glance, decisions waiting for you, recent activity |
| **Projects** | Each project's map (components owned by each team), data and solution, knowledge files and results against goals. Tap any component to propose a change. |
| **Agents** | Who the agents are, what they know and what they have done |
| **Chat** | Ask any agent or the project memory, in Arabic or English |

Switch roles at the top (AI Lead, Data Scientist, AI Engineer, Domain Expert) to see the same
project through each team's eyes, including that role's inbox. Every visitor gets an isolated
session, **Reset demo** starts over, and the layout works on a phone.

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

**Design choices:**

- **Structured answers.** Every agent ends with a strict, schema-checked answer (effort range,
  verdict, conflicts, evidence, alternative), so the output is always usable.
- **Risk is computed in code, not by the LLM**, from conflicts, blocked verdicts and total
  effort. It is predictable and explainable.
- **Deadlines are the Lead Agent's job.** Only the Lead Agent sees the total effort across all
  teams, so only it judges whether a promised date is at risk.
- **Never breaks on stage.** Without an API key, or if a call fails, deterministic demo agents
  answer instead. Each session gets 8 live reviews and 20 live chat messages, to cap cost.

### Knowledge search (RAG)

All knowledge lives in one committed SQLite file, with no external database:

- **Keyword search:** SQLite FTS5 with BM25 ranking.
- **Meaning search:** sqlite-vec with `multilingual-e5-small` embeddings, which match Arabic
  and English by meaning. It runs on CPU through ONNX, with no PyTorch.
- **Fusion:** the two rankings are merged with Reciprocal Rank Fusion.
- **Cross-language:** a non-English chat question is also searched with an English
  translation. The agent decides whether the passages actually answer it, and if they don't,
  it escalates to a human instead of guessing.
- **Live project memory** (activity, decisions, rules) is searched the same way and stays in
  memory.

## Results

Measured on a frozen 100-case evaluation, on held-out cases the agents were never tuned on:

| | Result |
|---|---|
| Change review, full card right (familiar projects) | **0.83** |
| Change review, full card right (a project never seen during development) | 0.43 |
| Change review, overall | 0.68 (target 0.80) |
| Never answers what it should hand to a human | **100%** |
| Prompt-injection cases resisted | **2 / 2** |
| Right document in the top 4 search results | **0.95** |
| Knowledge leaks between teams | **0** |
| Cost per change review (4 agents) | **about $0.06** |

Full method, iteration history and an honest look at what fails:
**[docs/TESTING.md](docs/TESTING.md)**.

## Tech stack

| Layer | Tools |
|---|---|
| Agents | Claude Sonnet 5.5 (Anthropic SDK), LangGraph |
| Backend | Python, FastAPI, NetworkX |
| Search | SQLite FTS5 + sqlite-vec, multilingual-e5-small (ONNX + sentencepiece) |
| Frontend | React 19, Vite, React Router, React Flow (`@xyflow/react`), plain CSS |
| Hosting (planned) | Render (API) and Vercel (web), configured in `render.yaml` |

## Run it locally

```bash
# API: put ANTHROPIC_API_KEY in backend/.env for live agents (optional)
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000

# Web, in a new terminal
cd frontend && npm install && npm run dev
```

Then open http://localhost:5173. Without a key, the demo agents answer.

| Task | Command |
|---|---|
| Run the tests | `cd backend && pytest` |
| Rebuild the search index (after editing `backend/knowledge/`) | `cd backend && python scripts/build_index.py` |
| Run the evaluation | `cd backend && python scripts/run_eval.py --split dev --mode live --repeats 1 --max-usd 1.5` |

The search index `backend/data/mayl.db` is committed, and a test fails if it no longer matches
the knowledge files. The embedding model (~118 MB) downloads on first use.

## Repository layout

```
backend/
  app/          API, agents, prompts, project graph, RAG, LLM client
  knowledge/    each demo project's knowledge (per team + shared)
  data/         mayl.db (search index) and sample data
  eval/         spec, frozen cases, eval-only product, numbered reports
  scripts/      build_index.py, run_eval.py
  tests/        44 automated tests
frontend/       React app
docs/           TESTING.md, design
render.yaml     backend hosting config
```

## Deploy (not done yet)

1. **Backend on Render:** New → Blueprint → pick this repo (it reads `render.yaml`).
   Add `ANTHROPIC_API_KEY` as an environment variable.
2. **Frontend on Vercel:** root directory `frontend`, environment variable `VITE_API_URL` =
   the Render URL.
3. Turn the Vercel URL into a QR code for the slides.

Render's free plan sleeps after about 15 minutes idle and takes 30–60 s to wake, so open the
link a minute before presenting.

## What's next

- Better Lead Agent judgement on brand-new projects, measured on new practice cases.
- Build the engine side of the project graph from a real code repository.
- Public deployment with a QR code for the demo.
