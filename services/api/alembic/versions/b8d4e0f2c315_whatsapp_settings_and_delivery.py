"""whatsapp settings and delivery status for buyer notices

Written by Ridanshi for the WhatsApp feature; Hritwik to review before it is merged into main.

Revision ID: b8d4e0f2c315
Revises: a7c3d9e1b204
Create Date: 2026-10-11 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d4e0f2c315'
down_revision: Union[str, Sequence[str], None] = 'a7c3d9e1b204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('messaging_settings',
    sa.Column('provider', sa.String(length=30), nullable=False),
    sa.Column('account_sid', sa.String(length=60), nullable=True),
    sa.Column('auth_token_encrypted', sa.Text(), nullable=True),
    sa.Column('from_number', sa.String(length=30), nullable=True),
    sa.Column('public_url', sa.String(length=200), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('id = 1', name=op.f('ck_messaging_settings_single_row')),
    sa.CheckConstraint("provider IN ('twilio_whatsapp')", name=op.f('ck_messaging_settings_provider_valid')),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name=op.f('fk_messaging_settings_updated_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_messaging_settings'))
    )
    op.add_column('buyer_notices', sa.Column('whatsapp_status', sa.String(length=12), server_default='not_sent', nullable=False))
    op.add_column('buyer_notices', sa.Column('whatsapp_detail', sa.String(length=300), nullable=True))
    op.add_column('buyer_notices', sa.Column('whatsapp_sid', sa.String(length=60), nullable=True))
    op.create_check_constraint(op.f('ck_buyer_notices_whatsapp_status_valid'), 'buyer_notices',
                               "whatsapp_status IN ('not_sent','sent','failed','skipped')")


def downgrade() -> None:
    op.drop_constraint(op.f('ck_buyer_notices_whatsapp_status_valid'), 'buyer_notices', type_='check')
    op.drop_column('buyer_notices', 'whatsapp_sid')
    op.drop_column('buyer_notices', 'whatsapp_detail')
    op.drop_column('buyer_notices', 'whatsapp_status')
    op.drop_table('messaging_settings')
