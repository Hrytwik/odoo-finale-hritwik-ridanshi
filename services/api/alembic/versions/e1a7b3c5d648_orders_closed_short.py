"""orders can be closed short

The owner ends an order that will never reach its ordered metres. Three nullable columns on orders (when, who, why), kept
all-or-none by the database, and the yarn-need view reports such an order's state as 'closed_short' so every existing
`state = 'confirmed'` filter on it (yarn reserved, shortage forecast, other orders' yarn check) stops counting it.

Revision ID: e1a7b3c5d648
Revises: d0f6a2b4e537
Create Date: 2026-10-11 07:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e1a7b3c5d648'
down_revision: Union[str, Sequence[str], None] = 'd0f6a2b4e537'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VIEW = """
CREATE OR REPLACE VIEW v_order_yarn_need AS
WITH recipe AS (
  SELECT o.id AS order_id, {state} AS state, frl.yarn_type_id,
         ROUND(o.qty_metres * frl.kg_per_metre * (1 + ft.wastage_pct / 100), 3) AS need_kg
  FROM orders o
  JOIN fabric_types ft ON ft.id = o.fabric_type_id
  JOIN fabric_recipe_lines frl ON frl.fabric_type_id = ft.id
), issued AS (
  SELECT r.order_id, l.yarn_type_id, -SUM(m.qty_kg) AS issued_kg
  FROM yarn_movements m
  JOIN production_runs r ON r.id = m.production_run_id
  JOIN yarn_lots l ON l.id = m.yarn_lot_id
  WHERE m.kind IN ('issue', 'return')
  GROUP BY r.order_id, l.yarn_type_id
)
SELECT recipe.order_id, recipe.state, recipe.yarn_type_id, recipe.need_kg,
       COALESCE(issued.issued_kg, 0) AS issued_kg,
       GREATEST(0, recipe.need_kg - COALESCE(issued.issued_kg, 0)) AS outstanding_kg
FROM recipe LEFT JOIN issued
  ON issued.order_id = recipe.order_id AND issued.yarn_type_id = recipe.yarn_type_id"""


def upgrade() -> None:
    op.add_column('orders', sa.Column('closed_short_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('closed_short_by', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('closed_short_reason', sa.String(length=200), nullable=True))
    op.create_foreign_key(op.f('fk_orders_closed_short_by_users'), 'orders', 'users', ['closed_short_by'], ['id'])
    op.create_check_constraint(
        op.f('ck_orders_closed_short_all_or_none'), 'orders',
        "(closed_short_at IS NULL) = (closed_short_by IS NULL) AND (closed_short_at IS NULL) = (closed_short_reason IS NULL)")
    op.create_check_constraint(op.f('ck_orders_closed_short_is_confirmed'), 'orders',
                               "closed_short_at IS NULL OR state = 'confirmed'")
    op.execute(_VIEW.format(state="(CASE WHEN o.closed_short_at IS NOT NULL THEN 'closed_short' ELSE o.state END)::varchar(12)"))


def downgrade() -> None:
    op.execute(_VIEW.format(state="o.state"))
    op.drop_constraint(op.f('ck_orders_closed_short_is_confirmed'), 'orders', type_='check')
    op.drop_constraint(op.f('ck_orders_closed_short_all_or_none'), 'orders', type_='check')
    op.drop_constraint(op.f('fk_orders_closed_short_by_users'), 'orders', type_='foreignkey')
    op.drop_column('orders', 'closed_short_reason')
    op.drop_column('orders', 'closed_short_by')
    op.drop_column('orders', 'closed_short_at')
