import json
import urllib.request

from app.config import SLACK_WEBHOOK_URL
from app.integrations.base import Integration


class SlackIntegration(Integration):
    name = "slack"

    def post_recap(self, meeting: dict, approved_items: list[dict]) -> str:
        if not SLACK_WEBHOOK_URL:
            raise RuntimeError(
                "SLACK_WEBHOOK_URL is not set. Add a sandbox/test workspace Incoming Webhook URL to .env."
            )

        lines = [f"*Meeting recap — {meeting.get('filename', 'meeting')} ({meeting.get('meeting_date')})*"]
        summary = meeting.get("executive_summary")
        if summary:
            lines.append(f"_{summary}_")
        if approved_items:
            lines.append("\n*Action items:*")
            for it in approved_items:
                owner = it.get("owner_name") or f"UNRESOLVED ({it.get('owner_raw') or 'no owner stated'})"
                due = it.get("due_date_resolved") or "no date"
                lines.append(f"• {it['text']} — *{owner}*, due {due} [{it.get('priority', 'medium')}]")
        else:
            lines.append("\n_No action items were approved this run._")

        payload = {"text": "\n".join(lines)}
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
        if status != 200:
            raise RuntimeError(f"Slack webhook returned status {status}")
        return f"slack:webhook:{meeting['id']}"
