"""Thresholds are the most arguable numbers in the analysis, so they live in a file
a reviewer can read rather than in a branch they cannot.
"""

from decimal import Decimal

import pytest

from cost_agent.thresholds import load_thresholds

REQUIRED_KEYS = (
    "idle_ceiling",
    "target_floor",
    "oversize_ratio",
    "cold_after_days",
    "stale_after_days",
    "weekend_ratio",
    "annualisation_multiplier",
    "savings_conservatism",
    "owner_tag_keys",
)


def test_defaults_load_and_carry_every_documented_key():
    thresholds = load_thresholds()

    for key in REQUIRED_KEYS:
        assert getattr(thresholds, key) is not None, f"{key} missing from defaults"


def test_the_annualisation_multiplier_is_exact_not_a_float():
    """365/30 as a float drifts. The multiplier scales the headline number, so it
    is the last place to accept drift."""
    assert isinstance(load_thresholds().annualisation_multiplier, Decimal)


def test_an_override_file_replaces_the_defaults(tmp_path):
    override = tmp_path / "custom.toml"
    override.write_text(
        "\n".join(
            [
                "idle_ceiling = 0.02",
                "target_floor = 0.80",
                "oversize_ratio = 1.2",
                "cold_after_days = 15",
                "stale_after_days = 7",
                "weekend_ratio = 3.0",
                'annualisation_multiplier = "12"',
                'savings_conservatism = "0.60"',
                'owner_tag_keys = ["team"]',
            ]
        )
    )

    thresholds = load_thresholds(override)

    assert thresholds.target_floor == pytest.approx(0.80)
    assert thresholds.owner_tag_keys == ("team",)
    assert thresholds.annualisation_multiplier == Decimal("12")
