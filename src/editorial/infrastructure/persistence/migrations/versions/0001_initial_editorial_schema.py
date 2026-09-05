"""Initial editorial schema: Document, Story, Chapter, PlatformVersion, PublishRecord

Revision ID: 0001_initial_editorial_schema
Revises:
Create Date: 2026-09-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from src.editorial.infrastructure.persistence.models import ApprovalStatus, PlatformName

# revision identifiers, used by Alembic.
revision: str = "0001_initial_editorial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PLATFORM_VALUES = [p.value for p in PlatformName]
_STATUS_VALUES = [s.value for s in ApprovalStatus]


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("agency", sa.String(length=200), nullable=False),
        sa.Column("doc_type", sa.String(length=100), nullable=False),
        sa.Column("published_date", sa.String(length=50), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("extraction_confidence", sa.String(length=50), nullable=True),
        sa.Column("source_ficha_id", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "stories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("narrative_angle", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "chapters",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("story_id", sa.String(length=36), sa.ForeignKey("stories.id"), nullable=False),
        sa.Column("chapter_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("script", sa.Text(), nullable=False),
        sa.Column("visual_notes", sa.Text(), nullable=True),
        sa.Column("source_citation", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "platform_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("chapter_id", sa.String(length=36), sa.ForeignKey("chapters.id"), nullable=False),
        sa.Column(
            "platform", sa.Enum(*_PLATFORM_VALUES, name="platformname", native_enum=False), nullable=False
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Enum(*_STATUS_VALUES, name="approvalstatus", native_enum=False), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "publish_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "platform_version_id",
            sa.String(length=36),
            sa.ForeignKey("platform_versions.id"),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_post_id", sa.String(length=200), nullable=True),
        sa.Column(
            "status", sa.Enum(*_STATUS_VALUES, name="approvalstatus", native_enum=False), nullable=False
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("publish_records")
    op.drop_table("platform_versions")
    op.drop_table("chapters")
    op.drop_table("stories")
    op.drop_table("documents")
