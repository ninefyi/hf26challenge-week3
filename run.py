"""Overnight batch: read a LINE export, summarise it chunk by chunk, write the digest.

  uv run python run.py inbox/chat.txt --until 06:30
Re-run the same command to resume after a stop or crash.

Secrets (emails, links, phone numbers, long numbers, voucher-style codes) are replaced with
placeholders before anything else sees the chat. Put names, clients and anything else to
hide in redact-terms.txt (one per line), then check what the model will read with
  uv run python run.py inbox/chat.txt --preview work/preview.txt
"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from nightshift.chunk import chunk_messages
from nightshift.digest import load_review, render
from nightshift.parse import parse_export
from nightshift.queue import Queue, run
from nightshift.redact import load_terms, redact_messages, summary
from nightshift.recheck import SCHEMA as CHECK_SCHEMA
from nightshift.summarise import MODEL, ollama_llm, summarise_chunk


def stop_time(hhmm: str, now: datetime) -> datetime:
    """Next occurrence of HH:MM (today if still ahead, otherwise tomorrow)."""
    h, m = map(int, hhmm.split(":"))
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return t if t > now else t + timedelta(days=1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", help="LINE .txt export")
    ap.add_argument("--work", default="work", help="folder for per-chunk results (default work/)")
    ap.add_argument("--out", default="digest/digest.md")
    ap.add_argument("--until", metavar="HH:MM", help="stop starting new chunks at this time")
    ap.add_argument("--max-chunks", type=int)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--no-second-pass", action="store_true",
                    help="skip the second pass that re-reads the chat to check each item (faster, less careful)")
    ap.add_argument("--terms", default="redact-terms.txt",
                    help="file of extra words to hide, one per line (default redact-terms.txt, if it exists)")
    ap.add_argument("--anonymise-senders", action="store_true", help="show senders as Person A, Person B, ...")
    ap.add_argument("--preview", metavar="FILE",
                    help="write the redacted chat to FILE and stop, without running the model")
    args = ap.parse_args()

    raw = Path(args.export).read_text(encoding="utf-8")
    messages = parse_export(raw)
    terms = load_terms(args.terms) if Path(args.terms).exists() else []
    messages, redacted = redact_messages(messages, terms, args.anonymise_senders)
    chunks = chunk_messages(messages)
    print(f"{len(messages)} messages, {len(chunks)} chunks; redacted: {summary(redacted)} "
          f"({len(terms)} custom terms)")

    if args.preview:
        preview = Path(args.preview)
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text(
            "\n".join(f"{m.when:%Y-%m-%d %H:%M} {m.sender}: {m.text}" for m in messages), encoding="utf-8"
        )
        print(f"redacted chat written to {preview}; read it before the real run")
        return

    queue = Queue(args.work)
    llm = ollama_llm(args.model)
    check_llm = None if args.no_second_pass else ollama_llm(args.model, CHECK_SCHEMA)
    salt = f":{args.model}:second-pass={'off' if check_llm is None else 'on'}"
    until = stop_time(args.until, datetime.now()) if args.until else None
    report = run(chunks, lambda c: summarise_chunk(c, llm, check_llm), queue,
                 until=until, max_chunks=args.max_chunks, salt=salt)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(queue.load_all(), load_review(args.work)), encoding="utf-8")
    print(f"done {report.done}, already done {report.skipped}, failed {len(report.failed)}, "
          f"left {report.remaining}" + (f" ({report.stopped})" if report.stopped else ""))
    print(f"digest: {out}")


if __name__ == "__main__":
    main()
