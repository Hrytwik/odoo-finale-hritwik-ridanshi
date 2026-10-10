import datetime as dt

import pytest

from tests.factories import make_shift, make_worker

SEPT = "2026-09"


def mark(client, shift, date, entries):
    return client.post("/api/attendance", json={
        "date": str(date), "shift_id": shift.id,
        "entries": [{"worker_id": w.id, "status": s} for w, s in entries]})


def wage_of(client, worker, month=SEPT):
    rows = client.get(f"/api/wages?month={month}").json()["rows"]
    return next(r for r in rows if r["worker_id"] == worker.id)


# ---------- attendance sheet ----------

def test_sheet_lists_active_workers_with_no_status_yet(client, login_as, db):
    login_as("supervisor")
    shift = make_shift(db)
    a, b = make_worker(db, name="Asha"), make_worker(db, name="Bhanu")
    make_worker(db, name="Retired", active=False)
    r = client.get(f"/api/attendance?date=2026-09-01&shift_id={shift.id}")
    assert r.status_code == 200
    rows = {x["worker_name"]: x for x in r.json()["rows"]}
    assert set(rows) >= {"Asha", "Bhanu"} and "Retired" not in rows
    assert rows["Asha"]["status"] is None and rows["Asha"]["worker_id"] == a.id and rows["Bhanu"]["worker_id"] == b.id
    assert r.json()["shift"] == {"id": shift.id, "name": shift.name}


def test_sheet_for_an_unknown_shift_is_404(client, login_as):
    login_as("supervisor")
    r = client.get("/api/attendance?date=2026-09-01&shift_id=999999")
    assert r.status_code == 404 and r.json()["field"] == "shift_id"


def test_marked_workers_show_their_status(client, login_as, db):
    login_as("supervisor")
    shift, w = make_shift(db), make_worker(db)
    assert mark(client, shift, "2026-09-01", [(w, "half_day")]).status_code == 200
    row = next(x for x in client.get(f"/api/attendance?date=2026-09-01&shift_id={shift.id}").json()["rows"]
               if x["worker_id"] == w.id)
    assert row["status"] == "half_day"


def test_an_inactive_worker_with_a_mark_still_shows_on_that_sheet(client, login_as, db):
    login_as("supervisor")
    shift, w = make_shift(db), make_worker(db, active=False)
    mark(client, shift, "2026-09-01", [(w, "present")])
    ids = [x["worker_id"] for x in client.get(f"/api/attendance?date=2026-09-01&shift_id={shift.id}").json()["rows"]]
    assert w.id in ids


# ---------- marking ----------

def test_marking_saves_each_worker(client, login_as, db):
    login_as("supervisor")
    shift, a, b = make_shift(db), make_worker(db), make_worker(db)
    r = mark(client, shift, "2026-09-01", [(a, "present"), (b, "absent")])
    assert r.status_code == 200
    statuses = {x["worker_id"]: x["status"] for x in r.json()["rows"]}
    assert statuses[a.id] == "present" and statuses[b.id] == "absent"


def test_marking_again_corrects_the_earlier_mark_instead_of_adding_another(client, login_as, db):
    login_as("supervisor")
    shift, w = make_shift(db), make_worker(db, daily_wage=1000)
    mark(client, shift, "2026-09-01", [(w, "absent")])
    mark(client, shift, "2026-09-01", [(w, "present")])
    login_as("accountant")
    after = wage_of(client, w)
    assert after["present"] == 1 and after["absent"] == 0 and after["earned"] == 1000


def test_the_same_worker_can_be_marked_in_two_shifts_on_one_day(client, login_as, db):
    login_as("supervisor")
    morning, night, w = make_shift(db), make_shift(db), make_worker(db, daily_wage=800)
    assert mark(client, morning, "2026-09-01", [(w, "present")]).status_code == 200
    assert mark(client, night, "2026-09-01", [(w, "present")]).status_code == 200
    login_as("accountant")
    assert wage_of(client, w)["present"] == 2


def test_a_future_date_is_refused(client, login_as, db):
    login_as("supervisor")
    shift, w = make_shift(db), make_worker(db)
    r = mark(client, shift, dt.date.today() + dt.timedelta(days=1), [(w, "present")])
    assert r.status_code == 422 and r.json()["code"] == "FUTURE_DATE" and r.json()["field"] == "date"


