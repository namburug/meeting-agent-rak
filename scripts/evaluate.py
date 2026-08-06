#!/usr/bin/env python3
"""
Scores a processed meeting against a gold-labelled action item list, matching
the metrics table in the buildathon brief (recall, precision, owner accuracy,
date resolution). Run this against the judges' gold transcript at kickoff.

Usage:
  python scripts/evaluate.py <meeting_id> <gold_labels.json>

Matching action items to gold items is done with a simple text-similarity
threshold on the task description — good enough for a demo-time sanity check,
not a substitute for the judges' own scoring.
"""
import difflib
import json
import sys
import urllib.request

API_BASE = "http://localhost:8000"
MATCH_THRESHOLD = 0.55


def fetch_meeting(meeting_id: str) -> dict:
    with urllib.request.urlopen(f"{API_BASE}/api/meetings/{meeting_id}") as resp:
        return json.loads(resp.read())


def similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def evaluate(meeting: dict, gold: dict):
    predicted = meeting["action_items"]
    gold_items = gold["action_items"]

    matched_gold_idx = set()
    matches = []  # (gold_item, predicted_item)

    for p in predicted:
        best_score, best_idx = 0.0, None
        for i, g in enumerate(gold_items):
            if i in matched_gold_idx:
                continue
            score = similar(p["text"], g["text"])
            if score > best_score:
                best_score, best_idx = score, i
        if best_score >= MATCH_THRESHOLD:
            matched_gold_idx.add(best_idx)
            matches.append((gold_items[best_idx], p))

    recall = len(matches) / len(gold_items) if gold_items else 0.0
    precision = len(matches) / len(predicted) if predicted else 0.0

    owner_correct = sum(1 for g, p in matches if (p.get("owner_name") or "").strip().lower() == g["owner"].strip().lower())
    owner_accuracy = owner_correct / len(matches) if matches else 0.0

    date_correct = sum(1 for g, p in matches if p.get("due_date_resolved") == g["due_date"])
    date_accuracy = date_correct / len(matches) if matches else 0.0

    print(f"Gold items:        {len(gold_items)}")
    print(f"Predicted items:   {len(predicted)}")
    print(f"Matched:           {len(matches)}")
    print(f"Recall:            {recall:.0%}  (target: 80%)")
    print(f"Precision:         {precision:.0%}  (target: 75%)")
    print(f"Owner accuracy:    {owner_accuracy:.0%}  (target: 85%)")
    print(f"Date resolution:   {date_accuracy:.0%}  (target: 90%)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    meeting_id, gold_path = sys.argv[1], sys.argv[2]
    with open(gold_path) as f:
        gold = json.load(f)
    meeting = fetch_meeting(meeting_id)
    evaluate(meeting, gold)
