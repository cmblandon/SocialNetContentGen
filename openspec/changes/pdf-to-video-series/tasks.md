## 1. Archive before deleting

- [ ] 1.1 Tag the current state and push an `archive/pre-pivot` branch, so the removed capabilities stay recoverable by checkout rather than by archaeology
- [ ] 1.2 Record in the branch's tag message what it contains: the video pipeline, publishing, research-agent, and per-platform text adaptation

## 2. Remove what the new goal does not need

- [ ] 2.1 Remove in-house video generation: `video_generation_use_case`, `video_management`, `ffmpeg_compositor`, `audio_duration`, `elevenlabs_client`, `unsplash_client`, and their routers and tests
- [ ] 2.2 Remove subtitle generation and review: `subtitle_generation_use_case`, `subtitle_review_use_case`, `subtitle_store`, and their router and tests
- [ ] 2.3 Remove publishing: `publishing_use_case`, `postiz_publisher`, the publish-records router, and the calendar handling in `project_memory`
- [ ] 2.4 Remove discovery: `research_agent_use_case`, `jina_scraper`, `firecrawl_scraper`, the research router's discovery endpoints, and the source-URL configuration
- [ ] 2.5 Remove the covered-cases capability: `cases_use_case` and its router
- [ ] 2.6 Remove the four-format platform adaptation, keeping the module only if the duration-cut logic lands there
- [ ] 2.7 Remove frontend routes `/calendar`, `/cases`, `/videos`, and the pipeline feed, with their components and tests
- [ ] 2.8 Drop `video_generations` and `publish_records` via migration; keep `discovered_documents` only if upload reuses it, otherwise drop it too
- [ ] 2.9 Remove now-unused dependencies and config: ElevenLabs, Unsplash, Postiz, Jina, Firecrawl keys, and the FFmpeg/ffprobe requirement from the README
- [ ] 2.10 Run the full suite and delete every test left orphaned by the above — a test for deleted code is noise, not coverage

## 3. Document upload

- [ ] 3.1 Write failing tests for PDF upload: a text-layer PDF, a scanned PDF needing OCR, a corrupt file, and a PDF yielding no text
- [ ] 3.2 Add the upload endpoint accepting a PDF and persisting its extracted text before any generation is attempted
- [ ] 3.3 Reuse the existing PDF/OCR adapters rather than writing new extraction
- [ ] 3.4 Mark OCR-derived text as lower-confidence so the operator knows the source may carry recognition errors
- [ ] 3.5 Reject a non-PDF, corrupt, or empty-after-OCR file with a message naming which of those it was

## 4. Measured progress reporting

- [ ] 4.1 Write failing tests: extraction progress tracks pages processed, generation progress tracks chapters completed, and an unmeasurable step reports as indeterminate
- [ ] 4.2 Report extraction progress from pages processed out of total pages
- [ ] 4.3 Report generation progress from chapters completed out of the plan's chapter count
- [ ] 4.4 Report a step whose remaining duration cannot be derived as indeterminate — never advance a bar on a timer
- [ ] 4.5 Expose progress to the panel by polling or SSE, and name the step currently running so a slow step is distinguishable from a stalled one

## 5. Curation as the upload gate

- [ ] 5.1 Write failing tests: a strong document proceeds, a weak one is blocked with its per-criterion reasoning
- [ ] 5.2 Point the existing five-criterion rubric at uploaded documents; leave the rubric itself unchanged
- [ ] 5.3 Block script generation below the threshold and return the total, per-criterion scores, and reasoning
- [ ] 5.4 Surface the score in the panel so a block is arguable rather than opaque, and so near-threshold non-determinism on a local model is visible

## 6. Series planning

- [ ] 6.1 Write failing tests: a plan is produced before any chapter, chapter count follows narrative beats, a single-beat document yields a one-chapter series
- [ ] 6.2 Add a `SeriesPlan` produced from the document, naming each chapter, what it covers, and the through-line
- [ ] 6.3 Derive chapter count from narrative beats, not from word count
- [ ] 6.4 Persist the plan so chapter generation can resume without re-planning
- [ ] 6.5 Present the plan for approval before any chapter is generated, since rejecting a plan must cost seconds rather than minutes of local inference
- [ ] 6.6 Add a test that a rejected plan generates no chapters

## 7. Chapter generation against the plan

