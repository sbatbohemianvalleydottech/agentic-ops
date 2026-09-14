"""Every section renders, on both estates, and counts read as English.

A cold reader with only the README found both of these. The README said
"categories with nothing in them are not printed"; three of the four printed
"none." and the fourth vanished, so the document was wrong about the tool and
the tool was inconsistent with its own report module, whose docstring says
empty sections still render because "checked, found nothing" and "never
checked" are different claims.

The two fixtures cover each other: estate_a has nothing healthy, estate_b has
nothing unassessable and nothing unmatched.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "cost_agent" / "fixtures"
SECTIONS = ("Contested attributions", "Unassessable", "Unmatched", "Healthy")


def render(estate: str) -> str:
    result = subprocess.run(
        [
            sys.executable, "-m", "cost_agent",
            "--costs", str(FIXTURES / estate / "costs.csv"),
            "--inventory", str(FIXTURES / estate / "inventory.json"),
            "--as-of", "2026-09-01",
        ],
        capture_output=True, text=True, cwd=REPO, check=True,
    )
    return result.stdout


@pytest.fixture(scope="module")
def estate_a():
    return render("estate_a")


@pytest.fixture(scope="module")
def estate_b():
    return render("estate_b")


@pytest.mark.parametrize("section", SECTIONS)
def test_every_section_renders_on_estate_a(estate_a, section):
    assert section in estate_a


@pytest.mark.parametrize("section", SECTIONS)
def test_every_section_renders_on_estate_b(estate_b, section):
    assert section in estate_b


def test_an_empty_section_says_so_rather_than_disappearing(estate_a):
    """estate_a has no healthy resource. The heading must still be there."""
    assert "Healthy" in estate_a
    assert "none" in estate_a.split("Healthy", 1)[1].splitlines()[0].lower()


def test_a_populated_section_reports_its_count(estate_b):
    assert "Healthy: 3 resources" in estate_b


def test_a_single_resource_is_not_called_resources(estate_a):
    """A driver explaining one resource read 'Explains: 1 resources'."""
    assert "1 resources" not in estate_a
    assert "1 resource," in estate_a


def test_a_single_finding_is_not_called_findings(estate_a, estate_b):
    for output in (estate_a, estate_b):
        assert "1 findings" not in output


def test_plurals_survive_where_they_belong(estate_a):
    assert "8 resources" in estate_a
