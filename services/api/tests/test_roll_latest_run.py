"""B4 Task 1: a roll's dyeing is finished when its LATEST dye run has ended. A hand-over of a dyeing run (or of a rework run
on a machine) carries the loaded rolls to the new run, so they do not look finished while the work goes on.
Hand-worked numbers: a dyeing run holds rolls of 300 m and 200 m; the order's dyed metres are 0 until the last run ends,
then 500 (counted once, not 1,000)."""
import datetime as dt

import pytest
from sqlalchemy import select

from app.db.models import ProductionRun, RollRun
from tests.factories import make_inspection, make_machine, make_order, make_roll, make_run, make_worker

T0 = dt.datetime(2026, 10, 1, 8, tzinfo=dt.UTC)


@pytest.fixture
def sup(login_as):
    return login_as("supervisor")


class Batch:
    """An order of 500 m with two woven rolls (300 m and 200 m) loaded into a running dyeing machine."""

    def __init__(self, client, db):
        self.client, self.db = client, db
        self.order = make_order(db, qty_metres=500)
        weave = make_run(db, self.order, make_machine(db, stage="weaving"))
        self.rolls = [make_roll(db, self.order, weave, 300), make_roll(db, self.order, weave, 200)]
        self.machine = make_machine(db, stage="dyeing")
        self.run = make_run(db, self.order, self.machine)
        r = client.post(f"/api/runs/{self.run.id}/load-rolls", json={"roll_codes": [x.code for x in self.rolls]})
        assert r.status_code == 200, r.text

    def statuses(self) -> set[str]:
        return {r["status"] for r in self.client.get(f"/api/rolls?order_code={self.order.code}").json()}

    def order_out(self) -> dict:
        return self.client.get(f"/api/orders/{self.order.code}").json()

    def machine_card(self) -> dict:
        return next(m for m in self.client.get("/api/floor").json()["machines"] if m["code"] == self.machine.code)

    def handover(self, run_id=None) -> dict:
        r = self.client.post(f"/api/runs/{run_id or self.run.id}/handover", json={"operator_worker_id": make_worker(self.db).id})
        assert r.status_code == 201, r.text
        return r.json()

    def end(self, run_id) -> None:
        assert self.client.post(f"/api/runs/{run_id}/end", json={}).status_code == 200


def test_handing_over_a_dyeing_run_keeps_its_rolls_dyeing(client, db, sup):
    b = Batch(client, db)
    new = b.handover()
    assert b.statuses() == {"dyeing"}
    assert sorted(new["roll_codes"]) == sorted(r.code for r in b.rolls) and new["metres"] == 500.0
    old = next(r for r in client.get(f"/api/runs?order_code={b.order.code}&stage=dyeing").json() if r["id"] == b.run.id)
    assert sorted(old["roll_codes"]) == sorted(r.code for r in b.rolls) and old["ended_at"]   # the old run keeps its history
    out = b.order_out()
    assert out["progress"]["dyed_m"] == 0.0 and out["stage"] == "dyeing"                        # not finished, not quality check


def test_when_the_new_run_ends_the_rolls_are_dyed_once_and_the_output_counts_once(client, db, sup):
    b = Batch(client, db)
    new = b.handover()
    b.end(new["id"])
    assert b.statuses() == {"awaiting_qc"}
    out = b.order_out()
    assert out["progress"]["dyed_m"] == 500.0 and out["stage"] == "quality_check"
    card = b.machine_card()
    assert card["output_today"] == 500.0 and card["output_unit"] == "m"


def test_two_hand_overs_in_a_row_still_keep_the_rolls_dyeing(client, db, sup):
    b = Batch(client, db)
    second = b.handover()
    third = b.handover(second["id"])
    assert b.statuses() == {"dyeing"} and sorted(third["roll_codes"]) == sorted(r.code for r in b.rolls)
    assert b.order_out()["progress"]["dyed_m"] == 0.0
    b.end(third["id"])
    assert b.statuses() == {"awaiting_qc"} and b.order_out()["progress"]["dyed_m"] == 500.0
    assert b.machine_card()["output_today"] == 500.0


def test_a_breakdown_after_a_hand_over_ends_the_new_run_and_sends_the_rolls_to_qc(client, db, sup):
    b = Batch(client, db)
    b.handover()
    assert client.post(f"/api/machines/{b.machine.code}/breakdown", json={"reason": "pump"}).status_code == 200
    assert b.statuses() == {"awaiting_qc"}


def test_an_ordinary_end_without_a_hand_over_is_unchanged(client, db, sup):
    b = Batch(client, db)
    assert b.statuses() == {"dyeing"} and b.order_out()["progress"]["dyed_m"] == 0.0
    b.end(b.run.id)
    assert b.statuses() == {"awaiting_qc"} and b.order_out()["progress"]["dyed_m"] == 500.0
    assert b.machine_card()["output_today"] == 500.0


def test_handing_over_a_weaving_run_leaves_its_rolls_on_the_run_that_made_them(client, db, sup):
    order, machine = make_order(db), make_machine(db, stage="weaving")
    run = make_run(db, order, machine)
    roll = make_roll(db, order, run, 100)
    new = client.post(f"/api/runs/{run.id}/handover", json={"operator_worker_id": make_worker(db).id}).json()
    assert new["roll_codes"] == [] and new["metres"] == 0.0
    assert [r.run_id for r in db.scalars(select(RollRun).where(RollRun.roll_id == roll.id))] == [run.id]


def test_handing_over_a_rework_run_on_a_machine_keeps_the_roll_in_rework(client, db, sup):
    order = make_order(db)
    roll = make_roll(db, order, make_run(db, order, make_machine(db, stage="weaving")), 100)
    make_inspection(db, roll, "rework", inspected_at=T0)
    machine = make_machine(db, stage="dyeing")
    run = make_run(db, order, machine, stage="rework", started_at=T0 + dt.timedelta(hours=1))
    db.add(RollRun(roll_id=roll.id, run_id=run.id, purpose="rework"))
    db.flush()
    status = lambda: client.get(f"/api/rolls?order_code={order.code}").json()[0]["status"]  # noqa: E731
    assert status() == "in_rework"
    new = client.post(f"/api/runs/{run.id}/handover", json={"operator_worker_id": make_worker(db).id}).json()
    assert new["stage"] == "rework" and new["roll_codes"] == [roll.code]
    assert status() == "in_rework"
    assert client.post(f"/api/runs/{new['id']}/end", json={}).status_code == 200
    assert status() == "awaiting_qc"


def test_the_copied_links_keep_their_purpose(client, db, sup):
    b = Batch(client, db)
    new = b.handover()
    purposes = {(l.run_id, l.purpose) for l in db.scalars(select(RollRun).where(RollRun.roll_id == b.rolls[0].id))}
    assert (new["id"], "dye") in purposes and (b.run.id, "dye") in purposes
    assert not any(p == "produce" and r == new["id"] for r, p in purposes)
