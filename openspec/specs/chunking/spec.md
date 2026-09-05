# Chunking Specification

## Purpose
TBD: The system provides functionality to divide text into chunks for processing by LLMs, ensuring context continuity via overlapping fragments.

## Requirements

### Requirement: Chunk short documents without overlap
The system SHALL return the original text as a single chunk when length does not exceed chunk_size_chars threshold.

#### Scenario: Document under size threshold
- **WHEN** input text is shorter than or equal to chunk_size_chars (6000)
- **THEN** dividir_en_chunks returns a list containing only the original text
- **AND** no overlap calculation is performed

#### Scenario: Empty document
- **WHEN** input text is an empty string
- **THEN** divider_en_chunks returns a list with one empty string element
- **AND** downstream components handle empty chunks gracefully

### Requirement: Chunk long documents with overlapping fragments
The system SHALL divide long texts into multiple chunks with overlap_chars bytes of overlap between consecutive chunks.

#### Scenario: Single boundary crossing
- **WHEN** input text is 6100 characters (just over threshold)
- **THEN** dividir_en_chunks creates exactly 2 chunks
- **AND** first chunk spans positions 0 to 6000
- **AND** second chunk spans positions 5700 to end (300 char overlap)

#### Scenario: Multiple boundary crossings
- **WHEN** input text is 12000 characters (far above threshold)
- **THEN** dividir_en_chunks creates multiple chunks with consistent overlap
- **AND** each transition between chunks maintains overlap_chars overlap
- **AND** final chunk may be smaller than chunk_size_chars if less text remains

#### Scenario: Odd-length document spanning multiple boundaries
- **WHEN** input text is 19500 characters (exactly 3x threshold with overlaps)
- **THEN** dividir_en_chunks creates correct number of chunks based on overlap calculation
- **AND** while loop termination condition prevents infinite iteration
- **AND** all chunks maintain proper overlap except potentially the last

### Requirement: Handle boundary conditions correctly
The system SHALL avoid edge cases that cause incorrect chunking behavior or infinite loops.

#### Scenario: Text exactly at boundary
- **WHEN** input text length equals chunk_size_chars precisely
- **THEN** divider_en_chunks treats it as short document (single chunk)
- **AND** the inequality check uses <= to include boundary in "short" category

#### Scenario: Very small overlap relative to chunk size
- **WHEN** chunk_overlap_chars is 300 and chunk_size_chars is 6000 (5% ratio)
- **THEN** chunks advance meaningfully while maintaining context continuity
- **AND** algorithm does not create excessive duplicate content

#### Scenario: Overlap greater than chunk size
- **WHEN** chunk_overlap_chars exceeds chunk_size_chars (malformed config)
- **THEN** algorithm converges by progressively reducing start position
- **AND** while condition `inicio < len(texto)` ensures eventual termination
