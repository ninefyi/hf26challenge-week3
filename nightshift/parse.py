"""Parse the standard LINE .txt chat export into messages.

Handled layouts (the app and language vary, so the date header is matched loosely):
  2026.10.19 Monday          2026/10/19 ...          2026-10-19 ...
  Mon, 19/10/2026            (weekday first, day/month/year)
A message line is  HH:MM<TAB>Sender<TAB>text  (HH:MM may carry AM/PM).
A line with a time and only one more field is a system message and is skipped.
Lines without a time prefix continue the previous message. Years above 2400 are
Buddhist Era and are converted.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime, time

_YMD = re.compile(r"^\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})\b")
_DMY = re.compile(r"^\s*[^\d\s,]+,?\s+(\d{1,2})/(\d{1,2})/(\d{4})\s*$")
_MSG = re.compile(r"^(\d{1,2}):(\d{2})\s*([AaPp][Mm])?\t(.*)$")
_MEDIA = re.compile(
    r"^\[(photo|video|sticker|file|voice message|audio|contact|location|"
    r"รูปภาพ|วิดีโอ|สติกเกอร์|ไฟล์|ข้อความเสียง|ตำแหน่ง)\]$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Message:
    when: datetime
    sender: str
    text: str


def _year(y: int) -> int:
    return y - 543 if y > 2400 else y


def _header_date(line: str) -> date | None:
    m = _YMD.match(line)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
    else:
        m = _DMY.match(line)
        if not m:
            return None
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
    try:
        return date(_year(y), mo, d)
    except ValueError:
        return None


def _clock(m: re.Match) -> time | None:
    h, mi, ampm = int(m[1]), int(m[2]), m[3]
    if ampm:
        h = h % 12 + (12 if ampm.lower() == "pm" else 0)
    if h > 23 or mi > 59:
        return None
    return time(h, mi)


def _unquote(text: str) -> str:
    """LINE wraps a multi-line message in double quotes."""
    text = text.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    return text


def parse_export(raw: str) -> list[Message]:
    """Messages in file order. Media placeholders and system lines are dropped."""
    out: list[Message] = []
    day: date | None = None
    cur: list | None = None  # [when, sender, [text lines]]

    def flush() -> None:
        nonlocal cur
        if cur:
            text = _unquote("\n".join(cur[2]))
            if text and not _MEDIA.match(text):
                out.append(Message(cur[0], cur[1], text))
        cur = None

    for line in raw.replace("\r\n", "\n").lstrip("﻿").split("\n"):
        d = _header_date(line)
        if d is not None:
            flush()
            day = d
            continue
        m = _MSG.match(line)
        if m and day is not None:
            t = _clock(m)
            if t is not None:
                flush()
                parts = m[4].split("\t", 1)
                if len(parts) == 2:  # system messages have no sender field
                    cur = [datetime.combine(day, t), parts[0].strip(), [parts[1]]]
                continue
        if cur is not None:
            cur[2].append(line)
    flush()
    return out
