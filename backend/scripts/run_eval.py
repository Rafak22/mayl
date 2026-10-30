"""Mayl evaluation runner. Implements eval/SPEC.md; the case files are read-only.

    python scripts/run_eval.py --split dev --mode demo
    python scripts/run_eval.py --split dev --mode live --limit 10 --repeats 1 --max-usd 2
    python scripts/run_eval.py --report-only          # rebuild eval/eval_report.md from eval/results/

Every case runs in a fresh API session (reset first) through FastAPI's TestClient. The eval-only
"retail" product is registered into each session, with its knowledge searched from
eval/knowledge/retail; the app's demo products are not changed. Results go to
eval/results/<timestamp>_<split>_<mode>.json and eval/eval_report.md is regenerated from the latest
result of every split/mode.
"""
import argparse
import copy
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
EVAL = BACKEND / "eval"
RESULTS = EVAL / "results"
sys.path.insert(0, str(BACKEND))

KINDS = ("change_review", "domain_qa", "retrieval", "intake")
ROBUSTNESS_TAGS = ("vague", "typos", "mixed_language", "injection", "missing_info", "leading_question",
                   "out_of_scope", "paraphrase")
# USD per million tokens (input, output), Claude API list prices.
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-sonnet-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0),
          "claude-haiku-5-5": (0.10, 0.50), "claude-fable-5-1": (10.0, 50.0)}
# Prior token use per case for the cost guard, from measured runs (docs/eval_after.md: ~22k in / 2.3k out per review).
ESTIMATE = {"change_review": (24_000, 2_500), "domain_qa": (3_500, 900), "retrieval": (0, 0), "intake": (9_000, 3_000)}
TRIAGE_SETUP = (9_000, 3_000)  # live intake before triage change reviews

JUDGE_RUBRIC = """You grade one answer from a domain assistant against reference key facts.
Mark "correct" when the answer states the reference's core conclusion (for example the yes/no and the rule or
number that decides it) and contradicts nothing in it. Extra correct detail is fine. The answer may be in any
language. Mark "incorrect" when the core conclusion is missing, hedged into no answer, or contradicted.
Judge only against the key facts given, not your own knowledge. Give a one-sentence reason."""
JUDGE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["verdict", "reason"],
                "properties": {"verdict": {"type": "string", "enum": ["correct", "incorrect"]}, "reason": {"type": "string"}}}

ARABIC = re.compile(r"[؀-ۿ]")
LATIN = re.compile(r"[A-Za-z]")
SENTENCE_END = re.compile(r"(?<=[.!?؟])\s+")


# --- setup ---------------------------------------------------------------------------------------
def load_cases():
    return {k: json.loads((EVAL / "cases" / f"{k}.json").read_text(encoding="utf-8")) for k in KINDS}


def retail_product() -> dict:
    """eval/products/retail.json, with the fields the app expects filled with defaults (file unchanged)."""
    p = json.loads((EVAL / "products" / "retail.json").read_text(encoding="utf-8"))
    for n in p["nodes"]:
        n.setdefault("status", "ok")
        n.setdefault("change_options", [])
        n.setdefault("short", n["label"])
    p["edges"] = [tuple(e) for e in p["edges"]]
    for key, default in (("metric_goals", {}), ("client", "Tamr Markets"), ("tech", "Time-series forecasting"),
                         ("expert", "the category managers")):
        p.setdefault(key, default)
    return p


class Usage:
    """Wraps messages.create and counts calls and tokens (the agents call it from parallel threads)."""

    def __init__(self, client):
        self.inner, self.lock = client.messages, threading.Lock()
        self.calls = self.input = self.output = 0
        client.messages = self

    def create(self, **kwargs):
        resp = self.inner.create(**kwargs)
        with self.lock:
            self.calls += 1
            self.input += resp.usage.input_tokens
            self.output += resp.usage.output_tokens
        return resp

    def snapshot(self):
        with self.lock:
            return self.calls, self.input, self.output


def cost(tokens_in, tokens_out, model):
    pin, pout = PRICES[model]
    return (tokens_in * pin + tokens_out * pout) / 1e6


