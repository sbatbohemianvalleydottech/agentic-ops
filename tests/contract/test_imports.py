"""Constitution Principle IV, made checkable.

These are regression guards rather than tests that drove new behaviour. They
exist because the one-way dependency rule is what separates reusable artifacts
from one application split across folders, and that is a property worth
enforcing automatically rather than trusting to review.
"""

import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHARED = ("ensemble", "ledger")

# Anything at the top level that is not shared infrastructure, tooling or docs
# is an agent package. Discovered rather than listed, so an agent added later is
# covered without anyone remembering to update this test.
NOT_AGENTS = {
    *SHARED, "tests", "specs", "docs", "build", "dist",
    ".git", ".github", ".specify", ".claude", ".venv", ".pytest_cache", ".ruff_cache",
}


def agent_packages() -> set[str]:
    return {
        entry.name
        for entry in REPO.iterdir()
        if entry.is_dir()
        and entry.name not in NOT_AGENTS
        and (entry / "__init__.py").exists()
    }


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_shared_packages_import_nothing_from_any_agent():
    agents = agent_packages()
    offences = []

    for package in SHARED:
        for source in (REPO / package).rglob("*.py"):
            for root in imported_roots(source) & agents:
                offences.append(f"{source.relative_to(REPO)} imports {root}")

    assert not offences, (
        "dependencies must point one way, from agents to shared primitives:\n"
        + "\n".join(offences)
    )


def test_the_core_imports_with_no_provider_library_installed():
    """If this ever fails, the gate has stopped being auditable without a paid
    dependency, which is the property worth protecting."""
    result = subprocess.run(
        [sys.executable, "-c", "import ensemble, ensemble.gate, ensemble.orchestrator, ledger"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 0, result.stderr


def test_importing_the_core_does_not_pull_in_a_provider_library():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, ensemble, ensemble.orchestrator; "
            "print('litellm' in sys.modules or 'anthropic' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.stdout.strip() == "False", result.stdout + result.stderr
