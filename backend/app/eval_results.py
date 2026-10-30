"""Per-project evaluation results for the Results tab, read from the saved eval runs (no API calls).

For each split (dev = practice, heldout = final exam) and each case kind, the latest full live
run that covered that kind is used. Trial runs with --limit are skipped.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

EVAL = Path(__file__).resolve().parent.parent / "eval"
RESULTS, REPORTS = EVAL / "results", EVAL / "reports"
KINDS = ("change_review", "domain_qa", "retrieval", "intake")
CASE_TEXT = {"change_review": "change", "domain_qa": "question", "retrieval": "query"}


REC = {"approve": "approving", "alternative": "the alternative", "reject": "rejecting", "needs_info": "asking for more detail"}
PLAIN = {"escalated instead of answering": "Handed the question to a human when the documents did answer it",
         "answered instead of escalating": "Answered a question it should have handed to a human",
         "no gold source": "Didn't cite the document that holds the answer",
         "wrong language": "Answered in a different language from the question",
         "no gold chunk in top 4": "The right document wasn't in the top 4 search results"}


def _ids(text):
    return re.findall(r"'([^']+)'", text)


def _explain(reason: str, rules: dict) -> str:
    """Scorer reasons ("missed conflicts ['p-pilot']") as plain sentences."""
    rule = lambda i: f"“{rules[i]}”" if i in rules else i  # noqa: E731
    if reason in PLAIN:
        return PLAIN[reason]
    if m := re.match(r"(missed|false) conflicts (.*)", reason):
        names = ", ".join(map(rule, _ids(m[2])))
        return f"Didn't flag the conflict with {names}" if m[1] == "missed" else f"Flagged {names}, which the change doesn't break"
    if m := re.match(r"(risk|recommendation) (\w+) not in (.*)", reason):
        name = REC if m[1] == "recommendation" else {}
        expected = " or ".join(name.get(x, x) for x in _ids(m[3]))
        return f"{'Recommended' if m[1] == 'recommendation' else 'Rated the risk'} {name.get(m[2], m[2])}; expected {expected}"
    if reason.startswith("facts wrong"):
        return "The answer's key facts were wrong"
    if m := re.match(r"(missed constraints|missed gaps|invented|scope leaks) (.*)", reason):
        label = {"missed constraints": "Missed the constraint", "missed gaps": "Missed the open question about",
                 "invented": "Added a detail not in the documents:", "scope leaks": "Returned another team's documents:"}[m[1]]
        return f"{label} {', '.join(f'“{x}”' for x in _ids(m[2]))}"
    return reason


def _rate(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return round(sum(map(bool, vals)) / len(vals), 3) if vals else None


def _kind_metrics(kind, rows):
    m = {"cases": len({r["id"] for r in rows}), "pass_rate": _rate(rows, "pass")}
    if kind == "change_review":
        total = sum(r["conflict_total"] for r in rows)
        m.update(conflict_recall=round(sum(r["conflict_hits"] for r in rows) / total, 3) if total else None,
                 false_conflicts=sum(r["false_conflicts"] for r in rows),
                 recommendation=_rate(rows, "recommendation_ok"), effort=_rate(rows, "effort_hit"))
    elif kind == "domain_qa":
        m.update(escalation=_rate(rows, "escalation_ok"), facts=_rate(rows, "fact_ok"),
                 made_up=sum(bool(r["answered_when_should_escalate"]) for r in rows))
    elif kind == "retrieval":
        m.update(scope_leaks=sum(len(r["scope_leaks"]) for r in rows))
    return m


@lru_cache(maxsize=1)
def _runs():
    """Full live runs, newest first, each with its report name when one was saved."""
    report_of = {}
    for rep in REPORTS.glob("*.md"):
        for f in re.findall(r"results/([\w-]+\.json)", rep.read_text(encoding="utf-8")):
            report_of.setdefault(f, rep.stem)
    runs = []
    for f in sorted(RESULTS.glob("*_live.json"), reverse=True):
        res = json.loads(f.read_text(encoding="utf-8"))
        if not res["meta"].get("limit"):
            runs.append((res, report_of.get(f.name)))
    return runs


@lru_cache(maxsize=1)
def _case_text():
    out = {}
    for kind, field in CASE_TEXT.items():
        for c in json.loads((EVAL / "cases" / f"{kind}.json").read_text(encoding="utf-8")):
            out[c["id"]] = c[field]
    return out


def project_results(pid: str, rules: list[dict] = ()) -> dict:
    texts, rule_text = _case_text(), {r["id"]: r["text"] for r in rules}
    splits = []
    for split in ("dev", "heldout"):
        kinds, failed = [], {}
        for kind in KINDS:
            run = next(((res, rep) for res, rep in _runs()
                        if res["meta"]["split"] == split and kind in res["meta"]["kinds"]), None)
            if not run:
                continue
            res, report = run
            rows = [r for r in res["cases"] if r["kind"] == kind]
            mine = [r for r in rows if r["product"] == pid]
            if not mine:
                continue
            meta = res["meta"]
            kinds.append({"kind": kind, **_kind_metrics(kind, mine),
                          "all_projects_pass_rate": _rate(rows, "pass"),
                          "run": {"report": report, "date": meta["timestamp"][:8], "commit": meta.get("commit"),
                                  "repeats": meta["repeats"], "model": meta["model"]}})
            for r in mine:
                if not r["pass"] and r["id"] not in failed:
                    failed[r["id"]] = {"id": r["id"], "kind": kind, "text": texts.get(r["id"], ""),
                                       "reasons": [_explain(x, rule_text) for x in r["fail_reasons"]],
                                       "tags": r.get("tags", [])}
        if kinds:
            splits.append({"split": split, "kinds": kinds, "failed": list(failed.values())})
    return {"product": pid, "splits": splits}
