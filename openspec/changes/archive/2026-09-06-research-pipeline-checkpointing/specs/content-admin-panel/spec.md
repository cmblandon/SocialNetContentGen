## ADDED Requirements

### Requirement: Show pipeline checkpoint status and allow resuming from the panel
The system SHALL indicate in the Pipeline view when discovered documents are pending curation or have failed curation, and SHALL provide an explicit action to resume processing them without re-scraping.

#### Scenario: Pending or failed checkpoints exist
- **WHEN** the Pipeline view loads and there are documents pending or failed curation
- **THEN** the panel shows an indicator of how many are pending and how many have failed
- **AND** offers a "Reanudar pipeline" (resume) action

#### Scenario: Operator resumes the pipeline
- **WHEN** an operator selects "Reanudar pipeline"
- **THEN** the panel invokes the resume action, which processes pending and failed checkpoints without requiring source URLs
- **AND** any newly-created pending cases appear in the Pipeline feed without a manual page reload

#### Scenario: No checkpoints outstanding
- **WHEN** there are no pending or failed checkpointed documents
- **THEN** the panel shows no checkpoint indicator and no resume action
