"""
Resolves relative date phrases ("by next Friday", "end of the quarter") into
ISO dates, anchored to the meeting date rather than today's date.

Common meeting phrases (weekday names, "today"/"tomorrow", "EOD") are handled
with explicit logic rather than left to dateparser, because dateparser 1.2.0
unreliably fails on plain phrases like "next Friday" in this environment —
this is exactly the example phrase called out in the brief, so it can't be
left to chance. dateparser is kept as a fallback for anything not covered
below (e.g. absolute dates, "in 3 weeks").
"""
import re
from datetime import date, datetime, timedelta

import dateparser

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _next_weekday(anchor: date, target_idx: int, allow_today: bool) -> date:
    days_ahead = (target_idx - anchor.weekday()) % 7
    if days_ahead == 0 and not allow_today:
        days_ahead = 7
    return anchor + timedelta(days=days_ahead)


def resolve_due_date(due_date_raw: str | None, meeting_date: str) -> str | None:
    if not due_date_raw:
        return None

    anchor_dt = datetime.strptime(meeting_date, "%Y-%m-%d")
    anchor = anchor_dt.date()

    cleaned = due_date_raw.strip().lower()
    cleaned = re.sub(r"^by\s+", "", cleaned).strip()

    # "today" / "tomorrow" / "yesterday"
    if cleaned in ("today", "eod", "end of day", "end of day today", "cod", "close of day"):
        return anchor.isoformat()
    if cleaned in ("tomorrow", "eod tomorrow", "end of day tomorrow"):
        return (anchor + timedelta(days=1)).isoformat()
    if cleaned == "yesterday":
        return (anchor - timedelta(days=1)).isoformat()

    # "next <weekday>" / "this <weekday>" / bare "<weekday>"
    m = re.match(r"^(next|this|coming)?\s*(" + "|".join(WEEKDAYS) + r")$", cleaned)
    if m:
        qualifier, day_name = m.group(1), m.group(2)
        target_idx = WEEKDAYS.index(day_name)
        allow_today = qualifier in (None, "this")
        result = _next_weekday(anchor, target_idx, allow_today=allow_today)
        # "next <weekday>" (with the word "next") always means the occurrence
        # in the following week, even if that weekday hasn't happened yet this week.
        if qualifier == "next" and result == anchor:
            result += timedelta(days=7)
        return result.isoformat()

    # "in N day(s)" / "in N week(s)"
    m = re.match(r"^in\s+(\d+)\s+(day|days|week|weeks)$", cleaned)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = timedelta(days=n) if "day" in unit else timedelta(weeks=n)
        return (anchor + delta).isoformat()

    # Handle "end of the quarter" / "end of quarter" explicitly — dateparser doesn't know this.
    if "end of" in cleaned and "quarter" in cleaned:
        q = (anchor.month - 1) // 3
        quarter_end_month = (q + 1) * 3
        year = anchor.year
        if quarter_end_month == 12:
            result = date(year, 12, 31)
        else:
            next_month_first = date(year, quarter_end_month + 1, 1)
            result = next_month_first - timedelta(days=1)
        return result.isoformat()

    if "end of" in cleaned and ("month" in cleaned):
        year = anchor.year
        month = anchor.month
        if month == 12:
            result = date(year, 12, 31)
        else:
            next_month_first = date(year, month + 1, 1)
            result = next_month_first - timedelta(days=1)
        return result.isoformat()

    if "end of" in cleaned and "week" in cleaned:
        # treat week as ending Sunday
        days_ahead = 6 - anchor.weekday() if anchor.weekday() != 6 else 0
        result = anchor + timedelta(days=days_ahead)
        return result.isoformat()

    parsed = dateparser.parse(
        due_date_raw,
        settings={
            "RELATIVE_BASE": anchor_dt,
            "PREFER_DATES_FROM": "future",
        },
    )
    if parsed:
        return parsed.date().isoformat()
    return None
