"""Render finished chunk results as a Markdown digest, honouring the review file.

Items the second pass called "unsupported" are left out unless the author keeps them.
The review file holds the author's verdict per item (keep / edit / wrong), reworded
text for edited items, and whether the digest is confirmed. Wrong items are left out.
"""
import json
import os
from pathlib import Path

HEADINGS = {"decision": "Decisions", "question": "Open questions", "point": "Points"}
REVIEW_FILE = "review.json"


def item_key(chunk_id: str, index: int) -> str:
    return f"{chunk_id}#{index}"


def load_review(work_dir: str | Path) -> dict:
    p = Path(work_dir) / REVIEW_FILE
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return empty_review()


def empty_review() -> dict:
    return {"verdicts": {}, "edits": {}, "confirmed": False}


def save_review(work_dir: str | Path, review: dict) -> None:
    path = Path(work_dir) / REVIEW_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)  # a reader never sees a half-written file


def render(results: list[dict], review: dict | None = None) -> str:
    review = review or empty_review()
    rejected = {k for k, v in review["verdicts"].items() if v == "wrong"}
    for r in results:  # the second pass's "unsupported" holds unless the author keeps the item
        for i, it in enumerate(r["items"]):
            key = item_key(r["id"], i)
            if it.get("check", {}).get("verdict") == "unsupported" and review["verdicts"].get(key) not in ("keep", "edit"):
                rejected.add(key)
    status = "Reviewed" if review["confirmed"] else "Draft, not yet reviewed"
    lines = [f"# Chat digest ({status})", ""]
    by_day: dict[str, list[tuple[str, dict]]] = {}
    for r in results:
        for i, it in enumerate(r["items"]):
            key = item_key(r["id"], i)
            if key not in rejected:
                text = review["edits"].get(key) or it["text"]
                by_day.setdefault(r["day"], []).append((r["id"], {**it, "text": text}))
    if not by_day:
        lines.append("Nothing to report.")
    for day in sorted(by_day):
        lines += [f"## {day}", ""]
        for kind, heading in HEADINGS.items():
            rows = [it for _, it in by_day[day] if it["kind"] == kind]
            if rows:
                lines += [f"### {heading}", ""]
                for it in rows:
                    lines += [f"- {it['text']}", f"  > {it['quote']}"]
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"
