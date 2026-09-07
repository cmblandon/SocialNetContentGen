## REMOVED Requirements

### Requirement: Document Discovery From Source URLs
**Reason**: Documents now enter the system by upload. The operator chooses which declassified document to work on and uploads its PDF, so crawling configured source URLs to discover candidates serves no remaining purpose.

**Migration**: Replaced by `document-upload`. The scraper adapters and the source-URL configuration are removed. Any document previously discovered by the scraper must be uploaded as a PDF to be processed.

### Requirement: Scraper Fallback Chain
**Reason**: With no discovery step, there is nothing for a primary and fallback scraper to fetch.

**Migration**: None required. Extraction failures are now surfaced by `document-upload`, which reports whether a file was unreadable, unparseable, or empty after OCR.
