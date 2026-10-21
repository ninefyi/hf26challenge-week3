# nightshift: an overnight digest of your LINE chat

Drop a LINE chat export in before bed. A local open model ([Gemma 3 12B](https://ollama.com/library/gemma3) through [Ollama](https://ollama.com)) works through it one day at a time while you sleep, and leaves a Markdown digest of decisions, open questions and news. **Nothing leaves your machine.**

Built for the [Hacktoberfest Open-Source AI Challenge: Week 3, "Slow and Steady"](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).

**Status: work in progress.** The code, the review page and the tests are in place; the real night run and its evaluation (see [EVAL.md](EVAL.md)) have not been done yet, so there are no accuracy numbers here.

## How it works

```
LINE .txt export ─► parse ─► one chunk per day ─► Gemma 3 12B (Ollama, local)
   ─► items: decision / question / point, each with a quote
   ─► quote check (drop any item whose quote is not in the chat)
   ─► work/<chunk>.json saved as each chunk finishes ─► digest/digest.md
```

- **Slow on purpose.** `--until 06:30` stops starting new chunks at that time.
- **Resumable.** Each finished chunk is written to `work/` right away. If the laptop sleeps, Ollama dies or you stop it, run the same command again and it picks up where it left off. After three chunks fail in a row it stops instead of burning the night.
- **The model cannot make things up silently.** Every item carries a quote copied from one message. If the quote is not in that day's chat word for word (ignoring spaces, since Thai has none, and case), the item is dropped and counted.
- **A valid quote is not a true item.** The digest is marked "Draft, not yet reviewed" until you check it.

## Run it

You need [uv](https://docs.astral.sh/uv/), Ollama, and about 8 GB of free memory for the model (a 16 GB MacBook is the target).

```bash
ollama pull gemma3:12b
uv sync
uv run python run.py demo/demo_chat.txt --until 06:30
```

Your own chat: use LINE's "Export chat history" on the group, and save the `.txt` into `inbox/` (git-ignored). Then `uv run python run.py inbox/<file>.txt --until 06:30`. Re-run the same command to resume. Useful flags: `--max-chunks N`, `--work DIR`, `--out FILE`.

## Review the digest

```bash
uv run python app.py          # http://127.0.0.1:7861
```

Pick a day and read each item beside the quote it came from. Give every item a verdict: **keep** (right as written), **edit** (right, but reword it: change the text and the item becomes "edit"), or **wrong** (false or misleading even though the quote exists; it is left out of the digest). Every click is saved at once to `work/review.json`, so closing the browser loses nothing. The top of the page keeps a running tally against the bar in [EVAL.md](EVAL.md): keep rate, wrong rate, items dropped by the quote check, and model time. "Confirm digest" is allowed only when every item has a verdict. It writes `digest/digest.md` marked "Reviewed". Any later change reopens the review.

`demo/demo_chat.txt` is a fabricated Thai group chat about a trip. Nobody in it is real.

## Export format

The LINE text export in either layout. Date header: `2026.10.19 Monday` (also `2026/10/19`, `2026-10-19` or `Mon, 19/10/2026`). Messages: `HH:MM<TAB>Sender<TAB>text`, or `HH:MM Sender text` with spaces only. In the space layout nothing marks where the name ends, so names are inferred from the file (names with spaces or emoji work; a one-word name whose lines nearly all start with the same word may pick up that word). Buddhist Era years (2569) are converted. Multi-line messages are joined. Stickers, photos, join/leave lines and call notices are skipped. Checked against one real export (space layout) and fabricated samples; another app version or language may need a change in `nightshift/parse.py`.

## Tests

```bash
uv run pytest
```

Covers the parser, chunking, the quote check, the resumable queue (resume, stop time, failures), the digest and the review logic (verdicts, edits, confirm, tally). They use a fake model, so they need no Ollama.

## Layout

```
run.py                 overnight command
nightshift/parse.py    LINE export -> messages
nightshift/chunk.py    messages -> one chunk per day
nightshift/summarise.py  Gemma call, JSON items, retries
nightshift/verify.py   the quote check
nightshift/queue.py    resumable job queue
nightshift/digest.py   Markdown digest and review file
nightshift/review.py   verdicts, edits, confirm and the tally (no Gradio)
app.py                 Gradio review page
EVAL.md                the bar, written before any real run
CONTEXT.md             glossary and flagged ambiguities
```

## Privacy

Real exports, `work/` and `digest/` are in `.gitignore`. The repository contains only a fabricated demo chat.

## License

[MIT](LICENSE)
