import json
import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.config import SLACK_WEBHOOK_URL
from app.integrations.slack import SlackIntegration
from app.pipeline.orchestrator import process_meeting
from app.schemas import ApproveRejectBody, FinalizeBody, ItemUpdate

app = FastAPI(title="Agentic Meeting Assistant")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@app.on_event("startup")
def startup():
    db.init_db()


def _meeting_out(meeting: dict) -> dict:
    items = db.get_items_for_meeting(meeting["id"])
    return {
        "id": meeting["id"],
        "filename": meeting["filename"],
        "meeting_date": meeting["meeting_date"],
        "executive_summary": meeting["executive_summary"],
        "decisions": json.loads(meeting["decisions_json"]),
        "open_questions": json.loads(meeting["open_questions_json"]),
        "risks": json.loads(meeting["risks_json"]),
        "action_items": items,
    }


@app.post("/api/meetings")
async def create_meeting(file: UploadFile = File(...), meeting_date: str = Form(...)):
    content = (await file.read()).decode("utf-8", errors="replace")
    try:
        result = process_meeting(file.filename, content, meeting_date)
    except RuntimeError as e:
        # Missing/misconfigured API key for the selected LLM_PROVIDER.
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # Network errors / provider API errors (anthropic, openai, google all raise their
        # own exception types here) — surfaced as a clean 502 instead of a raw traceback.
        raise HTTPException(status_code=502, detail=f"LLM provider call failed: {e}")

    meeting = db.get_meeting(result["meeting_id"])
    out = _meeting_out(meeting)
    out["duplicate"] = result["duplicate"]
    return out


@app.get("/api/meetings")
def list_meetings():
    return db.list_meetings()


@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: str):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return _meeting_out(meeting)


@app.patch("/api/items/{item_id}")
def edit_item(item_id: str, body: ItemUpdate):
    item = db.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if fields:
        db.update_item(item_id, fields)
        db.log_audit(item["meeting_id"], "item_edited", fields, actor="human:demo-user", item_id=item_id)
    return db.get_item(item_id)


@app.post("/api/items/{item_id}/approve")
def approve_item(item_id: str, body: ApproveRejectBody):
    item = db.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.update_item(item_id, {"status": "approved"})
    db.log_audit(item["meeting_id"], "item_approved", {}, actor=body.actor, item_id=item_id)
    return db.get_item(item_id)


@app.post("/api/items/{item_id}/reject")
def reject_item(item_id: str, body: ApproveRejectBody):
    item = db.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.update_item(item_id, {"status": "rejected"})
    db.log_audit(item["meeting_id"], "item_rejected", {}, actor=body.actor, item_id=item_id)
    return db.get_item(item_id)


@app.post("/api/meetings/{meeting_id}/finalize")
def finalize_meeting(meeting_id: str, body: FinalizeBody):
    """
    Fires the side effect (Slack recap) for approved items only, and only for
    items that don't already have an external_ref — this is what makes
    re-running finalize on the same meeting a no-op instead of a duplicate post.
    """
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    items = db.get_items_for_meeting(meeting_id)
    approved = [i for i in items if i["status"] == "approved"]
    pending_side_effect = [i for i in approved if not i["external_ref"]]

    if not pending_side_effect:
        db.log_audit(meeting_id, "finalize_skipped_duplicate", {"reason": "no approved items without external_ref"}, actor=body.actor)
        return {"status": "no_op", "reason": "All approved items already have a side effect recorded. Nothing to do."}

    if not SLACK_WEBHOOK_URL:
        raise HTTPException(status_code=400, detail="SLACK_WEBHOOK_URL is not set in .env — add a sandbox Slack Incoming Webhook to enable the side effect.")

    integration = SlackIntegration()
    meeting_out = _meeting_out(meeting)
    try:
        ref = integration.post_recap(meeting_out, pending_side_effect)
    except Exception as e:
        db.log_audit(meeting_id, "finalize_failed", {"error": str(e)}, actor=body.actor)
        raise HTTPException(status_code=502, detail=f"Slack post failed: {e}")

    for item in pending_side_effect:
        db.update_item(item["id"], {"external_ref": ref})
        db.log_audit(meeting_id, "created_slack_recap_item", {"external_ref": ref}, actor=body.actor, item_id=item["id"])

    db.log_audit(meeting_id, "finalize_completed", {"external_ref": ref, "items_sent": len(pending_side_effect)}, actor=body.actor)
    return {"status": "ok", "external_ref": ref, "items_sent": len(pending_side_effect)}


@app.get("/api/meetings/{meeting_id}/audit")
def audit_log(meeting_id: str):
    return db.get_audit_log(meeting_id)


# Static single-page UI
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
