"""Thin Claude wrapper: a tool-using agent loop with a structured final answer.

Every agent ends by calling a `submit` tool whose schema we define, so the
platform always gets structured, validated output instead of free text.
"""
import json
import logging
import os

log = logging.getLogger("relay.llm")
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
_client = None


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


def run_agent(system: str, prompt: str, tools: list[dict], handlers: dict, submit_schema: dict,
              max_steps: int = 5, max_tokens: int = 1500) -> tuple[dict, list[dict]]:
    """Run a tool-use loop until the agent calls `submit`. Returns (result, trace)."""
    submit = {"name": "submit", "description": "Submit your final structured answer. Call exactly once, at the end.",
              "input_schema": submit_schema}
    all_tools = tools + [submit]
    messages = [{"role": "user", "content": prompt}]
    trace = []
    for step in range(max_steps):
        last = step == max_steps - 1
        resp = client().messages.create(
            model=MODEL, max_tokens=max_tokens, system=system, tools=all_tools, messages=messages,
            tool_choice={"type": "tool", "name": "submit"} if last else {"type": "auto"},
        )
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
        if results:
            messages.append({"role": "user", "content": results})
        else:
            messages.append({"role": "user", "content": "Now call the submit tool with your final answer."})
    raise RuntimeError("Agent did not submit an answer")
