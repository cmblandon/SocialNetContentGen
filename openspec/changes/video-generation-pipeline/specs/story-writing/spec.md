## MODIFIED Requirements

### Requirement: Split extensive documents into independently publishable chapters
The system SHALL split a story into chapters of 150-220 words (60-90 seconds of spoken script) when the source document is extensive, and SHALL ensure each chapter has its own opening hook, is understandable on its own, includes embedded visual directives for video composition, and closes with a cliffhanger grounded in the source document that previews the next chapter.

#### Scenario: Short document, single piece
- **WHEN** the source document is short enough to cover in one 60-90s script
- **THEN** the writer agent produces a single chapter instead of splitting into a series
- **AND** includes visual directives for video composition

#### Scenario: Extensive document split into chapters with video optimization
- **WHEN** the source document is long (e.g. a lengthy report with multiple annexes)
- **THEN** the writer agent splits it into multiple chapters of 150-220 words each
- **AND** each chapter can be published independently without losing meaning
- **AND** each chapter ends with a document-grounded cliffhanger that previews the next chapter
- **AND** each chapter includes visual directives (e.g., "<visual: classified document + red text overlay>") for the video compositor

#### Scenario: Visual directives guide video compositor
- **WHEN** a chapter is written
- **THEN** it includes at least one visual directive that can be parsed as a search term for Unsplash (e.g., "archival military footage", "declassified document")
- **AND** these directives inform the video generator's visual selection process

#### Scenario: Pacing cues embedded in script
- **WHEN** a chapter is written for video
- **THEN** it MAY include optional pacing suggestions (e.g., "[PAUSE 2s]", "[TRANSITION: fade]") to guide video timing
- **AND** these are recognized but not required (fallback to auto-pacing if absent)

#### Scenario: Cliffhanger must be real
- **WHEN** a chapter closes with a cliffhanger
- **THEN** the cliffhanger references a fact or detail that genuinely exists later in the source document
- **AND** is never an invented hook unsupported by the document
