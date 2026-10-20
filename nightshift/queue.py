"""Resumable job queue: one JSON file per finished chunk in the work directory.

A chunk counts as done only when its file exists, and the file is written atomically,
so a crash, sleep or Ollama restart never leaves a half-finished result behind.
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .chunk import Chunk

MAX_CONSECUTIVE_FAILURES = 3


class Queue:
    def __init__(self, work_dir: str | Path):
        self.dir = Path(work_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, chunk_id: str) -> Path:
        return self.dir / f"{chunk_id}.json"

    def done(self, chunk_id: str) -> bool:
        return self._path(chunk_id).exists()

    def save(self, result: dict) -> None:
        path = self._path(result["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def load_all(self) -> list[dict]:
        return [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(self.dir.glob("*-[0-9][0-9].json"))
        ]


@dataclass
class Report:
    done: int = 0
    skipped: int = 0  # already finished in an earlier run
    failed: list[str] = field(default_factory=list)
    remaining: int = 0
    stopped: str = ""  # why the run ended early, if it did


def run(chunks: list[Chunk], summarise, queue: Queue, *, until: datetime | None = None,
        max_chunks: int | None = None, now=datetime.now, log=print) -> Report:
    """Work through the chunks in order. Finished ones are skipped, so re-running resumes."""
    report = Report()
    todo = []
    for c in chunks:
        if queue.done(c.id):
            report.skipped += 1
        else:
            todo.append(c)
    consecutive = 0
    for i, c in enumerate(todo):
        if until is not None and now() >= until:
            report.stopped = f"reached stop time {until:%H:%M}"
        elif max_chunks is not None and report.done >= max_chunks:
            report.stopped = f"reached --max-chunks {max_chunks}"
        elif consecutive >= MAX_CONSECUTIVE_FAILURES:
            report.stopped = f"{MAX_CONSECUTIVE_FAILURES} failures in a row (is Ollama running?)"
        if report.stopped:
            report.remaining = len(todo) - i
            break
        try:
            result = summarise(c)
        except Exception as e:  # leave it undone so the next run retries it
            consecutive += 1
            report.failed.append(c.id)
            log(f"FAILED {c.id}: {e}")
            continue
        consecutive = 0
        queue.save(result)
        report.done += 1
        log(f"done {c.id}: {len(result['items'])} items, {len(result['dropped'])} dropped, {result['seconds']}s")
    return report
