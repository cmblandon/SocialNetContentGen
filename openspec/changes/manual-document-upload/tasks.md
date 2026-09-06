## 0. Setup: Create Feature Branch (MANDATORY - FIRST STEP)

- [ ] 0.1 Create feature branch `feature/manual-document-upload` from the current branch (per design.md's Open Question: prefer branching from `feature/research-pipeline-checkpointing` if that change has landed on the working branch by the time this starts, so uploads get checkpoint/resume behavior via the shared per-document helper from day one; otherwise branch from whatever the current base is and follow Decision 3's inline fallback)
- [ ] 0.2 Verify branch creation and current branch status

## 1. Backend: editorial-side text extraction adapter

- [ ] 1.1 Write failing tests for `extract_text(file_path)` (new `src/editorial/infrastructure/uploads/file_text_extractor.py`): a `.txt` file is read directly with `confidence="alta"`; a PDF with a native text layer (mock `PdfTextInspector.tiene_texto_real` → `True`) is converted via `MarkItDown` with `confidence="alta"`; a PDF with no text layer (mock → `False`) goes through `OcrProcessor.aplicar` first, then `MarkItDown`, with `confidence="baja"`; a PDF with no text layer where `OcrProcessor.aplicar` returns `None` (OCR unavailable/failed) raises a clear, distinct exception rather than attempting extraction on nothing
- [ ] 1.2 Implement `extract_text` (constructor-injected `IPdfInspector`/`IOcrProcessor`/`MarkItDown` instances, matching `IngestUseCase`'s existing DI pattern) to make 1.1 pass

## 2. Backend: the upload endpoint

- [ ] 2.1 Write failing tests for `POST /research/upload`: a valid `.txt` upload returns a 200 with a curation outcome (advanced/discarded), and the resulting document was evaluated through `CaseCurationUseCase` (assert via a fake curation use case, matching `test_research_endpoint.py`'s existing fixture style); an unsupported file extension (e.g. `.docx`) returns `422` without attempting extraction; a file exceeding the size limit returns `413`; the endpoint requires no source-URL allowlist check (a document whose "source" is upload, not a URL, is never passed through `_is_allowed_source`)
- [ ] 2.2 Write failing tests confirming the uploaded document is deduplicated exactly like a scraped one: uploading a file whose title already appears in `casos_cubiertos.md` (via a fake/real `CaseCurationUseCase`+`ProjectMemoryStore`) results in no new curation entry and a response indicating it was already evaluated
- [ ] 2.3 Write failing tests confirming the raw uploaded file is persisted to `data/knowledge_base/editorial_uploads/` (using a `tmp_path`-scoped override of that directory, never the real one) with a unique filename that doesn't collide with a prior upload of the same original filename
- [ ] 2.4 Implement `POST /research/upload` in `src/editorial/presentation/routers/research.py`: multipart file field, optional `agency`/`doc_type` form fields, extension/size validation, calls `extract_text`, builds a `ScrapedDocument` (`source_url=None`), saves the raw file, and routes the resulting document through the same per-document curate→write→adapt→persist logic `run_research_cycle` uses (the shared helper from `research-pipeline-checkpointing` if merged onto this branch already; otherwise an equivalent inline call, per design.md Decision 3's fallback) — to make 2.1-2.3 pass

## 3. Backend: Mandatory closing steps

- [ ] 3.1 Review and Update Existing Unit Tests (MANDATORY)
- [ ] 3.2 Run Unit Tests and Verify Database State (MANDATORY) — capture pre/post baseline, run targeted then full suite, create report at `openspec/changes/manual-document-upload/reports/<YYYY-MM-DD>-step-3.2-unit-test-and-db-verification.md`
- [ ] 3.3 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): upload a real small `.txt` fixture and a real small PDF fixture (one with native text, and if feasible one requiring OCR) against a live backend using a test/fake curation wiring or an isolated test database — never mutating the real operator DB/memory files; confirm the response, the persisted upload file, and (if using real curation) the `casos_cubiertos.md` entry; restore/clean up all test artifacts afterward; document exact commands and how real data was kept isolated in the phase report

## 4. Frontend: upload control in Configuración

- [ ] 4.1 Add `uploadDocument(file, agency?, docType?)` to `frontend/src/lib/api.ts`, posting `multipart/form-data` to `/research/upload`
- [ ] 4.2 Write failing tests for a new upload component (or an addition to `SourceUrlManager.tsx`'s view): a file input, optional agency/doc-type fields, and a submit button; submitting calls `uploadDocument(...)` and displays the returned outcome; selecting an unsupported file type shows a rejection message without calling the API
- [ ] 4.3 Implement the component to make 4.2 pass and mount it in `frontend/src/app/settings/page.tsx` alongside `SourceUrlManager`

## 5. Final mandatory closing steps

- [ ] 5.1 Review and Update Existing Unit Tests (MANDATORY) — both backend and frontend
- [ ] 5.2 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/manual-document-upload/reports/<YYYY-MM-DD>-step-5.2-unit-test-and-db-verification.md`
- [ ] 5.3 E2E Testing (MANDATORY — AGENT MUST EXECUTE): re-run the existing Playwright specs against real, running frontend + backend servers to confirm no regression to the Configuración view; if feasible within this environment's E2E data-hygiene constraints, add or extend a scenario covering a successful upload with a small `.txt` fixture; seed/restore data as needed; document in the phase report
- [ ] 5.4 Update Technical Documentation (MANDATORY): `README.md` (new `POST /research/upload`, the `editorial_uploads/` directory, its relationship to the separate ingestion pipeline and `manual_curation_cli.py`), `docs/backend-standards.md` (the new editorial-side text-extraction adapter and its reuse of ingestion-pipeline infrastructure), `docs/frontend-standards.md` (the Configuración upload control)
