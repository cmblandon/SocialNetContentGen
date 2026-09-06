# Story Writing Specification

## Purpose
Turns a curated document into a hook-driven, chapterized, fact-bound narrative script with visual and sourcing notes.

## Requirements

### Requirement: Generate a fact-bound hook/development/close story structure
The system SHALL generate, for each curated document, a story with an opening hook (the case's most intriguing question or image, not background context), a development section (who/when/what was reported/what the agency did/what the document literally states), and a close (what remains unexplained, or what the document newly revealed), and SHALL NOT include any factual claim not traceable to the source document.

#### Scenario: Story generated from a curated document
- **WHEN** the writer agent receives a curated document and its narrative-angle note
- **THEN** it produces a story with a distinct hook, development, and close
- **AND** every factual claim in the story is traceable to the source document's text

#### Scenario: Speculation present in the source
- **WHEN** the underlying case involves an unresolved or speculative element
- **THEN** the story presents it explicitly as interpretation (e.g. "algunos investigadores sugieren...")
- **AND** never as a confirmed fact

### Requirement: Split extensive documents into independently publishable chapters
The system SHALL split a story into chapters of 150-220 words (60-90 seconds of spoken script) when the source document is extensive, and SHALL ensure each chapter has its own opening hook, is understandable on its own, and closes with a cliffhanger grounded in the source document that previews the next chapter.

#### Scenario: Short document, single piece
- **WHEN** the source document is short enough to cover in one 60-90s script
- **THEN** the writer agent produces a single chapter instead of splitting into a series

#### Scenario: Extensive document split into chapters
- **WHEN** the source document is long (e.g. a lengthy report with multiple annexes)
- **THEN** the writer agent splits it into multiple chapters of 150-220 words each
- **AND** each chapter can be published independently without losing meaning
- **AND** each chapter ends with a document-grounded cliffhanger that previews the next chapter

#### Scenario: Cliffhanger must be real
- **WHEN** a chapter closes with a cliffhanger
- **THEN** the cliffhanger references a fact or detail that genuinely exists later in the source document
- **AND** is never an invented hook unsupported by the document

### Requirement: Deliver each chapter with title, script, visuals, and cited source
The system SHALL deliver each chapter as: a short title, the full spoken script, visual-resource suggestions per line/beat (document, map, archive photo, on-screen text), and the cited source (agency, document type, date).

#### Scenario: Chapter delivery format
- **WHEN** a chapter is produced
- **THEN** it includes a short title, the complete spoken script, visual suggestions aligned to the script, and an explicit source citation

### Requirement: Prohibit fabricated quotes and sensationalist misrepresentation
The system SHALL NOT attribute textual quotes to real people unless those quotes appear in the source document, and SHALL NOT use language that overstates what the document establishes (e.g. claiming "proof" or "government admission" the document does not contain).

#### Scenario: No quote in source document
- **WHEN** the source document does not contain a direct quote from a named individual
- **THEN** the generated story does not attribute any quote to that individual

#### Scenario: Overstated claim attempted
- **WHEN** a draft script would claim something the document does not literally state (e.g. definitive proof, an admission)
- **THEN** the writer agent rephrases the claim to match only what the document actually states
