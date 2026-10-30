from pathlib import Path

from dotenv import load_dotenv

# backend/.env (gitignored) holds local secrets such as ANTHROPIC_API_KEY.
# Real environment variables win, so hosting and tests can override it.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
