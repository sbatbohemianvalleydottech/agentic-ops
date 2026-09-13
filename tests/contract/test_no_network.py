"""plan_cost judges a plan without touching the network.

A regression guard rather than a test that drove new behaviour, in the same
category as the import contract beside it. The claim in the README is that this
tool needs no credential and makes no call while judging, and a claim like that
decays quietly unless something checks it.
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / "plan_cost"

FORBIDDEN = {"socket", "ssl", "urllib", "http", "requests", "httpx", "aiohttp", "litellm"}


def imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_module_reaches_for_the_network():
    offenders = {
        path.name: sorted(imported_roots(path) & FORBIDDEN)
        for path in sorted(PACKAGE.glob("*.py"))
        if imported_roots(path) & FORBIDDEN
    }
    assert offenders == {}


def test_the_guard_is_looking_at_something():
    """A scan that silently found no files would pass for the wrong reason."""
    assert len(list(PACKAGE.glob("*.py"))) >= 3