def test_today_is_allowed(client, login_as, db):
    login_as("supervisor")
    shift, w = make_shift(db), make_worker(db)
    assert mark(client, shift, dt.date.today(), [(w, "present")]).status_code == 200


def test_an_unknown_worker_is_404_and_nothing_is_saved(client, login_as, db):
    login_as("supervisor")
    shift, w = make_shift(db), make_worker(db)
    r = client.post("/api/attendance", json={"date": "2026-09-01", "shift_id": shift.id, "entries": [
        {"worker_id": w.id, "status": "present"}, {"worker_id": 999999, "status": "present"}]})
    assert r.status_code == 404
    row = next(x for x in client.get(f"/api/attendance?date=2026-09-01&shift_id={shift.id}").json()["rows"]
               if x["worker_id"] == w.id)
    assert row["status"] is None


def test_an_unknown_shift_is_404(client, login_as, db):
    login_as("supervisor")
    w = make_worker(db)
    r = client.post("/api/attendance", json={"date": "2026-09-01", "shift_id": 999999,
                                            "entries": [{"worker_id": w.id, "status": "present"}]})
    assert r.status_code == 404 and r.json()["field"] == "shift_id"


@pytest.mark.parametrize("body", [
    {"entries": []},
    {"entries": [{"worker_id": 1, "status": "late"}]},
    {"entries": [{"worker_id": 1, "status": "present"}, {"worker_id": 1, "status": "absent"}]},
])
def test_bad_entries_are_422(client, login_as, db, body):
    login_as("supervisor")
    shift = make_shift(db)
    r = client.post("/api/attendance", json={"date": "2026-09-01", "shift_id": shift.id, **body})
    assert r.status_code == 422


def test_who_marked_it_is_recorded(client, login_as, db):
    from sqlalchemy import select

    from app.db.models import Attendance
    user = login_as("supervisor")
    shift, w = make_shift(db), make_worker(db)
    mark(client, shift, "2026-09-01", [(w, "present")])
    assert db.scalar(select(Attendance.marked_by).where(Attendance.worker_id == w.id)) == user.id


def test_marking_tells_live_screens(client, login_as, db, monkeypatch):
    seen = []
    monkeypatch.setattr("app.modules.people.router.broadcaster.publish", lambda t, i=None: seen.append(t))
    login_as("supervisor")
    shift, w = make_shift(db), make_worker(db)
    mark(client, shift, "2026-09-01", [(w, "present")])
    assert seen == ["attendance.changed"]


# ---------- who may do what ----------

def test_only_supervisor_and_owner_can_mark(client, login_as, db):
    shift, w = make_shift(db), make_worker(db)
    for role in ("accountant", "store", "qc", "dispatch", "buyer"):
        login_as(role)
        assert mark(client, shift, "2026-09-01", [(w, "present")]).status_code == 403, role
    login_as("owner")
    assert mark(client, shift, "2026-09-01", [(w, "present")]).status_code == 200


def test_accountant_can_read_the_sheet_but_a_buyer_cannot(client, login_as, db):
    shift = make_shift(db)
    login_as("accountant")
    assert client.get(f"/api/attendance?date=2026-09-01&shift_id={shift.id}").status_code == 200
    login_as("buyer")
    assert client.get(f"/api/attendance?date=2026-09-01&shift_id={shift.id}").status_code == 403


def test_not_logged_in_is_401(client):
    assert client.get("/api/attendance?date=2026-09-01&shift_id=1").status_code == 401
    assert client.get("/api/wages?month=2026-09").status_code == 401


def test_wages_and_wage_payments_are_for_accountant_and_owner_only(client, login_as, db):
    w = make_worker(db)
    body = {"worker_id": w.id, "period_start": "2026-09-01", "period_end": "2026-09-30", "amount": 100, "paid_at": "2026-10-01"}
    for role in ("supervisor", "store", "qc", "dispatch", "buyer"):
        login_as(role)
        assert client.get("/api/wages?month=2026-09").status_code == 403, role
        assert client.post("/api/payments/wages", json=body).status_code == 403, role


