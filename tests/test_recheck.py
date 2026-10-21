import json
from datetime import datetime

from nightshift.chunk import chunk_messages
from nightshift.digest import item_key, render
from nightshift.parse import Message
from nightshift.queue import Queue, run
from nightshift.recheck import check_item, check_items, missing_numbers, numbers_in
from nightshift.review import set_verdict, tally
from nightshift.summarise import summarise_chunk


def day(*texts, d=1):
    msgs = [Message(datetime(2026, 10, d, 9, i), "A", t) for i, t in enumerate(texts)]
    return chunk_messages(msgs)[0]


def verdict_llm(verdict, reason="ok"):
    return lambda prompt: json.dumps({"verdict": verdict, "reason": reason})


def test_numbers_normalise_thai_digits_and_commas():
    assert numbers_in("มัดจำ ๑,๐๐๐ บาท วันที่ 28-29") == {"1000", "28", "29"}
    assert numbers_in("เวลา 9.30", parts=True) == {"9.30", "9", "30"}


def test_missing_numbers_flags_invented_figures_only():
    c = day("ตกลงวันที่ 28 ถึง 29 มัดจำ 1,000 บาท นัด 9.30")
    assert missing_numbers("เดินทาง 28-29 มัดจำ 1000 บาท", c) == []
    assert missing_numbers("นัด 9:30", c) == []  # 9 and 30 are both in the chat
    assert missing_numbers("มัดจำ 1,500 บาท วันที่ 31", c) == ["1500", "31"]


def test_day_year_is_exempt_but_other_years_are_not():
    c = day("ไปเที่ยวเดือนหน้า")
    assert missing_numbers("ทริปปี 2026 หรือ 2569", c) == []
    assert missing_numbers("ทริปปี 2030", c) == ["2030"]


def test_invented_number_is_unsupported_without_calling_the_model():
    def boom(prompt):
        raise AssertionError("model must not be called")

    chk = check_item(day("มัดจำ 1,000 บาท"), {"kind": "point", "text": "มัดจำ 1,500 บาท", "quote": "มัดจำ"}, boom)
    assert chk["verdict"] == "unsupported" and chk["by"] == "numbers" and "1500" in chk["reason"]


def test_model_verdict_is_used_and_prompt_has_chat_and_item():
    seen = []

    def llm(prompt):
        seen.append(prompt)
        return json.dumps({"verdict": "supported", "reason": "said so"})

    chk = check_item(day("ตกลงไปวันศุกร์"), {"kind": "decision", "text": "ไปวันศุกร์", "quote": "ไปวันศุกร์"}, llm)
    assert chk == {"verdict": "supported", "by": "model", "reason": "said so"}
    assert "ตกลงไปวันศุกร์" in seen[0] and "kind: decision" in seen[0]


def test_bad_json_is_retried_then_becomes_unclear_not_a_failure():
    replies = iter(["nope", '{"verdict": "maybe"}', '{"verdict": "supported", "reason": "r"}'])
    item = {"kind": "point", "text": "x", "quote": "ข้อความ"}
    assert check_item(day("ข้อความ"), item, lambda p: next(replies))["verdict"] == "supported"
    chk = check_item(day("ข้อความ"), item, lambda p: "nope")
    assert chk["verdict"] == "unclear" and "no usable answer" in chk["reason"]


def test_model_errors_propagate_so_the_chunk_is_retried_later():
    def down(prompt):
        raise ConnectionError("ollama down")

    try:
        check_item(day("ข้อความ"), {"kind": "point", "text": "x", "quote": "ข้อความ"}, down)
    except ConnectionError:
        pass
    else:
        raise AssertionError("expected ConnectionError")


def test_check_items_adds_a_check_to_every_item():
    items = [{"kind": "point", "text": "a", "quote": "ข้อความ"}, {"kind": "point", "text": "b", "quote": "ข้อความ"}]
    out, secs = check_items(day("ข้อความ"), items, verdict_llm("unclear"))
    assert [i["check"]["verdict"] for i in out] == ["unclear", "unclear"] and secs >= 0
    assert "check" not in items[0]  # inputs untouched


def test_summarise_chunk_runs_second_pass_only_when_given_a_checker():
    c = day("ตกลงไปวันศุกร์")
    first = lambda p: json.dumps({"items": [{"kind": "decision", "text": "ไปวันศุกร์", "quote": "ไปวันศุกร์"}]})
    plain = summarise_chunk(c, first)
    assert plain["verified"] is False and "check" not in plain["items"][0]
    checked = summarise_chunk(c, first, verdict_llm("unsupported", "not agreed"))
    assert checked["verified"] is True and checked["items"][0]["check"]["verdict"] == "unsupported"


RESULTS = [{"id": "2026-10-01-01", "day": "2026-10-01", "dropped": [], "items": [
    {"kind": "decision", "text": "Go Friday", "quote": "q1", "check": {"verdict": "supported", "reason": "", "by": "model"}},
    {"kind": "point", "text": "Pay 1,500", "quote": "q2", "check": {"verdict": "unsupported", "reason": "no", "by": "numbers"}},
    {"kind": "question", "text": "Who drives?", "quote": "q3", "check": {"verdict": "unclear", "reason": "", "by": "model"}},
]}]
K = [item_key("2026-10-01-01", i) for i in range(3)]


def test_digest_leaves_out_unsupported_unless_the_author_keeps_it():
    md = render(RESULTS)
    assert "Go Friday" in md and "Who drives?" in md and "Pay 1,500" not in md
    kept = render(RESULTS, {"verdicts": {K[1]: "keep"}, "edits": {}, "confirmed": False})
    assert "Pay 1,500" in kept
    wrong = render(RESULTS, {"verdicts": {K[0]: "wrong"}, "edits": {}, "confirmed": False})
    assert "Go Friday" not in wrong


def test_second_pass_agreement_with_the_author(tmp_path):
    from nightshift.digest import load_review

    set_verdict(tmp_path, K[0], "wrong")   # second pass said supported: a miss
    set_verdict(tmp_path, K[1], "wrong")   # flagged and wrong: right
    set_verdict(tmp_path, K[2], "keep")
    sp = tally(RESULTS, load_review(tmp_path))["second_pass"]
    assert sp == {"checked": 3, "flagged": 1, "flag_right": 1, "false_alarms": 0, "missed_wrong": 1}
    set_verdict(tmp_path, K[1], "keep")    # now the flag was a false alarm
    sp = tally(RESULTS, load_review(tmp_path))["second_pass"]
    assert sp["flag_right"] == 0 and sp["false_alarms"] == 1


def test_tally_without_second_pass_reports_zero_checked():
    plain = [{"id": "2026-10-01-01", "day": "2026-10-01", "dropped": [],
              "items": [{"kind": "point", "text": "a", "quote": "q"}]}]
    assert tally(plain)["second_pass"]["checked"] == 0


def test_changing_second_pass_setting_makes_old_results_stale(tmp_path):
    q = Queue(tmp_path)
    calls = []

    def summarise(c):
        calls.append(1)
        return {"id": c.id, "day": c.day, "items": [], "dropped": [], "seconds": 0}

    cs = [day("ข้อความ")]
    run(cs, summarise, q, salt=":m:second-pass=off", log=lambda *_: None)
    run(cs, summarise, q, salt=":m:second-pass=off", log=lambda *_: None)
    assert len(calls) == 1
    run(cs, summarise, q, salt=":m:second-pass=on", log=lambda *_: None)
    assert len(calls) == 2
