"""The costing engine: pure functions on plain records, with no database and no clock ("now" is always passed in).
All arithmetic is exact (fractions.Fraction); rounding to the paisa happens once, at the edge, in costing/service.py."""
