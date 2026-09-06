"""Add VideoGeneration table (video-generation-pipeline)

Revision ID: 0004_video_generation_table
Revises: 0003_script_approval_workflow
Create Date: 2026-09-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0004_video_generation_table"
down_revision: Union[str, None] = "0003_script_approval_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "video_generations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "platform_version_id",
            sa.String(length=36),
            sa.ForeignKey("platform_versions.id"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("video_file_path", sa.String(length=500), nullable=True),
        sa.Column("subtitle_file_path", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "retry_of_id",
            sa.String(length=36),
            sa.ForeignKey("video_generations.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_video_generations_platform_version_id", "video_generations", ["platform_version_id"])


def downgrade() -> None:
    op.drop_index("ix_video_generations_platform_version_id", "video_generations")
    op.drop_table("video_generations")
