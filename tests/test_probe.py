import json
from collections import Counter
from pathlib import Path

from nightshift.chunk import chunk_messages
from nightshift.parse import parse_export
from nightshift.probe import find_chunk, load_probes, report, run_probe, summarise
from nightshift.recheck import missing_numbers
from nightshift.verify import quote_in_source

ROOT = Path(__file__).parent.parent
CHUNKS = chunk_messages(parse_export((ROOT / "demo" / "demo_chat.txt").read_text(encoding="utf-8")))
PROBES = load_probes(ROOT / "demo" / "probe_items.json")


def answer(verdict):
    return lambda prompt: json.dumps({"verdict": verdict, "reason": "r"})


def test_probe_set_is_well_formed_and_balanced():
    assert len({p["id"] for p in PROBES}) == len(PROBES)
    for p in PROBES:
        assert {"id", "day", "kind", "text", "quote", "expected", "label"} <= p.keys()
        assert p["expected"] in ("supported", "unsupported")
        assert (p["label"] == "control") == (p["expected"] == "supported")
    c = Counter(p["expected"] for p in PROBES)
    assert c["supported"] >= 5 and c["unsupported"] >= 10


def test_every_probe_quote_is_really_in_its_days_chat():
    for p in PROBES:
        assert quote_in_source(p["quote"], find_chunk(CHUNKS, p).source), p["id"]


def test_probes_test_what_their_label_says():
    """wrong_number probes must fail the number check; every other probe must pass it, so that
    the model (not the number check) is what is being tested."""
    for p in PROBES:
        missing = missing_numbers(p["text"], find_chunk(CHUNKS, p))
        if p["label"] == "wrong_number":
            assert missing, p["id"]
        else:
            assert not missing, (p["id"], missing)


def test_model_that_flags_everything_catches_all_wrong_but_false_alarms_on_controls():
    s = summarise(run_probe(CHUNKS, PROBES, answer("unsupported"), log=lambda *_: None))
    assert s["wrong_caught"] == s["wrong"] and s["false_alarms"] == s["controls"]


def test_model_that_approves_everything_still_gets_the_number_check_catches():
    s = summarise(run_probe(CHUNKS, PROBES, answer("supported"), log=lambda *_: None))
    assert s["number_check_caught"] == s["number_check_total"] > 0
    assert s["model_only_caught"] == 0 and s["model_only_called_supported"] == s["model_only_total"]
    assert s["controls_supported"] == s["controls"] and s["false_alarms"] == 0


def test_unclear_does_not_count_as_a_catch_or_a_false_alarm():
    s = summarise(run_probe(CHUNKS, PROBES, answer("unclear"), log=lambda *_: None))
    assert s["model_only_caught"] == 0 and s["model_only_called_unclear"] == s["model_only_total"]
    assert s["controls_unclear"] == s["controls"] and s["false_alarms"] == 0


def test_ok_flag_and_report_text():
    rows = run_probe(CHUNKS, PROBES, answer("supported"), log=lambda *_: None)
    assert all(r["ok"] for r in rows if r["expected"] == "supported")
    assert not any(r["ok"] for r in rows if r["expected"] == "unsupported" and r["by"] == "model")
    text = report(summarise(rows))
    assert "number check alone" in text and "false alarm" in text and "By kind of error" in text


def test_find_chunk_rejects_a_quote_that_is_not_in_the_chat():
    bad = {**PROBES[0], "quote": "ข้อความที่ไม่มีอยู่จริง"}
    try:
        find_chunk(CHUNKS, bad)
    except ValueError as e:
        assert "quote not found" in str(e)
    else:
        raise AssertionError("expected ValueError")
