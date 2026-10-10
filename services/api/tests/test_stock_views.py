from decimal import Decimal

from sqlalchemy import text

from app.db.models import YarnMovement
from tests.factories import (
    make_fabric_type, make_lot, make_machine, make_order, make_run, make_supplier, make_user, make_yarn_type,
)


def issue(db, lot, run, kg):
    db.add(YarnMovement(yarn_lot_id=lot.id, kind="issue", qty_kg=-Decimal(str(kg)), production_run_id=run.id,
                        moved_by=make_user(db).id))
    db.flush()


def give_back(db, lot, run, kg):
    db.add(YarnMovement(yarn_lot_id=lot.id, kind="return", qty_kg=Decimal(str(kg)), production_run_id=run.id,
                        moved_by=make_user(db).id))
    db.flush()


def spinning_run(db, order):
    return make_run(db, order, make_machine(db, stage="spinning"))


def one(db, sql, **params):
    return db.execute(text(sql), params).mappings().one()


def scenario(db, reorder=300):
    """5,000 m poplin, recipe 0.12 kg/m of 30s cotton, 5% wastage => need 630 kg. One lot of 800 kg at 250/kg."""
    cotton = make_yarn_type(db, reorder_level_kg=reorder)
    fabric = make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.12, wastage_pct=5)
    order = make_order(db, fabric_type=fabric, qty_metres=5000)
    lot = make_lot(db, yarn_type=cotton, qty_kg=800, cost_per_kg=250)
    return cotton, fabric, order, lot


# ---- v_lot_stock --------------------------------------------------------------------------

def test_lot_stock_is_the_sum_of_the_ledger(db):
    _, _, order, lot = scenario(db)
    run = spinning_run(db, order)
    issue(db, lot, run, 587.5)
    assert one(db, "select on_hand_kg from v_lot_stock where yarn_lot_id=:i", i=lot.id)["on_hand_kg"] == Decimal("212.5")
    give_back(db, lot, run, 20)
    assert one(db, "select on_hand_kg from v_lot_stock where yarn_lot_id=:i", i=lot.id)["on_hand_kg"] == Decimal("232.5")


def test_a_lot_with_only_its_receipt_shows_the_received_quantity(db):
    lot = make_lot(db, qty_kg=123.456)
    assert one(db, "select on_hand_kg from v_lot_stock where yarn_lot_id=:i", i=lot.id)["on_hand_kg"] == Decimal("123.456")


# ---- v_order_yarn_need --------------------------------------------------------------------

def need(db, order, yarn_type):
    return one(db, "select * from v_order_yarn_need where order_id=:o and yarn_type_id=:y", o=order.id, y=yarn_type.id)


def test_need_is_metres_times_recipe_times_wastage(db):
    cotton, _, order, _ = scenario(db)
    row = need(db, order, cotton)
    assert row["need_kg"] == Decimal("630.000") and row["issued_kg"] == 0 and row["outstanding_kg"] == Decimal("630.000")


def test_issuing_reduces_outstanding_and_a_return_gives_it_back(db):
    cotton, _, order, lot = scenario(db)
    run = spinning_run(db, order)
    issue(db, lot, run, 587.5)
    row = need(db, order, cotton)
    assert (row["issued_kg"], row["outstanding_kg"]) == (Decimal("587.500"), Decimal("42.500"))
    give_back(db, lot, run, 20)
    row = need(db, order, cotton)
    assert (row["issued_kg"], row["outstanding_kg"]) == (Decimal("567.500"), Decimal("62.500"))


def test_outstanding_never_goes_negative(db):
    cotton, _, order, lot = scenario(db)
    issue(db, lot, spinning_run(db, order), 700)          # more than the 630 needed
    row = need(db, order, cotton)
    assert row["issued_kg"] == Decimal("700.000") and row["outstanding_kg"] == 0


def test_a_recipe_with_two_yarn_types_gives_two_rows(db):
    cotton, poly = make_yarn_type(db), make_yarn_type(db)
    fabric = make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.1, wastage_pct=0)
    from app.db.models import FabricRecipeLine
    fabric.recipe_lines.append(FabricRecipeLine(yarn_type_id=poly.id, kg_per_metre=0.05))
    db.flush()
    order = make_order(db, fabric_type=fabric, qty_metres=1000)
    assert need(db, order, cotton)["need_kg"] == Decimal("100.000")
    assert need(db, order, poly)["need_kg"] == Decimal("50.000")


def test_yarn_issued_to_another_orders_run_is_not_counted(db):
    cotton, _, order, lot = scenario(db)
    other = make_order(db)
    issue(db, lot, spinning_run(db, other), 100)
    assert need(db, order, cotton)["issued_kg"] == 0


# ---- v_yarn_type_stock --------------------------------------------------------------------

def stock(db, yarn_type):
    return one(db, "select * from v_yarn_type_stock where yarn_type_id=:y", y=yarn_type.id)


def second_order_needing_400(db, cotton):
    fabric = make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.08, wastage_pct=0)    # 5000 m x 0.08 = 400 kg
    return make_order(db, fabric_type=fabric, qty_metres=5000)


def test_free_stock_after_reservations_is_minus_230(db):
    cotton, _, order, lot = scenario(db)
    issue(db, lot, spinning_run(db, order), 587.5)
    second_order_needing_400(db, cotton)
    row = stock(db, cotton)
    assert row["on_hand_kg"] == Decimal("212.500")
    assert row["outstanding_kg"] == Decimal("442.500")                  # 42.5 + 400
    assert row["free_kg"] == Decimal("-230.000")
    assert row["below_reorder"] is True


def test_a_yarn_type_with_no_lots_shows_zeros(db):
    row = stock(db, make_yarn_type(db, reorder_level_kg=100))
    assert (row["on_hand_kg"], row["outstanding_kg"], row["free_kg"]) == (0, 0, 0)
    assert row["below_reorder"] is True                                  # 0 < 100


def test_a_blocked_lots_stock_is_excluded(db):
    import datetime as dt
    cotton, _, _, lot = scenario(db)
    assert stock(db, cotton)["on_hand_kg"] == Decimal("800.000")
    lot.is_blocked, lot.blocked_at = True, dt.datetime(2026, 10, 10, tzinfo=dt.UTC)
    db.flush()
    assert stock(db, cotton)["on_hand_kg"] == 0


def test_draft_and_cancelled_orders_reserve_nothing(db):
    cotton, _, order, _ = scenario(db)
    assert stock(db, cotton)["outstanding_kg"] == Decimal("630.000")
    order.state = "draft"
    order.confirmed_at = None
    db.flush()
    assert stock(db, cotton)["outstanding_kg"] == 0
    order.state = "cancelled"
    db.flush()
    assert stock(db, cotton)["outstanding_kg"] == 0


def test_below_reorder_is_strictly_less_than(db):
    cotton, _, order, _ = scenario(db, reorder=170)                      # free = 800 - 630 = 170
    assert stock(db, cotton)["free_kg"] == Decimal("170.000") and stock(db, cotton)["below_reorder"] is False
    make_lot(db, yarn_type=cotton, qty_kg=1, cost_per_kg=1)   # +1 kg => free 171
    assert stock(db, cotton)["below_reorder"] is False


def test_two_lots_of_one_yarn_type_add_up_without_double_counting(db):
    cotton, _, order, lot = scenario(db)
    make_lot(db, yarn_type=cotton, qty_kg=200, cost_per_kg=250)
    second_order_needing_400(db, cotton)
    row = stock(db, cotton)
    assert row["on_hand_kg"] == Decimal("1000.000") and row["outstanding_kg"] == Decimal("1030.000")
