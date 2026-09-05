## ADDED Requirements

### Requirement: Orchestrator delegates each stage instead of doing the work itself
The system SHALL run the editorial cycle (research → curate → write → adapt → approve → publish) by delegating each stage to its corresponding subagent, and SHALL NOT perform a subagent's work directly in the orchestrator.

#### Scenario: Cycle stage execution
- **WHEN** the orchestrator advances the cycle to a given stage
- **THEN** it delegates that stage's work to the corresponding subagent (research, curator, writer, platform adapter, or publisher)
- **AND** the orchestrator itself does not generate the stage's content

### Requirement: Maintain project memory across cycles
The system SHALL maintain `/casos_cubiertos.md`, `/calendario.md`, and `/manual_de_marca.md` in the orchestrator's virtual filesystem, and SHALL keep them up to date as cycles complete so later cycles can read them.

#### Scenario: Memory files persist across cycles
- **WHEN** a cycle completes
- **THEN** `/casos_cubiertos.md`, `/calendario.md`, and `/manual_de_marca.md` reflect that cycle's outcomes
- **AND** the next cycle reads the updated files before making decisions

### Requirement: Block on explicit human approval before publishing
The system SHALL pause the editorial cycle before invoking the publisher subagent and SHALL present, for every piece pending approval, the source document, the story summary, each chapter's script, and all per-platform adapted versions — and SHALL NOT resume toward publishing without an explicit approval signal for that piece.

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

### Requirement: Discard or escalate ambiguous or unverifiable material instead of inventing details
The system SHALL discard, or send back to the research agent for more investigation, any document that is ambiguous, incomplete, or whose official origin cannot be verified, and SHALL NOT allow any subagent to invent details to complete a case.

#### Scenario: Ambiguous document encountered
- **WHEN** a document reaching the orchestrator is ambiguous, incomplete, or its official origin is unverifiable
- **THEN** the orchestrator either discards it or requests further research
- **AND** no subagent fabricates missing details to proceed

### Requirement: Produce an end-of-cycle summary
The system SHALL report, at the end of each cycle, how many documents were reviewed, how many became stories, how many chapters were generated, and what remains pending approval.

#### Scenario: Cycle summary produced
- **WHEN** an editorial cycle finishes
- **THEN** the orchestrator reports counts of documents reviewed, stories created, and chapters generated
- **AND** lists what is still pending human approval
