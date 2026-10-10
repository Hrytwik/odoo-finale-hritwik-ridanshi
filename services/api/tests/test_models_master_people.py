import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Attendance, User
from tests.factories import make_buyer, make_shift, make_supplier, make_user, make_worker


def test_supplier_name_cannot_be_blank(db):
    with pytest.raises(IntegrityError):
        make_supplier(db, name="   ")


def test_supplier_lead_time_cannot_be_negative(db):
    with pytest.raises(IntegrityError):
        make_supplier(db, lead_time_days=-1)


def test_buyer_user_must_have_buyer(db):
    with pytest.raises(IntegrityError):
        db.add(User(username="b1", password_hash="x", role="buyer"))
        db.flush()


def test_staff_user_must_not_have_buyer(db):
    buyer = make_buyer(db)
    with pytest.raises(IntegrityError):
        db.add(User(username="s1", password_hash="x", role="owner", buyer_id=buyer.id))
        db.flush()


def test_qc_user_needs_worker(db):
    with pytest.raises(IntegrityError):
        db.add(User(username="q1", password_hash="x", role="qc"))
        db.flush()


def test_attendance_is_unique_per_worker_date_shift(db):
    worker, shift, marker = make_worker(db), make_shift(db), make_user(db)
    day = dt.date(2026, 10, 1)
    db.add(Attendance(worker_id=worker.id, work_date=day, shift_id=shift.id, status="present", marked_by=marker.id))
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(Attendance(worker_id=worker.id, work_date=day, shift_id=shift.id, status="absent", marked_by=marker.id))
        db.flush()


def test_valid_rows_insert(db):
    assert make_supplier(db).id
    assert make_user(db, role="buyer").buyer_id
    assert make_user(db, role="qc").worker_id
