## MODIFIED Requirements

### Requirement: Approval actions are observable by the orchestrator
The system SHALL persist approve/reject decisions in a way the orchestrator can observe. Approving a chapter's platform version SHALL mark it eligible for publishing but SHALL NOT, by itself, trigger a publish attempt — publishing is a separate, explicit action (see "Publish an approved case to a network as an explicit action" below).

#### Scenario: Orchestrator observes approval
- **WHEN** an operator approves a chapter through the panel
- **THEN** the orchestrator's next check of that chapter's status sees `approved`
- **AND** the platform version becomes eligible for publishing, without a publish attempt starting automatically

#### Scenario: Operator rejects
- **WHEN** an operator selects reject on a pending chapter
- **THEN** the chapter's platform versions transition to the `rejected` state
- **AND** the orchestrator does not publish them

## ADDED Requirements

### Requirement: Trigger a pipeline run from the panel
The system SHALL provide an action in the panel that starts a research+curation+writing pass (per specs/research-agent and specs/case-curation) against an operator-configured list of source URLs, and SHALL show the run's progress and completion in the UI.

#### Scenario: Operator starts a run
- **WHEN** an operator selects "Ejecutar pipeline" in the Pipeline view
- **THEN** the panel calls the research/curation pipeline with the configured source URLs
- **AND** shows progress while the run is in flight

#### Scenario: Run completes
- **WHEN** a triggered run finishes
- **THEN** any newly-created pending cases appear in the Pipeline feed without a manual page reload

#### Scenario: No source URLs configured
- **WHEN** no source URLs are configured
- **THEN** the "Ejecutar pipeline" action is disabled
- **AND** the panel points the operator to the source-URL configuration view

### Requirement: Manage the source-URL list used by pipeline runs
The system SHALL let an operator view, add, and remove the source URLs a pipeline run targets, persisted so they don't need to be re-entered on every run.

#### Scenario: Operator adds a source URL
- **WHEN** an operator adds a URL in the Configuración view
- **THEN** subsequent pipeline runs include that URL among their targets

#### Scenario: Operator removes a source URL
- **WHEN** an operator removes a URL in the Configuración view
- **THEN** subsequent pipeline runs no longer target that URL

#### Scenario: Duplicate source URL
- **WHEN** an operator adds a URL that is already in the list
- **THEN** the list is unchanged (no duplicate entry is created)

### Requirement: Publish an approved case to a network as an explicit action
The system SHALL let an operator publish one approved platform version to its network via an explicit action, distinct from approval.

#### Scenario: Operator publishes a single case
- **WHEN** an operator selects "Publicar" for one approved platform version
- **THEN** the panel invokes the explicit publish action for that platform version
- **AND** shows the resulting outcome (published, proposed schedule, or failed)

### Requirement: Bulk-publish selected approved cases to one network
The system SHALL let an operator select multiple approved cases and publish all of them to one chosen network in a single action.

#### Scenario: Operator bulk-publishes
- **WHEN** an operator selects several approved cases and chooses "Publicar en <network>"
- **THEN** the panel invokes the explicit publish action for the matching platform version of every selected case
- **AND** reflects each case's resulting outcome independently as its own publish attempt completes

#### Scenario: One case in a bulk action fails
- **WHEN** one of several cases in a bulk-publish action fails to publish
- **THEN** the other selected cases' publish attempts are not blocked or cancelled by that failure