# ---------- wages earned ----------

def test_earned_is_the_daily_wage_for_a_full_day_half_for_a_half_day_nothing_for_absent(client, login_as, db):
    shift = make_shift(db)
    w = make_worker(db, daily_wage=800)
    login_as("supervisor")
    for day, status in [(1, "present"), (2, "present"), (3, "half_day"), (4, "absent")]:
        mark(client, shift, f"2026-09-0{day}", [(w, status)])
    login_as("accountant")
    row = wage_of(client, w)
    assert (row["present"], row["half_days"], row["absent"]) == (2, 1, 1)
    assert row["earned"] == 2000 and row["paid"] == 0 and row["owed"] == 2000
    assert row["daily_wage"] == 800 and row["worker_code"] == w.code


def test_only_the_asked_month_counts(client, login_as, db):
    shift = make_shift(db)
    w = make_worker(db, daily_wage=500)
    login_as("supervisor")
    mark(client, shift, "2026-08-31", [(w, "present")])
    mark(client, shift, "2026-09-01", [(w, "present")])
    mark(client, shift, "2026-09-30", [(w, "present")])
    mark(client, shift, "2026-10-01", [(w, "present")])
    login_as("accountant")
    assert wage_of(client, w, "2026-09")["earned"] == 1000
    assert wage_of(client, w, "2026-08")["earned"] == 500
    assert wage_of(client, w, "2026-10")["earned"] == 500


def test_a_worker_on_the_payroll_with_no_attendance_shows_with_zero(client, login_as, db):
    w = make_worker(db)
    login_as("accountant")
    row = wage_of(client, w)
    assert row["earned"] == 0 and row["owed"] == 0


def test_an_inactive_worker_shows_only_in_months_with_activity(client, login_as, db):
    shift = make_shift(db)
    w = make_worker(db, active=False, daily_wage=400)
    login_as("supervisor")
    mark(client, shift, "2026-09-01", [(w, "present")])
    login_as("accountant")
    assert wage_of(client, w)["earned"] == 400
    ids_in_july = [r["worker_id"] for r in client.get("/api/wages?month=2026-07").json()["rows"]]
    assert w.id not in ids_in_july


def test_totals_add_up_the_rows(client, login_as, db):
    shift = make_shift(db)
    a, b = make_worker(db, daily_wage=700), make_worker(db, daily_wage=900)
    login_as("supervisor")
    mark(client, shift, "2026-09-01", [(a, "present"), (b, "half_day")])
    login_as("accountant")
    sheet = client.get(f"/api/wages?month={SEPT}").json()
    assert sheet["total_earned"] == pytest.approx(sum(r["earned"] for r in sheet["rows"]))
    assert sheet["total_owed"] == pytest.approx(sheet["total_earned"] - sheet["total_paid"])
    assert wage_of(client, b)["earned"] == 450


@pytest.mark.parametrize("month", ["2026-13", "2026-00", "26-09", "september", "2026-9"])
def test_a_bad_month_is_422(client, login_as, month):
    login_as("accountant")
    assert client.get(f"/api/wages?month={month}").status_code == 422


# ---------- paying wages ----------

def pay(client, worker, amount, start="2026-09-01", end="2026-09-30", paid_at="2026-10-01"):
    return client.post("/api/payments/wages", json={
        "worker_id": worker.id, "period_start": start, "period_end": end, "amount": amount, "paid_at": paid_at})


def worker_with_days(client, login_as, db, days=3, wage=1000):
    shift, w = make_shift(db), make_worker(db, daily_wage=wage)
    login_as("supervisor")
    for d in range(1, days + 1):
        mark(client, shift, f"2026-09-0{d}", [(w, "present")])
    login_as("accountant")
    return w


def test_a_payment_reduces_what_is_owed(client, login_as, db):
    w = worker_with_days(client, login_as, db)  # earned 3000
    r = pay(client, w, 1200)
    assert r.status_code == 201
    assert (r.json()["earned"], r.json()["paid"], r.json()["owed"]) == (3000, 1200, 1800)
    row = wage_of(client, w)
    assert row["paid"] == 1200 and row["owed"] == 1800


