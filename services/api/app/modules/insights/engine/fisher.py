"""Fisher's exact test, one-sided, with exact arithmetic (no scipy). The same number scipy.stats.fisher_exact gives
for alternative='greater', but as an exact fraction."""
from fractions import Fraction
from math import comb


def fisher_greater(a: int, b: int, c: int, d: int) -> Fraction:
    """The chance, if defects were spread evenly by luck alone, of seeing at least `a` defective rolls in a group.
    Table: a = defective in the group, b = fine in the group, c = defective elsewhere, d = fine elsewhere.
    This is the hypergeometric tail with the table's row and column totals held fixed."""
    if min(a, b, c, d) < 0:
        raise ValueError("counts cannot be negative")
    group, defective, total = a + b, a + c, a + b + c + d
    if total == 0:
        raise ValueError("an empty table")
    ways = comb(total, group)
    return sum(Fraction(comb(defective, x) * comb(total - defective, group - x), ways)
               for x in range(a, min(group, defective) + 1))
