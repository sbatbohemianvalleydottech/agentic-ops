import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from ensemble.env import load_env, setting
from ledger import Ledger

from .completion import report_completion
from .report import render_completion, render_review
from .rubric import load_rubric
from .structure import check_structure
from .types import load_corpus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rca_agent",
        description=(
            "Catch the incident review that reads well and says nothing, and track "
            "whether its action items ever close."
        ),
    )
    parser.add_argument("--corpus", type=Path, help="directory of RCA JSON")
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "probe each configured model with one minimal call and exit. Costs a "
            "fraction of a cent and tells you what a failing run would have"
        ),
    )
    parser.add_argument("--rubric", type=Path, help="override the default rubric config")
    parser.add_argument(
        "--as-of",
        type=datetime.fromisoformat,
        default=datetime.now().replace(microsecond=0),
        help="analysis date, ISO format. A parameter so a run reproduces exactly",
    )
    parser.add_argument(
        "--completion", action="store_true", help="report action item completion"
    )
    parser.add_argument(
        "--judgement",
        action="store_true",
        help=(
            "assess the judgement dimensions with two independent assessors and a "
            "judge. The only part that spends money"
        ),
    )
    return parser


def configured_models() -> tuple[str, str, str]:
    return (
        setting("RATER_A", "anthropic/claude-opus-5"),
        setting("RATER_B", "gemini/gemini-3.8-flash"),
        setting("JUDGE", "anthropic/claude-sonnet-5"),
    )


def _needs_credentials() -> list[str]:
    return [
        key for key in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY") if not os.environ.get(key)
    ]


def main(argv: list[str] | None = None) -> int:
    load_env()
    args = build_parser().parse_args(argv)

    if args.check:
        from ensemble.preflight import preflight

        missing = _needs_credentials()
        if missing:
            print(f"--check needs {' and '.join(missing)}.", file=sys.stderr)
            return 1
        result = preflight(list(configured_models()))
        print(result.render())
        return 0 if result.ok else 1

    if not args.corpus:
        print("--corpus is required unless running --check.", file=sys.stderr)
        return 2

    rubric = load_rubric(args.rubric)
    corpus = load_corpus(args.corpus)

    assessor = None
    models = None
    if args.judgement:
        missing = _needs_credentials()
        if missing:
            print(f"--judgement needs {' and '.join(missing)}.", file=sys.stderr)
            return 1
        try:
            from ensemble.orchestrator import Rater
            from ensemble.preflight import preflight
            from ensemble.providers.litellm import LiteLLMProvider

            from .judgement import assess_judgement
        except ImportError:
            print('litellm not installed. pip install -e ".[providers]"', file=sys.stderr)
            return 1

        rater_a, rater_b, judge_model = configured_models()

        # One cheap call each, before the expensive pass. Four separate
        # misconfigurations each cost a full run to discover before this existed.
        check = preflight([rater_a, rater_b, judge_model])
        print(check.render(), file=sys.stderr)
        if not check.ok:
            print("Aborting before the run. Fix the above.", file=sys.stderr)
            return 1

        from ensemble.progress import StderrProgress

        provider = LiteLLMProvider()
        ledger = Ledger(Path(".ledger/calls.jsonl"))
        raters = [Rater(provider, rater_a), Rater(provider, rater_b)]
        judge = Rater(provider, judge_model)
        progress = StderrProgress()
        models = (rater_a, rater_b, judge_model)

        def assessor(rca):  # noqa: F811
            return assess_judgement(
                rca, rubric, raters=raters, judge=judge, ledger=ledger,
                progress=progress,
            )

    for rca in corpus:
        review = check_structure(rca, rubric, args.as_of)
        grades = assessor(rca) if assessor else None
        print(render_review(review, grades, models=models if assessor else None))

    if args.completion:
        print(render_completion(report_completion(corpus, rubric, args.as_of)))

    return 0
