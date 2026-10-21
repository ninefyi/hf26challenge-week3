from nightshift.digest import load_review, render
from nightshift.review import confirm, items_for_review, set_text, set_verdict, tally, unjudged_by_day

RESULTS = [
    {"id": "2026-10-01-01", "day": "2026-10-01", "seconds": 10.0, "dropped": [{"quote": "x"}], "items": [
        {"kind": "decision", "text": "Go on the 28th", "quote": "28"},
        {"kind": "question", "text": "Who drives?", "quote": "ขับ"},
    ]},
    {"id": "2026-10-02-01", "day": "2026-10-02", "seconds": 5.5, "dropped": [], "items": [
        {"kind": "point", "text": "Booked", "quote": "จอง"},
    ]},
]
K0, K1, K2 = "2026-10-01-01#0", "2026-10-01-01#1", "2026-10-02-01#0"


def test_items_for_review_order_and_keys():
    assert [i["key"] for i in items_for_review(RESULTS)] == [K0, K1, K2]


def test_verdicts_persist_and_tally(tmp_path):
    set_verdict(tmp_path, K0, "keep")
    set_verdict(tmp_path, K1, "wrong")
    t = tally(RESULTS, load_review(tmp_path))
    assert (t["keep"], t["wrong"], t["edit"], t["unjudged"]) == (1, 1, 0, 1)
    assert t["keep_rate"] == 0.5 and t["wrong_rate"] == 0.5
    assert t["dropped_by_quote_check"] == 1 and t["seconds"] == 15.5 and t["chunks"] == 2
    assert abs(t["dropped_share"] - 0.25) < 1e-9


def test_tally_with_nothing_judged_has_no_rates():
    t = tally(RESULTS)
    assert t["keep_rate"] is None and t["unjudged"] == 3


def test_clearing_a_verdict(tmp_path):
    set_verdict(tmp_path, K0, "keep")
    set_verdict(tmp_path, K0, None)
    assert K0 not in load_review(tmp_path)["verdicts"]


def test_editing_text_marks_item_edit_and_shows_in_digest(tmp_path):
    set_text(tmp_path, K0, "Go on the 28th", "We go on the 28th and 29th")
    review = load_review(tmp_path)
    assert review["verdicts"][K0] == "edit"
    assert "We go on the 28th and 29th" in render(RESULTS, review)


def test_edit_does_not_override_wrong_and_reverting_clears_it(tmp_path):
    set_verdict(tmp_path, K0, "wrong")
    set_text(tmp_path, K0, "Go on the 28th", "changed")
    assert load_review(tmp_path)["verdicts"][K0] == "wrong"
    set_text(tmp_path, K0, "Go on the 28th", "Go on the 28th")
    assert K0 not in load_review(tmp_path)["edits"]


def test_confirm_needs_every_item_judged_and_any_change_reopens(tmp_path):
    set_verdict(tmp_path, K0, "keep")
    assert "2 item(s)" in confirm(tmp_path, RESULTS)
    set_verdict(tmp_path, K1, "wrong")
    set_verdict(tmp_path, K2, "keep")
    assert confirm(tmp_path, RESULTS) == "Confirmed."
    assert load_review(tmp_path)["confirmed"] is True
    set_verdict(tmp_path, K2, "edit")
    assert load_review(tmp_path)["confirmed"] is False


def test_unjudged_by_day_lists_only_days_with_items_left(tmp_path):
    assert unjudged_by_day(RESULTS, None) == {"2026-10-01": 2, "2026-10-02": 1}
    set_verdict(tmp_path, K0, "keep")
    set_verdict(tmp_path, K2, "wrong")
    assert unjudged_by_day(RESULTS, load_review(tmp_path)) == {"2026-10-01": 1}
    set_verdict(tmp_path, K1, "edit")
    assert unjudged_by_day(RESULTS, load_review(tmp_path)) == {}
