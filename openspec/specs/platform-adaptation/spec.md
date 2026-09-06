# Platform Adaptation Specification

## Purpose
Reformats a chapter's script into TikTok/Reels, Instagram, X, and Facebook variants without changing facts or the core spoken script.

## Requirements

### Requirement: Adapt a chapter to TikTok/Reels format without changing facts
The system SHALL produce a TikTok/Reels version of each chapter that reuses the existing spoken script, adds on-screen text for the first two lines as a visual hook, includes 3-5 hashtags (mixing niche and reach tags), and includes a short description inviting comments or anticipation of the next chapter — without altering any fact or the core spoken script.

#### Scenario: TikTok/Reels version produced
- **WHEN** a chapter is submitted for platform adaptation
- **THEN** the TikTok/Reels version keeps the original spoken script intact
- **AND** includes on-screen text for the first two lines
- **AND** includes 3-5 hashtags mixing niche and broad-reach tags
- **AND** includes a short description that invites engagement or teases the next chapter

### Requirement: Adapt a chapter to an Instagram carousel when applicable
The system SHALL produce an Instagram carousel of 6-8 slides for a chapter when a carousel is requested in addition to the reel: a cover slide with the hook, 4-6 development slides (one idea per slide), and a final slide with the cited source and a call to follow for the next part.

#### Scenario: Carousel requested
- **WHEN** an Instagram carousel is requested for a chapter
- **THEN** the output has between 6 and 8 slides
- **AND** the first slide is a cover carrying the hook
- **AND** the last slide states the cited source and calls the reader to follow for the next part

### Requirement: Adapt a chapter to an X (Twitter) thread
The system SHALL produce an X thread of 4-8 tweets per chapter, where the first tweet contains the complete hook understandable without opening the thread, and the final tweets cite the source and announce the next chapter.

#### Scenario: X thread produced
- **WHEN** a chapter is submitted for platform adaptation
- **THEN** the X version is a thread of 4 to 8 tweets
- **AND** the first tweet alone communicates the complete hook
- **AND** one of the final tweets cites the source and announces the next chapter

### Requirement: Adapt a chapter to a Facebook post
The system SHALL produce a longer, conversational Facebook version of each chapter that can include the case's full context in a single post alongside the embedded video, and SHALL close with a question to the audience.

#### Scenario: Facebook version produced
- **WHEN** a chapter is submitted for platform adaptation
- **THEN** the Facebook version is longer and more conversational than the TikTok/X versions
- **AND** ends with a question directed at the audience

### Requirement: Deliver all four platform versions per chapter
The system SHALL produce all four platform versions (TikTok/Reels, Instagram, X, Facebook) for every chapter before that chapter is considered ready for the approval gate.

#### Scenario: All versions ready
- **WHEN** platform adaptation completes for a chapter
- **THEN** TikTok/Reels, Instagram, X, and Facebook versions all exist for that chapter
- **AND** the chapter is marked ready to enter the human-approval queue
