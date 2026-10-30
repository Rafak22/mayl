"""Thin Claude wrapper: a tool-using agent loop with a structured final answer.

Agents with tools end by calling a `submit` tool whose schema we define; agents
without tools answer through structured outputs. Either way the platform gets
validated JSON instead of free text. Current models (e.g. Sonnet 5.5) reject a
forced `tool_choice`, so the loop steers with `auto`, strict schemas and a
nudge instead.
"""
import copy
import json
import logging
import os

log = logging.getLogger("mayl.llm")
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
_client = None

# Strict schemas accept no numeric, string-length or array-size constraints; the code enforces those itself.
_UNSUPPORTED = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
                "minLength", "maxLength", "minItems", "maxItems"}


def enabled() -> bool:
    """Live mode needs a key; AGENT_MODE=demo forces the deterministic agents."""
    return _client is not None or (bool(os.getenv("ANTHROPIC_API_KEY")) and os.getenv("AGENT_MODE", "auto") != "demo")


def set_client(client):  # used by tests to inject a fake Claude
    global _client
    _client = client


def client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(timeout=45, max_retries=1)
    return _client


def strict_schema(schema: dict) -> dict:
    """Copy of `schema` that strict tools / structured outputs accept."""
    def clean(node):
        if isinstance(node, list):
            return [clean(n) for n in node]
        if not isinstance(node, dict):
            return node
        out = {k: clean(v) for k, v in node.items() if k not in _UNSUPPORTED}
        if out.get("type") == "object":
            out["additionalProperties"] = False
        return out
    return clean(copy.deepcopy(schema))


def _check(resp):
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"Claude stopped early: {resp.stop_reason}")


def run_agent(system: str, prompt: str, tools: list[dict], handlers: dict, submit_schema: dict,
              max_steps: int = 5, max_tokens: int = 8000) -> tuple[dict, list[dict]]:
    """Run until the agent submits. Returns (result, trace of tool calls).

    max_tokens is a ceiling, not a cost; it must leave room for thinking, which counts toward it."""
    messages = [{"role": "user", "content": prompt}]
    if not tools:  # a single structured answer: structured outputs guarantee valid JSON
        resp = client().messages.create(
            model=MODEL, max_tokens=max_tokens, system=system, messages=messages,
            output_config={"format": {"type": "json_schema", "schema": strict_schema(submit_schema)}})
        _check(resp)
        return json.loads(next(b.text for b in resp.content if b.type == "text")), []

    submit = {"name": "submit", "description": "Submit your final structured answer. Call exactly once, at the end.",
              "input_schema": submit_schema}
    all_tools = [{**t, "input_schema": strict_schema(t["input_schema"]), "strict": True} for t in tools + [submit]]
    trace = []
    for step in range(max_steps):
        resp = client().messages.create(model=MODEL, max_tokens=max_tokens, system=system, tools=all_tools,
                                        messages=messages, tool_choice={"type": "auto"})
        _check(resp)
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            if block.name == "submit":
                return dict(block.input), trace
            try:
                out = handlers[block.name](**(block.input or {}))
            except Exception as e:  # tool errors go back to the agent, not the user
                out = {"error": str(e)}
            trace.append({"tool": block.name, "input": block.input})
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": json.dumps(out, ensure_ascii=False)[:8000]})
        last_turn_next = step == max_steps - 2
        if results:
            if last_turn_next:
                results.append({"type": "text", "text": "This is your last turn: call the submit tool now."})
            messages.append({"role": "user", "content": results})
        else:
            messages.append({"role": "user", "content": "Now call the submit tool with your final answer."})
    raise RuntimeError("Agent did not submit an answer")
