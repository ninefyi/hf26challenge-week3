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

## Deviation (2026-10-21): no real-chat evaluation
The plan above was to judge at least 20 items from one real Night run. **That was not run.** The only real chat available is a work conversation with other people's details in it, and the author decided not to publish results about it. So the bar above (keep rate >= 70%, wrong <= 10%) **is untested**, and no accuracy rate for real chats may be claimed. The thresholds are unchanged.

What was run instead, all on the fabricated demo chat (`demo/demo_chat.txt`):
- **Demo run:** 20 messages, 3 days, 14 items; 0 dropped by the quote check, 1 flagged by the second pass; 39.4 s, 14.3 s and 22.1 s per day (about 76 s in all, first day includes loading the model); a stop-and-rerun resumed correctly (`done 2, already done 1`). Not yet judged item by item by the author.
- **Planted-error probe** (`probe.py`, 22 items written by hand, 7 correct and 15 wrong on purpose, with `gemma3:12b` and the first version of the second-pass prompt): 13 of 15 wrong items flagged (4 of 4 by the number check alone, 9 of 11 by the model's re-read), 0 of 7 correct items flagged. Both misses were "agreed" claims where the chat held only a request or a suggestion.

The probe items were fixed before the first probe run and have not been edited since. They are a sanity check, not a benchmark: 22 fabricated items, written by the same author who built the tool. If the second-pass prompt is changed, it must be measured on **new** probes it was not tuned on, and the old result reported next to the new one.
