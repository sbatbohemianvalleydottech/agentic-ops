import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from ensemble.env import load_env
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
    parser.add_argument("--corpus", required=True, type=Path, help="directory of RCA JSON")
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


def main(argv: list[str] | None = None) -> int:
    load_env()
    args = build_parser().parse_args(argv)

    rubric = load_rubric(args.rubric)
    corpus = load_corpus(args.corpus)

    assessor = None
    if args.judgement:
        missing = [
            key
            for key in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY")
            if not os.environ.get(key)
        ]
        if missing:
            print(f"--judgement needs {' and '.join(missing)}.", file=sys.stderr)
            return 1
        try:
            from ensemble.orchestrator import Rater
            from ensemble.providers.litellm import LiteLLMProvider

            from .judgement import assess_judgement
        except ImportError:
            print('litellm not installed. pip install -e ".[providers]"', file=sys.stderr)
            return 1

        provider = LiteLLMProvider()
        ledger = Ledger(Path(".ledger/calls.jsonl"))
        raters = [
            Rater(provider, os.environ.get("RATER_A", "anthropic/claude-opus-5")),
            Rater(provider, os.environ.get("RATER_B", "gemini/gemini-3.8-flash")),
        ]
        judge = Rater(provider, os.environ.get("JUDGE", "anthropic/claude-sonnet-5"))

        def assessor(rca):  # noqa: F811
            return assess_judgement(
                rca, rubric, raters=raters, judge=judge, ledger=ledger
            )

    for rca in corpus:
        review = check_structure(rca, rubric, args.as_of)
        grades = assessor(rca) if assessor else None
        print(render_review(review, grades))

    if args.completion:
        print(render_completion(report_completion(corpus, rubric, args.as_of)))

    return 0
