# Hacktoberfest Open-Source AI Challenge: Week 3 "Slow and Steady"

A fourth, separate project. Earlier weeks live in other repositories.

## Language

**Week 3 Challenge**:
The DEV "Hacktoberfest Open-Source AI Challenge: Week 3", theme "Slow and Steady". Submissions close Oct 25, 11:59 PM PDT (Oct 26, 14:59 author-local, UTC+8). One entry per author, and it must be a new project.

**Export**:
The standard LINE `.txt` chat export of one group: date header lines, then `HH:MM<TAB>Sender<TAB>text` lines.

**Message**:
One chat message: time, sender, text. Stickers, photos and system lines are not Messages.

**Chunk**:
Messages from one day, cut so a single model call stays small. The unit of work and of resuming.

**Item**:
One line of the digest: a Decision, an Open question or a Point, with a Quote.

**Quote**:
A few words the model copies from one Message to support an Item. If it is not in the Chunk word for word (ignoring spaces and case), the Item is dropped.

**Night run**:
One unattended `run.py` pass over an Export, stopping at a set time. Can be repeated; finished Chunks are skipped.

**Digest**:
The Markdown file of all kept Items by day. Marked "Draft, not yet reviewed" until the author confirms it.

**Review**:
The author unticks Items that are wrong or misleading and confirms. The author's judgements are the Evaluation.

**Evaluation**:
The author's keep / edit / wrong verdicts on Items from one real Night run, scored against the bar in EVAL.md.

**Submission**:
The single DEV post, using the challenge template, tagged `devchallenge` and `hf26challenge`. Judged mostly on writing.

## Flagged ambiguities
- "Slow" is the feature, not a limit: the laptop is idle at night, so a 12B model on a 16 GB machine is enough.
- A valid Quote proves the words exist, not that the Item says something true about them. A misleading Item with a valid Quote still counts against the model in the Evaluation.
- The real chat has other people in it. Only the fabricated demo chat is committed or shown.
