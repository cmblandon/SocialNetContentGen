## ADDED Requirements

### Requirement: Video Metadata Tracking
The system SHALL persist metadata for each generated video in the database, enabling retrieval, retry, and audit trail.

#### Scenario: Video metadata is recorded after generation
- **WHEN** video generation completes successfully
- **THEN** create a `VideoGeneration` record with: `platform_version_id`, `language`, `video_file_path`, `subtitle_file_path`, `status = "generated"`, `generated_at = now()`

#### Scenario: Failed video generation is logged
- **WHEN** video generation fails
- **THEN** create a `VideoGeneration` record with: `status = "failed"`, `error_message` set to exception message, `generated_at = now()`

#### Scenario: Video metadata is queryable
- **WHEN** `GET /chapters/{id}/video` is called
- **THEN** return list of `VideoGeneration` records for that chapter, including path, language, status, size, and timestamp

### Requirement: Local File Storage
The system SHALL store video files locally in a predictable directory structure without uploading to cloud storage.

#### Scenario: Video files are stored locally
- **WHEN** video generation completes
- **THEN** save MP4 file to `data/videos_generated/{platform}/{language}/{chapter_id}.mp4`

#### Scenario: File paths are deterministic so retries can reuse prior work
- **WHEN** a generation attempt is retried after a failure
- **THEN** the retry SHALL resolve the same paths as the failed attempt, so any audio, visual, or subtitle file the failed attempt already produced is reused rather than regenerated
- **AND** file paths SHALL NOT include a UUID or other per-attempt component, since a unique path per attempt would make prior work unfindable and force a full re-render (including paid TTS) on every retry

#### Scenario: Narration and subtitles are shared across a chapter's platforms
- **WHEN** a chapter's video is generated for more than one platform in the same language
- **THEN** the narration audio SHALL be stored once at `data/audio/{chapter_id}/{language}.mp3` and the canonical subtitle track once at `data/subtitles/{chapter_id}/{language}.srt`, both keyed by chapter and language only
- **AND** these SHALL be reused across all of that chapter's platform videos, because both derive from the chapter's script and not from the platform — generating them per platform would synthesize identical narration once per platform and create separately-editable copies of identical captions that can silently diverge

#### Scenario: Subtitle files accompany videos
- **WHEN** video generation completes
- **THEN** save a copy of the canonical subtitle track to `data/videos_generated/{platform}/{language}/{chapter_id}.srt` as the file burned into that platform's video

#### Scenario: File paths include metadata
- **WHEN** a video file is stored
- **THEN** file path encodes: platform (tiktok/instagram/x/facebook), language (es/en), and chapter_id

#### Scenario: Directory structure is created automatically
- **WHEN** `VideoGenerationUseCase` attempts to write a video file
- **THEN** create `data/videos_generated/{platform}/{language}/` directories if they do not exist

### Requirement: Retry Metadata
The system SHALL track retry attempts and link retries to the original generation record.

#### Scenario: Retry is associated with original attempt
- **WHEN** a video generation retry is requested
- **THEN** create a new `VideoGeneration` record with `retry_of_id` pointing to the original failed record

#### Scenario: Retry count is queryable
- **WHEN** `GET /chapters/{id}/video` is called
- **THEN** return retry chain (original attempt → retries) via `retry_of_id` linkage

### Requirement: Video File Lifecycle Management
The system SHALL support querying and deleting video files (for storage management).

#### Scenario: Video files are queryable by status
- **WHEN** `GET /videos?status=generated` is called
- **THEN** return all generated videos with their metadata

#### Scenario: Video files can be deleted manually
- **WHEN** `DELETE /videos/{id}` is called
- **THEN** delete the video file and its per-platform subtitle copy from disk, and mark the `VideoGeneration` record deleted by setting `deleted_at`, retaining the row

#### Scenario: Deletion preserves the retry lineage
- **WHEN** a `VideoGeneration` record that other records reference via `retry_of_id` is deleted
- **THEN** the record SHALL be retained as a soft-deleted row rather than removed, because `retry_of_id` is a self-referential foreign key with no cascade: removing the row would either violate referential integrity or orphan the retry chain this spec's audit trail requires

