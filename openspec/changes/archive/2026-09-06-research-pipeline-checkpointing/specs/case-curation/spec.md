## MODIFIED Requirements

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