# --- validation of the case files (reported, never edited) ---------------------------------------
def validate(cases, products, rag) -> list[str]:
    from app.agents import build_from_objective

    built = copy.deepcopy(products)
    build_from_objective(built["triage"], {})  # triage cases run after intake + confirm
    sources = {}
    for pid in built:
        chunks = [c for p_, c in rag.knowledge_chunks() if p_ == pid] if pid != "retail" else list(rag._extra_chunks("retail"))
        sources[pid] = {c.source for c in chunks}
    files = {pid: {s.split(" › ")[0].split("/")[-1] for s in srcs} | {s.split(" › ")[0] for s in srcs} for pid, srcs in sources.items()}
    problems = []
    for c in cases["change_review"]:
        p = built.get(c["product"])
        if not p:
            problems.append(f"{c['id']}: unknown product {c['product']}"); continue
        if c["node"] not in {n["id"] for n in p["nodes"]}:
            problems.append(f"{c['id']}: node '{c['node']}' not in {c['product']}")
        rule_ids = {r["id"] for r in p.get("rules", [])}
        for rid in c["gold"]["must_flag"] + c["gold"]["allowed_flags"]:
            if rid not in rule_ids:
                problems.append(f"{c['id']}: rule '{rid}' not in {c['product']} rules")
        for f in c["gold"]["must_cite"]:
            if f not in files[c["product"]]:
                problems.append(f"{c['id']}: must_cite '{f}' not in {c['product']} knowledge")
    for c in cases["domain_qa"]:
        for f in c["gold"]["sources"]:
            if f not in files[c["product"]]:
                problems.append(f"{c['id']}: source '{f}' not in {c['product']} knowledge")
    for c in cases["retrieval"]:
        for g in c["gold"]:
            if g not in sources[c["product"]]:
                problems.append(f"{c['id']}: gold chunk '{g}' does not exist")
    return problems


# --- scoring helpers -----------------------------------------------------------------------------
def has_any(text, phrases):
    t = (text or "").lower()
    return any(p.lower() in t for p in phrases)


def sentences(text):
    return [s for s in SENTENCE_END.split((text or "").strip()) if s.strip()]


def language(text):
    return "ar" if len(ARABIC.findall(text or "")) > len(LATIN.findall(text or "")) else "en"


def map_recommendation(card):
    rec = card.get("recommendation")
    return rec if rec in ("approve", "alternative", "reject") else "needs_info"


def citation_is_real(source, srcs, files):
    head = source.split(" › ")[0].strip()
    if head in ("project graph", "activity", "rules") or source.startswith(("project graph", "activity", "rules")):
        return True  # live project memory
    if source in srcs:
        return True
    if ".md" in head:  # a file citation: the file must exist; a heading, if given, must exist in it
        if head not in files and head.split("/")[-1] not in files:
            return False
        return " › " not in source or any(s.endswith(source.split(" › ", 1)[1]) and head.split("/")[-1] in s for s in srcs)
    return False


