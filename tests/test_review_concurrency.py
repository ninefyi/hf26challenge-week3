from concurrent.futures import ThreadPoolExecutor

from nightshift.digest import load_review
from nightshift.review import set_text, set_verdict


def test_verdicts_clicked_at_the_same_time_are_all_kept(tmp_path):
    """Gradio runs each click in its own thread; none of them may overwrite another's."""
    keys = [f"2026-10-18-01#{i}" for i in range(60)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda k: set_verdict(tmp_path, k, "keep"), keys))
    assert set(load_review(tmp_path)["verdicts"]) == set(keys)


def test_a_verdict_and_an_edit_at_the_same_time_are_both_kept(tmp_path):
    jobs = [lambda i=i: set_verdict(tmp_path, f"k{i}", "wrong") for i in range(30)]
    jobs += [lambda i=i: set_text(tmp_path, f"t{i}", "old", "new") for i in range(30)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda f: f(), jobs))
    review = load_review(tmp_path)
    assert sum(k.startswith("k") for k in review["verdicts"]) == 30
    assert len(review["edits"]) == 30
