## ADDED Requirements

### Requirement: Local Curation Provider
The system SHALL be able to run case curation against a locally-hosted model, so document discovery and scoring continue when no cloud API credit is available.

#### Scenario: Curation runs against the local model
- **WHEN** the curation LLM provider is configured as `ollama`
- **THEN** `CaseCurationUseCase` SHALL obtain its completions from the local Ollama server, and the curation rubric, threshold, and output contract SHALL be unchanged

#### Scenario: Anthropic remains the default
- **WHEN** no provider is configured
- **THEN** curation SHALL use Anthropic, so existing deployments behave exactly as before

#### Scenario: All document processing can run locally
- **WHEN** the local provider is selected
- **THEN** curation, story-writing and platform-adaptation SHALL all use the local model, so the pipeline can process a document end to end without a cloud API key

#### Scenario: The provider is chosen per deployment, not per stage
- **WHEN** the provider is left at its default
- **THEN** every stage SHALL use Anthropic, so existing deployments are unchanged

### Requirement: Structured Output From The Local Model
The system SHALL request JSON-constrained output from the local model, since curation parses the response as JSON and a conversational reply would fail the parse.

#### Scenario: JSON mode is requested
- **WHEN** a completion is requested from Ollama
- **THEN** the request SHALL set Ollama's JSON output format

#### Scenario: Unparseable output fails the document, not the run
- **WHEN** the local model returns text that is not valid JSON
- **THEN** the failure SHALL surface as a curation error recorded against that document, leaving it retryable, rather than aborting the research pass

### Requirement: Local Provider Failure Reporting
The system SHALL report a local-model failure distinguishably from a cloud-model failure, so an operator can tell "Ollama is not running" from "the API rejected the request".

#### Scenario: The local server is unreachable
- **WHEN** the Ollama server is not running or does not respond
- **THEN** the error SHALL name the base URL that was tried and state that the server appears unreachable

#### Scenario: The requested model is not installed
- **WHEN** Ollama reports that the configured model does not exist
- **THEN** the error SHALL name the model, so the fix (`ollama pull <model>`) is obvious from the message


### Requirement: Constraint Satisfaction On Small Models
The system SHALL retry generation with the validation failure fed back into the prompt, because a small local model cannot reliably satisfy a numeric constraint from a single instruction.

#### Scenario: A rejected draft is regenerated with the reason
- **WHEN** a generated chapter fails a mechanical check (notably the 150–220 word range)
- **THEN** the system SHALL retry, including in the retry prompt what was wrong and by how much, rather than failing the document on the first attempt
- **AND** measurement shows this is what makes a local model viable: an 8B model produced 121, then 149, then 150 words as the failure was fed back

#### Scenario: Retries are bounded
- **WHEN** repeated attempts keep failing validation
- **THEN** the system SHALL stop after a fixed number of attempts and raise the last validation error, so a model that cannot satisfy the constraint fails visibly instead of looping

#### Scenario: The constraint itself is never relaxed
- **WHEN** a local model struggles to reach the required length
- **THEN** the 150–220 word range SHALL remain unchanged, because it is what keeps a chapter inside a 15–60 second reel — the model is retried, the requirement is not lowered
