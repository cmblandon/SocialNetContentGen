## ADDED Requirements

### Requirement: Duration Cuts Per Chapter
The system SHALL produce each chapter in two lengths, so one script serves both long-form and short-form video.

#### Scenario: A long cut and a short cut are produced
- **WHEN** a chapter is generated
- **THEN** the system SHALL produce a long cut sized for a 3–5 minute video and a short cut sized for roughly 60 seconds

#### Scenario: The short cut is derived from the approved long cut
- **WHEN** the short cut is produced
- **THEN** it SHALL be compressed from the long cut rather than generated independently, so both carry the same facts, the same citations and the same beats — and so a slow local model is not asked to write the same chapter twice from scratch

#### Scenario: Script length maps to target runtime
- **WHEN** either cut is validated
- **THEN** its word count SHALL fall in the range that corresponds to its target runtime at natural narration pace, because the length constraint exists to make the script fit the video, not to satisfy a style rule

### Requirement: Generation Retries Against Validation Feedback
The system SHALL retry generation with the validation failure fed back into the prompt, because a local model cannot reliably satisfy a numeric constraint from a single instruction.

#### Scenario: A rejected draft is regenerated with the reason
- **WHEN** a generated script fails a mechanical check
- **THEN** the system SHALL retry, including in the retry prompt what was wrong and by how much

#### Scenario: Retries are bounded
- **WHEN** repeated attempts keep failing
- **THEN** the system SHALL stop after a fixed number of attempts and surface the last validation error, so a model that cannot satisfy the constraint fails visibly instead of looping

#### Scenario: Constraints are never relaxed to fit a weaker model
- **WHEN** a local model struggles to satisfy a constraint
- **THEN** the constraint SHALL remain unchanged and the model SHALL be retried — relaxing the length range would break the link between script length and video runtime that the range exists to enforce

## MODIFIED Requirements

### Requirement: Anti-Fabrication Validation
The system SHALL reject any script that attributes to the source document content the document does not contain. This applies across the whole series, not only within a single chapter.

These are real historical records. A quote attributed to a named officer that the document does not contain is a credibility failure that survives into a rendered video and cannot be quietly corrected, so this check is stricter here than it was when the output was a text post.

#### Scenario: A quote absent from the document is rejected
- **WHEN** a generated script contains quoted text that does not appear in the source document
- **THEN** the script SHALL be rejected and regenerated, never passed through with a warning

#### Scenario: A later chapter may not cite an earlier chapter's prose as source
- **WHEN** a chapter attributes a fact to the document
- **THEN** that fact SHALL be traceable to the source document itself, not to something an earlier chapter's narration asserted — otherwise an invention in chapter 1 becomes a documented fact by chapter 3

#### Scenario: Overstated claims are rejected
- **WHEN** a script contains language overstating what the document establishes
- **THEN** the script SHALL be rejected and regenerated