#### Scenario: Deletion never removes files another video still needs
- **WHEN** a video is deleted
- **THEN** the shared narration audio (`data/audio/...`) and canonical subtitle track (`data/subtitles/...`) SHALL NOT be removed, since a chapter's other platform videos depend on them
- **AND** a per-platform file SHALL be retained if another non-deleted `VideoGeneration` record still points at the same path

#### Scenario: Deleted videos are excluded from listings
- **WHEN** `GET /videos` or `GET /chapters/{id}/video` is called
- **THEN** soft-deleted records SHALL be excluded, while remaining visible in the audit trail

#### Scenario: Storage usage is reported
- **WHEN** `GET /videos/stats` is called
- **THEN** return total storage used, count of videos by status, and largest videos

### Requirement: Video File Retrieval
The system SHALL serve a generated video's bytes over HTTP, so the admin panel can preview and download it. The stored `video_file_path` is a server-side filesystem path and is not reachable by a browser on its own.

#### Scenario: A generated video is streamed to the browser
- **WHEN** `GET /videos/{id}/file` is called for a generated video whose file exists
- **THEN** return the MP4 with content type `video/mp4`
- **AND** honour HTTP `Range` requests, so the player can seek without downloading the whole file first

#### Scenario: Retrieval refuses anything without a playable file
- **WHEN** the record does not exist, has been soft-deleted, has no `video_file_path`, or its file is missing from disk
- **THEN** respond `404`

#### Scenario: Retrieval is confined to the video directory
- **WHEN** a record's `video_file_path` resolves outside `data/videos_generated/`
- **THEN** refuse to serve it with `403`, rather than reading an arbitrary path from the database — the endpoint turns a stored string into file bytes, so it SHALL NOT serve anything outside the directory this feature owns, whatever the row says

### Requirement: Video File Audit Trail
The system SHALL maintain a complete audit trail of video generation, recording when each attempt was triggered and how it ended.

#### Scenario: Generation is recorded with timing
- **WHEN** video generation is triggered via API
- **THEN** record `triggered_at` (the record's `created_at`) and `completed_at` (its `generated_at`)

#### Scenario: Caller identity is not yet attributable
- **WHEN** the audit trail reports `triggered_by`
- **THEN** it SHALL be `null`, because this service has no authentication and no endpoint resolves a caller identity
- **AND** the field SHALL be present rather than omitted, so real attribution can be filled in once an authentication mechanism exists without changing the response shape

#### Scenario: Audit trail is queryable
- **WHEN** `GET /chapters/{id}/audit` is called
- **THEN** return list of all video generation attempts with timestamps, status, error (if failed), retry lineage, and soft-deleted attempts

#### Scenario: Audit trail retains deleted attempts
- **WHEN** a video has been deleted
- **THEN** its attempt SHALL still appear in the audit trail, marked with `deleted_at`, since an audit trail that drops deleted work cannot answer what was produced

### Requirement: Video File Validation
The system SHALL validate that generated video files exist and are not corrupted before marking them as successfully generated.

#### Scenario: File exists validation
- **WHEN** video generation completes
- **THEN** verify that the MP4 file exists at the recorded path before updating status to `generated`

#### Scenario: File size validation
- **WHEN** video file is written
- **THEN** validate that file size > 0 MB (reject empty files)

#### Scenario: Generation fails if file validation fails
- **WHEN** file validation fails
- **THEN** mark `VideoGeneration.status = "failed"` with error message "Video file not found or corrupted at <path>"

### Requirement: Subtitle File Persistence
The system SHALL store and persist subtitle files alongside videos with the same lifecycle management.

#### Scenario: Subtitle files are stored with videos
- **WHEN** video generation completes
- **THEN** save the SRT subtitle file for that language to `data/videos_generated/{platform}/{language}/{chapter_id}.srt`

#### Scenario: Subtitles are associated with video metadata
- **WHEN** `VideoGeneration` record is created
- **THEN** store both `video_file_path` and `subtitle_file_path` for traceability
