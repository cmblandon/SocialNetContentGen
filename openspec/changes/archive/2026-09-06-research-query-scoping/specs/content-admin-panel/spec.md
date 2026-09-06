## MODIFIED Requirements

### Requirement: Trigger a pipeline run from the panel
The system SHALL provide an action in the panel that starts a research+curation+writing pass (per specs/research-agent and specs/case-curation) against an operator-configured list of source URLs, SHALL let the operator optionally supply a topic/query to scope that pass's extraction (per specs/research-agent's "Scope extraction to an operator-provided query when given"), and SHALL show the run's progress and completion in the UI.

#### Scenario: Operator starts a run
- **WHEN** an operator selects "Ejecutar pipeline" in the Pipeline view
- **THEN** the panel calls the research/curation pipeline with the configured source URLs
- **AND** shows progress while the run is in flight

#### Scenario: Operator starts a run with a query
- **WHEN** an operator enters a topic/query before selecting "Ejecutar pipeline"
- **THEN** the panel includes that query in the research/curation pipeline call
- **AND** the resulting pass's extraction is scoped accordingly

#### Scenario: Operator starts a run without a query
- **WHEN** an operator selects "Ejecutar pipeline" without entering a topic/query
- **THEN** the panel starts the run exactly as before this capability existed, with no query sent

#### Scenario: Run completes
- **WHEN** a triggered run finishes
- **THEN** any newly-created pending cases appear in the Pipeline feed without a manual page reload

#### Scenario: No source URLs configured
- **WHEN** no source URLs are configured
- **THEN** the "Ejecutar pipeline" action is disabled
- **AND** the panel points the operator to the source-URL configuration view
