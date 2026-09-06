## Why

Currently, the editorial pipeline converts classified documents into narrative stories and adapts them as text per platform, but stops before video generation. To reach TikTok/Instagram reel audiences with short-form video (15–60 seconds), we need to:

1. **Add script approval workflow**: Editors must review and approve scripts BEFORE video generation, not after—enabling last-minute changes at lower cost.
2. **Generate reels from approved scripts**: Convert approved scripts into video files with TTS audio, visuals, and captions, stored locally and ready for platform upload.
3. **Support multilingual subtitles**: Auto-generate subtitles in Spanish and English, approved alongside the script to ensure accuracy and cultural fit.

## What Changes

- **New**: Chapter-to-reel pipeline that turns approved scripts into video files with audio and captions.
- **New**: Frontend UI for script review: editors see each chapter's script, approve/edit/regenerate before video generation.
- **New**: Subtitle generation and approval integrated into the script-review workflow.
- **New**: Video file persistence to local storage (`data/videos_generated/`) with metadata tracking.
- **Modified**: `StoryWritingUseCase` to optimize chapter length for short-form video (≤60 seconds of narration).
- **Enhanced**: `PlatformAdaptationUseCase` to produce video-ready payloads (script + visual directives + timing cues).

## Capabilities

### New Capabilities

- `script-approval-workflow`: API and UI for editors to review, edit, and approve chapter scripts before video generation. Scripts start in `pending_script_review` state and transition to `script_approved` only after explicit approval.
- `video-generation-from-script`: Convert an approved script into a video file: resolve audio (ElevenLabs TTS), match visuals (Unsplash API with fallback to color/text), generate captions (via subtitle-generation), and composite into final reel.
- `subtitle-generation-and-approval`: Auto-generate Spanish and English subtitles from script with timing cues. Subtitles are part of script approval (editor can edit before video generation).
- `reel-optimized-chapters`: Modify `StoryWritingUseCase` to produce chapters optimized for short-form video: 150–220 words, ≤60 seconds of narration, with visual directives and pacing cues embedded.
- `video-file-persistence`: Store generated video files locally with metadata: script version, platform, language, generated timestamp, status.

### Modified Capabilities

- `story-writing`: Chapter generation is now length-optimized for reels and includes visual directives and timing metadata (not just script text).
- `platform-adaptation`: Platform versions now include video-ready directives (visual suggestions, pacing, caption timing) in addition to text.

## Impact

**New files/modules:**
- `src/editorial/application/video_generation_use_case.py` – orchestrates TTS, visuals, video composition.
- `src/editorial/application/subtitle_generation_use_case.py` – generates SRT/VTT with timing.
- `src/editorial/infrastructure/video/ffmpeg_compositor.py` – FFmpeg wrapper for video assembly.
- `src/editorial/infrastructure/external/unsplash_client.py` – fetch visuals from Unsplash.
- `src/editorial/presentation/routers/script_approval.py` – new endpoints for script review workflow.
- `frontend/src/views/ScriptApprovalView.tsx` – new UI component for editors.
- Database: new tables/columns in `editorial.sqlite` for script approval state and video metadata.

**Modified files:**
- `src/editorial/application/story_writing_use_case.py` – adjust prompt and chapter constraints for reel length.
- `src/editorial/application/platform_adaptation_use_case.py` – add visual directives.
- `src/editorial/infrastructure/persistence/models.py` – add columns: `script_approved_at`, `video_file_path`, `subtitle_lang`.
- `frontend/` – add script-approval view to pipeline feed.

**Dependencies:**
- ElevenLabs API (already in `.env` as `ELEVENLABS_API_KEY`).
- FFmpeg (local installation).
- Unsplash API (free tier, no auth required for basic usage; optional auth for higher limits).

**Breaking Changes:** None—the new workflow is additive. Existing approval gate logic is preserved; script approval is an additional gate before video generation.

## Implementation Notes

Recorded during implementation, for whoever reads this after it is archived.
These are the places where what was built diverges from what was proposed, or
where the reasoning is not obvious from the code.

**Amended specs.** Three scenarios in the original specs described behaviour
that turned out to be wrong and were corrected in place rather than left to
mislead:
- File paths were specified as `{chapter_id}_{uuid}.mp4`. Paths are
  deterministic with no UUID, because a retry has to find and reuse the
  previous attempt's audio and image; a unique path per attempt would re-buy
  narration every time.
- Subtitle timing was specified as estimated from ~150 wpm. It is measured
  with `ffprobe`, because an estimate drifts against real TTS output and the
  drift accumulates across a chapter.
- Deletion was specified as removing the record. It is a soft delete:
  `retry_of_id` is a self-referential FK with no cascade, so removing an
  attempt with retries would break the lineage the audit trail must report.

**Added beyond the original plan.**
- `GET /videos/{id}/file` (tasks 10.6–10.7). Phase 13 assumed the browser
  could play a video, but `video_file_path` is a server filesystem path and
  nothing served bytes. Preview and download were unbuildable until this
  existed.
- `deleted_at` column and migration 0005, for the soft delete above.
- Disk capacity in `/videos/stats` (task 10.8). `design.md` names storage
  growth as a risk mitigated by "warn on disk space", but stats reported only
  space *used*.
- `Pillow` in `requirements.txt`. The colour+text fallback needs it, and the
  fallback is the normal path whenever Unsplash has no key — so generation
  would have failed 100% of the time in a fresh environment.

**Scoping decisions made with the author.**
- Script approval is chapter-scoped and fans out to all four platform
  versions, even though the flag lives on `PlatformVersion`. The script is
  one shared text; approving it four times would be busywork.
- Editing UI is inline, not modal. `tasks.md` says "modal", but this panel
  has no modal primitive and `CasesView` already edits in place.
- `triggered_by` in the audit trail is always `null`. The service has no
  authentication, so no caller identity exists to record. The field is kept
  so attribution can be added later without changing the response shape.
- Video duration (task 14.1) was deferred: it is the only remaining gap
  needing a migration, and chapter length is already constrained to 150–220
  words, so duration is largely implied.

**Never verified against real services.** Tasks 2.4, 6.6, 9.6 and 15.6 remain
open. Every test substitutes ElevenLabs, Unsplash and FFmpeg, so the
request/response shapes against the live APIs are unproven, as is the actual
audio/video output quality. The E2E spec (`frontend/e2e/script-to-video.spec.ts`)
is written but has not been executed.
