from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

Kind = Literal["lot", "order", "roll", "dispatch", "invoice"]
# (sequence, prefix): fixed here, never built from user input
_SEQUENCES: dict[str, tuple[str, str]] = {
    "lot": ("lot_code_seq", "L"), "order": ("order_code_seq", "ORD"), "roll": ("roll_code_seq", "R"),
    "dispatch": ("dispatch_code_seq", "DSP"), "invoice": ("invoice_code_seq", "INV"),
}


def next_code(db: Session, kind: Kind) -> str:
    """Next human code such as L-0017. A database sequence, so two simultaneous requests can never get the same number
    (a failed request leaves a gap, which is fine)."""
    if kind not in _SEQUENCES:
        raise ValueError(f"unknown code kind: {kind!r}")
    sequence, prefix = _SEQUENCES[kind]
    number = db.execute(text(f"SELECT nextval('{sequence}')")).scalar_one()
    return f"{prefix}-{number:04d}"
