## ADDED Requirements

### Requirement: Chapter Length Constraint for Reels
The system SHALL generate chapters with script length optimized for short-form video (15–60 seconds). At ~150 words/min speaking pace, this translates to 150–220 words per chapter.

#### Scenario: Story writing respects reel length
- **WHEN** `StoryWritingUseCase.write_story()` is invoked
- **THEN** generated chapters SHALL have scripts between 150 and 220 words (validated by `_validate_word_count()`)

#### Scenario: Chapters are split to maintain length
- **WHEN** a document is too long for a single chapter
- **THEN** the LLM SHALL split it into multiple chapters, each 150–220 words, rather than creating oversized chapters

#### Scenario: Chapter splitting preserves narrative flow
- **WHEN** chapters are split across multiple segments
- **THEN** narrative continuity is maintained (e.g., cliffhangers link chapters, no abrupt topic jumps)

### Requirement: Visual Directives Embedded in Script
The system SHALL include visual suggestions in each chapter's script (e.g., "POV: classified document + red text overlay"), enabling the video compositor to fetch appropriate visuals.

#### Scenario: Visual directives are extracted from script
- **WHEN** a chapter is written
- **THEN** the script includes at least one visual directive comment or phrase (e.g., "<visual: archival footage of military base>") that can be parsed for Unsplash queries

#### Scenario: Visual directives guide Unsplash queries
- **WHEN** video generation begins
- **THEN** extract visual directive from script and use it as Unsplash search term

#### Scenario: Default visual if no directive found
- **WHEN** no visual directive is detected in a chapter's script
- **THEN** fallback to generic "classified document" or "declassified file" as Unsplash search term

### Requirement: Pacing Metadata in Script
The system SHALL annotate each chapter with pacing suggestions (e.g., pause length, transition type) to guide video composition timing.

#### Scenario: Script includes pacing cues
- **WHEN** a chapter is written
- **THEN** script MAY include pacing notes (e.g., "[PAUSE 2s]", "[TRANSITION: fade]") for video compositor guidance

#### Scenario: Pacing cues are optional but recognized
- **WHEN** video compositor processes a script
- **THEN** recognize and honor pacing cues if present; ignore if absent (no error)

### Requirement: Source Citation in Script
The system SHALL ensure every chapter includes a source citation (document agency, date, classification level) for credibility and compliance.

#### Scenario: Script includes mandatory source citation
- **WHEN** a chapter is written
- **THEN** script SHALL include a `source_citation` field with agency name, document date, and classification level

#### Scenario: Citation is preserved in video
- **WHEN** video is composed
- **THEN** source citation is displayed as text overlay at the end of the video

### Requirement: Reel-Specific Validation
The system SHALL validate that generated chapters meet reel-specific requirements (length, citation, visual directives) before persisting.

#### Scenario: Chapter validation succeeds
- **WHEN** `StoryWritingUseCase._validate_word_count()` is called
- **THEN** if 150 ≤ word_count ≤ 220, validation passes

#### Scenario: Chapter validation fails for oversized script
- **WHEN** a chapter has >220 words
- **THEN** raise `StoryGenerationError` with message "Chapter too long for reel: <X> words (max 220)"

#### Scenario: Chapter validation fails for undersized script
- **WHEN** a chapter has <150 words
- **THEN** raise `StoryGenerationError` with message "Chapter too short for reel: <X> words (min 150)"

### Requirement: LLM Prompt Optimization
The system SHALL update the story-writing LLM prompt to explicitly request reel-optimized chapters with visual directives and pacing cues.

#### Scenario: Prompt instructs for reel format
- **WHEN** `StoryWritingUseCase.write_story()` is invoked
- **THEN** the LLM prompt explicitly states: "Generate chapters optimized for TikTok/Instagram Reels (15–60 seconds, 150–220 words each). Include visual directives (e.g., '<visual: archival footage>') and pacing suggestions. Each chapter must include a source citation."
