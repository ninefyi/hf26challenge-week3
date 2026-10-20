"""The quote check: an item survives only if its quote is in the source, word for word.

Thai is written without spaces, so whitespace is ignored on both sides, along with
zero-width characters and letter case.
"""
import re
import unicodedata

_STRIP = re.compile(r"[\s​‌‍﻿]+")


def norm(s: str) -> str:
    return _STRIP.sub("", unicodedata.normalize("NFC", s)).casefold()


def quote_in_source(quote: str, source: str) -> bool:
    q = norm(quote)
    return bool(q) and q in norm(source)


def split_items(items: list[dict], source: str) -> tuple[list[dict], list[dict]]:
    """(kept, dropped). Dropped items are returned so the run can report how many."""
    kept, dropped = [], []
    for it in items:
        (kept if quote_in_source(str(it.get("quote", "")), source) else dropped).append(it)
    return kept, dropped
