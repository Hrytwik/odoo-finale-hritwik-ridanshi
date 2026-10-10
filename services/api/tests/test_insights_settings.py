"""The intelligence settings: the spec's defaults, and a bad STAGE_SHIFTS fails loudly when the app starts."""
import pytest
from app.config import Settings
from pydantic import ValidationError


def test_the_defaults_are_the_specs():
    s = Settings(_env_file=None)
    assert (s.qc_days, s.dispatch_days, s.default_efficiency, s.efficiency_window_days, s.efficiency_min_hours) == (1, 1, 0.8, 7, 1)
    assert (s.stage_shifts, s.root_cause_min_group, s.root_cause_alpha, s.reorder_round_kg) == ("", 5, 0.05, 50)


@pytest.mark.parametrize("text", ["weaving=2", "weaving=2,dyeing=1", " spinning = 3 ", "", "weaving=2,"])
def test_good_stage_shifts_are_accepted(text):
    assert Settings(_env_file=None, stage_shifts=text).stage_shifts == text


@pytest.mark.parametrize("text", ["weaving", "weaving=", "weaving=two", "weaving=0", "weaving=-1", "knitting=2", "weaving=2;dyeing=1"])
def test_bad_stage_shifts_are_refused(text):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, stage_shifts=text)
