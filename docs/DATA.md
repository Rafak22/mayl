# Mayl: data

What data Mayl uses, where each piece comes from, where it is stored and how it moves
through the system. For the evaluation method and results, see [TESTING.md](TESTING.md).

## In short

| Question | Answer |
|---|---|
| Is any of it real client data? | **No.** All clients, projects, documents, messages and numbers are synthetic, written for this demo. |
| Is any of it real at all? | Three helmet photos from a public MIT-licensed dataset, credited below. |
| Is there personal data? | **No.** No real people, patients or customers. Names of companies (Sahm Telecom, Binaa Contracting, Shifa Clinics, Tamr Markets) are invented. |
| Where is it stored? | Markdown and CSV files in the repo, one SQLite search index (`backend/data/mayl.db`), and each visitor's session in server memory. |
| Is there a user database? | **No.** No accounts, no logins, nothing a visitor does is written to disk. |
| What leaves the machine? | Only in live mode: the prompts sent to the Claude API. In demo mode nothing is sent anywhere. |

## Map of the data

```
backend/
  knowledge/<product>/<scope>/*.md   knowledge base the agents search    synthetic
  data/
    mayl.db                          search index built from knowledge/  generated
    samples/
      chatbot_eval_sample.csv        sample rows for the Data tab        synthetic
      triage_messages.csv            sample rows for the Data tab        synthetic
      ppe/images/*.jpg               3 helmet photos                     public, MIT
  app/products.py                    project graphs, rules, promises     synthetic
  app/details.py                     figures for the Data & solution tab synthetic
  eval/
    cases/*.json                     100 test cases with gold answers    synthetic
    products/retail.json             eval-only fourth product            synthetic
    knowledge/retail/                its knowledge base                  synthetic
    results/*.json                   raw output of every eval run        generated
    reports/*.md                     one report per run                  generated
```

There are four kinds of data:

| Kind | What it is | Who uses it |
|---|---|---|
| **1. Knowledge base** | The project documents each team agent searches | Agents, through RAG |
| **2. Project seed data** | Each project's graph, rules, client promises and starting state | The platform and the agents |
| **3. Display samples** | Images, CSV rows and figures shown in the app | The Data & solution and Knowledge tabs |
| **4. Evaluation data** | Test cases, an unseen product, results and reports | `scripts/run_eval.py` only |

## 1. Knowledge base

Every project has the same four folders. The folder decides which agent can read the file:

| Folder (scope) | Contents | Searched by |
|---|---|---|
| `shared/` | Briefs, meeting notes, decision logs | All agents |
| `ds/` | Dataset cards, experiment logs, sample data notes | DS Agent, Lead Agent |
| `engineer/` | Engine and integration contracts, change history with actual effort | Engineer Agent, Lead Agent |
| `domain/` | Domain rules and guidelines | Domain Agent, Lead Agent |

All files were written by Claude for this demo, in English. Arabic questions are matched to
them by meaning (see section 5). A file is split into one search chunk per `## ` section.

### Arabic Customer-Service Chatbot (`chatbot`), Sahm Telecom

| File | Contents | Words |
|---|---|---|
| `shared/project-brief.md` | Client, goal, scope, success metrics | 123 |
| `shared/decisions-log.md` | Decisions such as RAG instead of fine-tuning | 105 |
| `ds/knowledge-base-and-eval.md` | What the bot's knowledge base holds, the 600-question eval set | 130 |
| `ds/sample-chats.md` | Sample questions and bot answers | 111 |
| `engineer/system-contract.md` | Architecture, latency, limits | 102 |
| `domain/service-guidelines.md` | Tone, must-hand-over list, no refund promises | 99 |
| **Total** | 6 files, **21 search chunks** | 670 |

### Helmet Compliance Detection (`ppe`), Binaa Contracting

