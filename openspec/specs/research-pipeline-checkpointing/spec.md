# Research Pipeline Checkpointing Specification

## Purpose
Ensures documents fetched by the scraper are durably checkpointed before curation, so a downstream curation failure never loses discovered content, other documents in the same run are unaffected, and pending or failed documents can be resumed later without re-scraping.

## Requirements

### Requirement: Persist discovered documents before curation is attempted
The system SHALL persist every document successfully fetched by the scraper as a checkpoint record immediately, before curation is attempted on it, so the fetched content is never lost regardless of what happens downstream.

#### Scenario: Document checkpointed after a successful fetch
- **WHEN** the scraper successfully fetches a document for a given source URL
- **THEN** a checkpoint record is persisted for it, in a pending state, before curation runs

#### Scenario: Checkpoint survives a downstream curation crash
- **WHEN** curation fails for one checkpointed document (e.g. an LLM/API error)
- **THEN** that document's checkpoint record remains persisted and retrievable, unaffected by the failure

### Requirement: Isolate curation failures per document
The system SHALL isolate a curation failure to the single document it occurred on; it SHALL NOT prevent other documents discovered in the same run from being curated, written, and adapted.

#### Scenario: One document's curation fails, others proceed
- **WHEN** curation fails for one document in a batch of several discovered documents
- **THEN** the remaining documents in that batch are still curated, and advanced ones are still written and adapted
- **AND** the failed document's checkpoint is marked as failed, with the failure reason recorded

#### Scenario: A failed curation attempt is distinct from a discarded one
- **WHEN** a document's curation attempt raises an error before producing a score
- **THEN** the document is recorded as failed, not discarded
- **AND** it remains eligible for a future retry, unlike a permanently discarded document

### Requirement: Resume processing of checkpointed documents without re-scraping
The system SHALL provide an explicit action that reprocesses every checkpointed document still pending or failed — curating, and for advanced ones writing and adapting — without requiring source URLs and without re-invoking the scraper.

#### Scenario: Resume processes pending checkpoints
- **WHEN** an operator invokes the resume action and pending checkpointed documents exist
- **THEN** each pending document is curated (and, if advanced, written and adapted) without any scraping occurring

#### Scenario: Resume retries failed checkpoints
- **WHEN** an operator invokes the resume action and failed checkpointed documents exist
- **THEN** each failed document's curation is attempted again

#### Scenario: Resume with nothing to process
- **WHEN** an operator invokes the resume action and no pending or failed checkpoints exist
- **THEN** the action completes with no documents processed, and this is not treated as an error

### Requirement: Avoid re-scraping source URLs already checkpointed
The system SHALL NOT re-invoke the scraper for a source URL that already has a pending or failed checkpoint from a prior run.

#### Scenario: Source URL already checkpointed and unresolved
- **WHEN** a pipeline run is started with a source URL that already has a pending or failed checkpoint
- **THEN** the scraper is not invoked again for that URL in this run
