## ADDED Requirements

### Requirement: Local Curation Provider
The system SHALL be able to run case curation against a locally-hosted model, so document discovery and scoring continue when no cloud API credit is available.

#### Scenario: Curation runs against the local model
- **WHEN** the curation LLM provider is configured as `ollama`
- **THEN** `CaseCurationUseCase` SHALL obtain its completions from the local Ollama server, and the curation rubric, threshold, and output contract SHALL be unchanged

#### Scenario: Anthropic remains the default
- **WHEN** no provider is configured
- **THEN** curation SHALL use Anthropic, so existing deployments behave exactly as before

#### Scenario: Only curation is affected
- **WHEN** the local provider is selected
- **THEN** story-writing, platform-adaptation and subtitle translation SHALL continue to use Anthropic, because those stages generate prose under validation a small local model cannot reliably satisfy

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
