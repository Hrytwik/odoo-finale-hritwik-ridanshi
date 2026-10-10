"""code sequences

Revision ID: 2ee7b7a714bf
Revises: ae46451bab35
Create Date: 2026-10-10 14:35:24.451590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ee7b7a714bf'
down_revision: Union[str, Sequence[str], None] = 'ae46451bab35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Human-readable codes come from sequences, so simultaneous requests never share a number."""
    op.execute("CREATE SEQUENCE lot_code_seq")
    op.execute("CREATE SEQUENCE order_code_seq")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP SEQUENCE order_code_seq")
    op.execute("DROP SEQUENCE lot_code_seq")