# --- case runners --------------------------------------------------------------------------------
class Runner:
    def __init__(self, args, main, rag, usage):
        from fastapi.testclient import TestClient

        from app.products import build_products

        self.args, self.main, self.rag, self.usage = args, main, rag, usage
        self.client = TestClient(main.app)
        self.live = args.mode == "live"
        products = {**build_products(), "retail": retail_product()}
        self.sources = {}
        for pid in products:
            chunks = [c for p_, c in rag.knowledge_chunks() if p_ == pid] if pid != "retail" else list(rag._extra_chunks("retail"))
            srcs = {c.source for c in chunks}
            self.sources[pid] = (srcs, {s.split(" › ")[0] for s in srcs} | {s.split(" › ")[0].split("/")[-1] for s in srcs})

    def session(self):
        sid = f"eval-{uuid.uuid4().hex[:10]}"
        h = {"X-Session": sid}
        self.client.post("/api/reset", headers=h)
        st = self.main.session(sid)
        st["products"]["retail"] = retail_product()
        st["activity"]["retail"] = []
        if not self.args.keep_seed:  # the seeded bottleneck's review would hand the ppe cases their answer
            st["proposals"].clear()
            for pid, entries in st["activity"].items():
                st["activity"][pid] = [a for a in entries if a["kind"] not in ("review", "recommendation", "proposal")]
            for p in st["products"].values():
                for n in p["nodes"]:
                    n["status"] = "ok"
        return h

    def measure(self, fn):
        c0, i0, o0 = self.usage.snapshot() if self.usage else (0, 0, 0)
        t0 = time.perf_counter()
        out = fn()
        dt = time.perf_counter() - t0
        c1, i1, o1 = self.usage.snapshot() if self.usage else (0, 0, 0)
        return out, {"latency_s": round(dt, 2), "llm_calls": c1 - c0, "tokens_in": i1 - i0, "tokens_out": o1 - o0}

    def post(self, path, h, body=None):
        r = self.client.post(path, headers=h, json=body)
        r.raise_for_status()
        return r.json()

    # A. change review
    def change_review(self, case):
        h, g = self.session(), case["gold"]
        setup = {"tokens_in": 0, "tokens_out": 0}
        if case.get("setup") == "intake_confirm":
            _, setup = self.measure(lambda: (self.post(f"/api/products/{case['product']}/intake", h),
                                             self.post(f"/api/products/{case['product']}/confirm", h, {"answers": {}})))
        card, m = self.measure(lambda: self.post(f"/api/products/{case['product']}/proposals", h,
                                                 {"node_id": case["node"], "custom_text": case["change"], "role": case["proposer"]}))
        flagged = {c["id"] for c in card["conflicts"]}
        must, allowed = set(g["must_flag"]), set(g["allowed_flags"])
        false = sorted(flagged - must - allowed)
        teams = {r["team"] for r in card["responses"] if r["effort_range"][1] > 0}
        req = set(g["teams_required"])
        tp = len(teams & req)
        f1 = 1.0 if not teams and not req else (2 * tp / (len(teams) + len(req)) if teams or req else 1.0)
        mid = sum((r["effort_range"][0] + r["effort_range"][1]) / 2 for r in card["responses"])
        alt = card.get("alternative")
        rec = map_recommendation(card)
        messages = " ".join(r["message"] for r in card["responses"])
        evidence = [e for r in card["responses"] for e in (r.get("evidence") or [])]
        srcs, files = self.sources[case["product"]]
        fake = [e for e in evidence if not citation_is_real(e, srcs, files)]
        s = {
            "conflict_hits": len(flagged & must), "conflict_total": len(must),
            "conflict_recall": len(flagged & must) / len(must) if must else 1.0,
            "false_conflicts": len(false), "false_conflict_ids": false, "flagged": sorted(flagged),
            "teams": sorted(teams), "teams_f1": round(f1, 3),
            "effort_mid_total": round(mid, 2),
            "effort_hit": None if g["effort_total"] is None else g["effort_total"][0] <= mid <= g["effort_total"][1],
            "alternative_ok": None if not g["alternative"]["expected"] else bool(alt and has_any(alt["label"], g["alternative"]["keywords"])),
            "alternative": alt["label"] if alt else None,
            "risk": card["risk"], "risk_ok": card["risk"] in g["risk"],
            "recommendation": rec, "recommendation_ok": rec in g["recommendation"],
            "recommendation_mode": card.get("recommendation_mode"),
            "must_mention_ok": has_any(messages, g["must_mention"]) if g.get("must_mention") else None,
            "grounded": None if not g["must_cite"] else any(any(f in e for f in g["must_cite"]) for e in evidence),
            "fake_citations": fake,
            "brevity_ok": all(len(sentences(r["message"])) <= 3 for r in card["responses"]),
            "fallback": self.live and card.get("mode") != "live",
            "messages": {r["team"]: r["message"] for r in card["responses"]},
        }
        s["pass"] = s["conflict_recall"] == 1 and not false and s["risk_ok"] and s["recommendation_ok"]
        s["fail_reasons"] = [r for r, bad in [
            (f"missed conflicts {sorted(must - flagged)}", s["conflict_recall"] < 1), (f"false conflicts {false}", bool(false)),
            (f"risk {card['risk']} not in {g['risk']}", not s["risk_ok"]),
            (f"recommendation {rec} not in {g['recommendation']}", not s["recommendation_ok"])] if bad]
        return s | m | {"setup_tokens_in": setup["tokens_in"], "setup_tokens_out": setup["tokens_out"]}

    # B. Domain Agent Q&A
    def domain_qa(self, case):
        h, g = self.session(), case["gold"]
        a, m = self.measure(lambda: self.post(f"/api/products/{case['product']}/ask", h,
                                              {"question": case["question"], "agent": "domain"}))
        files = {s["source"].split(" › ")[0] for s in a["sources"]}
        answered = not a["escalated"]
        s = {"answer": a["answer"], "sources": [x["source"] for x in a["sources"]], "escalated": a["escalated"],
             "should_escalate": g["should_escalate"],
             "escalation_ok": a["escalated"] == g["should_escalate"],
             "answered_when_should_escalate": g["should_escalate"] and answered,
             "source_hit": None if g["should_escalate"] else bool(files & set(g["sources"])),
             "language_ok": None if case["lang"] == "any" or g["should_escalate"] else language(a["answer"]) == case["lang"],
             "fallback": self.live and a["mode"] != "live" and bool(a["sources"])}
        jm = {"tokens_in": 0, "tokens_out": 0}
        if g["should_escalate"]:
            s["keyword_precheck"] = s["fact_ok"] = None
        else:
            s["keyword_precheck"] = has_any(a["answer"], g["keywords"])
            if not answered:
                s["fact_ok"], s["judge"] = False, {"verdict": "incorrect", "reason": "Escalated instead of answering."}
            elif self.live:
                s["judge"], jm = self.measure(lambda: judge(case["question"], g["key_facts"], a["answer"], self.args.judge_model))
                s["fact_ok"] = s["judge"]["verdict"] == "correct"
            else:  # demo runs stay free: the keyword pre-check decides
                s["fact_ok"] = s["keyword_precheck"]
        s["pass"] = s["escalation_ok"] and (g["should_escalate"] or (s["source_hit"] and s["fact_ok"] and s["language_ok"] is not False))
        s["fail_reasons"] = [r for r, bad in [
            ("answered instead of escalating", s["answered_when_should_escalate"]),
            ("escalated instead of answering", a["escalated"] and not g["should_escalate"]),
            ("no gold source", s["source_hit"] is False), ("wrong language", s["language_ok"] is False),
            ("facts wrong" + (f" (judge: {s.get('judge', {}).get('reason', '')})" if self.live else " (keyword pre-check)"),
             s["fact_ok"] is False and answered)] if bad]
        return s | m | {"judge_tokens_in": jm["tokens_in"], "judge_tokens_out": jm["tokens_out"]}

    # C. Retrieval (no LLM: same in demo and live)
    def retrieval(self, case):
        from app.rag import AGENT_SCOPES, Retriever
        hits, m = self.measure(lambda: Retriever(case["product"]).search(case["query"], AGENT_SCOPES[case["agent"]], k=4))
        got = [x["source"] for x in hits]
        rank = next((i + 1 for i, src in enumerate(got) if src in case["gold"]), None)
        scopes = AGENT_SCOPES[case["agent"]]
        leaks = [src for src in got if (src.split("/")[0] if "/" in src.split(" › ")[0] else "live") not in scopes]
        s = {"returned": got, "recall_at_4": rank is not None, "mrr": 1 / rank if rank else 0.0, "scope_leaks": leaks,
             "fallback": False}
        s["pass"] = s["recall_at_4"] and not leaks
        s["fail_reasons"] = [r for r, bad in [("no gold chunk in top 4", not rank), (f"scope leaks {leaks}", bool(leaks))] if bad]
        return s | m

    # D. Objective intake
    def intake(self, case):
        h, g = self.session(), case["gold"]
        if case["documents"] != "default":
            st = self.main.session(h["X-Session"])
            st["products"][case["product"]]["documents"] = case["documents"]
        out, m = self.measure(lambda: self.post(f"/api/products/{case['product']}/intake", h))
        spec_text = json.dumps(out["spec"], ensure_ascii=False).lower()
        gap_text = json.dumps(out["gaps"], ensure_ascii=False).lower()
        cons = [has_any(spec_text, grp) for grp in g["constraints"]]
        gaps = [has_any(gap_text, grp) for grp in g["gaps"]]
        invented = [p for p in g["must_not_include"] if p.lower() in spec_text + gap_text]
        s = {"constraint_hits": sum(cons), "constraint_total": len(cons), "gap_hits": sum(gaps), "gap_total": len(gaps),
             "invented": invented, "spec": out["spec"], "gaps": out["gaps"],
             "fallback": self.live and out.get("mode") != "live"}
        s["pass"] = all(cons) and all(gaps) and not invented
        s["fail_reasons"] = [r for r, bad in [
            (f"missed constraints {[grp[0] for grp, ok in zip(g['constraints'], cons) if not ok]}", not all(cons)),
            (f"missed gaps {[grp[0] for grp, ok in zip(g['gaps'], gaps) if not ok]}", not all(gaps)),
            (f"invented {invented}", bool(invented))] if bad]
        return s | m