- [ ] 7.1 Write failing tests: a chapter receives the full plan, a cliffhanger references material assigned to a later chapter, the final chapter resolves instead of teasing
- [ ] 7.2 Pass the whole series plan into each chapter's generation, not only that chapter's entry
- [ ] 7.3 Require a recap beat opening every chapter after the first
- [ ] 7.4 Require the final chapter to resolve the through-line, or to name explicitly what the document leaves unresolved
- [ ] 7.5 Enforce continuity of names, dates and the incident's label across chapters
- [ ] 7.6 Add a test that a cliffhanger referencing nothing in the plan or the document is rejected

## 8. Duration cuts

- [ ] 8.1 Write failing tests: both cuts are produced, the short cut carries the same facts and citations as the long cut, each cut's length matches its target runtime
- [ ] 8.2 Generate the long cut sized for 3–5 minutes of narration
- [ ] 8.3 Derive the short cut by compressing the approved long cut, so a slow local model is not asked to write the chapter twice
- [ ] 8.4 Validate each cut's word count against its own target runtime range

## 9. Anti-fabrication, strengthened

- [ ] 9.1 Write failing tests: a quote absent from the document is rejected, and a later chapter citing an earlier chapter's prose as source is rejected
- [ ] 9.2 Keep quote verification against the source document, and extend it across the series so an invention in chapter 1 cannot become a documented fact by chapter 3
- [ ] 9.3 Keep rejection of overstated claims
- [ ] 9.4 Confirm no validation path can be satisfied by a warning — a failed check always regenerates or fails

## 10. Retry against validation feedback

- [ ] 10.1 Write failing tests: a draft failing once then passing, a draft never passing (bounded, raises the last error), and a valid first attempt making no extra call
- [ ] 10.2 Feed the specific validation failure back into the retry prompt
- [ ] 10.3 Bound retries and surface the last error when the model does not converge
- [ ] 10.4 Add a test asserting the length ranges are unchanged, so a future attempt to widen them to fit a weak model fails loudly

## 11. Script approval

- [ ] 11.1 Keep the approve/reject state machine; remove its four-platform fan-out
- [ ] 11.2 Rework approval to act on a chapter's script rather than on a platform version
- [ ] 11.3 Keep the rule that editing a script resets its approval
- [ ] 11.4 Update the approval tests for the new unit of work

## 12. Export

- [ ] 12.1 Write failing tests for each format, and for export being unavailable on a pending or rejected script
- [ ] 12.2 Copy to clipboard: full narration, visual directions, chapter number, source citation
- [ ] 12.3 Download as Markdown, readable and archivable outside the panel
- [ ] 12.4 Download as scene-structured JSON, ordered scenes each carrying narration and visual direction
- [ ] 12.5 Record that a script was exported, and take no further action — no video API key, no rendering request, no stored video

## 13. Admin panel

- [ ] 13.1 Reduce navigation to upload, review, and export
- [ ] 13.2 Build the upload view with measured progress and the current step named
- [ ] 13.3 Build the series review view: chapter breakdown, through-line, approve or reject the plan
- [ ] 13.4 Build the script review view: full text, visual directions, series position, citation, approve or reject
- [ ] 13.5 Add the export controls to approved scripts only
- [ ] 13.6 Add component tests for each view, including that no discovery, scheduling, publishing or rendering control is rendered anywhere

## 14. Verification

- [ ] 14.1 Run a real declassified PDF end to end on the local model: upload, curate, plan, generate, approve, export
- [ ] 14.2 Record measured timings per step, so the progress reporting can be judged against reality
- [ ] 14.3 Have the operator read the generated chapter one and judge whether the plot quality justifies the pivot — this is the assumption the whole change rests on, and it is unproven until a human reads the output
- [ ] 14.4 Paste an exported script into an external video tool by hand and confirm the export format is usable before declaring export done
- [ ] 14.5 Update the README to describe only the surviving system

## 15. Documentation

- [ ] 15.1 Rewrite the README around the new flow and delete the sections for removed capabilities
- [ ] 15.2 Add an ADR recording why in-house video generation was removed in favour of external tools, and what would have to be true to bring it back
- [ ] 15.3 Update the editor guide for the upload → plan → script → export flow
- [ ] 15.4 Archive the superseded OpenSpec changes whose capabilities this change removes
