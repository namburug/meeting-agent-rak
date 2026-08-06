"""
Resolves an extracted owner name (as spoken in the meeting) to a real identity
from the roster. Fails loudly (returns None + needs_owner=True) rather than
guessing when there's no confident match.
"""
import difflib
import json
import re

from app.config import ROSTER_PATH

_CLOSE_MATCH_CUTOFF = 0.72


def load_roster() -> list[dict]:
    try:
        with open(ROSTER_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def resolve_owner(owner_raw: str | None, roster: list[dict] | None = None) -> dict:
    """
    Returns {"matched": bool, "name": str|None, "email": str|None, "slack_id": str|None, "raw": owner_raw}
    """
    result = {"matched": False, "name": None, "email": None, "slack_id": None, "raw": owner_raw}
    if not owner_raw:
        return result

    roster = roster if roster is not None else load_roster()
    if not roster:
        return result

    target = _normalize(owner_raw)

    # exact / alias match first
    for person in roster:
        candidates = [person["name"]] + person.get("aliases", [])
        for c in candidates:
            if _normalize(c) == target:
                return {
                    "matched": True,
                    "name": person["name"],
                    "email": person.get("email"),
                    "slack_id": person.get("slack_id"),
                    "raw": owner_raw,
                }

    # fuzzy match fallback
    all_candidates = {}
    for person in roster:
        for c in [person["name"]] + person.get("aliases", []):
            all_candidates[_normalize(c)] = person

    matches = difflib.get_close_matches(target, all_candidates.keys(), n=1, cutoff=_CLOSE_MATCH_CUTOFF)
    if matches:
        person = all_candidates[matches[0]]
        return {
            "matched": True,
            "name": person["name"],
            "email": person.get("email"),
            "slack_id": person.get("slack_id"),
            "raw": owner_raw,
        }

    return result
