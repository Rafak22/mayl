import os

# Set before the app loads backend/.env (which never overrides existing variables), so tests can't
# reach the real Claude API. test_live injects a fake client instead.
os.environ["AGENT_MODE"] = "demo"
os.environ["ANTHROPIC_API_KEY"] = ""
