# ADR 0001 — Video generation stack: FFmpeg, Unsplash, and measured subtitles

- **Status**: Accepted
- **Date**: 2026-09-06
- **Context**: `openspec/changes/video-generation-pipeline`

This is the first ADR in this repo. Architectural decisions previously lived
only inside OpenSpec change folders, which works while a change is active but
buries the reasoning once it is archived. Decisions that outlive their change
belong here; per-change reasoning stays in that change's `design.md`.

## Context

Approved chapter scripts had to become MP4 reels for TikTok and Instagram:
narration, a visual, and burned-in captions. Constraints from `design.md`:
stay free or cheap, keep files local (no cloud upload), and never generate
from a script no human approved.

## Decision 1 — FFmpeg for composition

Local FFmpeg via a subprocess wrapper (`FFmpegCompositor`), producing 1080p
H.264 with AAC audio and hardcoded subtitles.

**Why**: free, ubiquitous, and already the tool anything else would wrap.
Paid APIs (Synthesia, Runway, Pika) cost per render for output we can produce
locally. Browser-side composition (FFmpeg.wasm) is slower and cannot run in a
backend batch job.

**Cost**: FFmpeg *and* `ffprobe` become deployment prerequisites, and a
missing binary fails at request time rather than startup. Documented in the
README.

## Decision 2 — Unsplash with a guaranteed fallback

Search Unsplash for the chapter's visual directive; on no match, no API key,
or any provider error, generate a solid-colour image with the text overlaid
(Pillow).

**Why**: free and copyright-safe, and the directive is already in the script
from story-writing, so no extra LLM call is needed to derive a query. The
fallback matters more than the search: it guarantees a video is always
producible, which makes the visual step non-blocking.

**Cost**: the fallback is the *normal* path, not an edge case — with no
`UNSPLASH_ACCESS_KEY` set, every video uses it. That made Pillow a hard
dependency, which was initially missed and would have failed every
generation in a fresh environment.

## Decision 3 — Subtitle timing is measured, never estimated

Total duration comes from `ffprobe` on the synthesized narration. It is then
divided across segments in proportion to their word count, with the last
segment absorbing rounding so captions end exactly with the audio. If the
audio cannot be measured, generation **fails** rather than falling back to an
estimate.

**Why**: the obvious alternative — words ÷ 150 wpm — drifts against real TTS
output, which varies with voice, punctuation and pauses, and the drift
accumulates across a chapter until captions no longer match speech. Failing
loudly is better than shipping a video that looks fine and is subtly wrong.

An earlier implementation cached subtitle drafts keyed on `(script,
language)` while ignoring duration, so re-synthesized audio returned stale
timing. The cache was removed rather than re-keyed: timing varies per
synthesis, so a duration-keyed cache would essentially never hit. The *LLM
translation* is cached instead — that is the expensive part, and it is stable
for a fixed script.

## Decision 4 — Narration and captions are shared; only video is per-platform

Audio lives at `data/audio/{chapter_id}/{lang}.mp3` and the canonical caption
track at `data/subtitles/{chapter_id}/{lang}.srt`, keyed by chapter and
language only. Composition copies the caption track into
`data/videos_generated/{platform}/{lang}/` alongside the MP4.

**Why**: both derive from `chapter.script`, which every platform version
shares. Storing them per-platform synthesized identical narration four times
(four TTS bills) and produced four separately-editable caption files free to
diverge the moment one was corrected.

**Cost**: the per-platform SRT is a copy, so the same content exists twice on
disk. Composition also *reuses* an existing caption track rather than
regenerating it — without that, every run silently discarded editor
corrections.

## Decision 5 — Paths are deterministic, so retries are cheap

Every artifact resolves to a fixed path per (chapter, language) or (platform,
language). No UUID per attempt.

**Why**: a retry after a composition failure finds the audio and image the
failed attempt already produced and re-runs only FFmpeg. A unique path per
attempt would re-buy narration on every retry.

**Cost**: two attempts for the same platform and language would write the
same file. That is why generation refuses when a pending or generated video
already exists for that pair, and why deletion checks for a surviving record
pointing at the same path before unlinking.

Note this contradicts the original spec text, which specified
`{chapter_id}_{uuid}.mp4`; the spec was amended to match.

## Decision 6 — Background composition in-process, no task queue

Generation returns `202` with pending rows and composes in a FastAPI
`BackgroundTasks` job; the admin panel polls.

**Why**: `design.md` Decision 7 rejected Celery/RQ as operational overhead
for a single-operator editorial workflow.

**Cost**: a server restart mid-composition strands rows at `pending` forever.
There is no sweeper — the retry endpoint is the recovery path, and the UI
stops polling after ~5 minutes and offers a manual refresh rather than
hammering a dead job.

## Consequences

- Deployment needs FFmpeg, ffprobe, and Pillow.
- With no Unsplash key, every video is a colour-and-text card. Acceptable for
  the archival aesthetic; revisit if it looks monotonous at volume.
- Storage grows at roughly video size × platforms × languages. `/videos/stats`
  reports free disk space so the panel can warn before generation fails.
- Nothing here has yet run against real ElevenLabs or Unsplash credentials
  (tasks 6.6, 9.6, 15.6). Every test substitutes those clients, so the
  request/response shapes against the live APIs remain unverified.
