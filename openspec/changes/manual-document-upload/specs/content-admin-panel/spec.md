## ADDED Requirements

### Requirement: Upload a document for evaluation from the panel
The system SHALL let an operator upload a file from the Configuración view and see the resulting evaluation outcome.

#### Scenario: Operator uploads a file
- **WHEN** an operator selects a file and submits it in the Configuración view
- **THEN** the panel sends it for evaluation and shows the outcome (advanced, discarded, or rejected as unsupported/unextractable)

#### Scenario: Unsupported file rejected in the panel
- **WHEN** an operator attempts to upload a file that is neither a PDF nor plain text
- **THEN** the panel shows a clear rejection message without sending the request as a success
