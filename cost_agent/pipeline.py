"""The whole analysis, end to end.

Deterministic and offline by default. Confidence is opt-in because it is the only
part that costs money, and the arithmetic a sceptical reader attacks should be
reproducible by them without an account.
"""

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from .classify import classify
from .drivers import Analysis, build_analysis
from .inputs import load_inputs
from .savings import estimate_savings
from .thresholds import Thresholds, load_thresholds


def analyse(
    cost_export_path: Path,
    inventory_path: Path,
    *,
    thresholds: Thresholds | None = None,
    thresholds_path: Path | None = None,
    as_of: datetime,
) -> Analysis:
    thresholds = thresholds or load_thresholds(thresholds_path)

    inputs = load_inputs(cost_export_path, inventory_path)
    findings = classify(inputs, thresholds, as_of)
    analysis = build_analysis(findings, inputs, thresholds)

    annual_by_resource = {
        resource.resource_id: resource.period_cost * thresholds.annualisation_multiplier
        for resource in inputs.matched
    }

    return replace(
        analysis,
        drivers=tuple(
            estimate_savings(driver, annual_by_resource, thresholds)
            for driver in analysis.drivers
        ),
    )


def total_attributed(analysis: Analysis) -> Decimal:
    return sum((driver.annual_cost for driver in analysis.drivers), Decimal("0"))
