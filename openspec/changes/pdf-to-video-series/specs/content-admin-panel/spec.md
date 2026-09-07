## REMOVED Requirements

### Requirement: Pipeline Feed
**Reason**: The feed listed chapters awaiting approval across a discovery-driven pipeline. With documents arriving one at a time by upload, the unit of work is a document and its series, not a queue of discovered cases.

**Migration**: Replaced by a per-document view showing that document's series plan and chapters.

### Requirement: Editorial Calendar View
**Reason**: The system no longer schedules or publishes.

**Migration**: None.

### Requirement: Covered Cases View
**Reason**: Tracked which cases had already been published, to avoid rework. With no publishing step, there is no publication history to track.

**Migration**: None. Preserved on the `archive/pre-pivot` branch.

### Requirement: Video Library View
**Reason**: Listed videos the system had rendered. The system no longer renders video.

**Migration**: Replaced by `script-export`.

## MODIFIED Requirements

### Requirement: Admin Panel Scope
The admin panel SHALL provide exactly three things: uploading a document, reviewing its series and scripts, and exporting approved scripts.

#### Scenario: Upload with visible progress
- **WHEN** an operator uploads a PDF
- **THEN** the panel SHALL show measured progress through extraction and analysis, and SHALL name the step currently running

#### Scenario: Review a series before its chapters exist
- **WHEN** a series plan has been produced
- **THEN** the panel SHALL show the chapter breakdown and through-line, and SHALL let the operator approve or reject the plan before chapters are generated

#### Scenario: Read a script before deciding on it
- **WHEN** a chapter script is presented for approval
- **THEN** the panel SHALL show the full script text, its visual directions, its position in the series, and its source citation, so the decision is made by reading rather than by trusting

#### Scenario: The panel offers nothing else
- **WHEN** an operator uses the panel
- **THEN** it SHALL expose no discovery, scheduling, publishing, or video-rendering controls, because the system performs none of those
