## ADDED Requirements

### Requirement: Bilingual Subtitle Generation
The system SHALL generate Spanish and English subtitles from an approved script with timing information derived from TTS audio length.

#### Scenario: Subtitles are generated for approved script
- **WHEN** `POST /chapters/{id}/subtitles/generate` is called for a chapter with `script_approved = true`
- **THEN** the system requests TTS audio duration from ElevenLabs for both ES and EN, divides script into segments, assigns timings, and returns SRT/VTT format

#### Scenario: Spanish subtitles are generated
- **WHEN** subtitles are generated
- **THEN** system generates Spanish subtitles with timing cues (00:00:00,000 --> 00:00:05,000 format per SRT spec)

#### Scenario: English subtitles are generated
- **WHEN** subtitles are generated
- **THEN** system generates English subtitles with the same timing as Spanish (translated content only)

#### Scenario: Subtitle generation fails without approved script
- **WHEN** `POST /chapters/{id}/subtitles/generate` is called for a chapter with `script_approved = false`
- **THEN** reject with HTTP 409 and return "Script must be approved before subtitle generation"

### Requirement: Subtitle Timing Synchronization
The system SHALL align subtitle segments with TTS audio timing, ensuring each subtitle appears at the moment its audio is spoken.

#### Scenario: Timing is calculated from TTS duration
- **WHEN** subtitles are generated
- **THEN** divide script into sentences or logical segments, estimate duration per segment based on speech rate (~150 words/min = ~2.5s per 6-word segment), and assign start/end times

#### Scenario: Subtitles do not overlap
- **WHEN** subtitle segments are generated
- **THEN** each segment's end time SHALL equal the next segment's start time (no gaps or overlaps)

### Requirement: Subtitle Editing Before Video Generation
The system SHALL allow editors to review and edit subtitles before they are composited into video.

#### Scenario: Editor views subtitles before approval
- **WHEN** `GET /chapters/{id}/subtitles` is called
- **THEN** return both ES and EN subtitles with timing, e.g.: `[{"lang": "es", "segments": [{"text": "...", "start": "00:00:00", "end": "00:00:05"}]}, ...]`

#### Scenario: Editor edits subtitle text
- **WHEN** `POST /chapters/{id}/subtitles/update` is called with edited segments
- **THEN** update the subtitle text (but preserve timing) and mark subtitles as `edited = true`

#### Scenario: Edited subtitles are used in video composition
- **WHEN** video generation is requested after subtitle edit
- **THEN** use the edited subtitle text with the original timing cues

### Requirement: Subtitle Format Standards
The system SHALL output subtitles in SRT format for universal compatibility.

#### Scenario: Subtitles conform to SRT spec
- **WHEN** subtitles are generated or edited
- **THEN** output format SHALL be SRT (1-indexed segments, millisecond precision, UTF-8 encoding)

#### Scenario: Subtitles are stored as files
- **WHEN** subtitles are generated
- **THEN** store SRT files at `data/videos_generated/{platform}/{language}/{chapter_id}.srt`

### Requirement: Translation Accuracy
The system SHALL auto-translate Spanish scripts to English and vice versa, preserving timing and meaning.

#### Scenario: English text is auto-translated from Spanish script
- **WHEN** Spanish script is approved
- **THEN** system auto-translates to English (via LLM or API) and generates English subtitles

#### Scenario: Translation quality is reviewable
- **WHEN** editor reviews English subtitles
- **THEN** editor can edit translations before video generation (e.g., for cultural fit or phrasing preferences)

#### Scenario: Translation errors are correctable
- **WHEN** editor detects poor translation
- **THEN** editor can edit subtitle text before video generation (no re-translation required)

### Requirement: Subtitle Approval Gate (Optional)
The system SHOULD track whether subtitles have been explicitly reviewed/approved by an editor (optional for MVP; can be enforced later).

#### Scenario: Subtitle approval is optional for MVP
- **WHEN** video generation is requested
- **THEN** use subtitles as-is if generated; no separate approval step required (editors review via subtitle edit UI)
