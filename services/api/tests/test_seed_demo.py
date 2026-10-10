"""B9a Task 2: the mid-day demo mill, built through the real services. Every number is in docs/plans/B9a-seed-and-demo-mill.md."""
import datetime as dt

import pytest
from sqlalchemy import func, select

from app.core.clock import today_ist
from app.db.models import Order, ProductionRun, Roll, YarnLot
from scripts import seed_demo, seed_dev


@pytest.fixture(autouse=True)
def fast_password_hash(monkeypatch):
    """bcrypt is slow on purpose; these tests never log in with a seeded password."""
    monkeypatch.setattr(seed_dev, "hash_password", lambda password: "not-a-real-hash")


@pytest.fixture
def mill(db, login_as):
    summary = seed_demo.build_demo(db)          # starts from an empty database: it seeds the starter facts itself
    login_as("owner")
    return summary


def get(client, path):
    r = client.get(path)
    assert r.status_code == 200, (path, r.text)
    return r.json()


def machine(client, code):
    return next(m for m in get(client, "/api/floor")["machines"] if m["code"] == code)


def stock_row(client, code):
    return next(r for r in get(client, "/api/stock") if r["yarn_type"]["code"] == code)


def test_the_board_shows_three_running_one_down_six_idle(client, mill):
    board = get(client, "/api/floor")
    assert (board["running"], board["down"], board["idle"]) == (3, 1, 6) and len(board["machines"]) == 10
    status = {m["code"]: m["status"] for m in board["machines"]}
    assert {c for c, s in status.items() if s == "running"} == {"SPIN-02", "LOOM-04", "DYE-01"}
    assert {c for c, s in status.items() if s == "down"} == {"LOOM-06"}
    broken = machine(client, "LOOM-06")
    assert broken["downtime"]["reason"] == "belt snapped" and broken["current_run"] is None


def test_the_stock_numbers(client, mill):
    cotton, blend = stock_row(client, "30S-COT-RAW"), stock_row(client, "40S-PC-RAW")
    assert (cotton["on_hand_kg"], cotton["outstanding_kg"], cotton["free_kg"]) == (212.5, 42.5, 170.0)
    assert cotton["below_reorder"] is True                                       # 170 < 300: a low yarn type
    assert (blend["on_hand_kg"], blend["outstanding_kg"], blend["free_kg"]) == (1150.0, 199.2, 950.8)
    assert blend["below_reorder"] is False


def test_order_a_is_in_dyeing_with_the_worked_progress(client, mill):
    a = get(client, f"/api/orders/{mill['order_a']}")
    assert (a["state"], a["stage"], a["colour"], a["qty_metres"]) == ("confirmed", "dyeing", "navy", 5000.0)
    p = a["progress"]
    assert (p["need_kg"], p["spun_kg"], p["woven_m"], p["dyed_m"], p["passed_m"]) == (630.0, 590.0, 2310.0, 0.0, 0.0)
    assert a["yarn_status"] == "can_start" and a["short_kg"] == 0.0
    assert a["deadline"] == str(today_ist() + dt.timedelta(days=10))


def test_order_b_is_spinning_and_order_c_is_a_draft_that_is_short_230(client, mill):
    b = get(client, f"/api/orders/{mill['order_b']}")
    assert (b["stage"], b["progress"]["need_kg"]) == ("spinning", 499.2)
    c = get(client, f"/api/orders/{mill['order_c']}")
    assert (c["state"], c["stage"], c["yarn_status"], c["short_kg"]) == ("draft", "draft", "short", 230.0)
    check = get(client, f"/api/orders/{mill['order_c']}/yarn-check")
    [line] = check["lines"]
    assert (line["need_kg"], line["available_kg"], line["short_kg"]) == (400.0, 170.0, 230.0) and check["can_start"] is False


def test_the_rolls_and_the_machines_that_made_them(client, mill):
    rolls = get(client, f"/api/rolls?order_code={mill['order_a']}")
    assert sorted(r["metres"] for r in rolls) == [510.0, 800.0, 1000.0]
    by_metres = {r["metres"]: r["status"] for r in rolls}
    assert by_metres == {1000.0: "dyeing", 800.0: "dyeing", 510.0: "woven"}
    loom = machine(client, "LOOM-04")
    assert loom["status"] == "running" and loom["output_today"] == 2310.0 and loom["output_unit"] == "m"
    assert loom["current_run"]["order_code"] == mill["order_a"] and loom["current_run"]["order_progress_pct"] == 46.2
    assert loom["current_run"]["operator"]["name"] == "Suresh Patil"
    spinner = machine(client, "SPIN-01")
    assert spinner["status"] == "idle" and spinner["output_today"] == 590.0 and spinner["output_unit"] == "kg"
    assert machine(client, "DYE-01")["status"] == "running"


def test_the_lots(client, mill):
    lots = {l["challan_no"]: l for l in get(client, "/api/lots")}
    assert set(lots) == {"CH-5521", "CH-5530"}
    assert (lots["CH-5521"]["qty_received_kg"], lots["CH-5521"]["on_hand_kg"], lots["CH-5521"]["cost_per_kg"]) == (800.0, 212.5, 250.0)
    assert (lots["CH-5530"]["qty_received_kg"], lots["CH-5530"]["on_hand_kg"]) == (1450.0, 1150.0)


def test_a_second_run_is_refused_and_changes_nothing(db, mill):
    before = (db.scalar(select(func.count()).select_from(Order)), db.scalar(select(func.count()).select_from(YarnLot)))
    with pytest.raises(seed_demo.DemoRefused) as err:
        seed_demo.build_demo(db)
    assert "already" in str(err.value) and "empty database" in str(err.value)
    after = (db.scalar(select(func.count()).select_from(Order)), db.scalar(select(func.count()).select_from(YarnLot)))
    assert before == after


def test_it_works_on_a_database_that_is_already_seeded(db, login_as, client):
    seed_dev.seed_all(db)
    summary = seed_demo.build_demo(db)
    login_as("owner")
    assert get(client, f"/api/orders/{summary['order_a']}")["stage"] == "dyeing"
    assert db.scalar(select(func.count()).select_from(Roll)) == 3
    assert db.scalar(select(func.count()).select_from(ProductionRun).where(ProductionRun.ended_at.is_(None))) == 3
