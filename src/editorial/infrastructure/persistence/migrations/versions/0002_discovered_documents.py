"""Add discovered_documents table (research-pipeline-checkpointing)

Revision ID: 0002_discovered_documents
Revises: 0001_initial_editorial_schema
Create Date: 2026-09-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from src.editorial.infrastructure.persistence.models import CurationStatus

# revision identifiers, used by Alembic.
revision: str = "0002_discovered_documents"
down_revision: Union[str, None] = "0001_initial_editorial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CURATION_STATUS_VALUES = [s.value for s in CurationStatus]


def upgrade() -> None:
    op.create_table(
        "discovered_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("agency", sa.String(length=200), nullable=False),
        sa.Column("doc_type", sa.String(length=100), nullable=False),
        sa.Column("published_date", sa.String(length=50), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("extraction_confidence", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.Enum(*_CURATION_STATUS_VALUES, name="curationstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("narrative_angle", sa.Text(), nullable=True),
        sa.Column(
            "document_id", sa.String(length=36), sa.ForeignKey("documents.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("discovered_documents")
