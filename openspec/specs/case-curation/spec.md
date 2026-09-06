# Case Curation Specification

## Purpose
Scores and filters documents for narrative/production readiness, and maintains the permanent record of every case evaluated so nothing is reprocessed.

## Requirements

### Requirement: Score every incoming document across the five editorial criteria
The system SHALL score each structured document record from 1 to 5 on each of: novedad (novelty against covered cases), potencial narrativo, respaldo documental, elemento visual, and encaje de audiencia, and SHALL compute their sum as the document's total score.

#### Scenario: All criteria scored
- **WHEN** a structured document record arrives from the research agent
- **THEN** the curator assigns a 1-5 score to each of the five criteria
- **AND** records the sum as the document's total score (0-25 range)

### Requirement: Only advance documents meeting the production threshold
The system SHALL advance a document to story-writing only when its total score is 15 or greater out of 25, and SHALL NOT advance documents scoring below that threshold.

#### Scenario: Document meets threshold
- **WHEN** a document's total score is 15 or higher
- **THEN** the curator advances it to the story-writing stage

#### Scenario: Document below threshold
- **WHEN** a document's total score is below 15
- **THEN** the curator does not advance it to story-writing

### Requirement: Record every evaluated case permanently
The system SHALL append an entry to `/casos_cubiertos.md` for every document it evaluates, whether advanced or discarded, including the evaluation date and the reason (score breakdown or discard rationale), so the document is never re-evaluated. A curation attempt that errors before producing a score is not an evaluation and SHALL NOT be recorded in `/casos_cubiertos.md` — it is tracked as a retryable, failed checkpoint instead (per `specs/research-pipeline-checkpointing`), so it remains eligible to be evaluated once the underlying failure is resolved.

#### Scenario: Advanced case recorded
- **WHEN** a document is advanced to story-writing
- **THEN** `/casos_cubiertos.md` gains an entry noting the date, the outcome "advanced", and its score

#### Scenario: Discarded case recorded
- **WHEN** a document scores below the threshold and is discarded
- **THEN** `/casos_cubiertos.md` gains an entry noting the date, the outcome "discarded", and the reason

#### Scenario: Previously recorded document reappears
- **WHEN** the research agent resurfaces a document already present in `/casos_cubiertos.md`
- **THEN** the curator does not re-score or re-record it

#### Scenario: A curation attempt that errors is not recorded as evaluated
- **WHEN** a curation attempt raises an error before a score is produced (e.g. an LLM/API failure)
- **THEN** `/casos_cubiertos.md` does not gain an entry for that document
- **AND** the document remains eligible for a future curation attempt

### Requirement: Provide a narrative angle note when advancing a document
The system SHALL attach a short narrative-angle note (what makes the case work as a story) to every document advanced to story-writing.

#### Scenario: Document advanced with angle note
- **WHEN** a document is advanced to story-writing
- **THEN** it is accompanied by a brief note describing the narrative angle (e.g. witness type, corroborating record, time classified) that makes it strong