def judge(question, key_facts, answer, model):
    from app import llm
    resp = llm.client().messages.create(
        model=model, max_tokens=2000, system=JUDGE_RUBRIC,
        messages=[{"role": "user", "content": f"Question: {question}\n\nReference key facts: {key_facts}\n\nAnswer to grade: {answer}"}],
        output_config={"format": {"type": "json_schema", "schema": JUDGE_SCHEMA}})
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


# --- aggregation and report ----------------------------------------------------------------------
def rate(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(bool(v) for v in vals) / len(vals) if vals else None


def per_repeat_metrics(rows, live=True):
    """Metrics for one repeat, per kind. Fallback rate only means something in live mode."""
    out = {}
    cr = [r for r in rows if r["kind"] == "change_review"]
    if cr:
        total = sum(r["conflict_total"] for r in cr)
        out["change_review"] = {
            "pass_rate": rate(cr, "pass"),
            "conflict_recall": sum(r["conflict_hits"] for r in cr) / total if total else None,
            "false_conflicts_per_case": sum(r["false_conflicts"] for r in cr) / len(cr),
            "teams_f1": statistics.mean(r["teams_f1"] for r in cr),
            "effort_hit": rate(cr, "effort_hit"), "alternative": rate(cr, "alternative_ok"),
            "risk": rate(cr, "risk_ok"), "recommendation": rate(cr, "recommendation_ok"),
            "must_mention": rate(cr, "must_mention_ok"), "grounding": rate(cr, "grounded"),
            "fake_citations_per_case": sum(len(r["fake_citations"]) for r in cr) / len(cr),
            "brevity": rate(cr, "brevity_ok"),
        }
    qa = [r for r in rows if r["kind"] == "domain_qa"]
    if qa:
        esc = [r for r in qa if r["escalated"]]
        should = [r for r in qa if r["should_escalate"]]
        out["domain_qa"] = {
            "pass_rate": rate(qa, "pass"),
            "escalation_precision": sum(r["should_escalate"] for r in esc) / len(esc) if esc else None,
            "escalation_recall": sum(r["escalated"] for r in should) / len(should) if should else None,
            "answered_when_should_escalate": sum(r["answered_when_should_escalate"] for r in qa),
            "source_hit": rate(qa, "source_hit"), "language_match": rate(qa, "language_ok"),
            "fact_accuracy": rate(qa, "fact_ok"),
        }
    rt = [r for r in rows if r["kind"] == "retrieval"]
    if rt:
        out["retrieval"] = {"pass_rate": rate(rt, "pass"), "recall_at_4": rate(rt, "recall_at_4"),
                            "mrr": statistics.mean(r["mrr"] for r in rt), "scope_leaks": sum(len(r["scope_leaks"]) for r in rt)}
    it = [r for r in rows if r["kind"] == "intake"]
    if it:
        ct, gt = sum(r["constraint_total"] for r in it), sum(r["gap_total"] for r in it)
        out["intake"] = {"pass_rate": rate(it, "pass"),
                         "constraint_recall": sum(r["constraint_hits"] for r in it) / ct if ct else None,
                         "gap_recall": sum(r["gap_hits"] for r in it) / gt if gt else None,
                         "invented_facts": sum(len(r["invented"]) for r in it)}
    llm_rows = [r for r in rows if r["kind"] != "retrieval"]
    out["system"] = {"fallback_rate": rate(llm_rows, "fallback") if live else None,
                     "cost_per_case_usd": statistics.mean(r["cost_usd"] for r in rows) if rows else None,
                     "total_cost_usd": sum(r["cost_usd"] for r in rows)}
    return out


def summarize(rows, repeats, live):
    by_rep = [per_repeat_metrics([r for r in rows if r["repeat"] == i], live) for i in range(repeats)]
    summary = {}
    for kind in by_rep[0]:
        summary[kind] = {}
        for metric in by_rep[0][kind]:
            vals = [b[kind][metric] for b in by_rep if b.get(kind, {}).get(metric) is not None]
            summary[kind][metric] = None if not vals else {
                "mean": statistics.mean(vals), "std": statistics.stdev(vals) if len(vals) > 1 else 0.0}
    lat = {}
    for kind in KINDS:
        xs = sorted(r["latency_s"] for r in rows if r["kind"] == kind)
        if xs:
            lat[kind] = {"p50": xs[len(xs) // 2], "p95": xs[min(len(xs) - 1, int(len(xs) * 0.95))]}
    summary["latency_s"] = lat
    if repeats > 1:
        recs = {}
        for r in rows:
            if r["kind"] == "change_review":
                recs.setdefault(r["id"], set()).add(r["recommendation"])
        summary["consistency"] = sum(len(v) == 1 for v in recs.values()) / len(recs) if recs else None
    return summary


TARGETS = [  # (label, kind, metric, op, value)
    ("Change-review pass rate (held-out)", "change_review", "pass_rate", ">=", 0.80),
    ("Conflict recall", "change_review", "conflict_recall", ">=", 0.90),
    ("False conflicts per case", "change_review", "false_conflicts_per_case", "<=", 0.2),
    ("Escalation recall", "domain_qa", "escalation_recall", "==", 1.0),
    ("Answered-when-should-escalate", "domain_qa", "answered_when_should_escalate", "==", 0),
    ("Retrieval Recall@4", "retrieval", "recall_at_4", ">=", 0.85),
    ("Scope leaks", "retrieval", "scope_leaks", "==", 0),
    ("Fallback rate", "system", "fallback_rate", "<=", 0.05),
]


def fmt(v, metric=""):
    if v is None:
        return "–"
    m, s = v["mean"], v["std"]
    if any(x in metric for x in ("leaks", "answered_when", "invented", "per_case", "cost")):
        body = f"{m:.3g}" if "cost" not in metric else f"${m:.4f}"
    else:
        body = f"{m:.2f}"
    return body + (f" ± {s:.2f}" if s else "")


def meets(v, op, target):
    if v is None:
        return "–"
    m = v["mean"]
    ok = {"<=": m <= target + 1e-9, ">=": m >= target - 1e-9, "==": abs(m - target) < 1e-9}[op]
    return "met" if ok else "**not met**"


def run_section(res) -> list[str]:
    meta, summary, rows = res["meta"], res["summary"], res["cases"]
    L = [f"## {meta['split']} · {meta['mode']} · {meta['timestamp']}", "",
         f"{len(set(r['id'] for r in rows))} cases × {meta['repeats']} repeat(s) · kinds: {', '.join(meta['kinds'])}"
         f"{f' · limit {meta['limit']}' if meta['limit'] else ''} · model `{meta['model']}`"
         f"{f' · judge `{meta['judge_model']}`' if meta['mode'] == 'live' else ' · no LLM judge (demo: keyword pre-check decides facts)'}"
         f" · seeded bottleneck {'kept' if meta['keep_seed'] else 'cleared'} · results `{meta['file']}`", ""]
    if meta.get("validation"):
        L += ["**Case-file problems found (not edited):**", *[f"- {p}" for p in meta["validation"]], ""]
    L += ["### Targets", "", "| Metric | Target | Result | |", "|---|---|---|---|"]
    for label, kind, metric, op, target in TARGETS:
        v = summary.get(kind, {}).get(metric)
        note = f" (this run: {meta['split']})" if "held-out" in label and meta["split"] != "heldout" else ""
        L.append(f"| {label}{note} | {op} {target} | {fmt(v, metric)} | {meets(v, op, target)} |")
    inj = [r for r in rows if "injection" in r.get("tags", [])]
    if inj:
        L.append(f"| Injection cases passed | all | {sum(r['pass'] for r in inj)} / {len(inj)} | {'met' if all(r['pass'] for r in inj) else '**not met**'} |")
    L.append("")
    names = {"change_review": "A. Change review", "domain_qa": "B. Domain Agent Q&A", "retrieval": "C. Retrieval",
             "intake": "D. Objective intake", "system": "E. System"}
    for kind, title in names.items():
        if kind not in summary:
            continue
        L += [f"### {title}", "", "| Metric | Mean ± std |", "|---|---|"]
        L += [f"| {k.replace('_', ' ')} | {fmt(v, k)} |" for k, v in summary[kind].items()]
        if kind == "system":
            for k, v in summary["latency_s"].items():
                L.append(f"| latency {k.replace('_', ' ')} p50 / p95 | {v['p50']:.2f} s / {v['p95']:.2f} s |")
            if summary.get("consistency") is not None:
                L.append(f"| consistency (same recommendation in all repeats) | {summary['consistency']:.2f} |")
            llm_cases = [r for r in rows if r["kind"] != "retrieval"]
            if meta["mode"] == "live" and llm_cases:
                for kind2 in ("change_review", "domain_qa", "intake"):
                    ks = [r for r in rows if r["kind"] == kind2]
                    if ks:
                        L.append(f"| cost per {kind2.replace('_', ' ')} case | ${statistics.mean(r['cost_usd'] for r in ks):.4f} "
                                 f"({statistics.mean(r['tokens_in'] + r.get('setup_tokens_in', 0) + r.get('judge_tokens_in', 0) for r in ks):,.0f} in / "
                                 f"{statistics.mean(r['tokens_out'] + r.get('setup_tokens_out', 0) + r.get('judge_tokens_out', 0) for r in ks):,.0f} out tokens) |")
        L.append("")
    tags = {}
    for r in rows:
        for t in r.get("tags", []):
            if t in ROBUSTNESS_TAGS:
                tags.setdefault(t, []).append(r)
    if tags:
        L += ["### Robustness tags", "", "| Tag | Cases | Pass rate |", "|---|---|---|"]
        L += [f"| {t} | {len({r['id'] for r in rs})} | {sum(r['pass'] for r in rs) / len(rs):.2f} |" for t, rs in sorted(tags.items())]
        L.append("")
    failed = [r for r in rows if not r["pass"]]
    L += [f"### Failed cases ({len({r['id'] for r in failed})} of {len({r['id'] for r in rows})})", ""]
    seen = set()
    for r in failed:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        reps = sum(1 for x in failed if x["id"] == r["id"])
        L.append(f"- **{r['id']}** ({r['kind'].replace('_', ' ')}{f', failed {reps}/{meta['repeats']} repeats' if meta['repeats'] > 1 else ''}): "
                 + "; ".join(r["fail_reasons"]))
    L.append("")
    judged = [r for r in rows if r.get("judge") and meta["mode"] == "live" and r["judge"]["reason"] != "Escalated instead of answering."]
    if judged:
        L += ["### Judge verdicts to hand-check (first 10)", "", "| Case | Verdict | Keyword pre-check | Judge reason | Answer |", "|---|---|---|---|---|"]
        for r in judged[:10]:
            ans = r["answer"].replace("|", "/").replace("\n", " ")[:160]
            L.append(f"| {r['id']} | {r['judge']['verdict']} | {'hit' if r['keyword_precheck'] else 'miss'} | {r['judge']['reason']} | {ans} |")
        L.append("")
    return L


REPORT_HEADER = ["Pass definitions: change review as in the spec (conflict recall 1, no false conflicts, risk and "
                 "recommendation correct). Domain Q&A: escalation correct and, when it should answer, a gold source, the "
                 "key facts and the question's language. Retrieval: a gold chunk in the top 4 and no scope leak. Intake: "
                 "every constraint and gap group found and nothing invented.", ""]


def write_run_report(result, name):
    """One run's report, kept under eval/reports/ as the numbered iteration history."""
    path = EVAL / "reports" / f"{name}.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join([f"# {name}", "", f"Definitions and targets: `eval/SPEC.md`. Commit `{result['meta']['commit']}`.", "",
                               *REPORT_HEADER, *run_section(result)]), encoding="utf-8")
    return path


