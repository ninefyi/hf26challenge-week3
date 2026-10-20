from datetime import datetime

from nightshift.chunk import chunk_messages
from nightshift.parse import Message
from nightshift.verify import norm, quote_in_source, split_items


def msg(day, hhmm, text, sender="A"):
    h, m = map(int, hhmm.split(":"))
    return Message(datetime(2026, 10, day, h, m), sender, text)


def test_chunks_never_span_days_and_ids_are_stable():
    chunks = chunk_messages([msg(1, "09:00", "a"), msg(2, "09:00", "b"), msg(1, "10:00", "c")])
    assert [c.id for c in chunks] == ["2026-10-01-01", "2026-10-02-01"]
    assert [m.text for m in chunks[0].messages] == ["a", "c"]


def test_long_day_is_cut_between_messages():
    msgs = [msg(1, "09:00", "x" * 50) for _ in range(5)]
    chunks = chunk_messages(msgs, max_chars=130)
    assert len(chunks) > 1
    assert sum(len(c.messages) for c in chunks) == 5
    assert [c.id for c in chunks] == [f"2026-10-01-{i:02d}" for i in range(1, len(chunks) + 1)]


def test_oversized_single_message_is_its_own_chunk():
    chunks = chunk_messages([msg(1, "09:00", "x" * 500), msg(1, "09:01", "y")], max_chars=100)
    assert len(chunks) == 2 and len(chunks[0].messages) == 1


def test_chunk_text_has_sender_source_does_not():
    c = chunk_messages([msg(1, "09:05", "hello", sender="Pim")])[0]
    assert c.text == "09:05 Pim: hello"
    assert c.source == "hello"


def test_empty_input():
    assert chunk_messages([]) == []


def test_quote_must_match_exactly_apart_from_spacing_and_case():
    src = "ตกลงวันที่ 28 ถึง 29 พฤศจิกายนนะ"
    assert quote_in_source("วันที่ 28 ถึง 29", src)
    assert quote_in_source("วันที่28ถึง29", src)  # Thai has no spaces
    assert not quote_in_source("วันที่ 28 ถึง 30", src)
    assert quote_in_source("HELLO  world", "say hello world")


def test_empty_quote_never_passes():
    assert not quote_in_source("", "anything")
    assert not quote_in_source("  ​ ", "anything")


def test_norm_applies_unicode_normalisation():
    assert norm("é") == norm("é")


def test_split_items_keeps_and_reports_dropped():
    items = [{"quote": "real words"}, {"quote": "invented"}, {}]
    kept, dropped = split_items(items, "some real words here")
    assert kept == [{"quote": "real words"}]
    assert len(dropped) == 2
