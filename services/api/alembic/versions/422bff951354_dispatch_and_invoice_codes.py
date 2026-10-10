"""dispatch and invoice codes

Revision ID: 422bff951354
Revises: 43caade7e8a6
Create Date: 2026-10-10 19:38:41.238460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '422bff951354'
down_revision: Union[str, Sequence[str], None] = '43caade7e8a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE dispatch_code_seq")
    op.execute("CREATE SEQUENCE invoice_code_seq")


def downgrade() -> None:
    op.execute("DROP SEQUENCE invoice_code_seq")
    op.execute("DROP SEQUENCE dispatch_code_seq")
