## ADDED Requirements

### Requirement: Publishing is an explicit action, not an automatic consequence of approval
The system SHALL only attempt to publish a platform version when a separate, explicit publish action is invoked for it — approval alone SHALL NOT trigger a publish attempt. The system SHALL support invoking this action for multiple approved platform versions in one bulk operation targeting a single platform, with each attempt independent of the others.

#### Scenario: Approval alone does not publish
- **WHEN** a platform version transitions to `approved`
- **THEN** no publish attempt is made until a separate publish action is invoked for it

#### Scenario: Explicit single publish
- **WHEN** an explicit publish action is invoked for one approved platform version
- **THEN** the publisher attempts to publish it, following the existing scheduling and recording requirements (approval gate, optimal-time lookup/proposal, `PublishRecord` creation, single-attempt-no-retry)

#### Scenario: Explicit bulk publish
- **WHEN** an explicit publish action is invoked for multiple approved platform versions targeting the same platform
- **THEN** the publisher attempts each one independently
- **AND** a failure on one attempt SHALL NOT block or cancel the attempts for the others
