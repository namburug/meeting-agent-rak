"""
Calls an LLM to turn a speaker-labelled transcript into a structured meeting
record with decisions, open questions, risks, and action items.

Provider is configurable via LLM_PROVIDER in .env: anthropic | openai | google.
All three speak the same prompt/schema — only the API call differs. Output is
forced into strict JSON via prompt instructions, parsed, and retried once on
failure regardless of provider.
"""
import json
import re

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    GOOGLE_API_KEY,
    GOOGLE_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)

SYSTEM_PROMPT = """You are a meeting-analysis engine. You read a speaker-labelled meeting \
transcript and output ONLY a single JSON object (no prose, no markdown fences) matching \
this exact schema:

{
  "executive_summary": "2-4 sentence summary of the meeting",
  "decisions": ["decision 1", "decision 2"],
  "open_questions": ["question 1"],
  "risks": ["risk or blocker 1"],
  "action_items": [
    {
      "text": "what needs to be done, phrased as a task",
      "owner_raw": "the name as stated in the transcript, or null if not stated",
      "due_date_raw": "the due date phrase as stated, e.g. 'by next Friday', or null if not stated",
      "priority": "low | medium | high",
      "confidence": 0.0-1.0,
      "evidence": "the closest verbatim quote from the transcript this was extracted from"
    }
  ]
}

Rules:
- Only extract action items that were actually committed to in the meeting. Do not invent tasks.
- If an owner or date was not stated, use null rather than guessing.
- confidence reflects how explicit/unambiguous the commitment was.
- Output must be valid JSON and nothing else.
"""


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    # Strip markdown fences if the model adds them despite instructions.
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return json.loads(raw)


def _call_anthropic(system: str, user: str) -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "LLM_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set. "
            "Add it to .env, or switch LLM_PROVIDER to openai/google."
        )
    from anthropic import Anthropic

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _call_openai(system: str, user: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "LLM_PROVIDER is 'openai' but OPENAI_API_KEY is not set. "
            "Add it to .env, or switch LLM_PROVIDER to anthropic/google."
        )
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


def _call_google(system: str, user: str) -> str:
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "LLM_PROVIDER is 'google' but GOOGLE_API_KEY is not set. "
            "Add it to .env, or switch LLM_PROVIDER to anthropic/openai."
        )
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GOOGLE_API_KEY)
    response = client.models.generate_content(
        model=GOOGLE_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            max_output_tokens=4096,
        ),
    )
    return response.text or ""


_PROVIDERS = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "google": _call_google,
}


def extract_meeting_record(transcript_text: str, meeting_date: str) -> dict:
    call = _PROVIDERS.get(LLM_PROVIDER)
    if call is None:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. Set it to one of: {', '.join(_PROVIDERS)} in .env."
        )

    user_prompt = (
        f"Meeting date: {meeting_date}\n\n"
        f"Transcript:\n{transcript_text}\n\n"
        "Return the JSON object now."
    )

    last_error = None
    for attempt in range(2):
        raw = call(SYSTEM_PROMPT, user_prompt)
        try:
            data = _extract_json(raw)
            data.setdefault("decisions", [])
            data.setdefault("open_questions", [])
            data.setdefault("risks", [])
            data.setdefault("action_items", [])
            return data
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            user_prompt = (
                "Your previous reply was not valid JSON. Reply again with ONLY the JSON object, "
                "no markdown fences, no commentary.\n\n" + user_prompt
            )
    raise RuntimeError(f"Model did not return valid JSON after retry: {last_error}")
