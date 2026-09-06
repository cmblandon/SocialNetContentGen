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

#### Scenario: Timing is calculated from measured TTS duration
- **WHEN** subtitles are generated
- **THEN** the total duration SHALL be measured from the synthesized audio file (via `ffprobe`), never estimated from word count and a speech rate — an estimate drifts against real TTS output, which varies with the voice, punctuation, and pauses, and that drift accumulates across a chapter until captions no longer match speech
- **AND** if the audio cannot be measured, generation SHALL fail rather than fall back to an estimate, so timing is never built on a number the caller believes was measured

#### Scenario: Segment timing is proportional to segment length
- **WHEN** the measured duration is divided across segments
- **THEN** each segment SHALL receive time in proportion to its length, so a short segment does not hold the screen as long as a long one
- **AND** the final segment SHALL absorb rounding so the captions end exactly with the audio

#### Scenario: Timing is never cached
- **WHEN** subtitles are regenerated for a script whose audio has been re-synthesized
- **THEN** timing SHALL be recomputed from the new measured duration
- **AND** subtitle segments SHALL NOT be served from a cache keyed only on script and language, which would return timing measured against different audio

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