| File | Contents | Words |
|---|---|---|
| `shared/project-brief.md` | Client, goal, pilot promise | 120 |
| `shared/meeting-notes.md` | Kickoff and site-visit notes | 121 |
| `ds/dataset-card.md` | Data sources, classes, label statistics, YOLO format | 118 |
| `ds/experiment-log.md` | Model experiments and why YOLOv8n | 116 |
| `engineer/engine-contract.md` | Alert pipeline, CPU-only edge boxes, latency | 120 |
| `engineer/change-history.md` | Past changes with actual effort in days | 78 |
| `domain/site-safety-rules.md` | Helmet must be worn, false-alert limit | 127 |
| **Total** | 7 files, **26 search chunks** | 800 |

### Smart Clinic Receptionist (`triage`), Shifa Clinics

| File | Contents | Words |
|---|---|---|
| `shared/client-brief.md` | Clinics, message volume, goals | 119 |
| `shared/kickoff-transcript.md` | What each stakeholder asked for | 96 |
| `ds/message-data-notes.md` | Patient message data, languages, outcome tags | 101 |
| `ds/sample-messages.md` | Example messages with expected outcomes | 174 |
| `engineer/integration-contract.md` | Calendar API (book and cancel only), data residency | 90 |
| `domain/triage-guidelines.md` | Emergency list, under-2 rule, routine cases. Marked "not medical advice". | 101 |
| **Total** | 6 files, **22 search chunks** | 681 |

