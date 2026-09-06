## 1. Database Schema & Migrations

- [x] 1.1 Create Alembic migration for `PlatformVersion.script_approved` and `script_approved_at` columns
- [x] 1.2 Create Alembic migration for new `VideoGeneration` table (id, platform_version_id, language, video_file_path, subtitle_file_path, status, error_message, retry_of_id, created_at, generated_at)
- [x] 1.3 Add `script_approved` and `script_approved_at` fields to `PlatformVersion` SQLAlchemy model
- [x] 1.4 Create `VideoGeneration` SQLAlchemy model and add relationship to `PlatformVersion`
- [x] 1.5 Create Alembic migration for `VideoGeneration.deleted_at` (soft delete — `retry_of_id` is a self-referential FK with no cascade, so a hard delete would break the retry lineage the audit trail requires)
- [x] 1.6 Add `deleted_at` field to `VideoGeneration` SQLAlchemy model and exclude soft-deleted rows from listings
- [x] 1.7 Run migrations locally and verify schema

## 2. Backend Core: Story Writing Optimization

- [x] 2.1 Update `StoryWritingUseCase` prompt template to request reel-optimized chapters (150–220 words, visual directives, pacing cues)
- [x] 2.2 Modify `_build_chapter()` to extract and validate visual directives from LLM response
- [x] 2.3 Add test coverage for visual directive parsing (verify directives are present in generated chapters)
- [ ] 2.4 Test modified story generation end-to-end to confirm 150–220 word constraint is enforced

## 3. Backend Core: Subtitle Generation

- [x] 3.1 Create `SubtitleGenerationUseCase` class with method `generate_subtitles(script: str, language: str) -> SubtitleDraft`
- [x] 3.2 Implement SRT format generation (text, timing, 4-digit milliseconds per SRT spec)
- [x] 3.3 Integrate with ElevenLabs TTS to fetch audio duration for accurate timing
- [x] 3.4 Add Spanish-to-English translation logic (via LLM) for bilingual subtitles
- [x] 3.5 Implement subtitle caching (store generated SRT locally to avoid re-generation)
- [x] 3.6 Add unit tests for subtitle generation and timing accuracy

## 4. Backend Infrastructure: TTS & Visuals

- [x] 4.1 Create `ElevenLabsTextToSpeechClient` class wrapping ElevenLabs API (handles audio generation, voice selection, language routing)
- [x] 4.2 Add configuration for Spanish and English voice IDs in `.env` and `settings.py`
- [x] 4.3 Create `UnsplashImageClient` class for fetching images (search, caching, fallback to solid color)
- [x] 4.4 Implement fallback strategy: solid color + text overlay when Unsplash returns no results
- [x] 4.5 Add unit tests for TTS client (mock ElevenLabs API)
- [x] 4.6 Add unit tests for Unsplash client (mock API, test fallback)

## 5. Backend Infrastructure: Video Composition

- [x] 5.1 Create `FFmpegCompositor` class wrapping FFmpeg for video assembly
- [x] 5.2 Implement method `composite(audio_path, visual_path, subtitle_path) -> video_path` to produce MP4
- [x] 5.3 Add FFmpeg command construction: handle 1080p H.264 codec, AAC audio, hardcoded subtitles
- [x] 5.4 Implement directory creation for `data/videos_generated/{platform}/{language}/`
- [x] 5.5 Add video file validation (check file exists, size > 0)
- [x] 5.6 Add unit tests for FFmpeg compositor (use temp files, verify output format)
- [x] 5.7 Verify FFmpeg is installed; add installation docs

## 6. Backend Use Case: Video Generation

- [x] 6.1 Create `VideoGenerationUseCase` class with method `generate_video(platform_version_id, language) -> VideoGenerationResult`
- [x] 6.2 Implement workflow: check script approval → request TTS → fetch visuals → generate subtitles → composite video → persist metadata
- [x] 6.3 Add error handling for each step (TTS failure, Unsplash failure, FFmpeg failure) with retry-friendly status tracking
- [x] 6.4 Implement video file path construction and storage
- [x] 6.5 Add unit tests for video generation orchestration (mock all external services)
- [ ] 6.6 Add integration tests against real ElevenLabs + Unsplash (use sandbox credentials)

## 7. Backend API: Script Approval Endpoints

- [x] 7.1 Create `/chapters/{id}/script/approve` POST endpoint (set `script_approved = true`)
- [x] 7.2 Create `/chapters/{id}/script/reject` POST endpoint (set `script_approved = false`)
- [x] 7.3 Create `/chapters/{id}/script/update` POST endpoint (update script text, reset `script_approved`)
- [x] 7.4 Create `/chapters/pending/scripts` GET endpoint (list all chapters with pending/approved scripts)
- [x] 7.5 Add request/response validation and error handling
- [x] 7.6 Add unit tests for script approval endpoints

## 8. Backend API: Subtitle Endpoints

- [x] 8.1 Create `/chapters/{id}/subtitles/generate` POST endpoint (generate ES + EN subtitles)
- [x] 8.2 Create `/chapters/{id}/subtitles` GET endpoint (retrieve generated subtitles)
- [x] 8.3 Create `/chapters/{id}/subtitles/update` POST endpoint (editor edits subtitle text)
- [x] 8.4 Add validation to reject generation if script not approved
- [x] 8.5 Add unit tests for subtitle endpoints

