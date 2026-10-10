"""B7: a busy mill (200 open orders, each with finished runs, rolls and inspections) is scheduled in reasonable time.
The budget is generous on purpose: it guards against an accidental slow-down, and the real figures (run with -s) are
recorded in docs/plans/B7-intelligence.md."""
import datetime as dt
import time

from app.db.models import QcDefect
from tests.factories import dye, make_inspection, make_order, make_roll, make_run, make_worker
from tests.insights_world import LONG_AGO, build_mill

BUDGET_SECONDS = 20
ORDERS = 200


def test_a_busy_mill_of_200_open_orders_is_scheduled_within_the_budget(client, login_as, db):
    mill = build_mill(db)
    inspector = make_worker(db, role="inspector").id
    hour = dt.timedelta(hours=1)
    for i in range(ORDERS):
        order = make_order(db, buyer=mill.buyer, fabric_type=mill.fabric, qty_metres=480,
                           deadline=mill.today + dt.timedelta(days=3 + i % 40),
                           confirmed_at=dt.datetime(2026, 9, 1, tzinfo=dt.UTC) + i * hour)
        start = LONG_AGO + i * hour
        spin = make_run(db, order, mill.machines["spinning"], started_at=start, ended_at=start + hour, output_kg=100)
        weave = make_run(db, order, mill.machines["weaving"], input_run_id=spin.id, started_at=start, ended_at=start + hour)
        dyed = make_run(db, order, mill.machines["dyeing"], started_at=start, ended_at=start + hour)
        for n in range(3):
            roll = make_roll(db, order, weave, 100)
            dye(db, roll, dyed)
            if n < 2:
                bad = (i + n) % 5 == 0
                inspection = make_inspection(db, roll, "rework" if bad else "pass", inspector_worker_id=inspector)
                if bad:
                    db.add(QcDefect(inspection_id=inspection.id, defect_type="hole", count=1))
    db.flush()
    login_as("owner")
    timings = {}
    for name, path in (("order list", "/api/orders"), ("late orders", "/api/insights/late-orders"),
                       ("shortages", "/api/insights/shortages"), ("root causes", "/api/insights/root-causes")):
        began = time.perf_counter()
        response = client.get(path)
        timings[name] = time.perf_counter() - began
        assert response.status_code == 200, path
    print("\n" + ", ".join(f"{name} {seconds:.2f} s" for name, seconds in timings.items()) + f" ({ORDERS} open orders)")
    assert max(timings.values()) < BUDGET_SECONDS
    assert len(client.get("/api/orders").json()) == ORDERS + 2                    # the two orders of the delivery mill as well
