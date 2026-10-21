"""Split messages into chunks small enough for one model call.

A chunk never spans two days. A long day is cut between messages; a single message
longer than the limit becomes its own chunk (it is not cut mid-message).
"""
import hashlib
from dataclasses import dataclass

from .parse import Message

MAX_CHARS = 6000


@dataclass(frozen=True)
class Chunk:
    id: str
    day: str
    messages: tuple[Message, ...]

    @property
    def text(self) -> str:
        """What the model reads: one line per message, with the sender."""
        return "\n".join(f"{m.when:%H:%M} {m.sender}: {m.text}" for m in self.messages)

    @property
    def fingerprint(self) -> str:
        """Changes whenever the text the model reads changes (including a change in redaction)."""
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]

    @property
    def source(self) -> str:
        """What a quote is checked against: the message bodies only."""
        return "\n".join(m.text for m in self.messages)


def _size(m: Message) -> int:
    return len(m.sender) + len(m.text) + 8


def chunk_messages(messages: list[Message], max_chars: int = MAX_CHARS) -> list[Chunk]:
    by_day: dict[str, list[Message]] = {}
    for m in messages:
        by_day.setdefault(f"{m.when:%Y-%m-%d}", []).append(m)

    chunks: list[Chunk] = []
    for day in sorted(by_day):
        group: list[Message] = []
        used = 0
        parts: list[list[Message]] = []
        for m in by_day[day]:
            if group and used + _size(m) > max_chars:
                parts.append(group)
                group, used = [], 0
            group.append(m)
            used += _size(m)
        if group:
            parts.append(group)
        for i, part in enumerate(parts, 1):
            chunks.append(Chunk(f"{day}-{i:02d}", day, tuple(part)))
    return chunks
