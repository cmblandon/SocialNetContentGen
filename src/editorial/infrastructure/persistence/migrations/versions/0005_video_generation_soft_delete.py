"""Add VideoGeneration.deleted_at (video-generation-pipeline soft delete)

Revision ID: 0005_video_generation_soft_delete
Revises: 0004_video_generation_table
Create Date: 2026-09-06

Deleting a video removes its file but retains the row. `retry_of_id` is a
self-referential foreign key with no cascade, so removing an attempt that has
retries would either violate referential integrity or orphan the retry chain
the audit trail is required to report.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0005_video_generation_soft_delete"
down_revision: Union[str, None] = "0004_video_generation_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "video_generations",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("video_generations", "deleted_at")
