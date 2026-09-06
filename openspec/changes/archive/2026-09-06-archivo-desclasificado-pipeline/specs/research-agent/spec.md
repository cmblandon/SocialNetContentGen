## ADDED Requirements

### Requirement: Discover documents only from prioritized official sources
The system SHALL discover candidate documents only from the prioritized source list (war.gov/UFO, cia.gov/readingroom, archives.gov, AARO/ODNI annual reports, The Black Vault as a locator only) and SHALL discard any source that is not an official/verifiable agency source or that requires login/authentication to access.

#### Scenario: Official source is reachable
- **WHEN** the research agent queries war.gov/UFO, cia.gov/readingroom, archives.gov, or an AARO/ODNI report page
- **THEN** it lists documents found on that source as candidates for extraction

#### Scenario: Black Vault entry used only as a locator
- **WHEN** a candidate document is found on The Black Vault
- **THEN** the agent attempts to resolve it back to the original issuing agency
- **AND** the record notes whether the original-agency source was confirmed

#### Scenario: Source requires login or is unverifiable
- **WHEN** a page is protected behind login, or its origin cannot be confirmed as an official agency
- **THEN** the agent discards that source
- **AND** reports the discard with a reason instead of extracting from it

### Requirement: Deduplicate against already-covered cases before extraction
The system SHALL compare each discovered document against `/casos_cubiertos.md` before downloading or extracting it, and SHALL skip documents already recorded there.

#### Scenario: Document already covered
- **WHEN** a discovered document matches an entry already present in `/casos_cubiertos.md`
- **THEN** the agent skips extraction for that document
- **AND** does not pass it downstream to curation

#### Scenario: Document not yet covered
- **WHEN** a discovered document has no matching entry in `/casos_cubiertos.md`
- **THEN** the agent proceeds to extract it

### Requirement: Extract a structured record per document
The system SHALL extract, for each retained document, a structured record containing title, date, issuing agency, document type (report, testimony, photo, video, transcription), and the full text or a faithful summary (using OCR when the source is a scanned PDF).

#### Scenario: Text-native document
- **WHEN** the source document has an extractable text layer
- **THEN** the agent produces a structured record with title, date, agency, doc type, and full extracted text

#### Scenario: Scanned document requiring OCR
- **WHEN** the source document is an image-only scanned PDF
- **THEN** the agent applies OCR before producing the structured record
- **AND** the record reflects the OCR-derived text

#### Scenario: Video or image asset
- **WHEN** the discovered asset is a video or image rather than text
- **THEN** the agent describes its content exactly as presented by the official source
- **AND** does not speculate about what the content "could be"

### Requirement: Research agent does not interpret or write content
The system SHALL limit the research agent's output to structured records; it SHALL NOT produce narrative text, interpretation, or speculation about a document's content.

#### Scenario: Extraction complete
- **WHEN** the research agent finishes processing a document
- **THEN** its output is a structured record (JSON-shaped) ready for the curation stage
- **AND** contains no narrative or interpretive text authored by the agent
