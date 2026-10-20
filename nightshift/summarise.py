"""Ask the local model for the points, decisions and open questions in one chunk.

`llm` is any callable taking a prompt and returning a JSON string, so tests can pass
a fake. `ollama_llm` is the real one. Every item must carry a quote; items whose
quote is not in the chunk are dropped (see verify.py).
"""
import json
import time

from .chunk import Chunk
from .verify import split_items

MODEL = "gemma3:12b"
KINDS = ("point", "decision", "question")
RETRIES = 2

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "text": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["kind", "text", "quote"],
            },
        }
    },
    "required": ["items"],
}

PROMPT = """You read one day of a group chat and write a short digest for someone who was not there.

Return JSON with a list "items". Each item has:
- "kind": "decision" (the group agreed or settled something), "question" (asked and not answered in this text), or "point" (other news worth knowing).
- "text": one short sentence in the language of the chat.
- "quote": a few words copied EXACTLY, character for character, from ONE message that supports the item. Never translate or fix it.

Rules:
- Skip greetings, jokes, stickers and small talk. If nothing matters, return {{"items": []}}.
- Use only what the messages say. Do not add names, dates or numbers that are not in them.
- At most 8 items.

Chat ({day}):
{chat}
"""


def ollama_llm(model: str = MODEL):
    import ollama

    def call(prompt: str) -> str:
        reply = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=SCHEMA,
            options={"temperature": 0},
        )
        return reply["message"]["content"]

    return call


def _parse(raw: str) -> list[dict]:
    data = json.loads(raw)
    items = []
    for it in data["items"]:
        if it.get("kind") in KINDS and str(it.get("text", "")).strip():
            items.append(
                {"kind": it["kind"], "text": str(it["text"]).strip(), "quote": str(it.get("quote", "")).strip()}
            )
    return items


def summarise_chunk(chunk: Chunk, llm) -> dict:
    """One chunk -> result dict. Raises if the model never returns usable JSON."""
    prompt = PROMPT.format(day=chunk.day, chat=chunk.text)
    started = time.monotonic()
    last: Exception | None = None
    for attempt in range(1, RETRIES + 2):
        try:
            items = _parse(llm(prompt))
        except (ValueError, KeyError, TypeError) as e:  # bad JSON or wrong shape
            last = e
            continue
        kept, dropped = split_items(items, chunk.source)
        return {
            "id": chunk.id,
            "day": chunk.day,
            "messages": len(chunk.messages),
            "items": kept,
            "dropped": dropped,
            "attempts": attempt,
            "seconds": round(time.monotonic() - started, 1),
        }
    raise ValueError(f"no usable JSON for {chunk.id} after {RETRIES + 1} tries: {last}")
