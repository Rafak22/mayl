"""Live eval: re-assess the PPE bottleneck with the real Claude agents and write a report.

    python scripts/eval_live.py before    # -> docs/eval_before.md
    python scripts/eval_live.py after     # -> docs/eval_after.md

Needs ANTHROPIC_API_KEY (backend/.env). Costs one live re-assessment.
"""
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app import llm  # noqa: E402
from app.main import app  # noqa: E402

PRODUCT = "ppe"


class Usage:
    """Wraps messages.create to count calls and the exact tokens the API reports."""

    def __init__(self, client):
        self.inner, self.lock = client.messages, threading.Lock()
        self.calls = self.input_tokens = self.output_tokens = 0
        client.messages = self

    def create(self, **kwargs):
        resp = self.inner.create(**kwargs)
        with self.lock:
            self.calls += 1
            self.input_tokens += resp.usage.input_tokens
            self.output_tokens += resp.usage.output_tokens
        return resp


def main(label: str):
    if not llm.enabled():
        sys.exit("Live agents are off: set ANTHROPIC_API_KEY in backend/.env (and AGENT_MODE not 'demo').")
    usage = Usage(llm.client())
    c = TestClient(app, headers={"X-Session": f"eval-{label}-{time.time_ns()}"})
    c.post("/api/reset")
    seeded = next(x for x in c.get("/api/inbox/lead").json() if x["product_id"] == PRODUCT)

    start = time.perf_counter()
    r = c.post(f"/api/proposals/{seeded['id']}/rerun")
    seconds = time.perf_counter() - start
    r.raise_for_status()
    card = r.json()
    if card.get("mode") != "live":
        sys.exit(f"Live run fell back to demo agents: {card.get('fallback_reason')}")

    out = BACKEND / "docs" / f"eval_{label}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(render(label, card, seconds, usage), encoding="utf-8")
    (out.with_suffix(".json")).write_text(json.dumps(
        {"card": card, "seconds": round(seconds, 1), "llm_calls": usage.calls,
         "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out} ({seconds:.1f} s, {usage.calls} calls, {usage.input_tokens} in / {usage.output_tokens} out tokens)")


def render(label, card, seconds, usage) -> str:
    alt = card.get("alternative")
    conflicts = ", ".join(f"`{x['id']}`" for x in card["conflicts"]) or "none"
    alternative = f"{alt['label']} ({alt['effort_days']:g} days)" if alt else "none"
    lines = [
        f"# Live eval ({label}): {card['title']}",
        "",
        f"Product `{card['product_id']}`, node *{card['node_label']}*, proposed by {card['proposer_name']}. "
        f"Model `{llm.MODEL}`. Run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.",
        "",
        "| | |",
        "|---|---|",
        f"| Risk | {card['risk']} |",
        f"| Verdict | {card['verdict']} |",
        f"| Conflicts | {conflicts} |",
        f"| Total effort (max) | {card['total_effort_max']:g} days |",
        f"| Alternative | {alternative} |",
    ]
    if "recommendation" in card:
        lines.append(f"| Lead recommendation | **{card['recommendation']}**: {card.get('recommendation_reason', '')} |")
    lines += [
        f"| Approvers | {', '.join(card['approvers']) or 'none'} |",
        f"| Time | {seconds:.1f} s |",
        f"| LLM calls | {usage.calls} |",
        f"| Tokens | {usage.input_tokens:,} input + {usage.output_tokens:,} output = {usage.input_tokens + usage.output_tokens:,} |",
        "",
    ]
    for resp in card["responses"]:
        lines += [
            f"## {resp['agent']}",
            "",
            f"- **Effort:** {resp['effort_text']} (range {resp['effort_range'][0]:g}–{resp['effort_range'][1]:g})",
            f"- **Verdict:** {resp.get('verdict')}"
            + (f", conflicts: {', '.join(resp['conflict_ids'])}" if resp.get("conflict_ids") else ""),
            f"- **Tools used:** {' → '.join(resp.get('tools_used') or []) or 'none'}",
            "- **Evidence:**" + ("" if resp.get("evidence") else " none"),
            *[f"  - {e}" for e in resp.get("evidence") or []],
            "",
            f"> {resp['message']}",
            "",
        ]
    return "\n".join(lines)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "run")
