import os
from dotenv import load_dotenv

load_dotenv()

# Which LLM does the extraction step (structured record + action items).
# One of: anthropic | openai | google
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/app.db")
ROSTER_PATH = os.getenv("ROSTER_PATH", "./data/roster.json")
