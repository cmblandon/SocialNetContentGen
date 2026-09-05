"""Shared URL-extension heuristic for inferring a document's type, used by
both scraper adapters."""
_VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".avi")
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")


def infer_doc_type_from_url(url: str) -> str:
    lower_url = url.lower()
    if lower_url.endswith(_VIDEO_EXTENSIONS):
        return "video"
    if lower_url.endswith(_IMAGE_EXTENSIONS):
        return "photo"
    return "report"
