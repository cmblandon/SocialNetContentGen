## MODIFIED Requirements

### Requirement: Block on explicit human approval before publishing
The system SHALL pause the editorial cycle before invoking the publisher subagent and SHALL present, for every piece pending approval, the source document, the story summary, each chapter's script, and all per-platform adapted versions. An explicit approval signal marks a piece eligible for publishing but SHALL NOT, by itself, trigger a publish attempt — publishing SHALL require a separate, explicit publish action per specs/publishing/spec.md, invoked individually or as part of a bulk selection.

#### Scenario: Approval requested
- **WHEN** a chapter and its platform versions are ready to be sent to the publisher
- **THEN** the orchestrator pauses and surfaces the source document, story summary, chapter script, and all platform versions for human review

#### Scenario: No approval given
- **WHEN** a piece pending approval has not received an explicit approval signal
- **THEN** the orchestrator does not invoke the publisher for that piece

#### Scenario: Rejection given
- **WHEN** a human explicitly rejects a piece pending approval
- **THEN** the orchestrator does not publish it
- **AND** records the rejection instead of retrying automatically

#### Scenario: Approval alone does not publish
- **WHEN** an operator approves a chapter through the panel
- **THEN** the orchestrator's next check of that chapter's status sees `approved`
- **AND** the chapter's platform versions become eligible for publishing, without a publish attempt being made automatically

#### Scenario: Operator explicitly publishes after approval
- **WHEN** an operator invokes the publish action for an approved platform version (individually or as part of a bulk selection)
- **THEN** the publisher attempts to publish it, following specs/publishing/spec.md
