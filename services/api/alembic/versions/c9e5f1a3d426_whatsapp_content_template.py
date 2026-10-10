"""whatsapp message template id

Written by Ridanshi for the WhatsApp feature; Hritwik to review before it is merged into main.

Revision ID: c9e5f1a3d426
Revises: b8d4e0f2c315
Create Date: 2026-10-11 03:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e5f1a3d426'
down_revision: Union[str, Sequence[str], None] = 'b8d4e0f2c315'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messaging_settings', sa.Column('content_sid', sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column('messaging_settings', 'content_sid')
