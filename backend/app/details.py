"""Per-product "Data & solution" and "Knowledge" content.

Figures in the curated blocks below are taken from each product's knowledge
files (the `source` field names the file), so the page and the agents quote the
same numbers. The document list and the sample rows are read from disk.
"""
import csv
from pathlib import Path

from .rag import KB_ROOT, SCOPES, chunk_file

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"
SCOPE_AGENT = {"ds": "ds", "engineer": "engineer", "domain": "domain", "shared": None}  # None = shared by all agents


def _csv(name: str) -> list[dict]:
    path = SAMPLES / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def documents(product_id: str) -> list[dict]:
    """Every knowledge document of a product, with its owning agent and its sections."""
    out = []
    for scope in SCOPES:
        for f in sorted((KB_ROOT / product_id / scope).glob("*.md")):
            first = f.read_text(encoding="utf-8").splitlines()[0]
            out.append({
                "title": first.lstrip("# ").strip(),
                "file": f"{scope}/{f.name}",
                "scope": scope,
                "agent": SCOPE_AGENT[scope],
                "sections": [{"heading": c.source.split(" › ", 1)[1], "text": c.text.split(": ", 1)[1]}
                             for c in chunk_file(f, scope)],
            })
    return out


def _ppe(product) -> dict:
    return {
        "examples": {
            "title": "Example run",
            "note": "Red box = helmet detected · blue box = head without a helmet · "
                    "images: Safety Helmet Wearing Dataset (MIT)",
            "items": [
                {"image": "/samples/ppe/images/site-compliant.jpg", "tone": "good", "title": "Compliant",
                 "alt": "A crew of construction workers in safety vests, every head boxed in red as a detected helmet",
                 "caption": "Every detected helmet is worn on the head. Same result under the old and the new rule."},
                {"image": "/samples/ppe/images/site-carried.jpg", "tone": "warn", "title": "The bottleneck case",
                 "alt": "People at a site entrance, most heads boxed without helmets, with red helmets held in hands",
                 "caption": "Helmets are carried, not worn. Old logic: a helmet inside the person box counts as "
                            "compliant. New rule: not on the head means a violation."},
                {"image": "/samples/ppe/images/site-violation.jpg", "tone": "bad", "title": "Violation, alert sent",
                 "alt": "Workers beside a truck; most wear helmets boxed in red, one man on the right is boxed in blue",
                 "caption": "One worker (blue box, right) has no helmet, so the engine raises an alert. "
                            "Current end-to-end time is 8 s against a 60 s limit."},
            ],
        },
        "data": {
            "stats": [{"value": "~7,000", "label": "Public images (public domain)"},
                      {"value": "1,200", "label": "Client site images"}],
            "bars": {"title": "Labeled boxes by class", "items": [
                {"label": "helmet", "value": 21000, "display": "~21,000"},
                {"label": "head", "value": 6500, "display": "~6,500"}]},
            "note": "9% of helmet boxes are carried helmets (hand, belt, ground), found in a 400-image review. "
                    "Under the new rule, these are violations.",
            "footer": "Format: YOLO boxes · classes: helmet, head, person",
            "source": "ds/dataset-card.md",
        },
        "solution": {
            "pipeline": [{"label": "Camera image · every 30 s", "owner": None},
                         {"label": "YOLOv8n · 640 px · CPU", "owner": "ds"},
                         {"label": "Compliance logic", "owner": "engineer"},
                         {"label": "Safety officer app", "owner": "engineer"}],
            "table": {"title": "Why this model", "columns": ["Experiment", "mAP50", "Speed", "Decision"], "rows": [
                {"cells": ["Exp 3 · YOLOv8n", "0.89", "Fits CPU on all 40 cameras", "Chosen (v3)"], "chosen": True},
                {"cells": ["Exp 4 · YOLOv8s", "0.91", "2.3× slower", "Parked: CPU limit"], "chosen": False}]},
            "stats": [{"value": "96%", "label": "Head recall"}, {"value": "8 s", "label": "End to end"},
                      {"value": "400", "label": "Eval images"}],
            "source": "ds/experiment-log.md · engineer/engine-contract.md",
        },
        "samples": None,
    }


