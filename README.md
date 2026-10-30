# Relay — agentic handoffs for AI product teams

Team agents (Data Scientist, AI Engineer, Domain Expert) work over a shared **Project Graph**.
Any change is assessed by every team's agent before anyone commits: what breaks, how long it
takes, conflicts with domain rules or client promises, and a cheaper alternative.
**Humans decide; agents do everything else.**

## What's in the demo

| Product | State | Shows |
|---|---|---|
| Arabic Support Ticket Classifier | Healthy | The calm control room: green graph, project chat |
| Transaction Fraud Detection | Bottleneck | Expert rule → impact analysis → conflict → cheaper alternative → 1 decision |
| Heart Reading Anomaly Detection | New | Objective intake from documents → agents build best + backup pipelines → handoff |

Switch roles at the top (AI Lead, Data Scientist, AI Engineer, Domain Expert). Same layout,
different lens. Tap any node to propose a change and watch the other agents respond.
Every visitor gets their own isolated demo state; **Reset demo** starts over.

## Live agents (Claude + tools + RAG)

Set `ANTHROPIC_API_KEY` (locally or in Render) and the agents go live. Without a key, or if a
call fails, the deterministic demo agents answer, so the demo never breaks.

| Agent | Tools | Knowledge base (`backend/knowledge/<product>/`) |
|---|---|---|
| DS Agent | graph impact, RAG search, rules | `ds/` + `shared/` + live project memory |
| AI Engineer Agent | graph impact, RAG search, rules | `engineer/` (contracts, change history with actual effort) + `shared/` |
| Domain Expert Agent (Expert Twin) | graph impact, RAG search, rules | `domain/` (guidelines, compliance) + `shared/` |
| Lead Agent | RAG search | everything; reads client documents into the Objective Spec |

LangGraph dispatches only the affected teams' agents, in parallel. Every agent ends with a
structured `submit` (effort range, verdict, conflicts, evidence, alternative). RAG is BM25 over
section chunks (no model download, handles Arabic); the `Retriever` class can be swapped for
embeddings later.

## Structure

```
backend/   FastAPI + NetworkX Project Graph + team agents (demo mode, deterministic)
frontend/  React + React Flow
render.yaml  backend hosting config
```

## Run locally

```bash
# API
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000
# Web (new terminal)
cd frontend && npm install && npm run dev
```
Tests: `cd backend && pytest`

## Deploy (public link + QR code)

1. **Push to GitHub** (this whole folder as one repo).
2. **Backend on Render:** render.com → New → Blueprint → pick the repo. It reads `render.yaml`.
   Copy the URL it gives you, e.g. `https://relay-api.onrender.com`.
3. **Frontend on Vercel:** vercel.com → Add New Project → pick the repo →
   Root Directory: `frontend` → Environment Variable `VITE_API_URL` = the Render URL → Deploy.
4. **QR code:** turn the Vercel URL into a QR code (any free QR generator) for your slides.

Every `git push` redeploys both automatically.

**Before presenting:** Render's free plan sleeps after ~15 minutes idle and takes ~30–60 s to
wake. Open the link a minute before you go on stage.

## Roadmap (not built yet)
- Live agent mode (Claude API) for free-text changes and objective intake on any document
- ChromaDB RAG per agent (project memory, codebase, domain knowledge)
- Code analysis (Python `ast`) to build the engine side of the graph from a real repo
- Real use cases replacing the placeholder products
