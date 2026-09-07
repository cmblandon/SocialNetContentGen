## Why

The system was built to discover documents, adapt them into four platform-native
text formats, and publish them on a schedule. The owner's verdict on that
product is that it is not useful to him. What he actually does is choose a
declassified document himself, and what he actually needs back is a **polished,
well-plotted script** he can take to an external animated-video tool.

Everything between those two points — scraping for documents, adapting text per
network, scheduling posts, and rendering video in-house — is machinery for a job
he is not doing.

This change reduces the system to that job: **document in, script out.** Video
production stays where it already is, in his hands, in external tools.

## What Changes

- **New**: upload a PDF and watch real extraction progress, rather than
  configuring source URLs for a scraper to crawl.
- **New**: a series plan produced *before* any chapter is written, so a
  multi-chapter document becomes a mini-series with a real arc — chapter 2 can
  set up what chapter 3 pays off. Naive chunking cannot do this.
- **New**: two duration cuts per chapter — a long cut (YouTube, 3–5 min) and a
  short cut (Reel/Short, ~60s) — same plot and same facts, different length.
- **New**: export an approved script by clipboard copy, Markdown download, or
  scene-structured JSON for storyboard-driven video tools.
- **Modified**: `story-writing` gains the series arc — recap beats, cross-chapter
  continuity, a finale that resolves rather than teases, and chapter count driven
  by narrative beats instead of word-count arithmetic.
- **Modified**: `platform-adaptation` stops producing four substitute text
  formats (X threads, Instagram carousels). With video as the deliverable, those
  solve a problem that no longer exists.
- **BREAKING — removed**: `research-agent` document discovery and its scrapers.
- **BREAKING — removed**: `publishing` — Postiz, publish records, the editorial
  calendar, and optimal-time scheduling.
- **BREAKING — removed**: in-house video generation — ElevenLabs narration,
  Unsplash visuals, FFmpeg composition, ffprobe timing, and bilingual subtitle
  generation and review. Nothing inside the system replaces it; video moves
  entirely to external tools.
- **BREAKING — removed**: the covered-cases view and the admin panel's pipeline,
  calendar and video sections.

**Retained deliberately, against a literal reading of "nothing else":**

- **Anti-fabrication validation.** These are real historical records. A quote
  attributed to a named officer that the document does not contain is a
  credibility problem that survives into the video and cannot be quietly
  retracted. This gets stricter, not weaker.
- **Case curation, as a filter.** Curation was built to judge what a scraper
  found, but the judgement is generic: is this document strong enough to carry a
  story? Without it, every upload produces a script regardless of whether the
  material supports one, and local inference is spent on weak documents.
- **Checkpointing.** PDF extraction and multi-chapter generation on a local model
  are exactly the long, failure-prone steps that need resumable progress.

## Capabilities

### New Capabilities

- `document-upload`: accept a PDF, extract its text, and report real progress
  through extraction and analysis — derived from pages and chunks actually
  processed, never a synthetic animation.
- `series-planning`: decide from the document how many chapters it supports and
  what each covers, producing a series outline before any chapter is written, so
  cliffhangers reference material that genuinely comes later.
- `script-export`: hand an approved script to an external video tool via
  clipboard, Markdown, or scene-structured JSON.

### Modified Capabilities

- `story-writing`: chapters are generated against a series plan rather than
  independently; adds recap beats for chapters after the first, cross-chapter
  continuity of names and dates, a distinct finale beat, and a long/short
  duration cut per chapter.
- `platform-adaptation`: reduced from four substitute text formats to the two
  duration cuts of a single script. The four-network fan-out is removed.
- `case-curation`: unchanged in rubric, repositioned as the gate on manual
  uploads rather than on scraper output.
- `research-agent`: removed. Documents arrive by upload.
- `publishing`: removed. The system's output is an approved script, not a post.
- `content-admin-panel`: reduced to upload, script review, and export.

## Impact

**Removed code** — archived on a branch before deletion, so an abandoned
capability stays recoverable:

- `research_agent_use_case`, `jina_scraper`, `firecrawl_scraper`
- `publishing_use_case`, `postiz_publisher`, `publish_records` router and table
- `video_generation_use_case`, `video_management`, `ffmpeg_compositor`,
  `audio_duration`, `elevenlabs_client`, `unsplash_client`
- `subtitle_generation_use_case`, `subtitle_review_use_case`, `subtitle_store`
- `cases_use_case` and the covered-cases view
- Frontend routes: `/calendar`, `/cases`, `/videos`, and the pipeline feed
- Tables: `video_generations`, `publish_records`

**Retained and extended:** `story_writing_use_case`, `case_curation_use_case`,
`script_approval`, the `ILLMClient` port with its Ollama and Anthropic adapters,
the PDF/OCR reading adapters, and checkpointing.

**Dependencies dropped:** ElevenLabs, Unsplash, Postiz, Jina, Firecrawl, and the
FFmpeg/ffprobe system requirement.

**Scripts are generated on local Ollama models**, with the existing provider
switch keeping a paid provider available without code changes.

**Not addressed here:** whether an external tool renders a script faithfully.
That is validated by hand, outside this system, before any integration is
considered — and no such integration is in scope.
