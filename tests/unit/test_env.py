"""Loading credentials from a .env file.

Convenience, not secrets management. The rules that matter are that a
deliberately exported variable always beats the file, and that no value can ever
reach stdout, a log, or git through this path.
"""

import os
import re
from pathlib import Path

import pytest

from ensemble.env import load_env

REPO = Path(__file__).resolve().parents[2]


TEST_KEYS = ("SOME_TEST_KEY", "ANOTHER_TEST_KEY")


@pytest.fixture
def env_file(tmp_path):
    """`load_env` writes to os.environ directly, which monkeypatch does not track,
    and monkeypatch.delenv *restores* at teardown. So clean up explicitly."""

    def _clear():
        for key in TEST_KEYS:
            os.environ.pop(key, None)

    def _write(contents: str) -> Path:
        path = tmp_path / ".env"
        path.write_text(contents)
        return path

    _clear()
    yield _write
    _clear()


def test_a_key_value_line_lands_in_the_environment(env_file):
    load_env(env_file("SOME_TEST_KEY=abc123\n"))

    assert os.environ["SOME_TEST_KEY"] == "abc123"


def test_an_already_exported_variable_wins(env_file, monkeypatch):
    """A file on disk must never silently override what the operator set for
    this session."""
    monkeypatch.setenv("SOME_TEST_KEY", "from-the-shell")

    load_env(env_file("SOME_TEST_KEY=from-the-file\n"))

    assert os.environ["SOME_TEST_KEY"] == "from-the-shell"


def test_a_missing_file_is_not_an_error(tmp_path):
    assert load_env(tmp_path / "nothing-here") == []


def test_export_prefixes_quotes_comments_and_blanks_are_handled(env_file):
    """People paste what they already have in their shell."""
    load_env(
        env_file(
            "\n".join(
                [
                    "# a comment",
                    "",
                    "export SOME_TEST_KEY='quoted-value'",
                    '  ANOTHER_TEST_KEY = "spaced"  ',
                ]
            )
        )
    )

    assert os.environ["SOME_TEST_KEY"] == "quoted-value"
    assert os.environ["ANOTHER_TEST_KEY"] == "spaced"


def test_a_value_containing_equals_survives_intact(env_file):
    """API keys carry padding characters. Splitting on every '=' corrupts them."""
    load_env(env_file("SOME_TEST_KEY=abc==def=ghi\n"))

    assert os.environ["SOME_TEST_KEY"] == "abc==def=ghi"


def test_a_malformed_line_is_skipped_without_stopping_the_rest(env_file):
    """A stray line should not discard a perfectly good key three lines above."""
    load_env(env_file("this line has no equals sign\nSOME_TEST_KEY=fine\n"))

    assert os.environ["SOME_TEST_KEY"] == "fine"


def test_an_empty_value_is_treated_as_not_set(env_file):
    """`.env.example` ships keys with empty values. Setting them to "" would beat
    the default in os.environ.get(name, DEFAULT) and blank a model name."""

    load_env(env_file('SOME_TEST_KEY=\nANOTHER_TEST_KEY=""\n'))

    assert "SOME_TEST_KEY" not in os.environ
    assert "ANOTHER_TEST_KEY" not in os.environ


def test_the_loader_returns_names_and_never_values(env_file):
    loaded = load_env(env_file("SOME_TEST_KEY=super-secret-value\n"))

    assert loaded == ["SOME_TEST_KEY"]
    assert "super-secret-value" not in repr(loaded)


def test_a_dotenv_in_a_parent_directory_is_found(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("SOME_TEST_KEY=found-upward\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    load_env()

    assert os.environ["SOME_TEST_KEY"] == "found-upward"


def test_setting_treats_an_empty_environment_value_as_absent(monkeypatch):
    """Our loader skips empty values, but litellm calls python-dotenv on import
    and loads the same file behind us, and python-dotenv does not. A template
    line of `RATER_A=` therefore arrives as "" no matter how careful we are, so
    the fix has to be at the point of use."""
    from ensemble.env import setting

    monkeypatch.setenv("SOME_TEST_KEY", "")
    assert setting("SOME_TEST_KEY", "the-default") == "the-default"

    monkeypatch.setenv("SOME_TEST_KEY", "   ")
    assert setting("SOME_TEST_KEY", "the-default") == "the-default"

    monkeypatch.setenv("SOME_TEST_KEY", "chosen")
    assert setting("SOME_TEST_KEY", "the-default") == "chosen"

    monkeypatch.delenv("SOME_TEST_KEY", raising=False)
    assert setting("SOME_TEST_KEY", "the-default") == "the-default"


def test_the_example_file_lists_every_variable_the_repo_reads():
    """Derived from source, not hardcoded, so adding a credential later without a
    template entry breaks the build rather than confusing somebody in six months."""
    referenced = set()
    for package in ("ensemble", "cost_agent", "rca_agent"):
        for source in (REPO / package).rglob("*.py"):
            referenced |= set(
                re.findall(
                    r'environ(?:\.get)?\(\s*["\']([A-Z][A-Z0-9_]+)["\']',
                    source.read_text(),
                )
            )

    documented = {
        line.split("=", 1)[0].strip()
        for line in (REPO / ".env.example").read_text().splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }

    assert referenced - documented == set(), (
        f"undocumented in .env.example: {sorted(referenced - documented)}"
    )


def test_dotenv_is_still_gitignored():
    assert ".env" in (REPO / ".gitignore").read_text().splitlines()
