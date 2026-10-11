"""buyer notices (the buyer's bell)

Written by Ridanshi for the delay-notice feature; Hritwik to review before it is merged into main.

Revision ID: a7c3d9e1b204
Revises: 422bff951354
Create Date: 2026-10-10 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3d9e1b204'
down_revision: Union[str, Sequence[str], None] = '422bff951354'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('buyer_notices',
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('buyer_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.String(length=30), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('sent_by', sa.Integer(), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("btrim(message) <> ''", name=op.f('ck_buyer_notices_message_nonblank')),
    sa.CheckConstraint("kind IN ('delay')", name=op.f('ck_buyer_notices_kind_valid')),
    sa.ForeignKeyConstraint(['buyer_id'], ['buyers.id'], name=op.f('fk_buyer_notices_buyer_id_buyers')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_buyer_notices_order_id_orders')),
    sa.ForeignKeyConstraint(['sent_by'], ['users.id'], name=op.f('fk_buyer_notices_sent_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_buyer_notices'))
    )
    op.create_index('ix_buyer_notices_buyer_id_created_at', 'buyer_notices', ['buyer_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_buyer_notices_buyer_id_created_at', table_name='buyer_notices')
    op.drop_table('buyer_notices')
