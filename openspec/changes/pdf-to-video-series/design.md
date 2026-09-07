## Context

The system currently spans discovery, curation, story-writing, per-platform text
adaptation, human approval, publishing, and in-house video rendering. Its owner
does none of that work: he picks a declassified PDF himself and wants a script
good enough to hand to an external animated-video tool.

What survives is the middle: turning a document into a faithful, well-plotted
script. What goes is everything on either side of it.

Two constraints shape the design. Scripts are generated on **local Ollama
models** on an M3 Pro, which are markedly weaker at following instructions than
the cloud model this codebase was written against — measured output missed a
150–220 word target at 42, 121, and 149 words before converging. And the source
material is **real historical records**, where an invented quote is a
credibility failure that survives into a published video.

## Goals / Non-Goals

**Goals:**

- A PDF becomes a chaptered mini-series script with a genuine narrative arc.
- Progress reporting reflects work actually done, so a two-minute local
  inference does not look like a hang.
- Every script is approvable, readable, and rejectable before it leaves.
- An approved script exits cleanly into an external tool.
- Local models produce output that passes the same validation the cloud model
  did — by retrying against feedback, never by lowering the bar.

**Non-Goals:**

- **Generating video.** Not by API, not in-house. The system's output is text.
- Integrating a video provider, storing rendered video, or holding a video API
  key. The owner does this by hand in external tools.
- Publishing, scheduling, or posting anywhere.
- Discovering documents. The owner chooses and uploads them.
- Native per-platform text content — X threads, Instagram carousels. With video
  as the deliverable, these solve a problem that no longer exists.

## Decisions

### Decision 1: A series plan is produced before any chapter is written

The LLM first reads the document and emits a `SeriesPlan`: how many chapters,
what each covers, and the through-line connecting them. Chapters are then
generated one at a time against that plan.

**Rationale**: the existing spec requires a cliffhanger to reference something
that genuinely appears later in the source. A chapter generated with no
knowledge of what follows cannot satisfy that except by luck. Planning first is
what separates a mini-series from N independent scripts about the same document.

**Alternatives**: generating chapters sequentially, each seeing the previous —
cheaper, but a chapter still cannot set up what has not been decided yet.
Chunking the text into word-count slices — the naive approach, and the one that
produces fake cliffhangers.

### Decision 2: Chapter count follows narrative beats, not word count

The series plan decides how many chapters the document supports by identifying
its narrative beats — setup, escalation, complication, resolution. A document
with one beat yields one chapter, and that single chapter is structured the same
way as a series of five.

**Rationale**: two documents of similar length should not become 2 and 4
chapters through chunk arithmetic. Chapter count is an editorial judgement about
the material.

**Trade-off**: a local model's beat identification will be less reliable than a
cloud model's. The plan is therefore shown to the operator and is itself
rejectable, before chapter generation spends minutes of local inference.

### Decision 3: Two duration cuts per chapter, one plot

Each chapter is produced as a long cut (YouTube, 3–5 minutes) and a short cut
(Reel/Short, ~60 seconds). Both carry the same facts, the same beats, and the
same citations; only the length differs.

**Rationale**: this is the only thing that genuinely changes between platforms
when the deliverable is video. Producing four *substitute* text formats was
solving a different problem.

**Trade-off**: two generations per chapter on a slow local model. Mitigated by
generating the long cut first and deriving the short cut by compression, which
also guarantees the two agree on the facts.

### Decision 4: Retry against validation feedback; never relax the constraint

When a generated script fails a mechanical check — length, missing citation,
fabricated quote — the failure is fed back into the prompt and generation is
retried, bounded.

**Rationale**: this is measured, not theoretical. A local model produced 121,
then 149, then 150 words once told what was wrong. The alternative — widening
the acceptable range to fit the model — breaks the link between script length
and target runtime, which is the reason the range exists.

### Decision 5: Anti-fabrication validation is strengthened, not removed

Quotes in a script must appear in the source document. This survives the pivot
and is extended across the series: a chapter may not attribute to the document
something only an earlier chapter's prose asserted.

**Rationale**: the output is now a video script that the owner will hand to a
renderer and publish under his own name. A misattributed quote is more expensive
to retract from a rendered video than from a text post, and these are real
records about real people.

### Decision 6: Curation gates uploads

The existing five-criterion rubric is kept and applied to uploaded documents. A
document scoring below the threshold does not produce a script; the operator is
told the score and why.

**Rationale**: uploading is cheap; generating a multi-chapter series on a local
model is not. The gate spends minutes of inference only on material that can
carry a story.

**Trade-off**: it will occasionally block a document the operator wanted. The
score and reasoning are shown so the judgement is visible rather than opaque.

### Decision 7: Progress is measured, never simulated

Upload and analysis report progress derived from pages extracted and chapters
generated. When a step's duration is genuinely unknown, it reports as
indeterminate rather than inventing a percentage.

**Rationale**: local inference takes tens of seconds to minutes per chapter. A
progress bar that advances on a timer while nothing happens teaches the operator
to distrust it, which is worse than no bar.

### Decision 8: Removed code is archived on a branch, then deleted

An `archive/pre-pivot` branch and tag preserve the current state before removal.

**Rationale**: roughly 60% of the codebase is being deleted, including a
working, tested video pipeline. Git history technically retains it, but
recovering a coherent feature from a history rewrite is meaningfully harder than
checking out a branch. The cost is zero.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| **Local model prose quality is simply worse** than the cloud model the prompts were tuned for, and gets misdiagnosed as a design flaw | Validate chapter-one output quality by hand before building the full series logic. The provider switch keeps a paid model one setting away. |
| **The series plan is the highest-value and least-proven step** — if beat identification is poor, every chapter inherits the flaw | The plan is a separate, rejectable artifact shown before chapter generation, so a bad plan costs seconds rather than minutes. |
| **Deleting the in-house video pipeline is irreversible in practice** if external tools disappoint on cost or fidelity | Archived on a branch. Note that external tools are *not* a like-for-like replacement: they animate, the removed pipeline composed stills with narration. |
| **"Faithful to the script" applies to narration, not visuals** — a scrupulously accurate script can still yield a video implying something the document does not support | Out of scope by design: the system stops at the script. Visual fidelity is checked by the operator in the external tool. |
| **Curation blocks a document the operator wanted** | Score and per-criterion reasoning are surfaced, so the block is arguable rather than silent. |
| **Two duration cuts double local inference time per chapter** | Short cut is derived from the approved long cut, not generated independently. |
| **Removing four-platform adaptation loses native text content** the owner may later want | Recorded here as a deliberate trade, not an oversight. The capability is on the archive branch. |
