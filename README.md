# nightshift: an overnight digest of your LINE chat

Drop a LINE chat export in before bed. A local open model ([Gemma 3 12B](https://ollama.com/library/gemma3) through [Ollama](https://ollama.com)) works through it one day at a time while you sleep, and leaves a Markdown digest of decisions, open questions and news. **Nothing leaves your machine.**

Built for the [Hacktoberfest Open-Source AI Challenge: Week 3, "Slow and Steady"](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).

**Status: work in progress.** The code and tests are in place; the real night run and its evaluation (see [EVAL.md](EVAL.md)) have not been done yet, so there are no accuracy numbers here.

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

`demo/demo_chat.txt` is a fabricated Thai group chat about a trip. Nobody in it is real.

## Export format

The standard LINE text export: a date header (`2026.10.19 Monday`, also `2026/10/19`, `2026-10-19` or `Mon, 19/10/2026`), then `HH:MM<TAB>Sender<TAB>text` lines. Buddhist Era years (2569) are converted. Multi-line messages in quotes are joined. Stickers, photos and system lines are skipped. This was written from the documented layout and a fabricated sample, not yet checked against a full real export, so a different layout may need a parser change in `nightshift/parse.py`.

## Tests

```bash
uv run pytest
```

Covers the parser, chunking, the quote check, the resumable queue (resume, stop time, failures) and the digest. They use a fake model, so they need no Ollama.

## Layout

```
run.py                 overnight command
nightshift/parse.py    LINE export -> messages
nightshift/chunk.py    messages -> one chunk per day
nightshift/summarise.py  Gemma call, JSON items, retries
nightshift/verify.py   the quote check
nightshift/queue.py    resumable job queue
nightshift/digest.py   Markdown digest and review file
EVAL.md                the bar, written before any real run
CONTEXT.md             glossary and flagged ambiguities
```

## Privacy

Real exports, `work/` and `digest/` are in `.gitignore`. The repository contains only a fabricated demo chat.

## License

[MIT](LICENSE)
