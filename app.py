"""Review page: judge each digest item against its quote, reword if needed, then confirm.

  uv run python app.py [--work work] [--out digest/digest.md]
Every click is saved to <work>/review.json straight away.
"""
import argparse
from pathlib import Path

import gradio as gr

from nightshift.digest import load_review, render
from nightshift.queue import Queue
from nightshift.review import VERDICTS, confirm, items_for_review, set_text, set_verdict, tally

KIND_LABEL = {"decision": "Decision", "question": "Open question", "point": "Point"}


def build(work: str, out: str):
    queue = Queue(work)

    def second_pass_md(t: dict) -> str:
        sp = t["second_pass"]
        if not sp["checked"]:
            return ""
        return (
            f"  \nSecond pass flagged {sp['flagged']} of {sp['checked']} items "
            f"({t['verify_seconds']} s). Against your verdicts: it was right on {sp['flag_right']}, "
            f"a false alarm on {sp['false_alarms']}, and missed {sp['missed_wrong']} wrong item(s)."
        )

    def stats_md() -> str:
        t = tally(queue.load_all(), load_review(work))
        rate = lambda x: "n/a" if x is None else f"{x:.0%}"
        return (
            f"**{t['judged']} of {t['items']} items judged** "
            f"(keep {t['keep']}, edit {t['edit']}, wrong {t['wrong']}) · "
            f"keep rate {rate(t['keep_rate'])} (bar ≥ 70%) · wrong rate {rate(t['wrong_rate'])} (bar ≤ 10%)  \n"
            f"{t['chunks']} chunks, {t['seconds']} s of model time · "
            f"{t['dropped_by_quote_check']} item(s) dropped by the quote check"
            + second_pass_md(t)
        )

    def preview_md() -> str:
        return render(queue.load_all(), load_review(work))

    with gr.Blocks(title="nightshift review") as demo:
        gr.Markdown(
            "# Review the digest\n"
            "Read each item against its quote. **keep** = right as written, **edit** = right but reword it "
            "(change the text), **wrong** = false or misleading, even though the quote exists. "
            "Your choices are saved as you click."
        )
        stats = gr.Markdown(stats_md())
        day = gr.Dropdown(label="Day", choices=[], value=None)
        refresh = gr.Button("Reload results from work/")

        @gr.render(inputs=day)
        def items_view(selected):
            results = queue.load_all()
            review = load_review(work)
            items = [it for it in items_for_review(results) if it["day"] == selected]
            if not items:
                gr.Markdown("No items for this day." if selected else "Pick a day.")
                return
            for it in items:
                with gr.Group():
                    chk = it.get("check")
                    note = f"  \nSecond pass: **{chk['verdict']}**, {chk['reason']}" if chk else ""
                    gr.Markdown(f"**{KIND_LABEL[it['kind']]}** · quote from the chat:  \n> {it['quote']}{note}")
                    box = gr.Textbox(
                        value=review["edits"].get(it["key"]) or it["text"], label="Item text", lines=2, interactive=True
                    )
                    verdict = gr.Radio(list(VERDICTS), value=review["verdicts"].get(it["key"]), label="Verdict", interactive=True)
                    verdict.input(
                        lambda v, k=it["key"]: (set_verdict(work, k, v), stats_md())[1],
                        verdict, stats,
                    )
                    box.input(
                        lambda t, k=it["key"], o=it["text"]: (set_text(work, k, o, t), stats_md())[1],
                        box, stats,
                    )

        def reload():
            days = sorted({r["day"] for r in queue.load_all()})
            return gr.Dropdown(choices=days, value=days[0] if days else None), stats_md()

        refresh.click(reload, None, [day, stats])
        demo.load(reload, None, [day, stats])

        gr.Markdown("## Finish")
        status = gr.Markdown()
        with gr.Row():
            confirm_btn = gr.Button("Confirm digest", variant="primary")
            preview_btn = gr.Button("Preview digest")
        preview = gr.Markdown()

        def do_confirm():
            msg = confirm(work, queue.load_all())
            if msg == "Confirmed.":
                path = Path(out)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(preview_md(), encoding="utf-8")
                msg += f" Wrote {path}."
            return msg, preview_md(), stats_md()

        confirm_btn.click(do_confirm, None, [status, preview, stats])
        preview_btn.click(lambda: preview_md(), None, preview)
    return demo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default="work")
    ap.add_argument("--out", default="digest/digest.md")
    ap.add_argument("--port", type=int, default=7861)
    args = ap.parse_args()
    build(args.work, args.out).launch(server_name="127.0.0.1", server_port=args.port)


if __name__ == "__main__":
    main()
