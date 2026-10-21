"""Test the second pass on items that are wrong (or right) on purpose.

  uv run python probe.py                 # uses demo/demo_chat.txt and demo/probe_items.json
Needs Ollama running, like run.py. Results go to results/probe.json (git-ignored).
"""
import argparse
import json
from pathlib import Path

from nightshift.chunk import chunk_messages
from nightshift.parse import parse_export
from nightshift.probe import load_probes, report, run_probe, summarise
from nightshift.recheck import SCHEMA as CHECK_SCHEMA
from nightshift.summarise import MODEL, ollama_llm


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chat", default="demo/demo_chat.txt")
    ap.add_argument("--probes", default="demo/probe_items.json")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--out", default="results/probe.json")
    args = ap.parse_args()

    chunks = chunk_messages(parse_export(Path(args.chat).read_text(encoding="utf-8")))
    probes = load_probes(args.probes)
    print(f"{len(probes)} probes, model {args.model}")
    rows = run_probe(chunks, probes, ollama_llm(args.model, CHECK_SCHEMA))
    summary = summarise(rows)
    print()
    print(report(summary))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": args.model, "summary": summary, "rows": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nfull results: {out}")


if __name__ == "__main__":
    main()
