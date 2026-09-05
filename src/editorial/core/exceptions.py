"""Domain exceptions for the editorial bounded context."""


class StoryGenerationError(Exception):
    """
    Raised when the LLM's output for a story/chapter can't be trusted: it
    isn't parseable, a chapter violates the required word-count range, is
    missing its source citation, contains a quote absent from the source
    document (fabrication), or contains overstated/sensationalist phrasing.
    Per specs/story-writing/spec.md, none of these are recoverable by
    silently proceeding — the caller must regenerate or escalate.
    """
