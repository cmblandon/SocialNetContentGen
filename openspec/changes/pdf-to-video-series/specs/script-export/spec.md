## ADDED Requirements

### Requirement: Approved Scripts Leave The System
The system SHALL let an operator take an approved script out to an external video tool. The system SHALL NOT itself generate, request, or store video.

#### Scenario: Copy to clipboard
- **WHEN** an operator copies an approved script
- **THEN** the full narration text, visual directions, chapter number and source citation SHALL be placed on the clipboard, ready to paste into an external tool

#### Scenario: Download as Markdown
- **WHEN** an operator downloads an approved script as Markdown
- **THEN** the file SHALL contain the script, its visual directions, its chapter position within the series, and the source citation, so it remains readable and archivable outside the panel

#### Scenario: Download as scene-structured JSON
- **WHEN** an operator downloads an approved script as JSON
- **THEN** the script SHALL be broken into ordered scenes, each carrying its narration text and its visual direction, because storyboard-driven video tools consume per-scene structure rather than a prose monologue

#### Scenario: Only approved scripts are exportable
- **WHEN** a script is pending or rejected
- **THEN** export SHALL be unavailable for it, so an unreviewed script cannot reach a rendering tool

### Requirement: Export Is The Terminal Step
The system SHALL treat export as the end of its responsibility for a script.

#### Scenario: No video provider integration exists
- **WHEN** a script has been exported
- **THEN** the system SHALL record that it was exported and take no further action — it holds no video provider API key, makes no rendering request, and stores no rendered video

#### Scenario: Visual fidelity is out of scope
- **WHEN** an operator renders an exported script in an external tool
- **THEN** verifying that the resulting visuals do not imply anything the source document fails to support SHALL be the operator's responsibility in that tool, because the system's guarantees end at the text it produced
