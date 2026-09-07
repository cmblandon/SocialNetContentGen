## MODIFIED Requirements

### Requirement: Curation Gates Uploaded Documents
The system SHALL score an uploaded document against the existing five-criterion rubric and SHALL NOT generate scripts for a document scoring below the advancement threshold.

The rubric is unchanged. What changes is what it guards: it previously judged what a scraper had found, and now judges what an operator has uploaded. The judgement is the same one — is this document strong enough to carry a story — and it is still needed, because uploading a document is cheap while generating a multi-chapter series on a local model costs minutes of inference per chapter.

#### Scenario: A strong document proceeds to series planning
- **WHEN** an uploaded document scores at or above the threshold
- **THEN** it SHALL proceed to series planning

#### Scenario: A weak document is blocked with its reasoning
- **WHEN** an uploaded document scores below the threshold
- **THEN** the system SHALL NOT generate scripts for it
- **AND** SHALL show the total, the per-criterion scores, and the reasoning, so the operator can see why it was blocked and argue with it rather than face an opaque refusal

#### Scenario: Curation runs on the local model
- **WHEN** a document is scored
- **THEN** scoring SHALL use the configured document-processing model, which may be local, since scoring a rubric and emitting a small verdict is within a local model's reach

#### Scenario: Scores near the threshold are not stable
- **WHEN** a document scores at or near the threshold on a local model
- **THEN** the operator SHALL be able to see the score, because local scoring is not deterministic and the same document may fall on either side of the threshold across runs
