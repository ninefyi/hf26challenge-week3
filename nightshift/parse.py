"""Parse a LINE .txt chat export into messages.

Date headers are matched loosely (the app and language vary):
  2026.10.19 Monday          2026/10/19 ...          2026-10-19 ...
  Mon, 19/10/2026            (weekday first, day/month/year)
Two message layouts are handled:
  tab layout     HH:MM<TAB>Sender<TAB>text
  space layout   HH:MM Sender text     (names may contain spaces, emoji or symbols)
In the tab layout a line with a time and only one more field is a system message. In the
space layout nothing marks where the name ends, so the names are inferred from the file
(see _detect_senders) and system lines are recognised by their wording.
Either way: lines without a time prefix continue the previous message, media placeholders
(Photos, Stickers, [Sticker], ...) are skipped, and years above 2400 are Buddhist Era.
"""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time

_YMD = re.compile(r"^\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})\b")
_DMY = re.compile(r"^\s*[^\d\s,]+,?\s+(\d{1,2})/(\d{1,2})/(\d{4})\s*$")
_MSG = re.compile(r"^(\d{1,2}):(\d{2})\s*([AaPp][Mm])?\t(.*)$")
_MSG_SPACE = re.compile(r"^(\d{1,2}):(\d{2})(?: ([AaPp][Mm]))? (\S.*)$")
_MEDIA = re.compile(
    r"^\[?(photos?|videos?|stickers?|files?|voice messages?|audio|contacts?|locations?|albums?|"
    r"รูปภาพ|วิดีโอ|สติกเกอร์|ไฟล์|ข้อความเสียง|ตำแหน่ง)\]?$",
    re.IGNORECASE,
)
# Wording of system lines in the space layout (the text after the sender name).
_SYSTEM = re.compile(
    r"(^|\s)(added|removed)\s.+\s(to|from) the group\.?$"
    r"|(^|\s)(joined|left) the group\.?$"
    r"|^Group (voice |video )?call (started|ended)\b"
    r"|\s(changed|updated) the group (name|photo|image)\b"
    r"|\sunsent a message\.?$",
    re.IGNORECASE,
)

MAX_NAME_WORDS = 6
MIN_NAME_SUPPORT = 3


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


def _detect_senders(rests: list[str]) -> list[str]:
    """Infer sender names from the text that follows each time stamp, longest first.

    A name is the longest run of leading words that (nearly) every line starting with its
    first word also starts with: "Ann Lee" if all of Ann Lee's lines begin with both words,
    but only "Bob" if Bob's lines go on in many different ways. A word is added only if at
    least MIN_NAME_SUPPORT lines share it, so a name seen once or twice is read as one word.
    """
    toks = [r.split(" ") for r in rests]
    counts: Counter = Counter()
    for t in toks:
        for k in range(1, min(len(t), MAX_NAME_WORDS) + 1):
            counts[tuple(t[:k])] += 1
    names = set()
    for t in toks:
        k = 1
        limit = min(len(t), MAX_NAME_WORDS)
        while k < limit and counts[tuple(t[: k + 1])] >= max(MIN_NAME_SUPPORT, 0.9 * counts[tuple(t[:k])]):
            k += 1
        names.add(" ".join(t[:k]))
    return sorted(names, key=len, reverse=True)


def _split_sender(rest: str, names: list[str]) -> tuple[str, str]:
    for n in names:
        if rest == n:
            return n, ""
        if rest.startswith(n + " "):
            return n, rest[len(n) + 1 :]
    first, _, text = rest.partition(" ")
    return first, text


def parse_export(raw: str) -> list[Message]:
    """Messages in file order. Media placeholders and system lines are dropped."""
    lines = raw.replace("\r\n", "\n").lstrip("﻿").split("\n")

    space_rests = []
    for line in lines:
        m = _MSG_SPACE.match(line)
        if m and not _MSG.match(line) and _clock(m) is not None:
            space_rests.append(m[4])
    names = _detect_senders(space_rests) if space_rests else []

    out: list[Message] = []
    day: date | None = None
    cur: list | None = None  # [when, sender, [text lines]]

    def flush() -> None:
        nonlocal cur
        if cur:
            text = _unquote("\n".join(cur[2]))
            if text and not _MEDIA.match(text) and not (cur[3] and _SYSTEM.search(text)):
                out.append(Message(cur[0], cur[1], text))
        cur = None

    for line in lines:
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
                    cur = [datetime.combine(day, t), parts[0].strip(), [parts[1]], False]
                continue
        m = _MSG_SPACE.match(line)
        if m and day is not None:
            t = _clock(m)
            if t is not None:
                flush()
                sender, text = _split_sender(m[4], names)
                cur = [datetime.combine(day, t), sender, [text], True]
                continue
        if cur is not None:
            cur[2].append(line)
    flush()
    return out
