"""B6: a busy month is costed in reasonable time. The budget is generous on purpose: it guards against an accidental
slow-down, and the real figure (run with -s) is recorded in the plan's Status section."""
import datetime as dt
import time

from app.db.models import Attendance
from tests.costing_world import at
from tests.factories import make_machine, make_order, make_run, make_shift, make_user, make_worker

BUDGET_SECONDS = 15


def test_a_busy_month_of_900_runs_is_costed_within_the_budget(client, login_as, db):
    marker = make_user(db, role="supervisor")
    shifts = [make_shift(db, name=name, start_time=dt.time(hour), end_time=dt.time((hour + 8) % 24))
              for name, hour in (("A", 6), ("B", 14), ("C", 22))]
    workers = [make_worker(db) for _ in range(12)]
    stages = ["spinning"] * 2 + ["weaving"] * 6 + ["dyeing"] * 2
    machines = [make_machine(db, stage=stage, created_at=at(1, 0)) for stage in stages]
    order = make_order(db)
    seed = make_run(db, order, machines[0], workers[0], started_at=at(1, 0), ended_at=at(1, 1))
    for day in range(1, 31):
        for number, (shift, hour) in enumerate(zip(shifts, (6, 14, 22))):
            for worker in workers:
                db.add(Attendance(worker_id=worker.id, work_date=dt.date(2026, 9, day), shift_id=shift.id,
                                  status="present", marked_by=marker.id))
            for index, machine in enumerate(machines):
                start = at(day, hour)
                extra = {"input_run_id": seed.id} if machine.stage == "weaving" else {}
                make_run(db, order, machine, workers[(index + number + day) % 12],
                         started_at=start, ended_at=start + dt.timedelta(hours=8), **extra)
    login_as("owner")
    began = time.perf_counter()
    response = client.get("/api/reports/month?month=2026-09")
    seconds = time.perf_counter() - began
    print(f"\nmonth report for 901 runs and 1,080 attendance records: {seconds:.2f} s")
    assert response.status_code == 200 and seconds < BUDGET_SECONDS
    assert response.json()["profit"]["wages_earned"] == 12 * 3 * 30 * 800          # everyone present on every shift
