## Context

The editorial pipeline currently generates story chapters with platform-specific text adaptations, but stops at the text layer. To enable short-form video content (TikTok, Instagram Reels), we need to:

1. **Introduce script approval as a mandatory gate** before expensive video generation (TTS + visuals + composition).
2. **Orchestrate video generation** from approved scripts by coordinating TTS (ElevenLabs), visuals (Unsplash), subtitles (auto-generated), and video composition (FFmpeg).
3. **Optimize chapter length** to produce scripts that fit 15–60 second reels when read aloud at typical speaking pace.

Current state:
- `Document` → `Story` (chapters) → `PlatformVersion` (text adaptations) → approval gate → publishing.
- Chapter scripts are generated with no length constraint or video-specific metadata.
- No subtitle generation or video file storage.

Constraints:
- Must remain free/low-cost (Unsplash for visuals, ElevenLabs already budgeted, local FFmpeg).
- Videos stored locally (`data/videos_generated/`) — no cloud upload initially.
- Approval gate enforced structurally: videos only generated for `script_approved` state.
- Existing approval and publishing workflows must remain intact.

## Goals / Non-Goals

**Goals:**
- Editors can review scripts before video generation and edit them without regenerating video.
- Scripts are optimized for speech: 150–220 words/chapter, ≤60 seconds of narration at ~150 words/min.
- Multilingual subtitles (Spanish + English) are generated and approved alongside scripts.
- Approved scripts → videos (audio + visuals + captions) stored locally with metadata.
- Workflow splits into logical interaction points: script review → subtitle review → video generation → approval → publishing.

**Non-Goals:**
- Live streaming or real-time video preview.
- Video effect editing UI (visual directives are authored by AI, not user-editable).
- Autonomous daily video posting (scheduling is manual via the existing `calendario.md`).
- Premium visuals (Unsplash free tier only; no paid stock footage or AI image generation initially).

## Decisions

### Decision 1: Script Approval as Structural Gate

**Choice**: Add `script_approved: bool` and `script_approved_at: datetime` to `PlatformVersion` table. Video generation is only invoked for `script_approved = true`.

**Rationale**: 
- Decouples script authoring from video generation, letting editors make last-minute changes without re-running LLM.
- Reuses existing approval infrastructure (same gate logic, same `approval_gate.run_if_approved` pattern).
- Ensures humans can review text before expensive TTS/visuals/composition.

**Alternatives**:
- New table `ScriptApprovalRecord`: more normalized, but adds operational complexity (two approval gates instead of one).
- Approval groups (e.g., "script approved + video approved"): over-engineered for current use case.

### Decision 2: Chapter Length Optimization via Modified Prompt

**Choice**: Adjust `StoryWritingUseCase` prompt to constrain chapters to 150–220 words, with explicit instruction to embed visual directives (e.g., "POV: classified document + archival footage").

**Rationale**:
- At ~150 words/min speaking pace, 150–220 words = 60–90 seconds of narration. Combined with intro/outro transitions, yields 15–60s reels.
- Visual directives embedded in script allow `PlatformAdaptationUseCase` to propose specific image/video types without additional LLM calls.
- No new model needed—reuse `StoryWritingUseCase` with tighter constraints.

**Alternatives**:
- Post-generation truncation: loses coherence and narrative quality.
- Separate video-writing model: overkill for constraint enforcement; LLM prompt adjustment is sufficient.

### Decision 3: Subtitle Generation as Separate Workflow

**Choice**: New `SubtitleGenerationUseCase` that takes an approved script and produces SRT/VTT with timing cues. Subtitles are part of script approval (editor sees both script and subtitles before approval).

**Rationale**:
- Decouples subtitle timing from video composition. Timing is generated from TTS metadata (phone time), not guessed.
- Bilingual support is explicit: generate Spanish + English for every script.
- Subtitles can be edited before video generation (e.g., correcting AI translations).

**Alternatives**:
- Generate subtitles during video composition: less flexible, harder to edit.
- No subtitles initially: limits accessibility and engagement on platforms that reward closed captions.

### Decision 4: Video Composition via FFmpeg

**Choice**: Local FFmpeg with a Python wrapper (`ffmpeg_compositor.py`) that:
1. Requests TTS audio from ElevenLabs.
2. Fetches visuals from Unsplash (with fallback to solid colors + text overlay).
3. Composites audio + visuals + subtitle track into MP4.

**Rationale**:
- FFmpeg is free, fast, and widely supported.
- Unsplash API is free and requires no auth for ~50 queries/hour (sufficient for editorial workflow).
- No vendor lock-in (can swap ElevenLabs later; can add other visual sources).
- Local storage avoids cloud dependency and keeps data in the project.

