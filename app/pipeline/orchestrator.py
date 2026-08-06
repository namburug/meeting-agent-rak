"""
Ties the pipeline together: ingest -> extract -> resolve dates/owners -> persist.
Idempotent at the transcript-content level: re-processing an identical file
returns the existing meeting instead of creating a duplicate.
"""
import uuid

from app import db
from app.pipeline.dates import resolve_due_date
from app.pipeline.extract import extract_meeting_record
from app.pipeline.ingest import ingest, to_plain_transcript
from app.pipeline.resolve_owners import load_roster, resolve_owner


def process_meeting(filename: str, content: str, meeting_date: str) -> dict:
    transcript_hash = db.hash_transcript(content)
    existing = db.find_meeting_by_hash(transcript_hash)
    if existing:
        return {"meeting_id": existing["id"], "duplicate": True}

    utterances = ingest(filename, content)
    transcript_text = to_plain_transcript(utterances)

    record = extract_meeting_record(transcript_text, meeting_date)

    meeting_id = str(uuid.uuid4())
    db.insert_meeting(meeting_id, filename, meeting_date, transcript_hash, record)
    db.log_audit(meeting_id, "extracted", {"num_action_items": len(record.get("action_items", []))}, actor="agent")

    roster = load_roster()
    for raw_item in record.get("action_items", []):
        owner_res = resolve_owner(raw_item.get("owner_raw"), roster)
        due_resolved = resolve_due_date(raw_item.get("due_date_raw"), meeting_date)

        item_id = str(uuid.uuid4())
        db.insert_action_item(item_id, meeting_id, {
            "text": raw_item.get("text", ""),
            "owner_raw": raw_item.get("owner_raw"),
            "owner_name": owner_res["name"],
            "owner_email": owner_res["email"],
            "owner_slack_id": owner_res["slack_id"],
            "owner_matched": owner_res["matched"],
            "due_date_raw": raw_item.get("due_date_raw"),
            "due_date_resolved": due_resolved,
            "priority": raw_item.get("priority", "medium"),
            "confidence": raw_item.get("confidence", 0.5),
            "evidence": raw_item.get("evidence", ""),
        })
        db.log_audit(
            meeting_id, "item_extracted",
            {"text": raw_item.get("text"), "owner_matched": owner_res["matched"], "due_date_resolved": due_resolved},
            actor="agent", item_id=item_id,
        )
        if not owner_res["matched"] and raw_item.get("owner_raw"):
            db.log_audit(meeting_id, "owner_resolution_failed", {"owner_raw": raw_item.get("owner_raw")}, actor="agent", item_id=item_id)

    return {"meeting_id": meeting_id, "duplicate": False}
