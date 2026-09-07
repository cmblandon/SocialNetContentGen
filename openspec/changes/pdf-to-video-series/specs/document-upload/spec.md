## ADDED Requirements

### Requirement: PDF Upload
The system SHALL accept a declassified document as an uploaded PDF and extract its text, replacing URL-based discovery as the way documents enter the pipeline.

#### Scenario: A PDF is uploaded and its text extracted
- **WHEN** an operator uploads a PDF
- **THEN** the system SHALL extract its text and retain it as the source material for every later stage
- **AND** the extracted text SHALL be persisted before any script generation is attempted, so a generation failure never costs the extraction

#### Scenario: A scanned PDF without a text layer
- **WHEN** an uploaded PDF has no extractable text layer
- **THEN** the system SHALL run OCR over it, and SHALL mark the resulting text as lower-confidence so the operator knows the source may contain recognition errors

#### Scenario: A file that is not a usable PDF
- **WHEN** the uploaded file is not a PDF, is corrupt, or yields no text after OCR
- **THEN** the system SHALL reject it with a message naming which of those happened, rather than producing an empty document

### Requirement: Measured Progress Reporting
The system SHALL report progress derived from work actually completed. Progress SHALL NOT be simulated from elapsed time.

#### Scenario: Extraction progress reflects pages processed
- **WHEN** a PDF is being extracted
- **THEN** progress SHALL be reported as pages processed out of total pages

#### Scenario: Analysis progress reflects chapters completed
- **WHEN** a series is being generated
- **THEN** progress SHALL be reported as chapters completed out of the number the series plan defined

#### Scenario: A step of unknown duration is honest about it
- **WHEN** a step's remaining duration cannot be derived from countable work
- **THEN** the system SHALL report it as indeterminate rather than advancing a percentage on a timer — a bar that moves while nothing happens teaches the operator to distrust it, which is worse than no bar

#### Scenario: Local inference takes minutes without appearing hung
- **WHEN** a generation step runs for tens of seconds or minutes on a local model
- **THEN** the interface SHALL show which step is running and what has completed so far, so a slow step is distinguishable from a stalled one
