"""Render finished chunk results as a Markdown digest, honouring the review file."""
import json
from pathlib import Path

HEADINGS = {"decision": "Decisions", "question": "Open questions", "point": "Points"}
REVIEW_FILE = "review.json"


def item_key(chunk_id: str, index: int) -> str:
    return f"{chunk_id}#{index}"


def load_review(work_dir: str | Path) -> dict:
    p = Path(work_dir) / REVIEW_FILE
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"rejected": [], "confirmed": False}


def save_review(work_dir: str | Path, review: dict) -> None:
    (Path(work_dir) / REVIEW_FILE).write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def render(results: list[dict], review: dict | None = None) -> str:
    review = review or {"rejected": [], "confirmed": False}
    rejected = set(review["rejected"])
    status = "Reviewed" if review["confirmed"] else "Draft, not yet reviewed"
    lines = [f"# Chat digest ({status})", ""]
    by_day: dict[str, list[tuple[str, dict]]] = {}
    for r in results:
        for i, it in enumerate(r["items"]):
            if item_key(r["id"], i) not in rejected:
                by_day.setdefault(r["day"], []).append((r["id"], it))
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
