# nightshift: an overnight digest of your LINE chat

Drop a LINE chat export in before bed. A local open model ([Gemma 3 12B](https://ollama.com/library/gemma3) through [Ollama](https://ollama.com)) works through it one day at a time while you sleep, and leaves a Markdown digest of decisions, open questions and news. **Nothing leaves your machine.**

Built for the [Hacktoberfest Open-Source AI Challenge: Week 3, "Slow and Steady"](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).

**Status: work in progress.** The code, the review page and the tests are in place; the real night run and its evaluation (see [EVAL.md](EVAL.md)) have not been done yet, so there are no accuracy numbers here.

## How it works

```
LINE .txt export ─► parse ─► one chunk per day ─► Gemma 3 12B (Ollama, local)
   ─► items: decision / question / point, each with a quote
   ─► quote check (drop any item whose quote is not in the chat)
   ─► second pass: numbers must be in the chat, then Gemma re-reads the day and judges each item
   ─► work/<chunk>.json saved as each chunk finishes ─► digest/digest.md
```

- **Slow on purpose.** `--until 06:30` stops starting new chunks at that time.
- **Resumable.** Each finished chunk is written to `work/` right away. If the laptop sleeps, Ollama dies or you stop it, run the same command again and it picks up where it left off. After three chunks fail in a row it stops instead of burning the night.
- **The model cannot make things up silently.** Every item carries a quote copied from one message. If the quote is not in that day's chat word for word (ignoring spaces, since Thai has none, and case), the item is dropped and counted.
- **A second pass, because a quote is not enough.** For each item that survives the quote check, any number in it must appear in that day's chat (no model needed), then Gemma re-reads the whole day and answers *supported*, *unsupported* or *unclear* with a one-sentence reason. Items called unsupported are left out of the digest unless you keep them on the review page, so nothing is deleted behind your back. It costs about as many extra model calls as there are items, which is the point of running overnight. `--no-second-pass` turns it off.
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

Pick a day and read each item beside the quote it came from. Give every item a verdict: **keep** (right as written), **edit** (right, but reword it: change the text and the item becomes "edit"), or **wrong** (false or misleading even though the quote exists; it is left out of the digest). Every click is saved at once to `work/review.json`, so closing the browser loses nothing. Each item shows what the second pass said about it. The top of the page keeps a running tally against the bar in [EVAL.md](EVAL.md): keep rate, wrong rate, items dropped by the quote check, model time, and how the second pass compares with your verdicts (right when it flagged an item you called wrong, a false alarm when it flagged one you kept, and how many wrong items it missed). "Confirm digest" is allowed only when every item has a verdict. It writes `digest/digest.md` marked "Reviewed". Any later change reopens the review.

`demo/demo_chat.txt` is a fabricated Thai group chat about a trip. Nobody in it is real.

## Export format

The LINE text export in either layout. Date header: `2026.10.19 Monday` (also `2026/10/19`, `2026-10-19` or `Mon, 19/10/2026`). Messages: `HH:MM<TAB>Sender<TAB>text`, or `HH:MM Sender text` with spaces only. In the space layout nothing marks where the name ends, so names are inferred from the file (names with spaces or emoji work; a one-word name whose lines nearly all start with the same word may pick up that word). Buddhist Era years (2569) are converted. Multi-line messages are joined. Stickers, photos, join/leave lines and call notices are skipped. Checked against one real export (space layout) and fabricated samples; another app version or language may need a change in `nightshift/parse.py`.

## Redaction

A chat export is full of other people's details, so everything is redacted right after parsing, before the model, the `work/` files, the review page or the digest see it. The original text is never written anywhere by this program.

| Replaced with | What |
|---|---|
| `[EMAIL]` | `name@domain`, with or without `.com` |
| `[URL:domain]` | links, keeping only the site name |
| `[REDACTED]` | words in `redact-terms.txt` (names, clients, employers), case-insensitive |
| `[PHONE]`, `[NUMBER]` | phone numbers, and any run of 9 or more digits |
| `[CODE]` | voucher- or token-style words mixing 10+ letters and digits, `XXXX-XXXX-XXXX` keys, and the value after `password`, `code`, `token`, `รหัส` |

```bash
cp redact-terms.example.txt redact-terms.txt     # git-ignored; list names and clients, one per line
uv run python run.py inbox/chat.txt --preview work/preview.txt   # writes the redacted chat, no model
uv run python run.py inbox/chat.txt --anonymise-senders ...      # Person A, Person B, ... (optional)
```

The run prints how many of each kind it replaced, never the text. **Read the preview before the real run**: this is a safety net, not a guarantee, and it cannot know that a Thai nickname is a person. If a chunk's text changes (for example you add a term), or you change the model or turn the second pass on or off, its old result is treated as stale and redone.

## Tests

```bash
uv run pytest
```

Covers the parser, redaction, chunking, the quote check, the second pass, the resumable queue (resume, stop time, failures), the digest and the review logic (verdicts, edits, confirm, tally). They use a fake model, so they need no Ollama.

## Layout

```
run.py                 overnight command
nightshift/parse.py    LINE export -> messages
nightshift/chunk.py    messages -> one chunk per day
nightshift/summarise.py  Gemma call, JSON items, retries
nightshift/verify.py   the quote check
nightshift/recheck.py  the second pass (numbers, then a model re-read)
nightshift/queue.py    resumable job queue
nightshift/redact.py   removes secrets and names before the model sees anything
nightshift/digest.py   Markdown digest and review file
nightshift/review.py   verdicts, edits, confirm and the tally (no Gradio)
app.py                 Gradio review page
EVAL.md                the bar, written before any real run
CONTEXT.md             glossary and flagged ambiguities
```

## Privacy

Real exports, `work/`, `digest/` and `redact-terms.txt` are in `.gitignore`. The repository contains only a fabricated demo chat.

## License

[MIT](LICENSE)
