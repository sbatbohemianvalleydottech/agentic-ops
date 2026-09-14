"""The rubric is cited practice made configurable. Organisations name their
timeline moments differently, and a rubric insisting on someone else's vocabulary
gets ignored.
"""

import pytest

from rca_agent.rubric import load_rubric

REQUIRED_KEYS = (
    "required_moments",
    "blame_phrases",
    "export_window_days",
    "grade_scale",
    "min_contributing_factors",
)


def test_defaults_load_and_carry_every_documented_key():
    rubric = load_rubric()

    for key in REQUIRED_KEYS:
        assert getattr(rubric, key), f"{key} missing or empty in defaults"


def test_the_four_moments_from_the_source_practice_are_the_default():
    assert load_rubric().required_moments == (
        "detection",
        "escalation",
        "mitigation",
        "resolution",
    )


def test_human_error_is_a_blame_phrase_by_default():
    """PagerDuty's central point: mistakes are rarely rooted in one person's
    actions, so 'human error' is never the cause.

    It sits in the standalone list rather than the conditional one, because it
    names a person by construction and needs no subject beside it.
    """
    rubric = load_rubric()
    assert "human error" in rubric.blame_phrases_standalone
    assert "human error" not in rubric.blame_phrases


def test_the_export_window_defaults_to_the_incident_io_policy_shape():
    assert load_rubric().export_window_days == 7


def test_an_override_file_replaces_the_defaults(tmp_path):
    override = tmp_path / "custom.toml"
    override.write_text(
        "\n".join(
            [
                'required_moments = ["detected", "resolved"]',
                'blame_phrases = ["fat fingered"]',
                "export_window_days = 30",
                'grade_scale = ["poor", "adequate", "strong"]',
                "min_contributing_factors = 2",
            ]
        )
    )

    rubric = load_rubric(override)

    assert rubric.required_moments == ("detected", "resolved")
    assert rubric.export_window_days == 30
    assert rubric.grade_scale == ("poor", "adequate", "strong")


def test_the_grade_scale_must_allow_disagreement(tmp_path):
    """A one-grade scale makes the gate meaningless, same as in ensemble."""
    override = tmp_path / "bad.toml"
    override.write_text(
        "\n".join(
            [
                'required_moments = ["detected"]',
                'blame_phrases = ["x"]',
                "export_window_days = 7",
                'grade_scale = ["fine"]',
                "min_contributing_factors = 1",
            ]
        )
    )

    with pytest.raises(ValueError):
        load_rubric(override)