## 9. Backend API: Video Generation Endpoints

- [x] 9.1 Create `/chapters/{id}/video/generate` POST endpoint (trigger video generation, return immediately with pending status)
- [x] 9.2 Create `/chapters/{id}/video` GET endpoint (retrieve video metadata: path, status, size, language, generated_at)
- [x] 9.3 Create `/chapters/{id}/video/retry` POST endpoint (retry failed video generation)
- [x] 9.4 Add validation to reject generation if script not approved
- [x] 9.5 Add unit tests for video generation endpoints
- [ ] 9.6 Add integration tests with real ElevenLabs + Unsplash

## 10. Backend API: Video Management Endpoints

- [x] 10.1 Create `/videos?status=generated` GET endpoint (list all generated videos with metadata)
- [x] 10.2 Create `/videos/{id}` DELETE endpoint (delete video file and metadata)
- [x] 10.3 Create `/videos/stats` GET endpoint (total storage, count by status, largest videos)
- [x] 10.4 Create `/chapters/{id}/audit` GET endpoint (audit trail of video generation attempts)
- [x] 10.5 Add unit tests for video management endpoints
- [x] 10.6 Create `/videos/{id}/file` GET endpoint streaming the MP4 with Range support (the admin panel cannot play a server-side filesystem path; required by 13.3 and 13.5)
- [x] 10.7 Add unit tests for video file retrieval, including path confinement to `data/videos_generated/`
- [x] 10.8 Report free/total disk capacity in `/videos/stats` (design.md names storage growth as a risk mitigated by warning on disk space; required by 14.3)

## 11. Frontend: Script Approval View

- [x] 11.1 Create `ScriptReviewCard` component (display script, visual directives, source citation)
- [x] 11.2 Add approve/reject/edit buttons to ScriptReviewCard
- [x] 11.3 Create `ScriptApprovalView` page (list of pending scripts, search/filter, bulk actions)
- [x] 11.4 Implement script edit modal (textarea for script text, with character count and word count feedback)
- [x] 11.5 Integrate `ScriptReviewCard` into Pipeline feed
- [x] 11.6 Add loading/error states and toast notifications

## 12. Frontend: Subtitle Review View

- [x] 12.1 Create `SubtitleReviewCard` component (display ES + EN subtitles with timing side-by-side)
- [x] 12.2 Add edit modal for subtitle text (preserves timing)
- [x] 12.3 Integrate subtitle review into Pipeline feed (shown after script approval)
- [x] 12.4 Add language toggle (view ES/EN subtitles separately or side-by-side)
- [x] 12.5 Add unit tests for subtitle components

## 13. Frontend: Video Generation UI

- [x] 13.1 Create `VideoGenerationCard` component (show generation status: pending/generated/failed, display generated video preview)
- [x] 13.2 Add "Generate Video" button in Pipeline feed (triggers generation, shows loading)
- [x] 13.3 Implement video preview modal (show MP4 preview with subtitles)
- [x] 13.4 Add retry button for failed video generation
- [x] 13.5 Add download/share buttons for generated videos
- [x] 13.6 Add polling for async video generation status (e.g., poll every 5s until status != pending)

## 14. Frontend: Video Management Views

- [x] 14.1 Add "Videos" page/tab listing all generated videos with metadata (size, platform, language, generated date). Duration deferred: it needs a `duration_seconds` column and migration, and chapter length is already constrained to 150–220 words (~60–90s), so it is largely implied
- [x] 14.2 Add filters: by platform, language, status, date range
- [x] 14.3 Add storage usage indicator (total used, remaining disk space warning)
- [x] 14.4 Add delete button for individual videos
- [x] 14.5 Add "Download all" button for batch export
- [x] 14.6 Add unit tests for video management UI

## 15. Integration & End-to-End Testing

- [ ] 15.1 Test full workflow: document → story → script approval → subtitle generation → video generation
- [ ] 15.2 Integration test: approve script, then attempt video generation (verify it succeeds)
- [ ] 15.3 Integration test: edit script after approval, verify script_approved resets
- [ ] 15.4 Integration test: retry failed video generation with cached TTS/visuals
- [ ] 15.5 E2E test in frontend: flow through script approval → subtitle review → video generation (using test data)
- [ ] 15.6 Test with real ElevenLabs + Unsplash APIs (use small test document)

## 16. Documentation & Deployment

- [ ] 16.1 Update README.md: add "Video Generation" section with setup steps (FFmpeg install, ElevenLabs/Unsplash API keys in .env)
- [ ] 16.2 Update OpenSpec change summary: add implementation notes for future reference
- [ ] 16.3 Add ADR (Architecture Decision Record) documenting FFmpeg, Unsplash, and subtitle choices
- [ ] 16.4 Document API endpoints in OpenAPI/Swagger (if applicable)
- [ ] 16.5 Write user guide for editors: "How to Approve Scripts and Generate Videos"
- [ ] 16.6 Tag release version and merge to main

## 17. Monitoring & Fallback

- [ ] 17.1 Add logging for video generation pipeline (TTS requests, Unsplash queries, FFmpeg calls, errors)
- [ ] 17.2 Add metrics: video generation success rate, average composition time, storage usage
- [ ] 17.3 Document fallback behavior: Unsplash → color + text, ElevenLabs quota → retry later, FFmpeg failure → mark as failed
- [ ] 17.4 Add admin panel alert: low disk space, high API usage
