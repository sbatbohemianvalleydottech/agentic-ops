"""A price row that is missing comes with the command that adds it.

Three public Terraform plans were put through this tool and all three priced
nothing, because the shipped table holds four rows. Refusing to invent a figure
is correct and is most of why the tool exists. Naming the key and stopping
there is not: the reader gets a string and no next step, and that is the most
likely first experience anyone has of this tool on their own input.

Two commands rather than one, because the operator has no catalogue file yet.
A command that assumes an input they do not have is a description of a command.
"""

from pathlib import Path

from plan_cost.refresh import CATALOGUE_SOURCE
from plan_cost.report import MOST_KEYS_SHOWN, _missing_rows

PRICES = Path("plan_cost/prices.toml")
ONE = ("google/machine-type/e2-standard-4/europe-west1",)
TWO = ONE + ("google/machine-type/n2-standard-8/europe-west1",)


def rendered(keys, prices=PRICES) -> str:
    return "\n".join(_missing_rows(keys, prices))


def test_nothing_missing_renders_nothing():
    assert _missing_rows((), PRICES) == []


def test_every_missing_key_is_named():
    out = rendered(TWO)
    for key in TWO:
        assert key in out


def test_the_refresh_command_is_printed():
    assert "--refresh-prices" in rendered(ONE)


def test_it_names_the_table_actually_in_use():
    """An operator pointed at their own table is told to refresh that one, not
    the shipped default."""
    out = rendered(ONE, prices=Path("/tmp/mine.toml"))
    assert "--prices /tmp/mine.toml" in out
    assert "plan_cost/prices.toml" not in out


def test_a_path_under_the_working_directory_prints_relative_to_it(tmp_path, monkeypatch):
    """The default table resolves to an absolute path. Printing it raw puts
    whoever ran the tool's home directory into a report that gets pasted into
    pull requests, and it is still runnable as printed without it."""
    monkeypatch.chdir(tmp_path)
    table = tmp_path / "plan_cost" / "prices.toml"
    table.parent.mkdir()
    table.touch()
    out = rendered(ONE, prices=table)
    assert "--prices plan_cost/prices.toml" in out
    assert str(tmp_path) not in out


def test_the_catalogue_url_is_the_one_the_refresh_calls():
    """Read from refresh.py rather than copied, so the printed command cannot
    drift from the command it describes."""
    assert CATALOGUE_SOURCE in rendered(ONE)


def test_the_catalogue_is_fetched_before_it_is_used():
    """The operator has no catalogue file yet, so one command is not enough."""
    out = rendered(ONE)
    assert out.index("curl") < out.index("--refresh-prices")


def test_the_refresh_reads_the_file_the_fetch_writes():
    """Two commands that do not join up are two descriptions of commands."""
    out = rendered(ONE)
    written = out.split("> ")[1].split()[0]
    assert f"--refresh-prices {written}" in out


def test_it_says_the_table_is_rewritten_in_place():
    """The file is committed. A command that edits it silently is a trap."""
    assert "in place" in rendered(ONE)


def test_a_long_list_is_capped_and_says_how_many_were_left_out():
    """A gate report goes into a pull request. Forty lines of keys is not a
    report. The command adds all of them either way, so nothing is lost."""
    keys = tuple(f"google/machine-type/m-{n}/europe-west1" for n in range(25))
    out = rendered(keys)
    assert out.count("google/machine-type/m-") == MOST_KEYS_SHOWN
    assert f"and {25 - MOST_KEYS_SHOWN} more" in out


def test_a_list_at_the_cap_says_nothing_about_more():
    keys = tuple(f"google/machine-type/m-{n}/europe-west1" for n in range(MOST_KEYS_SHOWN))
    assert "more" not in rendered(keys)