def _chatbot(product) -> dict:
    rows = _csv("chatbot_eval_sample.csv")
    return {
        "examples": None,
        "data": {
            "stats": [{"value": "312", "label": "Documents (Arabic + English)"},
                      {"value": "~2,400", "label": "Searchable chunks"}],
            "bars": {"title": "Evaluation set: 600 questions", "items": [
                {"label": "Arabic", "value": 70, "display": "70%"},
                {"label": "English", "value": 30, "display": "30%"}]},
            "note": "Some package names differ between Arabic and English documents (for example "
                    "\"باقة سوا\" vs \"Sawa Plus\"). A synonym list fixes most retrieval misses.",
            "footer": "120 questions are in Gulf dialect · refreshed monthly",
            "source": "ds/knowledge-base-and-eval.md",
        },
        "solution": {
            "pipeline": [{"label": "App + WhatsApp", "owner": "engineer"},
                         {"label": "Hybrid retriever", "owner": "ds"},
                         {"label": "LLM answer", "owner": "engineer"},
                         {"label": "Guardrails", "owner": "engineer"},
                         {"label": "Answer or human handover", "owner": "engineer"}],
            "table": {"title": "Why RAG", "columns": ["Option", "When prices change", "Decision"], "rows": [
                {"cells": ["RAG over official documents", "Weekly document refresh", "Chosen (Jun 2026)"], "chosen": True},
                {"cells": ["Fine-tuning", "Retrain the model", "Not chosen"], "chosen": False}]},
            "stats": [{"value": "91.2%", "label": "Accuracy (Oct 2026)"}, {"value": "1.4 s", "label": "First token, p95"},
                      {"value": "0.3%", "label": "Wrong prices, all caught"}],
            "source": "shared/decisions-log.md · ds/knowledge-base-and-eval.md · engineer/system-contract.md",
        },
        "samples": {
            "title": "Sample evaluation questions",
            "note": f"{len(rows)} questions from the evaluation sample, with the bot's result",
            "columns": [{"key": "question", "label": "Question"}, {"key": "topic", "label": "Topic"},
                        {"key": "result", "label": "Result"}],
            "rows": rows,
        },
    }


def _triage(product) -> dict:
    rows = _csv("triage_messages.csv")
    built = bool(product["nodes"])
    solution = None
    if built:  # designed by the agents after objective intake (agents.build_from_objective)
        solution = {
            "pipeline": [{"label": "WhatsApp message", "owner": None},
                         {"label": "Urgency classifier + safety rules", "owner": "ds"},
                         {"label": "Booking tool · nurse alert", "owner": "engineer"},
                         {"label": "Reply < 2 min", "owner": "engineer"}],
            "table": {"title": "Why Agent A", "columns": ["Design", "Emergency recall", "Routine accuracy", "Decision"],
                      "rows": [{"cells": ["Agent A · LLM + hard safety rules", "100%", "93%", "Chosen"], "chosen": True},
                               {"cells": ["Agent B · rules + keywords", "100%", "78%", "Backup"], "chosen": False}]},
            "stats": [{"value": "100%", "label": "Emergencies escalated"}, {"value": "93%", "label": "Routine accuracy"},
                      {"value": "400", "label": "Test messages"}],
            "source": "Agents' build log for this project",
        }
    return {
        "examples": None,
        "data": {
            "stats": [{"value": "12,000", "label": "Past WhatsApp messages"},
                      {"value": "82%", "label": "Written in Arabic"}],
            "bars": {"title": "Outcome tagged by reception staff", "items": [
                {"label": "Routine", "value": 58, "display": "58%"},
                {"label": "Admin", "value": 21, "display": "21%"},
                {"label": "Same-day", "value": 14, "display": "14%"},
                {"label": "Nurse call", "value": 6, "display": "6%"},
                {"label": "Emergency", "value": 1, "display": "1%"}]},
            "note": "Emergencies are rare (about 120 messages), so the urgency classifier needs rule-based "
                    "safety checks on top.",
            "footer": "Anonymized · many messages mix symptoms with a booking request",
            "source": "ds/message-data-notes.md",
        },
        "solution": solution,
        "solution_pending": None if built else "The agents design the solution after objective intake.",
        "samples": {
            "title": "Sample patient messages",
            "note": f"{len(rows)} synthetic messages with the outcome the agent must reach",
            "columns": [{"key": "text", "label": "Message"}, {"key": "language", "label": "Lang"},
                        {"key": "expected_outcome", "label": "Expected outcome"}],
            "rows": rows,
        },
    }


BUILDERS = {"ppe": _ppe, "chatbot": _chatbot, "triage": _triage}


def product_details(product: dict) -> dict:
    build = BUILDERS.get(product["id"])
    base = build(product) if build else {"examples": None, "data": None, "solution": None, "samples": None}
    return {"solution_pending": None} | base | {"documents": documents(product["id"])}
