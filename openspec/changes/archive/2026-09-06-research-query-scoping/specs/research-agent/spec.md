## ADDED Requirements

### Requirement: Scope extraction to an operator-provided query when given
The system SHALL accept an optional query (a topic or focus string) alongside the list of source URLs for a research pass, and, when a query is given, SHALL prefer a query-capable scraper for extraction so the fetched content is guided by that query rather than the source's entire page. When no query is given, extraction behaves exactly as it does today (full-page extraction via the default scraper order).

#### Scenario: Query provided and a query-capable scraper is available
- **WHEN** a research pass is started with a query and a query-capable scraper is configured
- **THEN** the query-capable scraper is tried first for each source URL, guided by the query
- **AND** the non-query-capable scraper is only used if the query-capable one fails to extract a document

#### Scenario: Query provided but no query-capable scraper is configured
- **WHEN** a research pass is started with a query but no query-capable scraper is available
- **THEN** the system falls back to its default scraper, which extracts the full page as it would without a query
- **AND** this is not treated as an error

#### Scenario: No query provided
- **WHEN** a research pass is started without a query
- **THEN** extraction proceeds exactly as it did before this capability existed — default scraper first, fallback on failure, full-page extraction throughout
