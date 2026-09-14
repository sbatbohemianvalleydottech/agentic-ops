"""What one call cost, worked out in one place.

Three sites needed this and each had its own version. The provider preferred
the figure LiteLLM attaches to the response and fell back to recomputing it.
The preflight probe only ever recomputed, so it missed the cheaper and more
accurate path. The drafting demo did neither and recorded a hard zero, which
made it the one model call in the repository that the constitution's metering
rule did not actually cover.
"""

from ensemble.providers import call_cost


class Response:
    """Enough of a LiteLLM response for the cost path. Nothing else is touched."""

    def __init__(self, hidden=None):
        if hidden is not None:
            self._hidden_params = hidden


def test_the_figure_litellm_attaches_is_preferred(monkeypatch):
    """It is already computed and it accounts for cached tokens."""
    monkeypatch.setattr(
        "ensemble.providers._recompute", lambda response: 99.0, raising=False
    )
    assert call_cost(Response(hidden={"response_cost": 0.0123})) == 0.0123


def test_a_string_figure_is_still_a_number():
    assert call_cost(Response(hidden={"response_cost": "0.0123"})) == 0.0123


def test_it_recomputes_when_litellm_attached_nothing(monkeypatch):
    monkeypatch.setattr("ensemble.providers._recompute", lambda response: 0.0456)
    assert call_cost(Response(hidden={})) == 0.0456


def test_it_recomputes_when_there_are_no_hidden_params_at_all(monkeypatch):
    monkeypatch.setattr("ensemble.providers._recompute", lambda response: 0.0456)
    assert call_cost(Response()) == 0.0456


def test_a_null_response_cost_falls_through_rather_than_counting_as_zero(monkeypatch):
    """None means not computed. Treating it as 0.0 would under-report silently."""
    monkeypatch.setattr("ensemble.providers._recompute", lambda response: 0.0456)
    assert call_cost(Response(hidden={"response_cost": None})) == 0.0456


def test_an_explicit_zero_is_kept(monkeypatch):
    """A free call is a real answer, and must not be recomputed away."""
    monkeypatch.setattr("ensemble.providers._recompute", lambda response: 99.0)
    assert call_cost(Response(hidden={"response_cost": 0.0})) == 0.0


def test_a_model_with_no_published_price_costs_zero_rather_than_raising(monkeypatch):
    """Bookkeeping must never discard a verdict the model actually produced."""

    def explode(response):
        raise RuntimeError("this model is not in the price map")

    monkeypatch.setattr("ensemble.providers._recompute", explode)
    assert call_cost(Response(hidden={})) == 0.0


def test_a_garbage_response_costs_zero_rather_than_raising(monkeypatch):
    monkeypatch.setattr("ensemble.providers._recompute", explode_on_anything)
    assert call_cost(object()) == 0.0


def explode_on_anything(response):
    raise ValueError("nothing usable here")
