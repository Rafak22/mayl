# Mayl: agentic platform for AI product teams

When anyone on an AI product team proposes a change, each affected team's agent (DS,
Engineer, Domain) checks it in parallel: what it touches, how long it takes, which rules or
client promises it breaks, and whether a cheaper alternative exists. The **Lead Agent**
then weighs the total effort against deadlines and priorities and recommends one option.
**Humans decide; agents do the legwork.**

- **[docs/PROJECT.md](docs/PROJECT.md):** the full project (agents, demo projects, app, architecture, stack)
- **[docs/TESTING.md](docs/TESTING.md):** how we test it and the results

## At a glance

| | |
|---|---|
| Agents | Lead, DS, Engineer and Domain Agents on Claude Sonnet 5.5, orchestrated with LangGraph |
| Knowledge | Hybrid search on SQLite: FTS5 keywords + sqlite-vec multilingual embeddings, Arabic and English |
| Demo projects | Arabic customer-service chatbot (healthy), helmet compliance detection (bottleneck), smart clinic receptionist (new) |
| Held-out eval | Change-review pass rate 0.68 (0.83 on familiar projects), 100% correct escalation, 2/2 injection cases resisted, retrieval Recall@4 0.95, about $0.06 per review |
| Tests | 44 automated tests (`cd backend && pytest`) |

## Run locally

```bash
# API: put ANTHROPIC_API_KEY in backend/.env for live agents (optional)
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000

# Web, in a new terminal
cd frontend && npm install && npm run dev
```

Without an API key, or if a call fails, deterministic demo agents answer, so the demo never
breaks. Each session gets 8 live reviews and 20 live chat messages.

### After editing knowledge files

The search index `backend/data/mayl.db` is committed, so the server never rebuilds it. After
editing anything in `backend/knowledge/`, rebuild and commit it:

```bash
cd backend && python scripts/build_index.py
```

A test fails if the committed index no longer matches the knowledge files. The embedding model
(~118 MB) downloads on first use to `backend/.cache/models`.

### Evaluation

```bash
cd backend && python scripts/run_eval.py --split dev --mode live --repeats 1 --max-usd 1.5
```

See [docs/TESTING.md](docs/TESTING.md) for the dev and held-out rules. Never tune on held-out.

## Structure

```
backend/   FastAPI, project graph, agents, RAG, eval, tests
frontend/  React 19 + Vite + React Flow
docs/      PROJECT.md, TESTING.md, design
render.yaml  backend hosting config
```

## Deploy (not done yet)

1. **Backend on Render:** New → Blueprint → pick this repo (it reads `render.yaml`).
   Add `ANTHROPIC_API_KEY` as an environment variable.
2. **Frontend on Vercel:** root directory `frontend`, environment variable `VITE_API_URL` =
   the Render URL.
3. Turn the Vercel URL into a QR code for the slides.

Render's free plan sleeps after about 15 minutes idle and takes 30–60 s to wake, so open the
link a minute before presenting.
