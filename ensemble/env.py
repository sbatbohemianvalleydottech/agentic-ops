"""Read credentials from a `.env` file so they survive closing a terminal.

Local convenience, not secrets management. Do not let it grow into one.

It lives in `ensemble` because this package owns the provider seam, and
credentials are what that seam needs. Stdlib only, like the rest of the core.
"""

import os
from pathlib import Path


def setting(name: str, default: str) -> str:
    """Read an optional setting, treating an empty value as absent.

    `os.environ.get(name, default)` is not enough. Our loader skips empty values,
    but litellm calls python-dotenv on import and loads the same `.env` behind
    us, and python-dotenv does not skip them. A template line of `RATER_A=`
    therefore arrives as `""` however careful this module is, and
    `os.environ.get` would hand that empty string straight to a caller as a model
    name.

    That is not hypothetical. It is what made the first live run of this
    repository fail: the model string was empty, and the vendor reported it as
    "LLM Provider NOT provided" across twelve lines of banner.
    """
    return (os.environ.get(name) or "").strip() or default


def _find_upward(start: Path) -> Path | None:
    """Look for `.env` from here up to the filesystem root, so the tools work
    when run from a subdirectory."""
    for directory in [start, *start.parents]:
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_env(path: Path | None = None) -> list[str]:
    """Load `KEY=value` lines into the environment.

    Returns the names it set, **never the values**. Nothing in this module may
    put a credential where it could reach stdout, a log, or a traceback.

    An absent file is not an error, and a variable already present in the
    environment is left alone: a file on disk must never silently override what
    somebody deliberately exported for this session.
    """
    resolved = Path(path) if path else _find_upward(Path.cwd())
    if resolved is None or not resolved.is_file():
        return []

    loaded: list[str] = []

    for line in resolved.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        stripped = stripped.removeprefix("export ").lstrip()

        # A stray line should not discard a perfectly good key three lines above.
        if "=" not in stripped:
            continue

        # Split once only. API keys carry padding characters and splitting on
        # every '=' would corrupt them.
        name, _, value = stripped.partition("=")
        name = name.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]

        # An empty value means "not set", not "set to nothing". `.env.example`
        # ships every key with an empty value, and honouring those literally
        # would beat the default in os.environ.get(name, DEFAULT) and blank a
        # model name.
        if not name or not value or name in os.environ:
            continue

        os.environ[name] = value
        loaded.append(name)

    return loaded
