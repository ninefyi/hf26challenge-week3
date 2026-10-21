# Evaluation plan (written before any real night run)

Fixed on 2026-10-20. Do not edit the thresholds after seeing results.

## Set
All Items from one real Night run on the author's own LINE group export, at least 20 Items. If a night gives fewer than 20, run a second night and say so.

## Verdicts
The author judges each kept Item against the chat: **keep** (right as written), **edit** (right but needs rewording), **wrong** (false, or misleading even though its Quote exists).

## Bar
- Keep rate >= 70% of judged Items.
- Wrong Items <= 10%.
- Every kept Item's Quote is found in its Chunk (checked by script, not by eye).

## Also record (no threshold)
- Items dropped by the Quote check, and the share of all model Items.
- Seconds per Chunk, total run time, number of Chunks, any failed or retried Chunks.
- Real decisions or questions in the chat that the Digest missed (author spot-check of three days).
- Memory and whether the laptop slept.

## Reporting
Report the real numbers even if they miss the bar, and say how many Items the claim rests on. Raw per-Chunk results stay in `work/` (git-ignored); only counts and fabricated examples are published.

## Amendment (2026-10-21, before any real run)
Added a second pass (a number check, then a model re-read of each item). The thresholds above are unchanged. Also record, with no threshold: how many items the second pass flagged, how many of those the author judged wrong (it was right) or keep/edit (false alarm), how many wrong items it missed, and the extra seconds it took. The author's verdicts stay the ground truth.
