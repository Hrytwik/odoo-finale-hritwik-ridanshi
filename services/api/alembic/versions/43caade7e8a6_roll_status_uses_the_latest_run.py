"""roll status uses the latest run

Revision ID: 43caade7e8a6
Revises: 70a0b5bd9a55
Create Date: 2026-10-10 18:49:49.152233

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43caade7e8a6'
down_revision: Union[str, Sequence[str], None] = '70a0b5bd9a55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LATEST_DYE = """
CREATE VIEW v_roll_latest_dye AS
SELECT DISTINCT ON (rr.roll_id) rr.roll_id, pr.id AS run_id, pr.machine_id, pr.started_at, pr.ended_at
FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
WHERE rr.purpose = 'dye'
ORDER BY rr.roll_id, pr.started_at DESC, pr.id DESC"""

STATUS_USES_LATEST_RUN = """
CREATE OR REPLACE VIEW v_roll_status AS
SELECT r.id AS roll_id,
  CASE
    WHEN d.state = 'dispatched' THEN 'dispatched'
    WHEN d.state = 'loading' THEN 'loading'
    WHEN li.verdict = 'reject' THEN 'rejected'
    WHEN li.verdict = 'pass' THEN 'in_store'
    WHEN li.verdict = 'rework' THEN
      CASE
        WHEN rw.run_id IS NULL THEN 'awaiting_rework'
        WHEN rw.ended_at IS NULL THEN 'in_rework'
        ELSE 'awaiting_qc'
      END
    WHEN dy.run_id IS NULL THEN 'woven'
    WHEN dy.ended_at IS NULL THEN 'dyeing'
    ELSE 'awaiting_qc'
  END AS status
FROM rolls r
LEFT JOIN dispatch_items di ON di.roll_id = r.id
LEFT JOIN dispatches d ON d.id = di.dispatch_id
LEFT JOIN LATERAL (SELECT q.verdict, q.inspected_at FROM qc_inspections q WHERE q.roll_id = r.id
                   ORDER BY q.inspected_at DESC, q.id DESC LIMIT 1) li ON true
LEFT JOIN v_roll_latest_dye dy ON dy.roll_id = r.id
LEFT JOIN LATERAL (SELECT pr.id AS run_id, pr.ended_at FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                   WHERE rr.roll_id = r.id AND rr.purpose = 'rework' AND pr.started_at >= li.inspected_at
                   ORDER BY pr.started_at DESC, pr.id DESC LIMIT 1) rw ON true"""

# the definition from the previous revision (B3), restored on downgrade
STATUS_B3 = """
CREATE OR REPLACE VIEW v_roll_status AS
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
                   ORDER BY q.inspected_at DESC, q.id DESC LIMIT 1) li ON true"""


def upgrade() -> None:
    op.execute(LATEST_DYE)
    op.execute(STATUS_USES_LATEST_RUN)


def downgrade() -> None:
    op.execute(STATUS_B3)
    op.execute("DROP VIEW v_roll_latest_dye")