**Alternatives**:
- Paid APIs (Synthesia, Runway, Pika): expensive and unnecessary for this use case.
- Browser-based composition (FFmpeg.js): slower, harder to debug, not suitable for backend batch jobs.

### Decision 5: Visual Resolution Strategy

**Choice**: 
1. Parse visual directives from script (e.g., "archival footage of military radar").
2. Query Unsplash API with directive as search term.
3. If no results, fallback to solid color background + large text overlay (script excerpt + source attribution).

**Rationale**:
- Unsplash provides high-quality, free, copyright-safe images.
- Fallback ensures videos are always generated, even if search yields nothing.
- Simple and cheap—no AI image generation or complex cache management.

**Alternatives**:
- Manual asset upload: requires editor involvement for every chapter (friction).
- AI image generation (DALL-E, Midjourney): expensive and requires API keys.
- Static brand images: boring and inflexible.

### Decision 6: Data Model: Video Metadata

**Choice**: New `VideoGeneration` table:
- `id`, `platform_version_id`, `script_approved_at`, `language`, `video_file_path`, `subtitle_file_path`, `status` (pending, generated, failed), `error_message`, `created_at`.
- One row per platform version. If same script needs multiple languages, generate separate video files.

**Rationale**:
- Decouples video generation from platform version (same script → multiple video files for different languages).
- Tracks generation status and enables retries on failure.
- Audit trail: when was video generated, from which approved script version.

**Alternatives**:
- Store video path directly in `PlatformVersion`: loses language tracking, makes retries harder.
- Embed video generation status in `PlatformVersion` (add `video_status` column): works but mixing concerns (approval vs. generation).

### Decision 7: API Workflow: Interaction Split Points

**Choice**: Separate endpoints for each logical step:
1. `POST /chapters/{id}/script/approve` — approve script (create `script_approved` record).
2. `POST /chapters/{id}/subtitles/generate` — generate subtitles from script.
3. `POST /chapters/{id}/video/generate` — generate video from approved script + subtitles.
4. `GET /chapters/{id}/video` — retrieve video file metadata.

**Rationale**:
- Each step is explicitly controlled by the editor (no auto-chaining).
- Decoupled failures: if subtitle generation fails, video generation can be retried independently.
- Mirrors the user's mental model: review script → review subtitles → generate video.

**Alternatives**:
- Single endpoint that does all: loses visibility and control.
- Background queue (Celery/RQ): adds operational complexity; polling is sufficient for editorial workflow.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| **Unsplash rate limit exceeded** (50 req/hour free tier) | Implement local cache of search results; fallback to color + text. Upgrade Unsplash plan if usage grows. |
| **ElevenLabs quota exceeded** | Monitor API usage; queue video generation during off-hours. Fallback to local TTS (e.g., pyttsx3) if budget exhausted. |
| **FFmpeg not installed** | Document installation (`brew install ffmpeg`); add validation in `VideoGenerationUseCase.__init__`. |
| **Long video composition time** (30–60s per video for high-res) | Generate videos asynchronously; show progress bar in UI. Cache visuals and audio to avoid re-fetching. |
| **Storage growth** (100 videos = ~10GB) | Implement retention policy (e.g., delete videos 30 days after publishing). Warn on disk space. |
| **Script approval scope creep** (editors re-generating scripts infinitely) | UI UX: show "regenerate count" and warn after 3 attempts. Require supervisor override for more. |

## Migration Plan

1. **Phase 1: Database schema** — Add `script_approved` columns to `PlatformVersion` via Alembic migration.
2. **Phase 2: Backend use cases** — Implement `VideoGenerationUseCase`, `SubtitleGenerationUseCase`, FFmpeg compositor.
3. **Phase 3: Backend API** — Add script approval and video generation endpoints.
4. **Phase 4: Frontend** — Add script review view to pipeline feed; add video generation UI.
5. **Phase 5: Testing** — Integration tests with real ElevenLabs + Unsplash API (use sandbox credentials).
6. **Rollback**: All changes are additive. Disable new endpoints and revert schema if needed. Existing pipelines unaffected.

## Open Questions

1. **Video resolution & codec**: Start with 1080p MP4 H.264? Or mobile-optimized (720p, H.265)?
2. **TTS voice selection**: Should editors choose voice per chapter, or use a fixed "Archivo Desclasificado" voice per language?
3. **Subtitle styling**: Embed hardcoded captions in video, or separate SRT file for platform upload (better for SEO)?
4. **Legal review**: Any liability concern with AI-generated subtitles/TTS? (Assume "editorial review" covers this per current workflow.)
5. **Platform upload**: Should API auto-upload videos to TikTok/Instagram, or only store locally and rely on Postiz for text?
