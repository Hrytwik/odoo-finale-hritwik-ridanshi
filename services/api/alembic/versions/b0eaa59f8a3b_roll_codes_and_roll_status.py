"""roll codes and roll status

Revision ID: b0eaa59f8a3b
Revises: 4958ba00e7a2
Create Date: 2026-10-10 17:11:11.490604

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0eaa59f8a3b'
down_revision: Union[str, Sequence[str], None] = '4958ba00e7a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE roll_code_seq")
    op.execute("""
CREATE VIEW v_roll_status AS
SELECT r.id AS roll_id,
  CASE
    WHEN d.state = 'dispatched' THEN 'dispatched'
    WHEN d.state = 'loading' THEN 'loading'
    WHEN li.verdict = 'reject' THEN 'rejected'
    WHEN li.verdict = 'pass' THEN 'in_store'
    WHEN li.verdict = 'rework' THEN
      CASE
        WHEN EXISTS (SELECT 1 FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                     WHERE rr.roll_id = r.id AND rr.purpose = 'rework'
                       AND pr.started_at >= li.inspected_at AND pr.ended_at IS NOT NULL) THEN 'awaiting_qc'
        WHEN EXISTS (SELECT 1 FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                     WHERE rr.roll_id = r.id AND rr.purpose = 'rework'
                       AND pr.started_at >= li.inspected_at AND pr.ended_at IS NULL) THEN 'in_rework'
        ELSE 'awaiting_rework'
      END
    WHEN EXISTS (SELECT 1 FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                 WHERE rr.roll_id = r.id AND rr.purpose = 'dye' AND pr.ended_at IS NOT NULL) THEN 'awaiting_qc'
    WHEN EXISTS (SELECT 1 FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                 WHERE rr.roll_id = r.id AND rr.purpose = 'dye' AND pr.ended_at IS NULL) THEN 'dyeing'
    ELSE 'woven'
  END AS status
FROM rolls r
LEFT JOIN dispatch_items di ON di.roll_id = r.id
LEFT JOIN dispatches d ON d.id = di.dispatch_id
LEFT JOIN LATERAL (SELECT q.verdict, q.inspected_at FROM qc_inspections q WHERE q.roll_id = r.id
                   ORDER BY q.inspected_at DESC, q.id DESC LIMIT 1) li ON true""")


def downgrade() -> None:
    op.execute("DROP VIEW v_roll_status")
    op.execute("DROP SEQUENCE roll_code_seq")
