## REMOVED Requirements

### Requirement: Four Native Platform Text Formats
**Reason**: This produced *substitute* text content — an X thread of 4–8 tweets, an Instagram carousel of 6–8 slides — for platforms that would carry text instead of video. With an animated video as the deliverable, those are a different product: there is no text thread when the payload is a video.

**Migration**: Replaced by the duration cuts in `story-writing`. What genuinely differs between platforms when the output is video is runtime, not format, so a chapter is produced as a long cut and a short cut rather than as four rewrites.

## MODIFIED Requirements

### Requirement: Platform Targeting
The system SHALL target platforms by video runtime rather than by text format.

#### Scenario: Long-form and short-form targets
- **WHEN** a chapter is generated
- **THEN** it SHALL be produced as a long cut for long-form video placement and a short cut for short-form placement, both carrying the same plot and the same facts

#### Scenario: No per-network content variants
- **WHEN** scripts are produced for a document
- **THEN** the system SHALL NOT generate network-specific rewrites — the same long cut serves every long-form platform, and the same short cut serves every short-form one
