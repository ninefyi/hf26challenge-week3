"""Overnight batch: read a LINE export, summarise it chunk by chunk, write the digest.

  uv run python run.py inbox/chat.txt --until 06:30
Re-run the same command to resume after a stop or crash.
"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from nightshift.chunk import chunk_messages
from nightshift.digest import load_review, render
from nightshift.parse import parse_export
from nightshift.queue import Queue, run
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
    args = ap.parse_args()

    raw = Path(args.export).read_text(encoding="utf-8")
    messages = parse_export(raw)
    chunks = chunk_messages(messages)
    print(f"{len(messages)} messages, {len(chunks)} chunks")

    queue = Queue(args.work)
    llm = ollama_llm(args.model)
    until = stop_time(args.until, datetime.now()) if args.until else None
    report = run(chunks, lambda c: summarise_chunk(c, llm), queue, until=until, max_chunks=args.max_chunks)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(queue.load_all(), load_review(args.work)), encoding="utf-8")
    print(f"done {report.done}, already done {report.skipped}, failed {len(report.failed)}, "
          f"left {report.remaining}" + (f" ({report.stopped})" if report.stopped else ""))
    print(f"digest: {out}")


if __name__ == "__main__":
    main()
