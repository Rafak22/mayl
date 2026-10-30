"""Seed data for the three demo products.

Placeholder scenarios until the real use cases arrive. Each product is a
Project Graph: nodes (objective, requirement, dataset, pipeline steps, engine
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


def _n(id, label, kind, owner, effort, desc, x, y, options=None, status="ok"):
    return {
        "id": id,
        "label": label,
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
        "support": {
            "id": "support",
            "name": "Arabic Support Ticket Classifier",
            "domain": "Business",
            "state": "healthy",
            "summary": "Live. Routes customer tickets to the right team. Metrics on target.",
            "objective": {
                "goal": "Route Arabic support tickets to the right team automatically",
                "success_metric": "Macro F1 >= 0.85",
                "priorities": ["accuracy", "speed", "cost"],
                "constraints": ["< 1s per ticket", "data stays in-country"],
                "deadline": "Live since Sep 2026",
            },
            "metrics": {"macro_f1": 0.88, "latency_ms": 420},
            "rules": [
                {"id": "r-dialect", "text": "Gulf dialect tickets must be supported", "source": "Domain expert, Aug 2026"},
            ],
            "nodes": [
                _n("obj", "Objective: route tickets", "objective", "lead", 0, "Macro F1 >= 0.85, < 1s", 0, 0),
                _n("req-dialect", "Req: Gulf dialect support", "requirement", "domain", 1, "Dialect tickets handled", 0, 120),
                _n("data", "Tickets dataset (48k)", "dataset", "ds", 2, "Labeled tickets, 9 teams", 260, 0),
                _n("clean", "Arabic normalization", "pipeline", "ds", 1, "Diacritics, alef forms, emojis", 520, 0),
                _n("model", "AraBERT classifier", "pipeline", "ds", 3, "Fine-tuned, 9 classes", 780, 0),
                _n("api", "Routing API", "engine", "engineer", 2, "FastAPI, < 1s", 1040, 0),
                _n("ui", "Agent console", "engine", "engineer", 1, "Shows predicted team", 1300, 0),
            ],
            "edges": [
                ("obj", "data", "feeds"), ("req-dialect", "clean", "feeds"),
                ("data", "clean", "feeds"), ("clean", "model", "feeds"),
                ("model", "api", "feeds"), ("api", "ui", "feeds"),
            ],
        },
        # ------------------------------------------------------------------
        "fraud": {
            "id": "fraud",
            "name": "Transaction Fraud Detection",
            "domain": "Finance",
            "state": "bottleneck",
            "summary": "Mid-project. The domain expert raised a new rule that ripples through the pipeline.",
            "objective": {
                "goal": "Flag fraudulent transfers in near real time",
                "success_metric": "Recall >= 90%, false alarms < 5%",
                "priorities": ["recall", "false_alarms", "speed"],
                "constraints": ["Decision < 300ms", "Explainable to compliance"],
                "deadline": "Pilot in 4 weeks",
            },
            "metrics": {"recall": 0.91, "false_alarm_rate": 0.083, "latency_ms": 180},
            "rules": [
                {"id": "p-large", "text": "Client promise: flag every transfer above SAR 50,000", "source": "Kickoff meeting"},
                {"id": "r-explain", "text": "Every flag must show its top reasons", "source": "Compliance"},
            ],
            "nodes": [
                _n("obj", "Objective: catch fraud", "objective", "lead", 0, "Recall >= 90%, FA < 5%", 0, 0),
                _n("req-large", "Promise: flag > SAR 50k", "requirement", "lead", 1, "Agreed with client", 0, 120),
                _n("req-family", "Rule: family transfers", "requirement", "domain", 1,
                   "Proposed by expert: transfers between family members are common, not fraud", 0, 240,
                   status="pending",
                   options=[
                       _opt("exclude-family", "Stop flagging family transfers", 1.0,
                            {"recall": -2, "false_alarms": -35},
                            "Expert: family transfers are a normal pattern in the region",
                            conflicts=["p-large"],
                            alternative={"label": "Post-filter rule: down-rank family transfers under SAR 50k only",
                                         "effort_days": 0.5, "metric_delta": {"recall": 0, "false_alarms": -28}}),
                   ]),
                _n("data", "Transactions (2.1M)", "dataset", "ds", 2, "6 months, 0.4% fraud", 260, 0),
                _n("features", "Feature builder", "pipeline", "ds", 2, "Velocity, amount, device, network", 520, 0,
                   options=[
                       _opt("add-relation", "Add 'sender-receiver relationship' feature", 1.0,
                            {"recall": 1, "false_alarms": -20}, "Captures family/known-contact patterns"),
                   ]),
                _n("model", "XGBoost model", "pipeline", "ds", 2, "Class-weighted", 780, 0,
                   options=[
                       _opt("to-gnn", "Switch to graph neural network", 1.6,
                            {"recall": 3, "false_alarms": -10}, "Learns money-flow networks",
                            conflicts=["r-explain"],
                            alternative={"label": "Keep XGBoost + add graph features",
                                         "effort_days": 2, "metric_delta": {"recall": 2, "false_alarms": -8}}),
                   ]),
                _n("explain", "Reason codes (SHAP)", "pipeline", "ds", 1, "Top-3 reasons per flag", 780, 140),
                _n("scoring", "Scoring service", "engine", "engineer", 3, "Real-time, < 300ms", 1040, 0,
                   options=[
                       _opt("cpu-only", "Move scoring to CPU-only to cut cost", 1.0,
                            {"latency_ms": 60}, "Cost reduction of ~40%"),
                   ]),
                _n("hw", "Serving hardware", "engine", "engineer", 1, "GPU pool", 1040, 160),
                _n("dash", "Analyst dashboard", "engine", "engineer", 2, "Case review UI", 1300, 0),
            ],
            "edges": [
                ("obj", "data", "feeds"), ("req-large", "features", "feeds"),
                ("req-family", "features", "feeds"),
                ("data", "features", "feeds"), ("features", "model", "feeds"),
                ("model", "explain", "feeds"), ("model", "scoring", "feeds"),
                ("explain", "dash", "feeds"), ("scoring", "dash", "feeds"),
                ("hw", "scoring", "constrains"), ("hw", "model", "constrains"),
            ],
        },
        # ------------------------------------------------------------------
        "heart": {
            "id": "heart",
            "name": "Heart Reading Anomaly Detection",
            "domain": "Healthcare",
            "state": "new",
            "summary": "New client. Documents uploaded; the agents have not built anything yet.",
            "objective": None,  # filled by objective intake
            "metrics": {},
            "rules": [],
            "documents": [
                {"name": "Client brief.pdf", "text": "We run 14 clinics and want to flag abnormal heart readings from patients' wearables so nurses can call them early. Missing a real case is much worse than a false alarm."},
                {"name": "Kickoff meeting transcript.txt", "text": "Ops lead: results should reach the nurse within 5 minutes. Cardiologist: we'll need to agree what counts as abnormal. Patient data must stay inside the country."},
                {"name": "Scope email.eml", "text": "Target: pilot in 6 weeks across 3 clinics."},
            ],
            "nodes": [],
            "edges": [],
        },
    }
