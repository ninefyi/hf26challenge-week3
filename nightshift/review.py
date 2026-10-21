"""Review logic behind the Gradio page: verdicts, edits, confirm, and the tally for EVAL.md.

Kept free of Gradio so it can be tested. Every change is written to the review file
at once, so closing the browser loses nothing.
"""
from .digest import empty_review, item_key, load_review, save_review

VERDICTS = ("keep", "edit", "wrong")


def items_for_review(results: list[dict]) -> list[dict]:
    """Flat list of items in digest order: key, day, kind, text, quote."""
    out = []
    for r in sorted(results, key=lambda r: r["id"]):
        for i, it in enumerate(r["items"]):
            out.append({"key": item_key(r["id"], i), "day": r["day"], **it})
    return out


def set_verdict(work_dir, key: str, verdict: str | None) -> None:
    review = load_review(work_dir)
    if verdict in VERDICTS:
        review["verdicts"][key] = verdict
    else:
        review["verdicts"].pop(key, None)
    review["confirmed"] = False  # any change reopens the review
    save_review(work_dir, review)


def set_text(work_dir, key: str, original: str, text: str) -> None:
    """Store reworded text, or clear it when it is empty or unchanged. Marks the item 'edit'."""
    review = load_review(work_dir)
    text = text.strip()
    if text and text != original:
        review["edits"][key] = text
        if review["verdicts"].get(key) in (None, "keep"):
            review["verdicts"][key] = "edit"
    else:
        review["edits"].pop(key, None)
    review["confirmed"] = False
    save_review(work_dir, review)


def unjudged_by_day(results: list[dict], review: dict | None = None) -> dict[str, int]:
    """Days that still have items without a verdict, with how many (the page shows one day at a time)."""
    review = review or empty_review()
    out: dict[str, int] = {}
    for it in items_for_review(results):
        if it["key"] not in review["verdicts"]:
            out[it["day"]] = out.get(it["day"], 0) + 1
    return dict(sorted(out.items()))


def tally(results: list[dict], review: dict | None = None) -> dict:
    """Counts for the evaluation. Rates are over judged items; None until something is judged."""
    review = review or empty_review()
    items = items_for_review(results)
    counts = {v: 0 for v in VERDICTS}
    for it in items:
        v = review["verdicts"].get(it["key"])
        if v in counts:
            counts[v] += 1
    judged = sum(counts.values())
    # Did the second pass agree with the author? Only items the author judged are compared.
    sp = {"checked": 0, "flagged": 0, "flag_right": 0, "false_alarms": 0, "missed_wrong": 0}
    for it in items:
        verdict = (it.get("check") or {}).get("verdict")
        if verdict is None:
            continue
        sp["checked"] += 1
        sp["flagged"] += verdict == "unsupported"
        author = review["verdicts"].get(it["key"])
        if verdict == "unsupported" and author == "wrong":
            sp["flag_right"] += 1
        elif verdict == "unsupported" and author in ("keep", "edit"):
            sp["false_alarms"] += 1
        elif verdict != "unsupported" and author == "wrong":
            sp["missed_wrong"] += 1
    dropped = sum(len(r["dropped"]) for r in results)
    total_model = len(items) + dropped
    return {
        "items": len(items),
        "judged": judged,
        "unjudged": len(items) - judged,
        **counts,
        "keep_rate": counts["keep"] / judged if judged else None,
        "wrong_rate": counts["wrong"] / judged if judged else None,
        "dropped_by_quote_check": dropped,
        "dropped_share": dropped / total_model if total_model else None,
        "seconds": round(sum(r.get("seconds", 0) for r in results), 1),
        "verify_seconds": round(sum(r.get("verify_seconds", 0) for r in results), 1),
        "second_pass": sp,
        "chunks": len(results),
    }


def confirm(work_dir, results: list[dict]) -> str:
    """Mark the digest reviewed. Refused while any item has no verdict. Returns a message."""
    t = tally(results, load_review(work_dir))
    if t["unjudged"]:
        return f"{t['unjudged']} item(s) still have no verdict."
    review = load_review(work_dir)
    review["confirmed"] = True
    save_review(work_dir, review)
    return "Confirmed."
