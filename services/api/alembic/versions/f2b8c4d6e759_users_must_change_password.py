"""users must change a temporary password

Revision ID: f2b8c4d6e759
Revises: e1a7b3c5d648
Create Date: 2026-10-11 07:09:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'f2b8c4d6e759'
down_revision: Union[str, Sequence[str], None] = 'e1a7b3c5d648'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
