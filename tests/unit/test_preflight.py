"""One cheap call per model, before anything expensive.

The first live run took four attempts against four different causes, each
costing a full pass to discover. Every one of them would have surfaced here.
"""

from ensemble.preflight import ModelCheck, preflight


def scripted(results: dict[str, tuple[bool, str | None]]):
    """A probe that answers from a script rather than the network."""

    def _probe(model: str) -> ModelCheck:
        ok, reason = results[model]
        return ModelCheck(
            model=model, reachable=ok, reason=reason, cost=0.00002 if ok else 0.0
        )

    return _probe


def test_every_reachable_model_is_reported_reachable():
    result = preflight(
        ["a/one", "b/two"],
        probe=scripted({"a/one": (True, None), "b/two": (True, None)}),
    )

    assert result.ok is True
    assert {c.model for c in result.checks} == {"a/one", "b/two"}
    assert all(c.reachable for c in result.checks)


def test_a_failing_model_is_named_with_the_providers_message():
    result = preflight(
        ["a/one", "b/gone"],
        probe=scripted(
            {
                "a/one": (True, None),
                "b/gone": (False, "NotFoundError: no longer available to new users"),
            }
        ),
    )

    assert result.ok is False
    failed = next(c for c in result.checks if not c.reachable)
    assert failed.model == "b/gone"
    assert "no longer available to new users" in failed.reason


def test_a_failure_message_is_redacted():
    result = preflight(
        ["a/one"],
        probe=scripted(
            {"a/one": (False, "auth failed for sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFF")}
        ),
    )

    assert "sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFF" not in result.checks[0].reason
    assert "REDACTED" in result.checks[0].reason


def test_the_total_cost_of_the_preflight_is_reported():
    result = preflight(
        ["a/one", "b/two"],
        probe=scripted({"a/one": (True, None), "b/two": (True, None)}),
    )

    assert result.total_cost == 0.00004


def test_duplicate_models_are_probed_once():
    """A rater and a judge on the same model should not cost two calls."""
    calls = []

    def counting(model: str) -> ModelCheck:
        calls.append(model)
        return ModelCheck(model=model, reachable=True, reason=None, cost=0.00001)

    preflight(["a/one", "b/two", "a/one"], probe=counting)

    assert calls.count("a/one") == 1


def test_rendering_names_every_model_and_the_cost():
    result = preflight(
        ["a/one", "b/gone"],
        probe=scripted({"a/one": (True, None), "b/gone": (False, "boom")}),
    )

    rendered = result.render()

    assert "a/one" in rendered
    assert "b/gone" in rendered
    assert "boom" in rendered
