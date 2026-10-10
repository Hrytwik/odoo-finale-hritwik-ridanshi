"""B9a Task 1: the base seed gives an empty database its starter facts, and is safe to run again."""
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.models import Buyer, FabricType, Machine, Shift, Supplier, User, Worker, YarnType
from scripts import seed_dev


@pytest.fixture(autouse=True)
def fast_password_hash(monkeypatch):
    """bcrypt is slow on purpose; these tests never log in with a seeded password."""
    monkeypatch.setattr(seed_dev, "hash_password", lambda password: "not-a-real-hash")


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_the_starter_facts_are_there(db):
    seed_dev.seed_all(db)
    shifts = {s.name: (s.start_time, s.end_time) for s in db.scalars(select(Shift))}
    assert shifts == {"A": (dt.time(6), dt.time(14)), "B": (dt.time(14), dt.time(22)), "C": (dt.time(22), dt.time(6))}
    machines = {m.code: m for m in db.scalars(select(Machine))}
    assert sorted(machines) == ["DYE-01", "DYE-02", "LOOM-01", "LOOM-02", "LOOM-03", "LOOM-04", "LOOM-05", "LOOM-06",
                                "SPIN-01", "SPIN-02"]
    assert {m.stage for m in machines.values() if m.code.startswith("SPIN")} == {"spinning"}
    assert {m.stage for m in machines.values() if m.code.startswith("LOOM")} == {"weaving"}
    assert {m.stage for m in machines.values() if m.code.startswith("DYE")} == {"dyeing"}
    assert all(m.active for m in machines.values())
    assert machines["SPIN-01"].rated_output_per_hour == Decimal("20") and machines["SPIN-02"].rated_output_per_hour == Decimal("22")
    assert all(m.running_cost_per_hour > 0 for m in machines.values())


def test_yarn_types_suppliers_buyers_and_fabrics(db):
    seed_dev.seed_all(db)
    yarn = {y.code: y for y in db.scalars(select(YarnType))}
    assert set(yarn) == {"30S-COT-RAW", "40S-PC-RAW"}
    assert yarn["30S-COT-RAW"].reorder_level_kg == Decimal("300") and yarn["40S-PC-RAW"].reorder_level_kg == Decimal("250")
    assert {s.name for s in db.scalars(select(Supplier))} == {"Vardhman Yarns", "Coastal Spinners"}
    assert {b.name for b in db.scalars(select(Buyer))} == {"Sharma Fabrics", "Kavya Garments"}
    fabrics = {f.name: f for f in db.scalars(select(FabricType))}
    assert set(fabrics) == {"Poplin 58in", "Twill 58in"}
    poplin, twill = fabrics["Poplin 58in"], fabrics["Twill 58in"]
    assert (poplin.wastage_pct, twill.wastage_pct) == (Decimal("5"), Decimal("4"))
    [p_line], [t_line] = poplin.recipe_lines, twill.recipe_lines
    assert (p_line.yarn_type.code, p_line.kg_per_metre) == ("30S-COT-RAW", Decimal("0.12"))
    assert (t_line.yarn_type.code, t_line.kg_per_metre) == ("40S-PC-RAW", Decimal("0.16"))


def test_people_and_logins(db):
    seed_dev.seed_all(db)
    assert count(db, User) == 7 and count(db, Worker) == 12
    roles = [w.role for w in db.scalars(select(Worker))]
    assert roles.count("operator") >= 7 and roles.count("inspector") == 2
    assert {w.code for w in db.scalars(select(Worker))} >= {f"W-{n:03d}" for n in range(1, 13)}
    assert all(w.active and w.daily_wage > 0 for w in db.scalars(select(Worker)))


def test_running_it_twice_adds_nothing(db):
    seed_dev.seed_all(db)
    before = {m.__name__: count(db, m) for m in (Shift, Machine, YarnType, Supplier, Buyer, FabricType, Worker, User)}
    seed_dev.seed_all(db)
    after = {m.__name__: count(db, m) for m in (Shift, Machine, YarnType, Supplier, Buyer, FabricType, Worker, User)}
    assert before == after
    assert count(db, Machine) == 10 and count(db, Shift) == 3


def test_a_row_someone_edited_is_not_overwritten(db):
    seed_dev.seed_all(db)
    loom = db.scalar(select(Machine).where(Machine.code == "LOOM-04"))
    loom.name, loom.active = "Renamed loom", False
    yarn = db.scalar(select(YarnType).where(YarnType.code == "30S-COT-RAW"))
    yarn.reorder_level_kg = Decimal("999")
    db.flush()
    seed_dev.seed_all(db)
    db.refresh(loom)
    db.refresh(yarn)
    assert (loom.name, loom.active) == ("Renamed loom", False) and yarn.reorder_level_kg == Decimal("999")
    assert count(db, Machine) == 10


def test_a_partly_seeded_database_is_completed(db):
    seed_dev.seed_all(db)
    db.delete(db.scalar(select(Machine).where(Machine.code == "DYE-02")))
    db.flush()
    seed_dev.seed_all(db)
    assert count(db, Machine) == 10
