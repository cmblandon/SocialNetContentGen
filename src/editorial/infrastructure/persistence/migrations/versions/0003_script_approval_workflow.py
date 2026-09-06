"""Add script approval to PlatformVersion (video-generation-pipeline)

Revision ID: 0003_script_approval_workflow
Revises: 0002_discovered_documents
Create Date: 2026-09-06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0003_script_approval_workflow"
down_revision: Union[str, None] = "0002_discovered_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("platform_versions", sa.Column("script_approved", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("platform_versions", sa.Column("script_approved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("platform_versions", "script_approved_at")
    op.drop_column("platform_versions", "script_approved")
