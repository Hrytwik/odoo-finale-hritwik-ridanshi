"""Spec §7.1 and §7.3, hand-worked: rolls R1 1,000 m, R2 600 m, R3 400 m (rejected)."""
from fractions import Fraction as F

from app.modules.costing.engine.allocation import allocate_order, is_final
from app.modules.costing.engine.records import YarnMove
from app.modules.costing.engine.runs import RunCost, run_costs
from tests.costing_records import at, issue, link, machine, roll, run

R = lambda id, **kw: run(id, 1, at(3, 6), at(3, 10), **kw)       # noqa: E731


def cost(yarn=0, machine=0, labour=0):
    return RunCost(F(yarn), F(machine), F(labour), F(0))


def test_the_worked_order_gives_17_50_and_18_33_a_metre():
    spin, weave, dye_run, mend = R(1, stage="spinning"), R(2), R(3, stage="dyeing"), R(4, stage="rework", machine=None)
    rolls = [roll(1, 1000), roll(2, 600), roll(3, 400, rejected=True)]
    links = [link(r, 2) for r in (1, 2, 3)] + [link(r, 3, "dye") for r in (1, 2, 3)] + [link(2, 4, "rework")]
    costs = {1: cost(15000, 3000, 2000), 2: cost(0, 4000, 2000), 3: cost(0, 1500, 500), 4: cost(0, 300, 200)}
    result = allocate_order([spin, weave, dye_run, mend], rolls, links, costs)
    assert result.total == 28500 and result.good_metres == 1600 and result.rejected_metres == 400
    assert result.reject_cost == 5600 and result.unabsorbed == 0
    r1, r2, r3 = (result.rolls[i] for i in (1, 2, 3))
    assert (r1.own_total, r2.own_total, r3.own_total) == (14000, 8900, 5600)
    assert (r1.reject_share, r2.reject_share, r3.reject_share) == (3500, 2100, 0)
    assert (r1.total, r2.total) == (17500, 11000) and r1.per_metre == F("17.5") and round(float(r2.per_metre), 2) == 18.33
    assert r1.total + r2.total == result.total                       # the good rolls carry the whole order
    assert result.cost_per_good_metre == F(28500, 1600) == F("17.8125")
    assert result.parts["rework"] == 500                             # the rework run is its own part
    assert r2.parts["rework"] == 500 and r1.parts["rework"] == 0


def test_a_run_with_no_rolls_goes_into_the_pool_and_is_spread_by_metres():
    broken = R(1, stage="weaving")                                   # a loom that broke before making a roll
    result = allocate_order([broken], [roll(1, 300), roll(2, 100)], [], {1: cost(machine=400)})
    assert result.rolls[1].parts["machine"] == 300 and result.rolls[2].parts["machine"] == 100


def test_no_good_roll_means_everything_is_unabsorbed_and_there_is_no_cost_per_metre():
    result = allocate_order([R(1, stage="spinning")], [roll(1, 500, rejected=True)], [], {1: cost(yarn=1000)})
    assert result.good_metres == 0 and result.cost_per_good_metre is None and result.unabsorbed == 1000
    nothing_woven = allocate_order([R(1, stage="spinning")], [], [], {1: cost(yarn=1000)})
    assert nothing_woven.total == 1000 and nothing_woven.unabsorbed == 1000 and nothing_woven.rolls == {}


def test_a_roll_dyed_in_two_runs_takes_a_share_of_each():
    first, second = R(1, stage="dyeing"), R(2, stage="dyeing")
    links = [link(1, 1, "dye"), link(2, 1, "dye"), link(1, 2, "dye")]
    result = allocate_order([first, second], [roll(1, 100), roll(2, 100)], links, {1: cost(machine=200), 2: cost(machine=50)})
    assert result.rolls[1].parts["machine"] == 150 and result.rolls[2].parts["machine"] == 100


def test_a_hand_mended_rework_costs_only_labour_and_lands_on_its_roll():
    mend = R(1, stage="rework", machine=None)
    result = allocate_order([mend], [roll(1, 100), roll(2, 100)], [link(2, 1, "rework")], {1: cost(labour=80)})
    assert result.rolls[2].parts["rework"] == 80 and result.rolls[1].parts["rework"] == 0


def test_each_final_condition_alone_keeps_the_cost_provisional():
    done, rolls = [R(1)], [roll(1, 1000)]
    assert is_final(done, rolls, F(1000), F(1000), cancelled=False)
    assert not is_final([R(1), run(2, 1, at(4, 6), None)], rolls, F(1000), F(1000), False)     # a run still open
    assert not is_final(done, [roll(1, 1000, settled=False)], F(1000), F(1000), False)         # a roll in flight
    assert not is_final(done, rolls, F(1000), F(1500), False)                                  # more metres to come
    assert is_final(done, rolls, F(1000), F(1500), cancelled=True)                             # ...unless cancelled


def test_run_costs_use_the_machine_rate_the_lot_cost_and_the_operators_share():
    spin = run(1, 1, at(3, 6), at(3, 10), stage="spinning", machine=1)
    moves = [issue(1, 120, 250), YarnMove(1, F(20), F(250), at(4, 9))]      # 120 kg issued, 20 kg returned
    costs = run_costs([spin], {1: machine(1, "spinning", rate=55)}, moves, {1: F(400)}, at(30, 12))
    assert (costs[1].yarn, costs[1].machine, costs[1].labour, costs[1].hours) == (25000, 220, 400, 4)


def test_property_the_good_rolls_always_carry_exactly_the_order_total():
    import random
    rng = random.Random(6)
    for _ in range(300):
        n = rng.randint(1, 5)
        rolls = [roll(i, rng.randint(50, 900), rejected=rng.random() < 0.3) for i in range(1, n + 1)]
        runs = [R(i, stage=rng.choice(["spinning", "weaving", "dyeing", "rework"]), machine=None if i % 4 == 0 else 1) for i in range(1, 7)]
        links = [link(rl.id, r.id, "produce") for r in runs for rl in rolls if rng.random() < 0.4]
        costs = {r.id: cost(rng.randint(0, 5000), rng.randint(0, 5000), rng.randint(0, 5000)) for r in runs}
        result = allocate_order(runs, rolls, links, costs)
        assert sum(result.parts.values()) == sum(c.total for c in costs.values())
        if result.good_metres > 0:
            assert sum(rr.total for rr in result.rolls.values() if not rr.rejected) == result.total
        else:
            assert result.unabsorbed == result.total
