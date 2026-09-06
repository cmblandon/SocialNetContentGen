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
- **THEN** save MP4 file to `data/videos_generated/{platform}/{language}/{chapter_id}_{uuid}.mp4` (UUIDs prevent collisions on reruns)

#### Scenario: Subtitle files accompany videos
- **WHEN** video generation completes
- **THEN** save SRT subtitle file to `data/videos_generated/{platform}/{language}/{chapter_id}_{uuid}.srt`

#### Scenario: File paths include metadata
- **WHEN** a video file is stored
- **THEN** file path encodes: platform (tiktok/instagram/x/facebook), language (es/en), chapter_id, and UUID for uniqueness

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
- **THEN** delete the video file and the corresponding `VideoGeneration` record (or mark as deleted)

#### Scenario: Storage usage is reported
- **WHEN** `GET /videos/stats` is called
- **THEN** return total storage used, count of videos by status, and largest videos

### Requirement: Video File Audit Trail
The system SHALL maintain a complete audit trail of video generation, including who triggered it and when.

#### Scenario: Generation is recorded with user context
- **WHEN** video generation is triggered via API
- **THEN** record `triggered_by` (user ID or API key), `triggered_at`, and `completed_at`

#### Scenario: Audit trail is queryable
- **WHEN** `GET /chapters/{id}/audit` is called
- **THEN** return list of all video generation attempts with user, timestamp, status, and error (if failed)

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
- **THEN** save SRT subtitle file (Spanish + English segments) to `data/videos_generated/{platform}/{language}/{chapter_id}_{uuid}.srt`

#### Scenario: Subtitles are associated with video metadata
- **WHEN** `VideoGeneration` record is created
- **THEN** store both `video_file_path` and `subtitle_file_path` for traceability
