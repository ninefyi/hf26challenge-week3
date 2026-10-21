"""Remove secrets and identifying details from messages before anything else sees them.

This runs right after parsing, so the model, the files in work/, the review page and the
digest only ever contain the redacted text. Each replacement is a bracketed placeholder
such as [EMAIL] or [CODE]; the original is never written anywhere.

What it catches, in this order:
  email      name@domain, with or without a .com ending (a bare @mention is left alone)
  url        http(s):// and www. links, kept as [URL:domain] so the topic survives
  term       words listed in the terms file (names, clients, employers), case-insensitive
  phone      Thai and international phone numbers
  number     any run of 9 or more digits (ID cards, bank and card numbers)
  code       a word of 10+ letters and digits mixing both (vouchers, tokens), XXXX-XXXX-XXXX
             style keys, and the value after "password:", "code", "token", "otp", "รหัส"
Optionally, sender names (and their mentions inside messages) become Person A, Person B...

It is a safety net, not a guarantee. Check what the model will see with
`run.py --preview FILE` and add anything it missed to the terms file.
"""
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from .parse import Message

_PLACEHOLDER = re.compile(r"\[(?:EMAIL|URL(?::[^\]]*)?|REDACTED|PHONE|NUMBER|CODE)\]")
_ASCII_EDGE_BEFORE = r"(?<![A-Za-z0-9])"
_ASCII_EDGE_AFTER = r"(?![A-Za-z0-9])"

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*")
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]]+", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+?66[\s-]?|0)\d{1,2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)")
_LONG_DIGITS = re.compile(r"(?<!\d)\d(?:[ -]?\d){8,}(?!\d)")
_MIXED_CODE = re.compile(
    _ASCII_EDGE_BEFORE + r"(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{10,}" + _ASCII_EDGE_AFTER
)
_DASHED_KEY = re.compile(
    _ASCII_EDGE_BEFORE + r"[A-Z0-9]{4,}(?:-[A-Z0-9]{4,}){2,}" + _ASCII_EDGE_AFTER
)
_KEYWORD_VALUE = re.compile(
    r"(?i)(\b(?:voucher|code|password|passcode|pwd|token|otp|pin)\b|รหัส[\u0E00-\u0E7F]{0,8}|พาสเวิร์ด)"
    r"(\s*[:=]?\s*(?:is\s+|คือ\s*)?)"
    r"(?=[A-Za-z0-9_!@#$%^&*\-]*[\d!@#$%^&*])([A-Za-z0-9_!@#$%^&*\-]{6,})"
)


def _sub_outside(pattern: re.Pattern, repl, text: str) -> tuple[str, int]:
    """Apply a substitution, leaving earlier placeholders untouched."""
    parts, last, total = [], 0, 0
    for m in _PLACEHOLDER.finditer(text):
        seg, n = pattern.subn(repl, text[last : m.start()])
        parts += [seg, m.group(0)]
        total += n
        last = m.end()
    seg, n = pattern.subn(repl, text[last:])
    parts.append(seg)
    return "".join(parts), total + n


def _domain(url: str) -> str:
    u = url if "//" in url else "//" + url
    host = (urlparse(u).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return host.rstrip(".,;:!?)")


def _term_pattern(term: str) -> re.Pattern:
    body = re.escape(term)
    if re.match(r"[A-Za-z0-9]", term):
        body = _ASCII_EDGE_BEFORE + body
    if re.search(r"[A-Za-z0-9]$", term):
        body += _ASCII_EDGE_AFTER
    return re.compile(body, re.IGNORECASE)


def load_terms(path: str | Path) -> list[str]:
    """One term per line; blank lines and lines starting with # are ignored."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [t for t in (ln.strip() for ln in lines) if t and not t.startswith("#")]


def redact_text(text: str, terms: list[str] | tuple[str, ...] = ()) -> tuple[str, Counter]:
    counts: Counter = Counter()

    def run(kind: str, pattern: re.Pattern, repl) -> None:
        nonlocal text
        text, n = _sub_outside(pattern, repl, text)
        if n:
            counts[kind] += n

    run("email", _EMAIL, "[EMAIL]")
    run("url", _URL, lambda m: f"[URL:{_domain(m.group(0))}]" if _domain(m.group(0)) else "[URL]")
    for term in sorted(set(terms), key=len, reverse=True):
        run("term", _term_pattern(term), "[REDACTED]")
    run("phone", _PHONE, "[PHONE]")
    run("number", _LONG_DIGITS, "[NUMBER]")
    run("code", _KEYWORD_VALUE, lambda m: f"{m.group(1)}{m.group(2)}[CODE]")
    run("code", _DASHED_KEY, "[CODE]")
    run("code", _MIXED_CODE, "[CODE]")
    return text, counts


def _alias(i: int) -> str:
    letters = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        letters = chr(65 + r) + letters
    return f"Person {letters}"


def redact_messages(
    messages: list[Message],
    terms: list[str] | tuple[str, ...] = (),
    anonymise_senders: bool = False,
) -> tuple[list[Message], Counter]:
    """Redacted copies of the messages and a count per kind (never the redacted text itself)."""
    aliases: dict[str, str] = {}
    if anonymise_senders:
        for m in messages:
            aliases.setdefault(m.sender, _alias(len(aliases)))
    # Longest names first so "Ann Lee" is replaced before "Ann".
    names = sorted(aliases, key=len, reverse=True)

    total: Counter = Counter()
    out = []
    for m in messages:
        text, counts = redact_text(m.text, terms)
        total.update(counts)
        sender = m.sender
        if anonymise_senders:
            for n in names:
                text, k = _sub_outside(_term_pattern(n), aliases[n], text)
                if k:
                    total["sender"] += k
            sender = aliases[m.sender]
        out.append(Message(m.when, sender, text))
    return out, total


def summary(counts: Counter) -> str:
    return ", ".join(f"{n} {kind}" for kind, n in sorted(counts.items())) or "nothing"
