# Agentic AI Meeting Assistant

Built for TechBharat Cohort #2 Buildathon — Use Case B.

Ingests a meeting transcript, produces a structured record (summary, decisions,
open questions, risks), extracts action items with owners/dates/priority/confidence,
puts them in front of a human for review, and only then fires a real side effect
(a Slack recap). Nothing is created, sent or posted without explicit approval.

## Quickstart (local, no Docker)

Requires Python 3.10+.

```bash
git clone <this-repo-url>
cd meeting-agent
./run.sh
```

`run.sh` creates a virtualenv, installs dependencies, copies `.env.example` to
`.env` on first run, and starts the server. Open **http://localhost:8000**.

Before processing a real meeting, edit `.env`:

```
LLM_PROVIDER=anthropic             # anthropic | openai | google — pick whichever key you have
ANTHROPIC_API_KEY=sk-ant-...       # fill in the key for whichever provider you picked above
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...   # optional — needed only to finalize/send
```

The extraction step (structured record + action items) works with any of the
three providers — set `LLM_PROVIDER` and fill in the matching API key
(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GOOGLE_API_KEY`); the other two
can stay blank. See `app/pipeline/extract.py` if you want to point the model
name env vars (`ANTHROPIC_MODEL` / `OPENAI_MODEL` / `GOOGLE_MODEL`) at a
different model.

Get a free Slack Incoming Webhook by creating a **sandbox/test workspace**
(Slack → create workspace → Apps → Incoming Webhooks). Do not point this at a
production workspace, per the brief's constraints.

If the API key for the selected `LLM_PROVIDER` is missing, the server still
boots — the upload endpoint returns a clear 400 error instead of crashing.

## Quickstart (Docker)

```bash
cp .env.example .env   # then fill in your keys
docker compose up --build
```

Open **http://localhost:8000**.

## Demo flow

1. Open the app, upload `data/sample_transcripts/sample_standup.txt`, set the
   meeting date, click **Process meeting**.
2. Review the structured record and the action item table. Edit an owner or
   date inline, click **Save**. Approve most items, reject a weak one.
3. Click **Finalize & send approved items to Slack** — check your sandbox
   Slack channel for the recap.
4. Re-upload the exact same file — the app reports it as a duplicate and does
   not create a second meeting or re-post to Slack.
5. Scroll to the audit log — every extraction, edit, approval, rejection and
   Slack post is timestamped with who did it.

This mirrors the buildathon's suggested demo narrative.

## How it maps to the brief's requirements

| Requirement | Where |
|---|---|
| Ingest txt/vtt/srt | `app/pipeline/ingest.py` |
| Speaker attribution | Parsed from transcript labels (`Speaker: text`); diarization for raw audio is out of scope for this MVP — see Limitations |
| Structured meeting record | `app/pipeline/extract.py` (LLM call — Anthropic/OpenAI/Google, configurable via `LLM_PROVIDER`; strict JSON schema) |
| Action items w/ owner, date, priority, confidence | `extract.py` + `app/pipeline/resolve_owners.py` + `app/pipeline/dates.py` |
| Relative date resolution anchored to meeting date | `app/pipeline/dates.py` (uses `dateparser` with `RELATIVE_BASE`) |
| Owner resolution, fails loudly | `resolve_owners.py` — unmatched owners are flagged `unresolved` in the UI and never silently guessed |
| Real side effect via integration | `app/integrations/slack.py` (Incoming Webhook recap) |
| Human-in-the-loop review, editable/rejectable | `app/static/index.html` + `app/static/app.js`, gated by `/api/items/*/approve|reject` |
| Idempotency | `app/db.py::hash_transcript` — re-processing the same file returns the existing meeting; `finalize` only sends items without an `external_ref` |
| Audit log | `audit_log` table, `/api/meetings/{id}/audit` |

## Evaluating against a gold transcript

At kickoff you'll get a gold-labelled transcript. After processing it through
the app, score it:

```bash
python scripts/evaluate.py <meeting_id> data/gold_labels_example.json
```

(`data/gold_labels_example.json` shows the expected format — replace with the
judges' file.) Prints recall, precision, owner accuracy and date resolution
against the targets in the brief.

## Architecture

Single FastAPI process serves both the JSON API and a static vanilla-JS
review page — no separate frontend build step, no Node dependency. Storage is
a single SQLite file (`data/app.db`), so there's nothing else to stand up.

```
transcript file
     │
     ▼
ingest.py (parse speakers/timestamps)
     │
     ▼
extract.py (Claude → structured JSON: summary, decisions, risks, action items)
     │
     ├─► dates.py (resolve relative due dates against meeting date)
     └─► resolve_owners.py (match names to data/roster.json, or flag unresolved)
     │
     ▼
db.py (persist meeting + action items, keyed by transcript hash)
     │
     ▼
review UI (approve / edit / reject each item)
     │
     ▼
finalize → integrations/slack.py (only for approved items without an external_ref yet)
     │
     ▼
audit_log (every step, every actor)
```

## Limitations / stretch goals not implemented

Per the brief's stretch list, not built in this MVP: audio/video transcription
(text/vtt/srt only — you own the transcription step for audio), diarization,
code-switched speech handling, cross-meeting memory, automated pre-due-date
nudges, evidence timestamp deep-links (evidence quotes are captured but not
timestamp-linked), disagreement detection, meeting health analytics, and live
mode. The architecture (`app/integrations/base.py`) is written so a Jira/
Linear/GitHub integration can be dropped in alongside Slack without touching
the API layer.

## Roster

`data/roster.json` is the identity map used for owner resolution — add real
teammates (or your demo team) there before running against the gold
transcript, matching the names that will appear in it.