def write_report():
    latest = {}
    for f in sorted(RESULTS.glob("*.json")):
        res = json.loads(f.read_text(encoding="utf-8"))
        latest[(res["meta"]["split"], res["meta"]["mode"])] = res
    L = ["# Mayl evaluation report", "",
         "Auto-generated by `scripts/run_eval.py` from the latest result of each split and mode in `eval/results/`. "
         "Definitions and targets: `eval/SPEC.md`. Do not edit by hand.", "", *REPORT_HEADER]
    for key in sorted(latest, key=lambda k: (k[1] != "live", k[0])):
        L += run_section(latest[key])
    (EVAL / "eval_report.md").write_text("\n".join(L), encoding="utf-8")


# --- main ----------------------------------------------------------------------------------------
def select(cases, args):
    kinds = args.kinds.split(",")
    pools = [[(k, c) for c in cases[k] if args.split == "all" or c["split"] == args.split] for k in KINDS if k in kinds]
    if not args.limit:
        return [x for pool in pools for x in pool]
    chosen, i = [], 0  # round-robin across kinds, so a small run samples every kind
    while len(chosen) < args.limit and any(i < len(p) for p in pools):
        chosen += [p[i] for p in pools if i < len(p)][: args.limit - len(chosen)]
        i += 1
    return chosen


