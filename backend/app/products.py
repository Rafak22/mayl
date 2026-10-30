"""Seed data for the three demo products.

Healthy: Arabic customer-service chatbot (NLP / RAG).
Bottleneck: helmet compliance detection on construction sites (computer vision).
New: agentic patient triage and booking (healthcare, built from scratch).

Each product is a Project Graph: nodes (objective, requirement, dataset, pipeline steps, engine
components) linked by edges.

Edge kinds:
  feeds      - upstream output flows into downstream node (A -> B)
  constrains - an engine/infra decision limits a pipeline node (A -> B)

Each node may carry `change_options`: pre-defined, realistic changes used in
demo mode so the agents' answers are deterministic and safe on stage.
"""

ROLES = {
    "lead": "AI Lead",
    "ds": "Data Scientist",
    "engineer": "AI Engineer",
    "domain": "Domain Expert",
}


def _goal(label, goal, better, unit):
    """Target for one metric: better = "higher" | "lower"; unit = "%" (value is a 0-1 ratio), "s" or ""."""
    return {"label": label, "goal": goal, "better": better, "unit": unit}


def _n(id, label, kind, owner, effort, desc, x, y, options=None, status="ok", short=None):
    return {
        "id": id,
        "label": label,
        "short": short or label,  # one-word step name for compact pipeline views
        "kind": kind,  # objective | requirement | dataset | pipeline | engine
        "owner": owner,  # lead | ds | engineer | domain
        "effort_days": effort,  # typical rework effort if this node must change
        "description": desc,
        "status": status,  # ok | pending | changed | empty
        "position": {"x": x, "y": y},
        "change_options": options or [],
    }


def _opt(id, label, severity, metric, rationale, conflicts=None, alternative=None):
    return {
        "id": id,
        "label": label,
        "severity": severity,  # 0.3 low, 1.0 normal, 1.6 heavy
        "metric_delta": metric,  # e.g. {"recall": -2, "false_alarms": -35}
        "rationale": rationale,
        "conflicts": conflicts or [],  # ids of domain rules / client promises
        "alternative": alternative,  # cheaper option {label, effort_days, metric_delta}
    }


