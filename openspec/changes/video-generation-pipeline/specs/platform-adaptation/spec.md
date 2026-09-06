## MODIFIED Requirements

### Requirement: Adapt a chapter to TikTok/Reels format without changing facts
The system SHALL produce a TikTok/Reels version of each chapter that reuses the existing spoken script, adds on-screen text for the first two lines as a visual hook, includes 3-5 hashtags (mixing niche and reach tags), includes a short description inviting comments or anticipation of the next chapter, and includes video-specific directives (visual suggestions, timing cues, subtitle overlays) for the video compositor — without altering any fact or the core spoken script.

#### Scenario: TikTok/Reels version produced with video directives
- **WHEN** a chapter is submitted for platform adaptation
- **THEN** the TikTok/Reels version keeps the original spoken script intact
- **AND** includes on-screen text for the first two lines
- **AND** includes 3-5 hashtags mixing niche and broad-reach tags
- **AND** includes a short description that invites engagement or teases the next chapter
- **AND** includes video-specific directives: visual suggestions extracted from the script, timing cues from TTS duration, subtitle overlay styling (font size, color, position)

### Requirement: Adapt a chapter to an Instagram carousel when applicable
The system SHALL produce an Instagram carousel of 6-8 slides for a chapter when a carousel is requested in addition to the reel: a cover slide with the hook, 4-6 development slides (one idea per slide), and a final slide with the cited source and a call to follow for the next part. Video adaptation SHALL include alt-text and accessibility descriptions for each slide.

#### Scenario: Carousel requested
- **WHEN** an Instagram carousel is requested for a chapter
- **THEN** the output has between 6 and 8 slides
- **AND** the first slide is a cover carrying the hook
- **AND** the last slide states the cited source and calls the reader to follow for the next part
- **AND** each slide includes alt-text for accessibility

### Requirement: Adapt a chapter to an X (Twitter) thread
The system SHALL produce an X thread of 4-8 tweets per chapter, where the first tweet contains the complete hook understandable without opening the thread, and the final tweets cite the source and announce the next chapter. Video adaptation SHALL include a link or reference to the video where applicable.

#### Scenario: X thread produced with video reference
- **WHEN** a chapter is submitted for platform adaptation
- **THEN** the X version is a thread of 4 to 8 tweets
- **AND** the first tweet alone communicates the complete hook
- **AND** one of the final tweets cites the source and announces the next chapter
- **AND** includes a video link or reference where applicable (e.g., "Watch the full story on TikTok: <link>")

### Requirement: Adapt a chapter to a Facebook post
The system SHALL produce a longer, conversational Facebook version of each chapter that can include the case's full context in a single post alongside the embedded video, and SHALL close with a question to the audience. Video adaptation SHALL include video metadata (duration, language) and subtitle availability.

#### Scenario: Facebook version produced with video metadata
- **WHEN** a chapter is submitted for platform adaptation
- **THEN** the Facebook version is longer and more conversational than the TikTok/X versions
- **AND** ends with a question directed at the audience
- **AND** includes video metadata: estimated video duration (based on script length), language(s) available, subtitle availability (ES/EN)

### Requirement: Deliver all four platform versions per chapter
The system SHALL produce all four platform versions (TikTok/Reels, Instagram, X, Facebook) for every chapter, each with video-specific directives where applicable, before that chapter is considered ready for the approval gate.

#### Scenario: All versions ready with video directives
- **WHEN** platform adaptation completes for a chapter
- **THEN** TikTok/Reels, Instagram, X, and Facebook versions all exist for that chapter
- **AND** each version includes video-specific directives (visuals, timing, metadata) where relevant
- **AND** the chapter is marked ready to enter the human-approval queue
