## ADDED Requirements

### Requirement: Detect PDFs with extractable text without OCR
The system SHALL identify PDFs that have sufficient textual content and skip OCR processing for those documents.

#### Scenario: Text-rich PDF with sufficient content
- **WHEN** a PDF page contains more than min_chars_texto_real (50 chars per page) across the first 3 pages
- **THEN** PdfTextInspector.tiene_texto_real returns True
- **AND** no OCR processing is required for this document

#### Scenario: Text-rich PDF with borderline content
- **WHEN** a PDF page contains exactly min_chars_texto_real characters across all checked pages
- **THEN** PdfTextInspector.tiene_texto_real returns False (strict greater-than comparison)
- **AND** document proceeds to OCR processing as precautionary measure

#### Scenario: Text-poor scanned document
- **WHEN** a PDF has less than 50 chars per page in the first 3 pages (scanned image without text layer)
- **THEN** PdfTextInspector.tiene_texto_real returns False
- **AND** downstream components prepare for OCR processing

#### Scenario: PDF with no extractable text layers
- **WHEN** pypdf.extract_text() raises an exception due to encrypted or image-only PDF
- **THEN** exception is caught and logged as warning
- **AND** tiene_texto_real returns False gracefully without crashing

#### Scenario: Corrupted PDF file
- **WHEN** attempting to read a malformed/encrypted/incomplete PDF fails with pypdf.PdfReader exception
- **THEN** exception is caught and logged
- **AND** tiene_texto_real returns False allowing fallback to OCR

### Requirement: Apply OCR to documents without extractable text
The system SHALL process scanned/image-only PDFs through OCR and return the resulting path for subsequent text extraction.

#### Scenario: OCR processor receives document lacking text
- **WHEN** input PDF has no extractable text layer (as verified by IpdfInspector)
- **THEN** OcrProcessor.aplicar invokes external ocrmypdf tool with proper flags
- **AND** --skip-text flag is passed to prevent reprocessing already-textured pages

#### Scenario: OCR processor encounters missing dependency
- **WHEN** ocrmypdf command is not found in PATH (not installed on system)
- **THEN** OcrProcessor.aplicar logs error message specifying brew install command
- **AND** return value is None indicating processing failure

#### Scenario: OCR processor fails mid-processing
- **WHEN** subprocess.CalledProcessError exception is raised during ocrmypdf execution
- **THEN** stderr output is logged for debugging
- **AND** return value is None propagating failure upstream

#### Scenario: OCR creates output file successfully
- **WHEN** ocrmypdf completes without errors and creates output path
- **THEN** output_path is returned to caller for subsequent text extraction
- **AND** log message includes source filename and target output name

### Requirement: Preserve original PDF metadata during OCR
The system SHALL maintain document identification information through the OCR pipeline.

#### Scenario: OCR preserves original filename reference
- **WHEN** processing requires output path distinct from input path
- **THEN** original pdf_path is kept as reference parameter throughout
- **AND** output naming convention includes "ocr_" prefix to indicate processed status
