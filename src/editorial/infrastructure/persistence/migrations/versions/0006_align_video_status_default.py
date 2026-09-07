"""Align video_generations.status server default with the persisted form

Revision ID: 0006_align_video_status_default
Revises: 0005_video_generation_soft_delete
Create Date: 2026-09-06

`VideoGeneration.status` is mapped with SQLAlchemy's `Enum(VideoGenerationStatus)`,
which persists the enum *name* — `PENDING`, `GENERATED`, `FAILED`. Migration
0004 declared the column's server default as the enum *value* (`pending`).

Nothing is broken today because every row is created through the ORM, which
supplies the name and never falls back to the default. But a row inserted by
raw SQL or a future data migration would get `pending`, and reading it back
through the ORM raises LookupError — a failure that would surface far from
its cause.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0006_align_video_status_default"
down_revision: Union[str, None] = "0005_video_generation_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite cannot alter a column in place; batch mode recreates the table.
    with op.batch_alter_table("video_generations") as batch:
        batch.alter_column(
            "status",
            existing_type=sa.String(length=50),
            existing_nullable=False,
            server_default="PENDING",
        )


def downgrade() -> None:
    with op.batch_alter_table("video_generations") as batch:
        batch.alter_column(
            "status",
            existing_type=sa.String(length=50),
            existing_nullable=False,
            server_default="pending",
        )
