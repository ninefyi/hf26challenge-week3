"""A planted-error test for the second pass.

Feeds the second pass items whose answer is known: correct ones (controls) and ones made
wrong on purpose, then counts what it flagged. "0 flagged" on a real run cannot tell a model
that found nothing wrong from one that cannot find anything; this can.

The probes are tied to demo/demo_chat.txt, which is fabricated. A probe is only fair if its
quote really is in that day's chat, and if its label says how it can be caught (a number that
is not in the chat, or a claim only a re-read can judge); tests/test_probe.py checks both.
"""
import json
from collections import defaultdict
from pathlib import Path

from .chunk import Chunk
from .recheck import check_item
from .verify import quote_in_source

NUMBER_LABEL = "wrong_number"  # the only label the number check can catch; the rest need the model


def load_probes(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_chunk(chunks: list[Chunk], probe: dict) -> Chunk:
    """The chunk of the probe's day whose messages contain its quote."""
    for c in chunks:
        if c.day == probe["day"] and quote_in_source(probe["quote"], c.source):
            return c
    raise ValueError(f"probe {probe['id']}: quote not found in the chat for {probe['day']}")


def run_probe(chunks: list[Chunk], probes: list[dict], llm, log=print) -> list[dict]:
    """One row per probe. `ok` means the second pass did the right thing: flagged a wrong
    item, or did not flag a correct one."""
    rows = []
    for p in probes:
        chunk = find_chunk(chunks, p)
        chk = check_item(chunk, {"kind": p["kind"], "text": p["text"], "quote": p["quote"]}, llm)
        flagged = chk["verdict"] == "unsupported"
        row = {**p, "got": chk["verdict"], "by": chk["by"], "reason": chk["reason"],
               "ok": flagged == (p["expected"] == "unsupported")}
        rows.append(row)
        log(f"{'ok  ' if row['ok'] else 'MISS'} {p['id']:<4} {p['label']:<15} expected {p['expected']:<11} "
            f"got {chk['verdict']:<11} ({chk['by']}) {chk['reason'][:60]}")
    return rows


def summarise(rows: list[dict]) -> dict:
    wrong = [r for r in rows if r["expected"] == "unsupported"]
    controls = [r for r in rows if r["expected"] == "supported"]
    model_only = [r for r in wrong if r["label"] != NUMBER_LABEL]
    by_label: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in wrong:
        by_label[r["label"]][1] += 1
        by_label[r["label"]][0] += r["got"] == "unsupported"
    return {
        "wrong": len(wrong),
        "wrong_caught": sum(r["got"] == "unsupported" for r in wrong),
        "number_check_total": len(wrong) - len(model_only),
        "number_check_caught": sum(r["got"] == "unsupported" for r in wrong if r["label"] == NUMBER_LABEL),
        "model_only_total": len(model_only),
        "model_only_caught": sum(r["got"] == "unsupported" for r in model_only),
        "model_only_called_unclear": sum(r["got"] == "unclear" for r in model_only),
        "model_only_called_supported": sum(r["got"] == "supported" for r in model_only),
        "controls": len(controls),
        "controls_supported": sum(r["got"] == "supported" for r in controls),
        "controls_unclear": sum(r["got"] == "unclear" for r in controls),
        "false_alarms": sum(r["got"] == "unsupported" for r in controls),
        "by_label": {k: tuple(v) for k, v in by_label.items()},
    }


def report(s: dict) -> str:
    lines = [
        f"Wrong items flagged: {s['wrong_caught']} of {s['wrong']}",
        f"  number check alone (no model): {s['number_check_caught']} of {s['number_check_total']}",
        f"  needing the model re-read:     {s['model_only_caught']} of {s['model_only_total']} "
        f"(called unclear {s['model_only_called_unclear']}, called supported {s['model_only_called_supported']})",
        f"Correct items: {s['controls_supported']} of {s['controls']} called supported, "
        f"{s['controls_unclear']} unclear, {s['false_alarms']} false alarm(s)",
        "By kind of error:",
    ]
    lines += [f"  {k:<16} {c} of {n}" for k, (c, n) in sorted(s["by_label"].items())]
    lines.append(f"Probes are fabricated ({s['wrong'] + s['controls']} in all): a sanity check, not a benchmark.")
    return "\n".join(lines)
