# Publishing Specification

## Purpose
Schedules and publishes human-approved content via a pluggable social API connector and records outcomes for later metrics correlation.

## Requirements

### Requirement: Publish only content marked approved
The system SHALL publish or schedule a platform version only when its associated approval state is `approved`, and SHALL NOT publish content in any other state (`pending_review`, `rejected`, `failed`).

#### Scenario: Approved content
- **WHEN** a platform version's status is `approved`
- **THEN** the publisher proceeds to schedule/publish it

#### Scenario: Non-approved content
- **WHEN** a platform version's status is `pending_review` or `rejected`
- **THEN** the publisher does not attempt to publish it

### Requirement: Schedule using the defined calendar slot, or propose one for approval
The system SHALL schedule each approved piece at the optimal time recorded in `/calendario.md` for its platform, and SHALL, when no time is defined, propose a time and leave that proposal pending approval rather than publishing immediately.

#### Scenario: Optimal time already defined
- **WHEN** `/calendario.md` defines an optimal time slot for the target platform
- **THEN** the publisher schedules the piece at that time

#### Scenario: No optimal time defined
- **WHEN** `/calendario.md` has no defined time slot for the target platform
- **THEN** the publisher proposes a time
- **AND** leaves the proposal pending approval instead of publishing immediately

### Requirement: Record every publish outcome in the editorial calendar
The system SHALL record, for every publish or schedule attempt, what was published, on which network, at what time, and the post ID returned by the social API, so it can later be cross-referenced with metrics.

#### Scenario: Successful publish recorded
- **WHEN** a piece is successfully published or scheduled
- **THEN** `/calendario.md` gains a record with the network, time, and the API-returned post ID

### Requirement: Report failures without silent repeated retries
The system SHALL report a publish failure (network error, rejected content, account limit) to the orchestrator, and SHALL NOT silently retry more than once.

#### Scenario: Publish attempt fails
- **WHEN** a publish attempt returns an error from the social API
- **THEN** the publisher reports the failure to the orchestrator

#### Scenario: Repeated failure
- **WHEN** a retried publish attempt fails again
- **THEN** the publisher does not retry again silently
- **AND** surfaces the failure for human attention

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
