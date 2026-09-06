## Context

The editorial pipeline has exactly one automated input path today: `ResearchAgentUseCase.discover()`, which scrapes a fixed list of operator-supplied URLs restricted to an official-source allowlist (`ALLOWED_SOURCE_DOMAINS`). The only manual path, `manual_curation_cli.py`, requires a `FichaEstructurada` already produced by the *separate* ingestion pipeline (`python -m src.main`, itself requiring a local MLX model server) and then bypasses curation entirely — `run_manual_curation()` goes straight to `StoryWritingUseCase`/`PlatformAdaptationUseCase`, with the human supplying `doc_type` and `narrative_angle` directly instead of curation producing them.

There is no way today to hand the editorial service a file directly (no separate ingestion step, no CLI) and have it evaluated the same way a scraped document is — scored by `CaseCurationUseCase`, and only advanced to story-writing if it clears the threshold.

The ingestion pipeline's full PDF-to-text flow (`IngestUseCase.procesar_pdf` → `_preparar_pdf` → `_extraer_texto`, `src/application/ingest_use_case.py`) is three pieces working together: `PdfTextInspector.tiene_texto_real(pdf_path)` (heuristic: enough extractable text in the first few pages, `src/infrastructure/pdf/pdf_reader.py`) decides whether OCR is needed; if so, `OcrProcessor.aplicar(pdf_path, output_dir)` shells out to `ocrmypdf` and returns the OCR'd file path (or `None` if `ocrmypdf` isn't installed or fails); either way, the resulting (original-or-OCR'd) PDF path is then run through `markitdown.MarkItDown().convert(str(path)).text_content` to actually produce the extracted text string — `PdfTextInspector`/`OcrProcessor` alone only decide *whether* OCR is needed and *perform* it; they don't extract text themselves.

## Goals / Non-Goals

**Goals:**
- An uploaded PDF or plain-text file becomes a document that goes through the exact same curation → writing → adaptation pipeline as a scraped one — same scoring, same threshold, same `casos_cubiertos.md` recording.
- Reuse the ingestion pipeline's existing, already-tested PDF/OCR adapters rather than duplicating that logic in `src/editorial/`.
- A minimal panel control to upload a file, consistent with this project's "no unnecessary complexity" posture.

**Non-Goals:** see proposal.md (video/image/audio, batch upload, automated authenticity verification, changes to the ingestion pipeline or `manual_curation_cli.py`).

## Decisions

### 1. Reuse `PdfTextInspector`/`OcrProcessor`/`MarkItDown` directly via a thin editorial-side adapter, not a duplicate implementation
New `src/editorial/infrastructure/uploads/file_text_extractor.py` wraps `src.infrastructure.pdf.pdf_reader.PdfTextInspector`/`OcrProcessor` and `markitdown.MarkItDown` (imported directly — all three are stateless, dependency-light utilities, not domain logic tied to the ingestion bounded context's own entities) behind a small editorial-side function, `extract_text(file_path: Path) -> ExtractedText` (dataclass: `text: str`, `confidence: Literal["alta", "baja"]` — "alta" when a native text layer was found, "baja" when OCR was needed, mirroring `ScrapedDocument.extraction_confidence`'s existing two values), following the exact same detect → OCR-if-needed → `MarkItDown.convert(...).text_content` sequence as `IngestUseCase._preparar_pdf`/`_extraer_texto`. Plain-text (`.txt`) files skip all of this — read directly, `confidence="alta"`.
**Alternative considered**: duplicate a parallel inspector/OCR/MarkItDown pipeline inside `src/editorial/infrastructure/`, to keep the two bounded contexts fully independent per `docs/backend-standards.md`'s framing. Rejected: that framing is about *domain* independence (different entities, different persistence, different concerns) — PDF text detection, `ocrmypdf` invocation, and MarkItDown conversion are generic, stateless infrastructure utilities with zero coupling to either context's domain model; duplicating already-tested subprocess/OCR/conversion code for the sake of a boundary that wouldn't actually be crossed in any meaningful (domain-coupling) sense is unjustified duplication, not architectural hygiene.

### 2. No source-URL allowlist check for uploads; the same title-based dedup applies unchanged
`ResearchAgentUseCase._is_allowed_source` governs *scraping* — it exists because an autonomous scraper has no human judgment about whether a page belongs to a real official source. An upload is the opposite case: a human explicitly selected and submitted this specific file, which *is* the provenance decision. No new verification step is added. Deduplication still works exactly as it does for scraped documents today, since `CaseCurationUseCase.curate()` already dedups by `document.title` (a string-containment check against `casos_cubiertos.md`), independent of `source_url` — an uploaded `ScrapedDocument`-shaped record naturally participates in this without any change to `curate()`.

