## ADDED Requirements

### Requirement: Video Generation from Approved Script
The system SHALL generate a video file (MP4) from an approved script by orchestrating TTS audio, visuals from Unsplash, and subtitle overlays, storing the result locally.

#### Scenario: Video generation succeeds
- **WHEN** `POST /chapters/{id}/video/generate` is called for a chapter with `script_approved = true`
- **THEN** the system requests TTS from ElevenLabs, fetches visuals from Unsplash, composites the audio + visuals + subtitles, and stores the MP4 file in `data/videos_generated/{platform}/{language}/`

#### Scenario: Video generation fails due to missing script approval
- **WHEN** `POST /chapters/{id}/video/generate` is called for a chapter with `script_approved = false`
- **THEN** the system rejects the request with HTTP 409 and returns error "Script must be approved before video generation"

#### Scenario: Video generation tracks status
- **WHEN** a video generation request is submitted
- **THEN** the system creates a `VideoGeneration` record with `status = pending` and returns immediately; video composition happens asynchronously

### Requirement: TTS Integration with ElevenLabs
The system SHALL use ElevenLabs API to generate audio from the approved script in Spanish and English, using consistent voice selections per language.

#### Scenario: Audio is generated for approved script
- **WHEN** video generation is requested for a chapter
- **THEN** the system sends the chapter's `script` to ElevenLabs with language specified (es or en) and receives WAV/MP3 audio

#### Scenario: TTS failure is recoverable
- **WHEN** ElevenLabs API returns an error or quota is exceeded
- **THEN** the `VideoGeneration` record is marked `status = failed` with `error_message` logged, and retry is possible via `POST /chapters/{id}/video/retry`

#### Scenario: Consistent voice per language
- **WHEN** generating audio in Spanish
- **THEN** use voice ID `<SPANISH_VOICE_ID>` (configured in `.env`)
- **WHEN** generating audio in English
- **THEN** use voice ID `<ENGLISH_VOICE_ID>` (configured in `.env`)

### Requirement: Visual Resolution Strategy
The system SHALL fetch visuals from Unsplash API based on directives embedded in the script; if no results, fallback to solid color background with text overlay.

#### Scenario: Visuals are fetched from Unsplash
- **WHEN** video generation is requested
- **THEN** extract visual directive from script (e.g., "classified document + archival footage"), query Unsplash API, download image

#### Scenario: Fallback to color + text if no Unsplash results
- **WHEN** Unsplash returns no results for the visual directive
- **THEN** generate background image (solid color #1a1a1a with text overlay: script excerpt + source attribution)

#### Scenario: Image cache prevents duplicate downloads
- **WHEN** multiple chapters request the same visual directive
- **THEN** Unsplash results are cached locally to avoid redundant API calls

### Requirement: Video Composition with FFmpeg
The system SHALL composite audio, visuals, and subtitle tracks into a single MP4 file using FFmpeg.

#### Scenario: MP4 is generated with correct format
- **WHEN** audio, visuals, and subtitles are ready
- **THEN** FFmpeg composites them into MP4 (1080p, H.264 codec, AAC audio)

#### Scenario: Video duration matches audio duration
- **WHEN** FFmpeg composites the video
- **THEN** the output video duration SHALL match the TTS audio duration (no truncation or padding)

#### Scenario: Subtitles are hardcoded into video
- **WHEN** FFmpeg composites subtitles
- **THEN** subtitle text is rendered directly on the video frame (not as separate SRT track) for platform compatibility

### Requirement: Video File Persistence
The system SHALL store generated video files locally with predictable paths and metadata.

#### Scenario: Video file is stored with metadata
- **WHEN** video generation completes successfully
- **THEN** store MP4 file at `data/videos_generated/{platform}/{language}/{chapter_id}.mp4` and create `VideoGeneration` record with path and timestamp

#### Scenario: Video path is queryable
- **WHEN** `GET /chapters/{id}/video` is called
- **THEN** return metadata: `video_file_path`, `platform`, `language`, `status`, `generated_at`, `size_mb`

### Requirement: Video Generation Retry Mechanism
The system SHALL support retrying video generation without re-generating TTS or re-fetching visuals if only the composition step failed.

#### Scenario: Retry uses cached audio and visuals
- **WHEN** `POST /chapters/{id}/video/retry` is called after a failed composition
- **THEN** reuse cached TTS audio and visuals; only re-run FFmpeg composition step
