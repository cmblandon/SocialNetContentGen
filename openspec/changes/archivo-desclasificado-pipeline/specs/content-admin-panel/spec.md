## ADDED Requirements

### Requirement: Present a human-approval queue with full review context
The system SHALL display, for each chapter pending approval, the source document, the story summary, the chapter's spoken script, and every per-platform adapted version, and SHALL provide explicit approve and reject actions.

#### Scenario: Pending item displayed
- **WHEN** an operator opens the approval queue
- **THEN** each pending chapter shows its source document, story summary, script, and all platform versions

#### Scenario: Operator approves
- **WHEN** an operator selects approve on a pending chapter
- **THEN** the chapter's platform versions transition to the `approved` state

#### Scenario: Operator rejects
- **WHEN** an operator selects reject on a pending chapter
- **THEN** the chapter's platform versions transition to the `rejected` state
- **AND** the orchestrator does not publish them

### Requirement: Approval actions are observable by the orchestrator
The system SHALL persist approve/reject decisions in a way the orchestrator can observe and act on to resume or halt the publishing stage for that piece.

#### Scenario: Orchestrator observes approval
- **WHEN** an operator approves a chapter through the panel
- **THEN** the orchestrator's next check of that chapter's status sees `approved`
- **AND** proceeds to publishing for that chapter

### Requirement: Display the editorial calendar
The system SHALL display what has been published or scheduled, per network and time, reflecting the contents of `/calendario.md`.

#### Scenario: Calendar view requested
- **WHEN** an operator opens the calendar view
- **THEN** it lists published/scheduled items with their network and time, matching `/calendario.md`

### Requirement: Manage covered cases
The system SHALL let an operator search, browse, and manually edit the covered-cases history recorded in `/casos_cubiertos.md`.

#### Scenario: Operator searches covered cases
- **WHEN** an operator searches the covered-cases view
- **THEN** matching entries from `/casos_cubiertos.md` are shown

#### Scenario: Operator edits a case entry
- **WHEN** an operator manually edits a covered-case entry
- **THEN** the change is reflected back into `/casos_cubiertos.md`