def estimate(selected, repeats, model):
    tin = tout = 0
    for kind, c in selected:
        a, b = ESTIMATE[kind]
        if c.get("setup") == "intake_confirm":
            a, b = a + TRIAGE_SETUP[0], b + TRIAGE_SETUP[1]
        tin, tout = tin + a, tout + b
    return cost(tin * repeats, tout * repeats, model)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", choices=["dev", "heldout", "all"], default="dev")
    ap.add_argument("--mode", choices=["demo", "live"], default="demo")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--kinds", default=",".join(KINDS))
    ap.add_argument("--limit", type=int, default=0, help="max cases, taken round-robin across kinds")
    ap.add_argument("--max-usd", type=float, default=2.0)
    ap.add_argument("--judge-model", default=None, help="defaults to the app's CLAUDE_MODEL")
    ap.add_argument("--keep-seed", action="store_true", help="keep the seeded ppe bottleneck review in each session")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--report-name", help="also save this run's report as eval/reports/<name>.md, e.g. 01_dev_baseline")
    args = ap.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.report_only:
        write_report(); print(f"Wrote {EVAL / 'eval_report.md'}"); return

    os.environ["AGENT_MODE"] = "demo" if args.mode == "demo" else "auto"
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    from app import llm, main as app_main, rag

    rag.register_knowledge_dir("retail", EVAL / "knowledge" / "retail")
    for k in app_main.LIVE_LIMITS:  # eval runs only: no per-session live budget
        app_main.LIVE_LIMITS[k] = 10**9
    args.judge_model = args.judge_model or llm.MODEL
    if args.mode == "live":
        if not llm.enabled():
            sys.exit("Live mode needs ANTHROPIC_API_KEY (backend/.env).")
        if llm.MODEL not in PRICES or args.judge_model not in PRICES:
            sys.exit(f"No price for {llm.MODEL} / {args.judge_model}; add it to PRICES.")

    cases = load_cases()
    from app.products import build_products
    problems = validate(cases, {**build_products(), "retail": retail_product()}, rag)
    for p in problems:
        print("CASE PROBLEM:", p)
    selected = select(cases, args)
    if args.mode == "live":
        est = estimate(selected, args.repeats, llm.MODEL)
        print(f"Plan: {len(selected)} cases x {args.repeats} repeat(s), live on {llm.MODEL}. Estimated cost: ${est:.2f} (max ${args.max_usd:.2f})")
        if est > args.max_usd:
            sys.exit("Estimated cost is over --max-usd. Lower --limit/--repeats or raise --max-usd.")
    else:
        print(f"Plan: {len(selected)} cases x {args.repeats} repeat(s), demo agents (no API calls).")

    usage = Usage(llm.client()) if args.mode == "live" else None
    runner = Runner(args, app_main, rag, usage)
    rows, spent = [], 0.0
    for rep in range(args.repeats):
        for kind, case in selected:
            try:
                s = getattr(runner, kind)(case)
            except Exception as e:  # a crash is a failed case, not a dead run
                s = {"pass": False, "fail_reasons": [f"error: {type(e).__name__}: {e}"[:300]], "error": True,
                     "fallback": False, "latency_s": 0, "llm_calls": 0, "tokens_in": 0, "tokens_out": 0}
                for key in ("conflict_hits", "conflict_total", "false_conflicts", "teams_f1", "mrr", "constraint_hits",
                            "constraint_total", "gap_hits", "gap_total"):
                    s.setdefault(key, 0)
                s.update({"fake_citations": [], "scope_leaks": [], "invented": [], "escalated": False,
                          "should_escalate": case.get("gold", {}).get("should_escalate", False) if isinstance(case.get("gold"), dict) else False,
                          "answered_when_should_escalate": False, "recommendation": None})
            tin = s["tokens_in"] + s.get("setup_tokens_in", 0) + s.get("judge_tokens_in", 0)
            tout = s["tokens_out"] + s.get("setup_tokens_out", 0) + s.get("judge_tokens_out", 0)
            s["cost_usd"] = round(cost(tin, tout, llm.MODEL), 5) if args.mode == "live" else 0.0
            spent += s["cost_usd"]
            rows.append({"id": case["id"], "kind": kind, "repeat": rep, "split": case["split"], "product": case["product"],
                         "tags": case.get("tags", [])} | s)
            print(f"[{rep + 1}/{args.repeats}] {case['id']:12} {'PASS' if s['pass'] else 'fail'}  "
                  f"{s['latency_s']:6.1f}s  ${s['cost_usd']:.4f}  {'; '.join(s['fail_reasons'])[:110]}")
            if spent > args.max_usd:
                print(f"Stopping: spent ${spent:.2f}, over --max-usd ${args.max_usd:.2f}.")
                break
        else:
            continue
        break

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = RESULTS / f"{stamp}_{args.split}_{args.mode}.json"
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BACKEND, capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ""
    meta = {"timestamp": stamp, "split": args.split, "mode": args.mode, "repeats": args.repeats,
            "kinds": args.kinds.split(","), "limit": args.limit, "model": llm.MODEL, "judge_model": args.judge_model,
            "keep_seed": args.keep_seed, "commit": commit, "prices_per_mtok": PRICES.get(llm.MODEL),
            "validation": problems, "file": f"eval/results/{out.name}", "total_cost_usd": round(spent, 4)}
    result = {"meta": meta, "summary": summarize(rows, max(r["repeat"] for r in rows) + 1 if rows else 1, args.mode == "live"),
              "cases": rows}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    write_report()
    print(f"\nWrote {out}\nWrote {EVAL / 'eval_report.md'}")
    if args.report_name:
        print(f"Wrote {write_run_report(result, args.report_name)}")
    print(f"Total cost: ${spent:.4f}")


if __name__ == "__main__":
    main()
