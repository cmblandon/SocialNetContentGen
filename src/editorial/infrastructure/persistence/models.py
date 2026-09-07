"""
SQLAlchemy models for the editorial schema — "Archivo Desclasificado".

Chain: Document -> Story -> Chapter -> PlatformVersion -> PublishRecord.

This is a distinct bounded context from the ingestion pipeline's
`documentos` table (src/infrastructure/persistence/sqlite_repo.py):
a Document here is an editorial case record, not a raw depuration
output. When a Document originates from the manual PDF pipeline,
`source_ficha_id` references that pipeline's FichaEstructurada by id
instead of duplicating its fields (see design.md, Decision 3).
"""
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PlatformName(str, enum.Enum):
    """The four networks covered by platform-adaptation."""

    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    X = "x"
    FACEBOOK = "facebook"


class ApprovalStatus(str, enum.Enum):
    """
    Lifecycle of a PlatformVersion (and its PublishRecord), per design.md
    Decision 5: the human-approval gate is enforced by this persisted status,
    not by prompt instructions alone.
    """

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    FAILED = "failed"


class Document(Base):
    """An editorial case record produced by research-agent (or referencing a
    manually-ingested FichaEstructurada via source_ficha_id)."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    agency: Mapped[str] = mapped_column(String(200), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    published_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_confidence: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_ficha_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    stories: Mapped[list["Story"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Story(Base):
    """The narrative generated from a curated Document (story-writing spec)."""

    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    narrative_angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    document: Mapped["Document"] = relationship(back_populates="stories")
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="story",
        cascade="all, delete-orphan",
        order_by="Chapter.chapter_index",
    )


class Chapter(Base):
    """One chapter of a Story: title, spoken script, visual notes, and citation
    (story-writing spec)."""

    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    story_id: Mapped[str] = mapped_column(ForeignKey("stories.id"), nullable=False)
    chapter_index: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    script: Mapped[str] = mapped_column(Text, nullable=False)
    visual_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_citation: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    story: Mapped["Story"] = relationship(back_populates="chapters")
    platform_versions: Mapped[list["PlatformVersion"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan"
    )


class PlatformVersion(Base):
    """A chapter adapted for one platform (platform-adaptation spec), carrying
    the approval status the publisher and admin panel act on."""

    __tablename__ = "platform_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    platform: Mapped[PlatformName] = mapped_column(SAEnum(PlatformName), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING_REVIEW
    )
    script_approved: Mapped[bool] = mapped_column(nullable=False, default=False)
    script_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    chapter: Mapped["Chapter"] = relationship(back_populates="platform_versions")
    publish_records: Mapped[list["PublishRecord"]] = relationship(
        back_populates="platform_version", cascade="all, delete-orphan"
    )
    video_generations: Mapped[list["VideoGeneration"]] = relationship(
        back_populates="platform_version", cascade="all, delete-orphan"
    )


class PublishRecord(Base):
    """The outcome of a publish/schedule attempt for a PlatformVersion
    (publishing spec): network, time, and the API-returned post id."""

    __tablename__ = "publish_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    platform_version_id: Mapped[str] = mapped_column(
        ForeignKey("platform_versions.id"), nullable=False
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    external_post_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING_REVIEW
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    platform_version: Mapped["PlatformVersion"] = relationship(back_populates="publish_records")


class CurationStatus(str, enum.Enum):
    """
    Lifecycle of a DiscoveredDocument checkpoint (research-pipeline-
    checkpointing design.md Decision 1). PENDING until curation is
    attempted; ADVANCED/DISCARDED are terminal outcomes of a curation call
    that actually ran; FAILED means curation itself errored (LLM/network
    error, malformed response) — distinct from DISCARDED (curation ran to
    completion and scored below threshold) because a FAILED row is
    retryable via POST /research/resume and a DISCARDED one is not.
    """

    PENDING = "pending"
    ADVANCED = "advanced"
    DISCARDED = "discarded"
    FAILED = "failed"


class DiscoveredDocument(Base):
    """
    A document research-agent successfully scraped, checkpointed
    immediately — before curation is ever attempted — so a curation-stage
    failure can never silently lose already-scraped content (design.md
    Decision 1). Deliberately a separate table from Document: Document
    continues to mean "an editorial case with a story" everywhere else in
    this codebase (its `stories` relationship, the admin panel's cases
    view, manual_curation_cli), not "anything ever scraped, including
    permanently discarded/failed ones".

    Rows are never deleted (design.md Decision 5): once ADVANCED or
    DISCARDED they stay as a permanent audit trail; FAILED rows stay
    FAILED until a resume attempt changes their status.
    """

    __tablename__ = "discovered_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    agency: Mapped[str] = mapped_column(String(200), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    published_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_confidence: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[CurationStatus] = mapped_column(
        SAEnum(CurationStatus), nullable=False, default=CurationStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    narrative_angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_id: Mapped[Optional[str]] = mapped_column(ForeignKey("documents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class VideoGenerationStatus(str, enum.Enum):
    """Lifecycle of a VideoGeneration record."""

    PENDING = "pending"
    GENERATED = "generated"
    FAILED = "failed"


class VideoGeneration(Base):
    """Video file generated from an approved script (video-generation-pipeline).
    One row per platform version and language combination."""

    __tablename__ = "video_generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    platform_version_id: Mapped[str] = mapped_column(
        ForeignKey("platform_versions.id"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    video_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    subtitle_file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[VideoGenerationStatus] = mapped_column(
        SAEnum(VideoGenerationStatus),
        nullable=False,
        default=VideoGenerationStatus.PENDING,
        # Declared here as well as in the migration so `create_all` (which
        # builds the test schema) and Alembic (which builds production) agree.
        # SAEnum persists the enum *name*, so the default must be the name —
        # the value ("pending") would be unreadable back through the ORM.
        server_default=VideoGenerationStatus.PENDING.name,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_of_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("video_generations.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Soft delete: the row outlives its file. retry_of_id is a self-referential
    # FK with no cascade, so removing an attempt that has retries would break
    # the lineage the audit trail reports.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    platform_version: Mapped["PlatformVersion"] = relationship(back_populates="video_generations")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
