## ADDED Requirements

### Requirement: Accept an uploaded file as a document source
The system SHALL accept an uploaded PDF or plain-text file, extract its text, and evaluate it through the same curation process (scoring, threshold, permanent recording) as a scraped document — with no source-domain allowlist check, since the operator uploading the file is the provenance decision for it.

#### Scenario: PDF with a native text layer
- **WHEN** an operator uploads a PDF that has extractable text
- **THEN** the system extracts that text directly and evaluates the resulting document through curation

#### Scenario: Scanned PDF requiring OCR
- **WHEN** an operator uploads a PDF with no extractable text layer
- **THEN** the system applies OCR to extract the text before evaluating the resulting document through curation

#### Scenario: Plain text file
- **WHEN** an operator uploads a `.txt` file
- **THEN** the system reads its content directly and evaluates the resulting document through curation

#### Scenario: Unsupported file type
- **WHEN** an operator uploads a file that is neither a PDF nor plain text
- **THEN** the system rejects the upload without attempting extraction

#### Scenario: No extractable text and OCR unavailable
- **WHEN** an uploaded PDF has no native text layer and OCR cannot be performed
- **THEN** the system rejects the upload with a clear reason, rather than evaluating an empty document

#### Scenario: Uploaded document deduplicated like any other
- **WHEN** an uploaded document's title matches an entry already recorded in `/casos_cubiertos.md`
- **THEN** the system does not re-evaluate it, per the existing case-curation deduplication behavior

### Requirement: Retain the uploaded file for provenance
The system SHALL persist the original uploaded file to disk, independent of and in addition to the extracted text used for evaluation.

#### Scenario: Upload succeeds
- **WHEN** an uploaded file is successfully accepted
- **THEN** the original file is retained on disk under a dedicated uploads location
