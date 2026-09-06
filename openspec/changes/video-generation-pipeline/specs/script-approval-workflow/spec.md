## ADDED Requirements

### Requirement: Script Approval State Tracking
The system SHALL track whether a chapter's script has been explicitly approved by an editor before video generation. Approval SHALL be an atomic action that updates the database and cannot be undone (only re-approved after rejection or re-generation).

#### Scenario: Editor approves a script
- **WHEN** editor clicks "Approve Script" on a chapter with `script_approved = false`
- **THEN** the chapter transitions to `script_approved = true` and `script_approved_at` is set to the current timestamp

#### Scenario: Editor rejects a script
- **WHEN** editor clicks "Reject Script" on an approved chapter
- **THEN** the chapter transitions to `script_approved = false` and remains eligible for re-submission

#### Scenario: Video generation requires prior script approval
- **WHEN** a request to generate video is received for a chapter with `script_approved = false`
- **THEN** the system SHALL reject the request with HTTP 409 Conflict and return error message "Script must be approved before video generation"

### Requirement: Script Review Endpoint
The system SHALL provide an API endpoint that lists all chapters with pending or approved scripts and allows editors to fetch, approve, or reject scripts.

#### Scenario: List pending scripts
- **WHEN** `GET /chapters/pending/scripts` is called
- **THEN** return a list of chapters with fields: `id`, `title`, `script`, `source_citation`, `script_approved`, `script_approved_at`, `created_at`

#### Scenario: Approve script via endpoint
- **WHEN** `POST /chapters/{id}/script/approve` is called
- **THEN** update the chapter's `script_approved = true` and record the approval timestamp

#### Scenario: Reject script via endpoint
- **WHEN** `POST /chapters/{id}/script/reject` is called
- **THEN** update the chapter's `script_approved = false`

### Requirement: Script Edit Before Approval
The system SHALL allow editors to modify a chapter's script text before approving it, without triggering a full story regeneration.

#### Scenario: Editor submits edited script
- **WHEN** `POST /chapters/{id}/script/update` is called with a new `script_text`
- **THEN** the chapter's script is updated and `script_approved` is reset to `false`

#### Scenario: Edit resets approval state
- **WHEN** a chapter's script is edited after approval
- **THEN** `script_approved` is set to `false` and `script_approved_at` is cleared, requiring re-approval before video generation

### Requirement: Approval Audit Trail
The system SHALL maintain an audit trail of all script approvals and rejections.

#### Scenario: Approval is recorded with timestamp
- **WHEN** a script is approved
- **THEN** the database records the approval timestamp, and this timestamp is persisted with the chapter

#### Scenario: Approval history is queryable
- **WHEN** `GET /chapters/{id}/script/approval-history` is called
- **THEN** return a list of all approval/rejection events with timestamps (if history table exists; optional for MVP)
