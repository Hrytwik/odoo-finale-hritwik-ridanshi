import re
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy.orm import Session

from app.core.codes import next_code


def test_codes_have_the_expected_shape_and_are_unique(db):
    a, b = next_code(db, "lot"), next_code(db, "lot")
    assert re.fullmatch(r"L-\d{4,}", a) and re.fullmatch(r"L-\d{4,}", b) and a != b
    assert re.fullmatch(r"ORD-\d{4,}", next_code(db, "order"))


def test_unknown_kind_is_refused(db):
    with pytest.raises(ValueError):
        next_code(db, "invoice")  # type: ignore[arg-type]


def test_simultaneous_callers_never_get_the_same_number(engine):
    def grab(_):
        with Session(engine) as s:
            return [next_code(s, "order") for _ in range(20)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = [c for batch in pool.map(grab, range(2)) for c in batch]
    assert len(codes) == 40 and len(set(codes)) == 40
