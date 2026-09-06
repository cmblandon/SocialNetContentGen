## Why

Today the only way content enters the editorial pipeline is `research_agent.discover()` scraping URLs from a fixed official-source allowlist, or the `manual_curation_cli.py` CLI tool — which requires the file to already be processed by the *separate* ingestion pipeline first (its own local-MLX-model CLI step) and, once there, skips curation entirely rather than going through the same scoring/threshold gate every other document does. There is no way for an operator who already has a file in hand (a FOIA response PDF, a screenshot, a text transcript) to feed it into the pipeline directly — through the panel or a single API call — and have it evaluated the same way a scraped document would be.

## What Changes

- Add `POST /research/upload`: accepts a single uploaded file (PDF or plain text) plus optional `agency`/`doc_type` hints, extracts its text (reusing the ingestion pipeline's existing PDF/OCR adapters for PDFs), and feeds the result into the same curate → write → adapt → persist pipeline every scraped document goes through — including the same curation scoring/threshold gate (no skip-curation shortcut, unlike `manual_curation_cli.py`).
- An uploaded document has no source URL and is exempt from the official-source-domain allowlist check (`ResearchAgentUseCase`'s allowlist governs *scraping*; a human explicitly uploading a file is itself the provenance/trust decision for that document) — it still goes through the existing title-based dedup against `casos_cubiertos.md`, same as any other document.
- Add a minimal upload control to the Configuración view (file picker + optional agency/doc-type fields + submit), alongside the existing source-URL manager, since both are about controlling what feeds the pipeline.
- Persist the raw uploaded file to disk (a new `data/knowledge_base/editorial_uploads/` directory) for basic provenance, mirroring the ingestion pipeline's plain-files-on-disk pattern — no database blob storage.

**Non-Goals**:
- No support for video/image/audio uploads — PDF and plain text only, matching what the existing PDF/OCR tooling already handles; anything else is a validation error.
- No change to `manual_curation_cli.py` or the separate ingestion pipeline — this is a new, independent input path for the editorial service, not a replacement for either.
- No batch upload (multiple files in one request) — one file per call, matching the "one document, one evaluation" mental model curation already has.
- No automated content/authenticity verification of an uploaded file — per the allowlist exemption above, the human uploading it is the trust decision; this change does not add any new verification machinery.

## Capabilities

### New Capabilities
- `manual-document-upload`: accept an uploaded file, extract its text, and feed it into the existing curation/writing/adaptation pipeline as an alternate document source alongside URL scraping.

### Modified Capabilities
- `content-admin-panel`: the Configuración view gains a file-upload control.

## Impact

- **Backend**: a new `POST /research/upload` endpoint (`src/editorial/presentation/routers/research.py` or a new router); a new editorial-side text-extraction adapter reusing `src/infrastructure/pdf/pdf_reader.py`'s `PdfTextInspector`/`OcrProcessor`; reuse of the shared per-document curate→write→adapt→persist logic (from `research-pipeline-checkpointing`, if that change has landed — see design.md's Open Question on sequencing).
- **Frontend**: `frontend/src/lib/api.ts` (`uploadDocument()`), `frontend/src/components/SourceUrlManager.tsx` or a new small component mounted alongside it in `/settings`.
- **Filesystem**: new `data/knowledge_base/editorial_uploads/` directory for raw uploaded files (not committed, matching `data/`'s existing `.gitignore` treatment).
- **Existing tests touched**: none directly broken — this is a wholly new endpoint/component; `test_research_endpoint.py`-adjacent new test file, new frontend test file.
- **No breaking changes**: purely additive.
