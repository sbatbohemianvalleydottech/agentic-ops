import argparse
import os
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from ensemble.env import load_env, setting
from ledger import Ledger

from .pipeline import analyse
from .report import render_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cost_agent",
        description=(
            "Find the structural reasons a cloud bill is what it is, rather than "
            "ranking line items by size."
        ),
    )
    parser.add_argument("--costs", required=True, type=Path, help="cost export CSV")
    parser.add_argument(
        "--inventory", required=True, type=Path, help="resource inventory JSON"
    )
    parser.add_argument(
        "--thresholds", type=Path, help="override the default threshold config"
    )
    parser.add_argument(
        "--as-of",
        type=datetime.fromisoformat,
        default=datetime.now().replace(microsecond=0),
        help=(
            "analysis date, ISO format. Passed in rather than read from the clock "
            "so a run can be reproduced exactly"
        ),
    )
    parser.add_argument(
        "--confidence",
        action="store_true",
        help=(
            "rate each driver's confidence with two independent assessors and a "
            "judge. The only part that spends money, and it needs API keys"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_env()
    args = build_parser().parse_args(argv)

    models = None
    analysis = analyse(
        args.costs,
        args.inventory,
        thresholds_path=args.thresholds,
        as_of=args.as_of,
    )

    if args.confidence:
        missing = [
            key
            for key in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY")
            if not os.environ.get(key)
        ]
        if missing:
            print(f"--confidence needs {' and '.join(missing)}.", file=sys.stderr)
            return 1

        try:
            from ensemble.orchestrator import Rater
            from ensemble.providers.litellm import LiteLLMProvider

            from .confidence import rate_confidence
        except ImportError:
            print('litellm not installed. pip install -e ".[providers]"', file=sys.stderr)
            return 1

        from ensemble.preflight import preflight
        from ensemble.progress import StderrProgress

        rater_a = setting("RATER_A", "anthropic/claude-opus-5")
        rater_b = setting("RATER_B", "gemini/gemini-3.8-flash")
        judge_model = setting("JUDGE", "anthropic/claude-sonnet-5")

        # One cheap call each before the expensive pass.
        check = preflight([rater_a, rater_b, judge_model])
        print(check.render(), file=sys.stderr)
        if not check.ok:
            print("Aborting before the run. Fix the above.", file=sys.stderr)
            return 1

        provider = LiteLLMProvider()
        ledger = Ledger(Path(".ledger/calls.jsonl"))
        progress = StderrProgress()
        models = (rater_a, rater_b, judge_model)
        analysis = replace(
            analysis,
            drivers=tuple(
                rate_confidence(
                    driver,
                    raters=[
                        Rater(provider, rater_a),
                        Rater(provider, rater_b),
                    ],
                    judge=Rater(provider, judge_model),
                    ledger=ledger,
                    as_of=args.as_of,
                    progress=progress,
                )
                for driver in analysis.drivers
            ),
        )

    print(render_report(analysis, models=models))
    return 0
