"""
Parses txt, vtt and srt transcripts into a normalized list of utterances.

Each utterance: {"speaker": str | None, "text": str, "start": str | None}

Supported txt conventions (checked in order):
  "[00:01:23] Priya: some text"
  "Priya: some text"
  plain lines with no speaker label (speaker=None)
"""
import re

TXT_TIMESTAMPED = re.compile(r"^\s*\[?(?P<ts>\d{1,2}:\d{2}(:\d{2})?)\]?\s*(?P<speaker>[^:]{1,40}):\s*(?P<text>.+)$")
TXT_SPEAKER_ONLY = re.compile(r"^\s*(?P<speaker>[A-Za-z][A-Za-z .'-]{0,39}):\s*(?P<text>.+)$")

VTT_TIME = re.compile(r"(?P<start>\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[.,]\d{3})")
VTT_SPEAKER_TAG = re.compile(r"^<v\s+([^>]+)>(.*)$")

SRT_INDEX = re.compile(r"^\d+$")
SRT_TIME = re.compile(r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})")


def parse_txt(content: str) -> list[dict]:
    utterances = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        m = TXT_TIMESTAMPED.match(line)
        if m:
            utterances.append({"speaker": m.group("speaker").strip(), "text": m.group("text").strip(), "start": m.group("ts")})
            continue
        m = TXT_SPEAKER_ONLY.match(line)
        if m:
            utterances.append({"speaker": m.group("speaker").strip(), "text": m.group("text").strip(), "start": None})
            continue
        utterances.append({"speaker": None, "text": line, "start": None})
    return utterances


def parse_vtt(content: str) -> list[dict]:
    utterances = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip() and l.strip().upper() != "WEBVTT"]
        if not lines:
            continue
        start_ts = None
        text_lines = []
        for l in lines:
            tmatch = VTT_TIME.search(l)
            if tmatch:
                start_ts = tmatch.group("start")
                continue
            if re.match(r"^\d+$", l.strip()):
                continue
            text_lines.append(l.strip())
        if not text_lines:
            continue
        text = " ".join(text_lines)
        speaker = None
        vmatch = VTT_SPEAKER_TAG.match(text)
        if vmatch:
            speaker = vmatch.group(1).strip()
            text = vmatch.group(2).strip()
        else:
            m = TXT_SPEAKER_ONLY.match(text)
            if m:
                speaker = m.group("speaker").strip()
                text = m.group("text").strip()
        utterances.append({"speaker": speaker, "text": text, "start": start_ts})
    return utterances


def parse_srt(content: str) -> list[dict]:
    utterances = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        start_ts = None
        text_lines = []
        for l in lines:
            if SRT_INDEX.match(l.strip()):
                continue
            tmatch = SRT_TIME.search(l)
            if tmatch:
                start_ts = tmatch.group("start")
                continue
            text_lines.append(l.strip())
        if not text_lines:
            continue
        text = " ".join(text_lines)
        speaker = None
        m = TXT_SPEAKER_ONLY.match(text)
        if m:
            speaker = m.group("speaker").strip()
            text = m.group("text").strip()
        utterances.append({"speaker": speaker, "text": text, "start": start_ts})
    return utterances


def ingest(filename: str, content: str) -> list[dict]:
    lower = filename.lower()
    if lower.endswith(".vtt"):
        return parse_vtt(content)
    if lower.endswith(".srt"):
        return parse_srt(content)
    if lower.endswith(".txt"):
        return parse_txt(content)
    raise ValueError(f"Unsupported transcript format: {filename}. Use .txt, .vtt or .srt (audio/video ingestion is not wired up in this MVP).")


def to_plain_transcript(utterances: list[dict]) -> str:
    """Render utterances back into a single speaker-labelled text block for the LLM prompt."""
    lines = []
    for u in utterances:
        prefix = f"[{u['start']}] " if u.get("start") else ""
        speaker = u.get("speaker") or "Unknown"
        lines.append(f"{prefix}{speaker}: {u['text']}")
    return "\n".join(lines)