def build_products():
    return {
        # ------------------------------------------------------------------
        # HEALTHY: NLP / RAG chatbot. Calm control room, nothing pending.
        # ------------------------------------------------------------------
        "chatbot": {
            "id": "chatbot",
            "name": "Arabic Customer-Service Chatbot",
            "domain": "Telecom · NLP",
            "client": "Sahm Telecom",
            "tech": "NLP · RAG",
            "expert": "the customer-service lead",  # the human the Domain Agent speaks for
            "state": "healthy",
            "summary": "Live. Answers Sahm Telecom customers in Arabic and English and hands over to humans when needed. All metrics on target.",
            "objective": {
                "goal": "Resolve routine customer questions without waiting for an agent",
                "success_metric": "Accuracy >= 90%, containment >= 60%",
                "priorities": ["accuracy", "handover speed", "containment"],
                "constraints": ["Handover < 30 s", "Never promise refunds"],
                "deadline": "Live since Aug 2026",
            },
            "metrics": {"accuracy": 0.912, "containment": 0.64, "handover_s": 22},
            "metric_goals": {  # from the project brief's agreed success metrics
                "accuracy": _goal("Answer accuracy", 0.90, "higher", "%"),
                "containment": _goal("Resolved without a human", 0.60, "higher", "%"),
                "handover_s": _goal("Handover time", 30, "lower", "s"),
            },
            "rules": [
                {"id": "r-dispute", "text": "Billing disputes always go to a human agent", "source": "Customer-service lead, Jul 2026"},
                {"id": "r-refund", "text": "The bot must never promise refunds", "source": "Service guidelines"},
            ],
            "nodes": [
                _n("obj", "Objective: self-service answers", "objective", "lead", 0, "Accuracy >= 90%, containment >= 60%", 0, 0),
                _n("req-handover", "Rule: hand over disputes", "requirement", "domain", 1, "Disputes, cancellations, formal complaints → human", 0, 150),
                _n("kb", "Knowledge base (312 docs)", "dataset", "ds", 1, "Packages, roaming, billing policies · AR + EN", 280, 0,
                   options=[_opt("synonyms", "Add Arabic/English package-name synonyms", 0.3, {"accuracy": 1},
                                 "Fixes retrieval misses like 'باقة سوا' vs 'Sawa Plus'")], short="Docs"),
                _n("retriever", "Hybrid retriever", "pipeline", "ds", 2, "Keyword + vector search over 2,400 chunks", 560, 0, short="Search"),
                _n("eval", "Eval set (600 questions)", "pipeline", "ds", 1, "70% Arabic, 120 Gulf-dialect questions · accuracy 91.2%", 560, 150, short="Eval"),
                _n("llm", "Answer + guardrails", "engine", "engineer", 2, "LLM answer, price check, sensitive-topic detector", 840, 0, short="Answer"),
                _n("handover", "Human handover", "engine", "engineer", 1, "POST /handover to contact centre · median 22 s", 840, 150, short="Handover"),
                _n("channels", "App + WhatsApp", "engine", "engineer", 2, "Channel adapters · p95 first token 1.4 s", 1120, 0, short="Channels"),
            ],
            "edges": [
                ("obj", "kb", "feeds"), ("kb", "retriever", "feeds"), ("retriever", "llm", "feeds"),
                ("eval", "llm", "feeds"), ("req-handover", "handover", "feeds"),
                ("llm", "handover", "feeds"), ("llm", "channels", "feeds"), ("handover", "channels", "feeds"),
            ],
        },
        # ------------------------------------------------------------------
        # BOTTLENECK: computer vision. A safety rule ripples through the
        # annotations, the model and the alert engine.
        # ------------------------------------------------------------------
        "ppe": {
            "id": "ppe",
            "name": "Helmet Compliance Detection",
            "domain": "Construction · Computer Vision",
            "client": "Binaa Contracting",
            "tech": "Computer vision",
            "expert": "the site safety officer",
            "state": "bottleneck",
            "summary": "Mid-project. The safety officer says a helmet carried in the hand doesn't count. The rule ripples through annotations, model and alert engine.",
            "objective": {
                "goal": "Alert the safety officer when a worker on site has no helmet",
                "success_metric": "Violation recall >= 95%, < 10 false alerts per camera per day",
                "priorities": ["violation recall", "false alerts", "speed"],
                "constraints": ["Alert < 60 s", "CPU-only edge boxes"],
                "deadline": "Pilot on 2 sites in 3 weeks",
            },
            "metrics": {"violation_recall": 0.88, "false_alerts_per_cam_day": 6, "latency_s": 8},
            "metric_goals": {  # from the project brief's agreed success metrics
                "violation_recall": _goal("Violation recall", 0.95, "higher", "%"),
                "false_alerts_per_cam_day": _goal("False alerts / camera / day", 10, "lower", ""),
                "latency_s": _goal("Alert speed", 60, "lower", "s"),
            },
            "rules": [
                {"id": "p-pilot", "text": "Client promise: pilot on 2 sites in 3 weeks", "source": "Kickoff meeting, Sep 2026"},
                {"id": "r-worn", "text": "A helmet counts only when worn on the head", "source": "HSE safety officer, site visit Oct 2026"},
                {"id": "r-fatigue", "text": "Keep false alerts under ~10 per camera per day", "source": "Site safety rules"},
                {"id": "e-cpu", "text": "Edge boxes are CPU-only; models larger than YOLOv8n miss latency", "source": "Engine contract"},
            ],
            "nodes": [
                _n("obj", "Objective: catch missing helmets", "objective", "lead", 0, "Violation recall >= 95%", 0, 0),
                _n("req-pilot", "Promise: pilot in 3 weeks", "requirement", "lead", 1, "2 sites, agreed at kickoff", 0, 150),
                _n("rule-worn", "Rule: helmet must be worn", "requirement", "domain", 1,
                   "Safety officer: a helmet in the hand, on a belt or on the ground is a violation", 0, 300,
                   status="pending",
                   options=[_opt("relabel-retrain", "Relabel carried helmets as a new class and retrain", 1.0,
                                 {"violation_recall": 7, "false_alerts": 10},
                                 "Safety officer: only a worn helmet counts (9% of helmet boxes are carried helmets)",
                                 conflicts=["p-pilot"],
                                 alternative={"label": "Post-processing rule: a helmet only counts if it overlaps the top of the head box. No relabeling, no retraining.",
                                              "effort_days": 1, "metric_delta": {"violation_recall": 6, "false_alerts": 0}})]),
                _n("data", "Images (~8,200)", "dataset", "ds", 1, "Public-domain Hard Hat Workers + 1,200 client site images", 290, 0, short="Images"),
                _n("annot", "Annotation guide v1", "pipeline", "ds", 3, "Classes: helmet, head, person · YOLO format", 580, 0, short="Labels"),
                _n("model", "YOLOv8n model v3", "pipeline", "ds", 2, "mAP50 0.89 · head recall 96%", 870, 0,
                   options=[_opt("to-v8s", "Upgrade to YOLOv8s for better accuracy", 1.6, {"violation_recall": 2, "latency_s": 11},
                                 "mAP50 0.91 in Exp 4", conflicts=["e-cpu"],
                                 alternative={"label": "Keep YOLOv8n, add 1,000 tiled small-head crops to training",
                                              "effort_days": 2, "metric_delta": {"violation_recall": 1}})], short="Model"),
                _n("eval", "Evaluation set", "pipeline", "ds", 1, "400 reviewed site images", 870, 150, short="Eval"),
                _n("logic", "Compliance logic", "engine", "engineer", 2, "Compliant if a helmet box is inside the person box", 1160, 0, short="Alerts"),
                _n("edge", "Edge boxes (CPU)", "engine", "engineer", 1, "40 cameras · 8 s end to end", 1160, 160, short="Edge"),
                _n("app", "Safety officer app", "engine", "engineer", 1, "Alert with image crop and reason", 1450, 0, short="App"),
            ],
            "edges": [
                ("obj", "data", "feeds"), ("req-pilot", "logic", "feeds"), ("rule-worn", "annot", "feeds"),
                ("data", "annot", "feeds"), ("annot", "model", "feeds"), ("model", "eval", "feeds"),
                ("model", "logic", "feeds"), ("eval", "logic", "feeds"), ("logic", "app", "feeds"),
                ("edge", "model", "constrains"), ("edge", "logic", "constrains"),
            ],
            "seed_proposal": {"node": "rule-worn", "option": "relabel-retrain", "proposer": "domain"},
            "resolved": {"summary": "Bottleneck resolved in one decision: the agents found a rule-only fix that keeps the pilot date.",
                         "metrics": {"violation_recall": 0.94}},
            "samples": "ppe",
        },
        # ------------------------------------------------------------------
        # NEW: agentic system built from scratch via objective intake.
        # ------------------------------------------------------------------
        "triage": {
            "id": "triage",
            "name": "Smart Clinic Receptionist",
            "domain": "Healthcare · Agentic AI",
            "client": "Shifa Clinics",
            "tech": "Agentic AI",
            "expert": "the head nurse",
            "state": "new",
            "summary": "New client. Shifa Clinics uploaded their documents; the agents haven't built anything yet.",
            "objective": None,
            "metrics": {},
            "metric_goals": {},  # set when the agents build the project (agents.build_from_objective)
            "rules": [],
            "documents": [
                {"name": "Client brief.pdf", "text": "Shifa Clinics runs 8 family clinics. Patients send about 3,000 WhatsApp messages a week asking for appointments or describing symptoms, and wait hours for a reply. We want an AI agent that reads patient messages, understands how urgent they are, books the right appointment by itself, and immediately alerts a nurse for anything serious. Replies within 2 minutes, day and night. Never miss an emergency: a patient with chest pain must never be offered an appointment next week."},
                {"name": "Kickoff transcript.txt", "text": "Operations manager: replies within 2 minutes; the agent should book directly in our calendar. Pilot in 4 weeks in 2 clinics. Head nurse: we still need to agree which symptoms are always emergencies; I don't want the agent deciding that alone. Anything with children under 2 should come to a nurse. IT manager: patient data must stay inside the country; the calendar API allows booking and cancelling, not deleting."},
                {"name": "Scope email.eml", "text": "Pilot: 2 clinics (Riyadh Olaya, Jeddah Rawdah), 4 weeks. Languages: Arabic and English."},
            ],
            "nodes": [],
            "edges": [],
        },
    }