def test_paying_exactly_what_is_owed_is_allowed_then_nothing_more(client, login_as, db):
    w = worker_with_days(client, login_as, db)
    assert pay(client, w, 3000).status_code == 201
    again = pay(client, w, 1)
    assert again.status_code == 409 and again.json()["code"] == "OVERPAYMENT" and again.json()["field"] == "amount"


def test_paying_more_than_owed_is_refused_and_says_how_much_is_owed(client, login_as, db):
    w = worker_with_days(client, login_as, db)
    r = pay(client, w, 3000.01)
    assert r.status_code == 409 and r.json()["code"] == "OVERPAYMENT"
    assert "3,000.00" in r.json()["message"]
    assert wage_of(client, w)["paid"] == 0


def test_two_part_payments_cannot_together_exceed_the_wage(client, login_as, db):
    w = worker_with_days(client, login_as, db)
    assert pay(client, w, 2000).status_code == 201
    assert pay(client, w, 1500).status_code == 409
    assert pay(client, w, 1000).status_code == 201


def test_a_payment_for_part_of_the_month_counts_against_the_month(client, login_as, db):
    w = worker_with_days(client, login_as, db)
    assert pay(client, w, 2000, start="2026-09-01", end="2026-09-15").status_code == 201
    assert wage_of(client, w)["owed"] == 1000


def test_the_period_limits_what_can_be_paid(client, login_as, db):
    w = worker_with_days(client, login_as, db)  # days 1 to 3
    # nothing was earned on the 20th to the 30th
    assert pay(client, w, 100, start="2026-09-20", end="2026-09-30").status_code == 409
    assert pay(client, w, 1000, start="2026-09-01", end="2026-09-01").status_code == 201
    assert pay(client, w, 1, start="2026-09-01", end="2026-09-01").status_code == 409


def test_a_payment_with_nothing_earned_is_refused(client, login_as, db):
    w = make_worker(db)
    login_as("accountant")
    assert pay(client, w, 10).status_code == 409


def test_a_future_payment_date_is_refused(client, login_as, db):
    w = worker_with_days(client, login_as, db)
    tomorrow = str(dt.date.today() + dt.timedelta(days=1))
    r = pay(client, w, 100, paid_at=tomorrow)
    assert r.status_code == 422 and r.json()["code"] == "FUTURE_DATE" and r.json()["field"] == "paid_at"


def test_an_unknown_worker_is_404(client, login_as):
    login_as("accountant")
    r = client.post("/api/payments/wages", json={"worker_id": 999999, "period_start": "2026-09-01",
                                                "period_end": "2026-09-30", "amount": 10, "paid_at": "2026-10-01"})
    assert r.status_code == 404 and r.json()["field"] == "worker_id"


@pytest.mark.parametrize("patch", [
    {"amount": 0}, {"amount": -5}, {"amount": 100_000_001},
    {"period_start": "2026-09-30", "period_end": "2026-09-01"},
])
def test_bad_payment_values_are_422(client, login_as, db, patch):
    w = worker_with_days(client, login_as, db)
    body = {"worker_id": w.id, "period_start": "2026-09-01", "period_end": "2026-09-30", "amount": 100,
            "paid_at": "2026-10-01", **patch}
    assert client.post("/api/payments/wages", json=body).status_code == 422


def test_paying_wages_tells_live_screens(client, login_as, db, monkeypatch):
    w = worker_with_days(client, login_as, db)
    seen = []
    monkeypatch.setattr("app.modules.people.router.broadcaster.publish", lambda t, i=None: seen.append(t))
    pay(client, w, 100)
    assert seen == ["payment.changed"]


def test_rupees_and_paise_are_kept_exactly(client, login_as, db):
    shift, w = make_shift(db), make_worker(db, daily_wage=333.33)
    login_as("supervisor")
    for d in (1, 2, 3):
        mark(client, shift, f"2026-09-0{d}", [(w, "present")])
    login_as("accountant")
    assert wage_of(client, w)["earned"] == 999.99
    assert pay(client, w, 999.99).status_code == 201
    assert wage_of(client, w)["owed"] == 0
