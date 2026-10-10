"""stock views

Revision ID: 4958ba00e7a2
Revises: 2ee7b7a714bf
Create Date: 2026-10-10 14:36:34.902395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4958ba00e7a2'
down_revision: Union[str, Sequence[str], None] = '2ee7b7a714bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
CREATE VIEW v_lot_stock AS
SELECT yarn_lot_id, COALESCE(SUM(qty_kg), 0)::numeric(12,3) AS on_hand_kg
FROM yarn_movements GROUP BY yarn_lot_id""")
    op.execute("""
CREATE VIEW v_order_yarn_need AS
WITH recipe AS (
  SELECT o.id AS order_id, o.state, frl.yarn_type_id,
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
  ON issued.order_id = recipe.order_id AND issued.yarn_type_id = recipe.yarn_type_id""")
    op.execute("""
CREATE VIEW v_yarn_type_stock AS
SELECT yt.id AS yarn_type_id, yt.reorder_level_kg,
       COALESCE(oh.on_hand_kg, 0) AS on_hand_kg,
       COALESCE(os.outstanding_kg, 0) AS outstanding_kg,
       COALESCE(oh.on_hand_kg, 0) - COALESCE(os.outstanding_kg, 0) AS free_kg,
       (COALESCE(oh.on_hand_kg, 0) - COALESCE(os.outstanding_kg, 0)) < yt.reorder_level_kg AS below_reorder
FROM yarn_types yt
LEFT JOIN (SELECT l.yarn_type_id, SUM(s.on_hand_kg) AS on_hand_kg
           FROM yarn_lots l JOIN v_lot_stock s ON s.yarn_lot_id = l.id
           WHERE NOT l.is_blocked GROUP BY l.yarn_type_id) oh ON oh.yarn_type_id = yt.id
LEFT JOIN (SELECT yarn_type_id, SUM(outstanding_kg) AS outstanding_kg
           FROM v_order_yarn_need WHERE state = 'confirmed' GROUP BY yarn_type_id) os ON os.yarn_type_id = yt.id""")


def downgrade() -> None:
    op.execute("DROP VIEW v_yarn_type_stock")
    op.execute("DROP VIEW v_order_yarn_need")
    op.execute("DROP VIEW v_lot_stock")
