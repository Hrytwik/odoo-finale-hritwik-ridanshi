"""machine status view

Revision ID: 70a0b5bd9a55
Revises: b0eaa59f8a3b
Create Date: 2026-10-10 17:13:30.574861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70a0b5bd9a55'
down_revision: Union[str, Sequence[str], None] = 'b0eaa59f8a3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
CREATE VIEW v_machine_status AS
SELECT m.id AS machine_id,
  CASE
    WHEN EXISTS (SELECT 1 FROM machine_downtimes dt WHERE dt.machine_id = m.id AND dt.ended_at IS NULL) THEN 'down'
    WHEN EXISTS (SELECT 1 FROM production_runs pr WHERE pr.machine_id = m.id AND pr.ended_at IS NULL) THEN 'running'
    ELSE 'idle'
  END AS status
FROM machines m WHERE m.active""")


def downgrade() -> None:
    op.execute("DROP VIEW v_machine_status")