The figures inside these documents (for example "about 7,000 public images", "1,200 client
site images" or "12,000 past WhatsApp messages") describe the **fictional** project. Those
datasets do not exist in this repository and were never used to train anything. They are part
of the story the agents reason about.

## 2. Project seed data

Defined in code in [`backend/app/products.py`](../backend/app/products.py) and loaded fresh
into every new session.

| Item | What it is |
|---|---|
| **Project graph** | Nodes (objective, requirements, datasets, pipeline steps, engine parts), each with an owning team and a typical rework effort in days, linked by `feeds` and `constrains` edges. Used with NetworkX to find which teams a change affects. |
| **Objective** | Goal, success metric, priorities in order, deadline |
| **Metrics and goals** | The numbers on each project card, for example violation recall 88% against a goal of 95% |
| **Rules and promises** | Records with an id, text and source (see below). Agents cite these ids as conflicts. |
| **Change options** | Pre-written changes with fixed answers, used by the demo agents so the demo is deterministic |
| **Seeded bottleneck** | The open "relabel carried helmets" proposal on the helmet project |
| **Intake documents** | Three short client documents for the clinic project (`Client brief.pdf`, `Kickoff transcript.txt`, `Scope email.eml`), stored as text in the code |

### Rules and promises on record

| Project | Id | Rule or promise | Recorded source |
|---|---|---|---|
| chatbot | `r-dispute` | Billing disputes always go to a human agent | Customer-service lead |
| chatbot | `r-refund` | The bot must never promise refunds | Service guidelines |
| ppe | `p-pilot` | Client promise: pilot on 2 sites in 3 weeks | Kickoff meeting |
| ppe | `r-worn` | A helmet counts only when worn on the head | HSE safety officer |
| ppe | `r-fatigue` | Keep false alerts under about 10 per camera per day | Site safety rules |
| ppe | `e-cpu` | Edge boxes are CPU-only; nothing larger than YOLOv8n | Engine contract |
| triage | `r-emergency` | Symptoms that are always an emergency | Head nurse, added by intake |
| triage | `r-child` | Any child under 2 goes to a nurse | Head nurse, added by intake |
| triage | `e-nodelete` | Calendar API: book and cancel only, never delete | IT manager, added by intake |

The triage rules start empty and are created when the Lead Agent reads the intake documents.

## 3. Display samples

What the Data & solution and Knowledge tabs show.

| File | Rows or size | Columns | Origin |
|---|---|---|---|
| `data/samples/chatbot_eval_sample.csv` | 10 questions | `question_id, language, question, topic, result` | Synthetic, Arabic and English |
| `data/samples/triage_messages.csv` | 20 messages | `message_id, channel, language, text, expected_outcome` | Synthetic. 4 each: emergency, nurse callback, same-day, routine, admin |
| `data/samples/ppe/images/site-compliant.jpg` | 72 KB | | Public dataset, MIT |
| `data/samples/ppe/images/site-carried.jpg` | 86 KB | | Public dataset, MIT |
| `data/samples/ppe/images/site-violation.jpg` | 65 KB | | Public dataset, MIT |

The headline figures, small tables and charts on the Data & solution tab are written in
[`backend/app/details.py`](../backend/app/details.py). Each block names the knowledge file it
was taken from, so the page and the agents quote the same numbers. The list of documents and
their sections on the Knowledge tab is read straight from `backend/knowledge/`.

### The helmet images

| | |
|---|---|
| Source | [Safety Helmet Wearing Dataset](https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset) |
| License | MIT, Copyright (c) 2019 njvisionpower |
| Credit file | [`backend/data/samples/ppe/images/CREDITS.md`](../backend/data/samples/ppe/images/CREDITS.md) |
| Detection boxes | Drawn by that repository's own model, not by us. Mayl trains no vision model. |
| Use | Illustrate the three cases of the bottleneck story: compliant, carried helmet, violation |

## 4. Evaluation data

Written and run only by the evaluation. The app reads the saved results, never the cases
themselves: each project's **Results** tab shows how the agents scored on that project's cases
(through [`backend/app/eval_results.py`](../backend/app/eval_results.py), with no API calls).
Full method in [TESTING.md](TESTING.md).

| File | What it is |
|---|---|
| `eval/cases/change_review.json` | 30 proposed changes with gold conflicts, risk, recommendation, effort range, teams and a reason |
| `eval/cases/domain_qa.json` | 30 questions with the gold answer: key facts and source, or "escalate" |
| `eval/cases/retrieval.json` | 36 search queries with the chunks that should come back |
| `eval/cases/intake.json` | 4 sets of client documents with the constraints and gaps that should be found |
| `eval/products/retail.json` | Fresh-Food Demand Forecasting for Tamr Markets: graph, objective, rules (`p-cutoff`, `r-staple`, `r-ramadan`, `r-loyalty`, `e-window`) |
| `eval/knowledge/retail/` | Its knowledge base: 7 files, 28 chunks, same folder layout |
| `eval/results/*.json` | Raw output of each run: metadata (commit, model, cost) and, per case, every score, the agents' messages, latency, tokens and cost. Read by the Results tab. |
| `eval/reports/*.md`, `eval/eval_report.md` | Reports generated from the results |

### How the cases are split

| Kind | Dev: chatbot / ppe / triage | Held-out: chatbot / ppe / triage / retail | Total |
|---|---|---|---|
| Change review | 4 / 4 / 3 | 4 / 5 / 3 / 7 | 30 |
| Domain Agent Q&A | 4 / 4 / 3 | 4 / 4 / 5 / 6 | 30 |
| Retrieval | 5 / 5 / 5 | 5 / 5 / 5 / 6 | 36 |
| Objective intake | 0 / 0 / 1 | 0 / 0 / 2 / 1 | 4 |
| **Total** | **38** | **62** | **100** |

Rules that protect this data:

- The cases were committed in `eb6fd0c` **before** any tuning and have not been edited since.
- The retail product appears only in held-out cases and is never loaded by the app.
  The eval registers its knowledge folder in memory, so it is not in `mayl.db`.
- Knowledge files were never changed to make a case pass.

## 5. Storage and processing

### The search index: `backend/data/mayl.db`

One SQLite file (about 400 KB), committed to the repo. The server opens it read-only.

| Table | Type | Holds |
|---|---|---|
| `chunks_fts` | FTS5 virtual table | Chunk text, id, product, scope, source; keyword search with BM25 ranking |
| `chunks_vec` | sqlite-vec `vec0` table | One 384-number vector per chunk (cosine distance), partitioned by product |
| `meta` | Table | Embedding model name, model file, vector size, and a fingerprint of all knowledge files |

| Product | shared | ds | engineer | domain | Total chunks |
|---|---|---|---|---|---|
| chatbot | 6 | 7 | 4 | 4 | 21 |
| ppe | 6 | 8 | 8 | 4 | 26 |
| triage | 6 | 8 | 4 | 4 | 22 |
| **All** | | | | | **69** |

How it is built and kept honest:

```
backend/knowledge/**/*.md
   │  split into one chunk per "## " section
   ▼
scripts/build_index.py ──► embed each chunk ("passage: " prefix) ──► mayl.db
                                                                       │
tests/test_rag.py ── recomputes the fingerprint ── fails if mayl.db is out of date
```

### The embedding model

| | |
|---|---|
| Model | `intfloat/multilingual-e5-small` (MIT license), int8 ONNX export |
| Download | About 118 MB from Hugging Face on first use, cached in `backend/.cache/` (gitignored) |
| Runs on | CPU, through onnxruntime and sentencepiece. No GPU or PyTorch needed. |
| Why | Matches Arabic and English text by meaning, so an Arabic question finds an English passage |

### How a search runs

| Step | What happens |
|---|---|
| 1 | The agent's scope decides which folders it may search (see section 1) |
| 2 | Keyword search (BM25) and meaning search (vectors) each return up to 20 candidates |
| 3 | The two rankings are merged with Reciprocal Rank Fusion; the top 4 are returned with their source |
| 4 | For a non-English chat question, the same search also runs on an English translation |
| 5 | The agent decides whether the passages answer the question; if not, it escalates to a human |

### Live project memory

Things that change while the demo runs (activity, decisions, rules, graph nodes) are not in
`mayl.db`. They are turned into chunks in memory and searched the same two ways, under the
scope `live`. Past chat questions and answers are left out, so old questions are not echoed
back as evidence.

### Sessions: what happens to what a visitor does

| | |
|---|---|
| Where | Server memory only ([`backend/app/main.py`](../backend/app/main.py)). Nothing is written to disk. |
| Isolation | Each browser gets a random session id, kept in its local storage and sent as the `X-Session` header, and its own copy of the projects |
| Holds | Proposals, decisions, the activity log (including chat answers and escalations), live-call counters |
| Limits | 8 live reviews and 20 live chat messages per session; at most 300 sessions, oldest dropped first |
| Ends | **Reset demo** replaces the session with fresh seed data; a server restart clears all sessions |

## 6. What is sent outside the machine

| Destination | When | What is sent |
|---|---|---|
| **Anthropic Claude API** | Live mode only (an API key is set and the session has live calls left) | The agents' prompts: the proposal or question typed by the visitor, project details, rules, and the knowledge passages the agent retrieved. During an eval, also the test cases and, for the judge, the answer to be graded. |
| **Hugging Face** | Once, to download the embedding model | A download request only. No project data. |
| Nowhere | Demo mode (no key, `AGENT_MODE=demo`, or the live limit is reached) | The rule-based demo agents answer locally |

The API key lives only in `backend/.env`, which is gitignored. It is never in the code,
the commits or the frontend.

## 7. Licenses and credits

| Item | Source | License |
|---|---|---|
| Knowledge files, CSV samples, projects, test cases, retail product | Written for this project | Part of this repository |
| Three helmet images and their boxes | [njvisionpower/Safety-Helmet-Wearing-Dataset](https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset) | MIT |
| Embedding model | [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) | MIT |

The triage content is invented for a demo. It is not medical advice and was not reviewed by
clinicians.

## 8. Changing the data

| You want to | Do this |
|---|---|
| Edit or add a knowledge file | Edit `backend/knowledge/<product>/<scope>/`, run `cd backend && python scripts/build_index.py`, commit the new `mayl.db`. The tests fail until you do. |
| Change a project, rule or promise | Edit `backend/app/products.py` |
| Change the Data & solution figures | Edit `backend/app/details.py` and keep them in line with the knowledge file it names |
| Add sample rows or images | Add them under `backend/data/samples/`; credit any outside image in `CREDITS.md` |
| Add test cases | Add them to `backend/eval/cases/` as **new** dev cases. Do not edit held-out cases. |
