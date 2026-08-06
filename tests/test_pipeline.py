import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.pipeline.dates import resolve_due_date
from app.pipeline.ingest import parse_srt, parse_txt, parse_vtt
from app.pipeline.resolve_owners import resolve_owner

ROSTER = [
    {"name": "Priya Sharma", "aliases": ["Priya"], "email": "priya@example.com", "slack_id": "U1"},
    {"name": "Rahul Nair", "aliases": ["Rahul"], "email": "rahul@example.com", "slack_id": "U2"},
]


def test_parse_txt_with_timestamp():
    content = "[00:01:23] Priya: We should ship Friday."
    out = parse_txt(content)
    assert out[0]["speaker"] == "Priya"
    assert out[0]["start"] == "00:01:23"
    assert "ship Friday" in out[0]["text"]


def test_parse_txt_speaker_only():
    out = parse_txt("Rahul: I'll do the migration.")
    assert out[0]["speaker"] == "Rahul"


def test_parse_srt():
    srt = "1\n00:00:01,000 --> 00:00:04,000\nPriya: hello team\n"
    out = parse_srt(srt)
    assert out[0]["speaker"] == "Priya"
    assert out[0]["start"] == "00:00:01,000"


def test_parse_vtt():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\n<v Priya>hello team\n"
    out = parse_vtt(vtt)
    assert out[0]["speaker"] == "Priya"


def test_resolve_owner_exact():
    r = resolve_owner("Priya", ROSTER)
    assert r["matched"] is True
    assert r["name"] == "Priya Sharma"


def test_resolve_owner_unmatched_fails_loudly():
    r = resolve_owner("Someone Unknown", ROSTER)
    assert r["matched"] is False
    assert r["name"] is None


def test_resolve_owner_none_input():
    r = resolve_owner(None, ROSTER)
    assert r["matched"] is False


def test_resolve_due_date_end_of_quarter():
    d = resolve_due_date("end of the quarter", "2026-08-06")
    assert d == "2026-09-30"


def test_resolve_due_date_relative():
    d = resolve_due_date("tomorrow", "2026-08-06")
    assert d == "2026-08-07"


def test_resolve_due_date_none():
    assert resolve_due_date(None, "2026-08-06") is None


def test_resolve_due_date_next_friday():
    # 2026-08-06 is a Thursday; "next Friday" -> the very next day.
    assert resolve_due_date("next Friday", "2026-08-06") == "2026-08-07"
    assert resolve_due_date("by next Friday", "2026-08-06") == "2026-08-07"


def test_resolve_due_date_eod():
    assert resolve_due_date("end of day today", "2026-08-06") == "2026-08-06"
    assert resolve_due_date("EOD", "2026-08-06") == "2026-08-06"


def test_resolve_due_date_end_of_month():
    assert resolve_due_date("end of the month", "2026-08-06") == "2026-08-31"


def test_resolve_due_date_in_n_days():
    assert resolve_due_date("in 3 days", "2026-08-06") == "2026-08-09"
    assert resolve_due_date("in 2 weeks", "2026-08-06") == "2026-08-20"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
