"""The exact one-sided test. Checked against known values and against an independent brute-force count."""
from fractions import Fraction as F
from itertools import combinations
from math import comb

import pytest
from app.modules.insights.engine.fisher import fisher_greater


def brute_force(a, b, c, d):
    """Pick the group's members out of everyone in every possible way and count the ways with at least `a` defective."""
    people = [True] * (a + c) + [False] * (b + d)             # True = defective
    group = a + b
    hits = sum(1 for chosen in combinations(range(len(people)), group) if sum(people[i] for i in chosen) >= a)
    return F(hits, comb(len(people), group))


def test_known_values():
    assert fisher_greater(9, 11, 3, 77) == F(277559, 20251032410)            # 9 of 20 defective vs 3 of 80 elsewhere
    assert fisher_greater(0, 5, 0, 5) == 1 and fisher_greater(5, 0, 5, 0) == 1
    assert fisher_greater(5, 0, 0, 5) == F(1, comb(10, 5))                   # all five defective in a group of five
    assert fisher_greater(1, 0, 0, 0) == 1


@pytest.mark.parametrize("table", [(2, 3, 1, 4), (3, 1, 2, 4), (0, 4, 4, 0), (4, 0, 0, 4), (1, 2, 3, 2), (2, 2, 2, 2),
                                   (3, 0, 1, 6), (5, 1, 0, 3), (1, 5, 3, 1), (2, 0, 2, 5)])
def test_it_agrees_with_counting_every_arrangement(table):
    assert fisher_greater(*table) == brute_force(*table)


def test_a_bigger_excess_is_always_less_likely_and_probabilities_stay_in_range():
    previous = F(1)
    for hit in range(0, 11):                                                  # 10 of a group of 20 defective in the best case
        p = fisher_greater(hit, 20 - hit, 10 - hit, 70 + hit)
        assert 0 < p <= previous <= 1
        previous = p


def test_bad_tables_are_refused():
    with pytest.raises(ValueError):
        fisher_greater(-1, 2, 3, 4)
    with pytest.raises(ValueError):
        fisher_greater(0, 0, 0, 0)
