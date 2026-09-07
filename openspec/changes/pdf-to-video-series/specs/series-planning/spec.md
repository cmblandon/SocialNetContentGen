## ADDED Requirements

### Requirement: Series Plan Precedes Chapter Generation
The system SHALL produce a series plan for a document before generating any chapter, so that each chapter is written with knowledge of what the others contain.

#### Scenario: A plan is produced first
- **WHEN** an approved document enters script generation
- **THEN** the system SHALL first produce a series plan naming each chapter, what it covers, and the through-line connecting them
- **AND** no chapter SHALL be generated until that plan exists

#### Scenario: Chapters are generated against the plan
- **WHEN** a chapter is generated
- **THEN** the generation SHALL receive the full series plan, not only the current chapter's entry, so a chapter can set up what a later one pays off

#### Scenario: A cliffhanger references material that genuinely follows
- **WHEN** a chapter other than the last ends on a cliffhanger
- **THEN** the cliffhanger SHALL reference something the series plan assigns to a later chapter and that the source document actually contains — a chapter written without knowledge of what follows can only satisfy this by accident

### Requirement: Chapter Count Follows Narrative Beats
The system SHALL determine how many chapters a document supports from its narrative structure, not from its length.

#### Scenario: Chapter count comes from the material
- **WHEN** the series plan is produced
- **THEN** the number of chapters SHALL follow the narrative beats identified in the document — setup, escalation, complication, resolution — rather than the document's word count divided by a target chapter length

#### Scenario: A document supporting only one chapter
- **WHEN** the document sustains a single beat
- **THEN** the system SHALL produce a one-chapter series, structured the same way as a longer one, rather than padding it into several chapters

#### Scenario: Similar-length documents may yield different chapter counts
- **WHEN** two documents of comparable length carry different numbers of narrative beats
- **THEN** they SHALL yield different chapter counts, because chapter count is an editorial judgement about the material and not arithmetic on its length

### Requirement: Series Plan Is Reviewable Before Generation
The system SHALL present the series plan for approval before spending inference on chapters.

#### Scenario: The operator reviews the plan first
- **WHEN** a series plan has been produced
- **THEN** it SHALL be shown to the operator with its chapter breakdown and through-line, and chapter generation SHALL wait for approval
- **AND** rejecting a plan SHALL cost only the plan, since generating chapters on a local model takes minutes per chapter

### Requirement: Continuity Across Chapters
The system SHALL keep a series internally consistent across its chapters.

#### Scenario: Names, dates and framings stay consistent
- **WHEN** a multi-chapter series is generated
- **THEN** witness names, agency names, dates and the label given to the central incident SHALL be identical across chapters, rather than independently re-derived per chapter

#### Scenario: Later chapters recap for a returning viewer
- **WHEN** a chapter after the first is generated
- **THEN** it SHALL open with a brief recap beat orienting a viewer who watched the previous chapter — which is a different requirement from each chapter being understandable on its own

#### Scenario: The final chapter resolves rather than teases
- **WHEN** the last chapter of a series is generated
- **THEN** it SHALL close by resolving the series through-line, or by explicitly naming what the document leaves unresolved, and SHALL NOT end on a cliffhanger for a chapter that does not exist
