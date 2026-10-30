# Relay — agentic handoffs for AI product teams

Team agents (Data Scientist, AI Engineer, Domain Expert) work over a shared **Project Graph**.
Any change is assessed by every team's agent before anyone commits: what breaks, how long it
takes, conflicts with domain rules or client promises, and a cheaper alternative.
**Humans decide; agents do everything else.**

## What's in the demo

| Product | State | Shows |
|---|---|---|
| Arabic Customer-Service Chatbot | Healthy | The calm control room: green graph, project chat |
| Helmet Compliance Detection | Bottleneck | Expert rule (a carried helmet doesn't count) → impact analysis → conflict → cheaper alternative → 1 decision |
| Smart Clinic Receptionist | New | Objective intake from documents → agents design main + backup triage agents → handoff |

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
structured `submit` (effort range, verdict, conflicts, evidence, alternative).

### RAG: hybrid search on SQLite

Knowledge files are split into chunks at `## ` headings and indexed into one SQLite file,
`backend/data/mayl.db`:

- **Keyword search:** an FTS5 table ranked by BM25.
- **Vector search:** a sqlite-vec table with
  [`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small) embeddings
  (int8 ONNX on CPU via onnxruntime, with the model's own sentencepiece tokenizer; no PyTorch).
  It matches Arabic and English by meaning, e.g.
  "helmet hanging from a worker's belt" finds the *Helmet rule*, and "شكوى رسمية" finds the
  chatbot's human-handover guideline.

Each query runs both searches, filtered to the product and the agent's scopes. The two rankings are
merged with Reciprocal Rank Fusion. Vector matches below 0.80 cosine are dropped, so off-topic
questions return nothing, and the Expert Twin escalates them instead of guessing.

Live project memory (activity, rules, graph nodes) changes at runtime, so it stays in memory. It is
searched the same two ways at query time and is never written to the db.

The db is committed, so the server never rebuilds it. **After editing anything in `knowledge/`,
rebuild and commit it:**

```bash
cd backend && python scripts/build_index.py
```

A test fails if the committed index no longer matches the knowledge files. The embedding model
(~118 MB) downloads on first use to `backend/.cache/models`; on Render it is fetched at build time.

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
- Code analysis (Python `ast`) to build the engine side of the graph from a real repo
- Real use cases replacing the placeholder products
