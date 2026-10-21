"""The second pass: re-read the day's chat and judge every kept item, one item at a time.

The quote check (verify.py) proves the quoted words exist. This pass asks the harder
question: does the item say what the messages say, and nothing more? Two checks, cheapest first:

  numbers  every number in the item must appear in the day's messages (no model needed)
  model    the model re-reads the whole day and answers supported / unsupported / unclear

Each item gets a `check` = {"verdict", "reason", "by"}. Items judged "unsupported" are left
out of the digest unless the author keeps them in the review page; nothing is deleted, so
the author can see what the second pass flagged and whether it was right.
"""
import json
import re
import time

from .chunk import Chunk

VERDICTS = ("supported", "unsupported", "unclear")
RETRIES = 2

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
}

PROMPT = """You check one line of a chat digest against the chat it came from. Be strict.

Chat ({day}):
{chat}

Digest line:
kind: {kind}
text: {text}
quote: {quote}

Decide:
- "supported": the messages clearly say what the line says, and nothing more.
- "unsupported": the messages do not say it, say something different, or the line adds a name, date, number, place or who-did-what that the messages do not state. Also use this if a question the line calls open is answered later in the chat, or a decision the line reports was not actually agreed.
- "unclear": you cannot tell.

Return JSON: {{"verdict": "...", "reason": "one short sentence"}}.
"""

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def numbers_in(text: str, parts: bool = False) -> set[str]:
    """Numbers as plain digit strings: Thai digits converted, thousands commas removed.

    With parts=True a decimal such as "9.30" also yields its pieces "9" and "30".
    """
    found = set()
    for n in _NUMBER.findall(text.translate(_THAI_DIGITS)):
        n = n.replace(",", "")
        found.add(n)
        if parts:
            found.update(n.split("."))
    return found


def missing_numbers(item_text: str, chunk: Chunk) -> list[str]:
    """Numbers the item states that the day's messages never do (the day's own year is exempt)."""
    year = int(chunk.day[:4])
    exempt = {str(year), str(year + 543)}
    have = numbers_in(chunk.source, parts=True)
    return sorted(
        n for n in numbers_in(item_text)
        if n not in exempt and n not in have and not all(p in have for p in n.split("."))
    )


def check_item(chunk: Chunk, item: dict, llm) -> dict:
    """Judge one item. Raises only if the model itself fails (for example Ollama is down)."""
    missing = missing_numbers(item["text"], chunk)
    if missing:
        return {"verdict": "unsupported", "by": "numbers",
                "reason": f"number(s) not in the chat: {', '.join(missing)}"}
    prompt = PROMPT.format(day=chunk.day, chat=chunk.text, kind=item["kind"], text=item["text"], quote=item["quote"])
    for _ in range(RETRIES + 1):
        try:
            data = json.loads(llm(prompt))
            if data["verdict"] in VERDICTS:
                return {"verdict": data["verdict"], "by": "model", "reason": str(data.get("reason", "")).strip()}
        except (ValueError, KeyError, TypeError):
            pass
    return {"verdict": "unclear", "by": "model", "reason": "the second pass gave no usable answer"}


def check_items(chunk: Chunk, items: list[dict], llm) -> tuple[list[dict], float]:
    """Items with a `check` added, and the seconds the pass took."""
    started = time.monotonic()
    out = [{**it, "check": check_item(chunk, it, llm)} for it in items]
    return out, round(time.monotonic() - started, 1)