### 3. An upload produces a `ScrapedDocument`, entering the pipeline through the same per-document processing as a discovered one
`POST /research/upload`'s handler builds a `ScrapedDocument` (`title` from an optional form field or the filename, `agency` from an optional form field defaulting to `""`, `doc_type` from an optional form field defaulting to an inferred value or `"document"`, `extracted_text` from the extractor, `source_url=None`, `extraction_confidence` from the extractor) and passes it into the same shared per-document curate→write→adapt→persist helper that `research-pipeline-checkpointing`'s design introduces (Decision 2 of that change) for scraped documents — so an uploaded document is checkpointed, curated, and (if advanced) written/adapted exactly like a scraped one, with the same failure isolation.
**Sequencing note**: this change is written to depend on that shared helper existing. If `research-pipeline-checkpointing` has not yet landed when this change is implemented, the fallback is to call `run_research_cycle`'s equivalent inline logic directly (today's un-refactored version) — functionally correct either way, but the shared-helper version is preferred and should be used if available at implementation time. See Open Questions.

### 4. Store the raw uploaded file on disk, not in the database
`data/knowledge_base/editorial_uploads/<uuid>_<original_filename>` — write-once, never modified, following this project's existing "plain files on disk, not blobs in SQL" pattern (`ProjectMemoryStore`, the ingestion pipeline's `data/docs_raw/`). Not referenced by any DB column in this change (no `Document.source_upload_path` field) — if that's needed later for the panel to let an operator re-download the original, it's a small additive follow-up, not required for the core capability.

### 5. Validation: file type and size
Accept `.pdf` and `.txt` only (by extension and a basic content-type check); reject anything else with `422`. A generous but bounded size limit (e.g. 20MB) rejected with `413` — prevents an accidental multi-hundred-MB upload from blocking the request thread or exhausting disk, without building a full streaming-upload system for a single-operator internal tool.

### 6. Frontend: a small upload form in Configuración, not a new view
Per this project's minimal-UI-per-feature precedent: a file input, optional "Agencia"/"Tipo de documento" text fields, and an "Subir documento" button, mounted in `/settings` next to `SourceUrlManager`. On success, show the resulting curation outcome inline (advanced/discarded/pending — matching whatever `POST /research/upload`'s response shape reports), not a redirect elsewhere.

## Risks / Trade-offs

- **[Risk]** Reusing `ocrmypdf` via subprocess (as the ingestion pipeline already does) means OCR silently no-ops if `ocrmypdf` isn't installed on the server running the editorial service (`OcrProcessor.aplicar` returns `None` and logs an error, per existing behavior). **[Mitigation]** If OCR is unavailable and the PDF has no native text layer, `POST /research/upload` returns a clear `422`/`500` distinguishing "no extractable text and OCR unavailable" from other failures, rather than silently persisting an empty document.
- **[Risk]** An uploaded file bypassing the allowlist means the editorial service will happily curate/write about literally anything a user uploads, with no source-quality gate at all (curation's scoring is about narrative/production quality, not source legitimacy). **[Accepted]**: this matches the explicit intent — uploads are for content the operator already trusts and has in hand; the scraping allowlist was never meant to gate manually-vetted content, per `manual_curation_cli.py`'s existing precedent of trusting a human-selected `doc_id` unconditionally.
- **[Risk]** Depends on `research-pipeline-checkpointing`'s shared helper for its cleanest implementation (Decision 3). **[Mitigation]** Non-blocking fallback documented in Decision 3; functionality doesn't require that change to land first, just benefits from it.

## Migration Plan

1. Add the editorial-side text-extraction adapter wrapping the ingestion pipeline's PDF/OCR classes.
2. Add `POST /research/upload`, building a `ScrapedDocument` and routing it through the shared (or inline, per Decision 3's fallback) per-document pipeline logic.
3. Frontend: upload form in Configuración.
4. Mandatory verification: unit tests (including a real small PDF and `.txt` fixture), curl testing (upload flow end to end against a real test PDF, confirming curation/threshold/dedup behavior matches a scraped-document equivalent), E2E regression check, documentation updates.

Rollback: revert the commit(s); no schema change in this capability itself (it reuses whatever persistence `research-pipeline-checkpointing` or today's `run_research_cycle` already provides), no data migration involved. The `editorial_uploads/` directory can be left in place or cleared independently.

## Open Questions

- Should this change be implemented before or after `research-pipeline-checkpointing`? Recommended order: checkpointing first, so uploads get checkpoint/resume behavior for free via the shared helper from day one, rather than being retrofitted onto it later. Not a hard blocker either way (Decision 3's fallback covers implementing this first if needed).
- Should the panel let an operator see/re-download previously uploaded files? Deferred — start with write-once storage and no read-back UI; add if it proves needed.
