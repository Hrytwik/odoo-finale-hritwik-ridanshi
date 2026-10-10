"""allow dispatch notices

Written by Ridanshi for the WhatsApp feature; Hritwik to review before it is merged into main.

Revision ID: d0f6a2b4e537
Revises: c9e5f1a3d426
Create Date: 2026-10-11 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd0f6a2b4e537'
down_revision: Union[str, Sequence[str], None] = 'c9e5f1a3d426'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(op.f('ck_buyer_notices_kind_valid'), 'buyer_notices', type_='check')
    op.create_check_constraint(op.f('ck_buyer_notices_kind_valid'), 'buyer_notices', "kind IN ('delay','dispatch')")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_buyer_notices_kind_valid'), 'buyer_notices', type_='check')
    op.create_check_constraint(op.f('ck_buyer_notices_kind_valid'), 'buyer_notices', "kind IN ('delay')")
