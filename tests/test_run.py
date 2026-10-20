import json
from datetime import datetime

from nightshift.chunk import chunk_messages
from nightshift.digest import item_key, render
from nightshift.parse import Message
from nightshift.queue import MAX_CONSECUTIVE_FAILURES, Queue, run
from nightshift.summarise import summarise_chunk


def chunks(n):
    msgs = [Message(datetime(2026, 10, d, 9, 0), "A", f"message number {d}") for d in range(1, n + 1)]
    return chunk_messages(msgs)


def fake_llm(items):
    return lambda prompt: json.dumps({"items": items})


def test_summarise_keeps_quoted_items_and_drops_invented_ones():
    c = chunks(1)[0]
    llm = fake_llm([
        {"kind": "decision", "text": "ok", "quote": "message number 1"},
        {"kind": "point", "text": "made up", "quote": "never said"},
    ])
    r = summarise_chunk(c, llm)
    assert [i["text"] for i in r["items"]] == ["ok"]
    assert len(r["dropped"]) == 1 and r["attempts"] == 1


def test_summarise_retries_bad_json_then_succeeds():
    replies = iter(["not json", '{"wrong": 1}', json.dumps({"items": []})])
    r = summarise_chunk(chunks(1)[0], lambda p: next(replies))
    assert r["items"] == [] and r["attempts"] == 3


def test_summarise_gives_up_after_retries():
    try:
        summarise_chunk(chunks(1)[0], lambda p: "nope")
    except ValueError as e:
        assert "no usable JSON" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_unknown_kind_is_ignored():
    r = summarise_chunk(chunks(1)[0], fake_llm([{"kind": "gossip", "text": "x", "quote": "message"}]))
    assert r["items"] == []


def test_run_resumes_without_redoing_finished_chunks(tmp_path):
    cs = chunks(4)
    q = Queue(tmp_path)
    calls = []

    def summarise(c):
        calls.append(c.id)
        return {"id": c.id, "day": c.day, "items": [], "dropped": [], "seconds": 0.0}

    first = run(cs, summarise, q, max_chunks=2, log=lambda *_: None)
    assert first.done == 2 and first.remaining == 2 and "max-chunks" in first.stopped
    second = run(cs, summarise, Queue(tmp_path), log=lambda *_: None)
    assert second.skipped == 2 and second.done == 2 and second.remaining == 0
    assert calls == [c.id for c in cs]  # each chunk summarised exactly once


def test_run_stops_at_stop_time(tmp_path):
    clock = iter([datetime(2026, 10, 1, 5, 0), datetime(2026, 10, 1, 7, 0)])
    rep = run(chunks(3), lambda c: {"id": c.id, "day": c.day, "items": [], "dropped": [], "seconds": 0},
              Queue(tmp_path), until=datetime(2026, 10, 1, 6, 0), now=lambda: next(clock), log=lambda *_: None)
    assert rep.done == 1 and rep.remaining == 2 and "stop time" in rep.stopped


def test_failed_chunk_is_not_saved_and_is_retried_next_run(tmp_path):
    cs = chunks(2)
    q = Queue(tmp_path)

    def flaky(c):
        if c.id == cs[0].id:
            raise RuntimeError("ollama down")
        return {"id": c.id, "day": c.day, "items": [], "dropped": [], "seconds": 0}

    rep = run(cs, flaky, q, log=lambda *_: None)
    assert rep.failed == [cs[0].id] and rep.done == 1 and not q.done(cs[0].id)
    rep2 = run(cs, lambda c: {"id": c.id, "day": c.day, "items": [], "dropped": [], "seconds": 0}, q, log=lambda *_: None)
    assert rep2.done == 1 and q.done(cs[0].id)


def test_aborts_after_consecutive_failures(tmp_path):
    def boom(c):
        raise RuntimeError("down")

    rep = run(chunks(10), boom, Queue(tmp_path), log=lambda *_: None)
    assert len(rep.failed) == MAX_CONSECUTIVE_FAILURES and "failures in a row" in rep.stopped
    assert rep.remaining == 10 - MAX_CONSECUTIVE_FAILURES


def test_no_partial_files_left_behind(tmp_path):
    q = Queue(tmp_path)
    q.save({"id": "2026-10-01-01", "day": "2026-10-01", "items": [], "dropped": []})
    assert [p.name for p in tmp_path.iterdir()] == ["2026-10-01-01.json"]


def test_load_all_ignores_review_file(tmp_path):
    q = Queue(tmp_path)
    q.save({"id": "2026-10-01-01", "day": "2026-10-01", "items": [], "dropped": []})
    (tmp_path / "review.json").write_text("{}")
    assert len(q.load_all()) == 1


RESULTS = [{"id": "2026-10-01-01", "day": "2026-10-01", "items": [
    {"kind": "decision", "text": "Go on the 28th", "quote": "28 ถึง 29"},
    {"kind": "question", "text": "Who drives?", "quote": "ใครจะขับ"},
], "dropped": []}]


def test_render_groups_by_kind_and_marks_draft():
    md = render(RESULTS)
    assert "Draft, not yet reviewed" in md
    assert md.index("### Decisions") < md.index("### Open questions")
    assert "> 28 ถึง 29" in md


def test_render_hides_rejected_items_and_shows_reviewed():
    md = render(RESULTS, {"rejected": [item_key("2026-10-01-01", 1)], "confirmed": True})
    assert "Who drives?" not in md and "Go on the 28th" in md and "(Reviewed)" in md


def test_render_empty():
    assert "Nothing to report" in render([])
