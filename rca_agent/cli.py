import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from ci import Exit
from ensemble.env import load_env, setting
from ledger import DEFAULT_PATH, Ledger

from .completion import report_completion
from .report import render_completion, render_review
from .rubric import load_rubric
from .structure import check_structure
from .types import load_corpus
from .worth_judging import below_bar


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
        "--fail-on-defects",
        action="store_true",
        help=(
            "exit 1 if any review has a structural defect, for use as a pipeline "
            "gate. Off by default: reporting is the default because a tool that "
            "starts failing builds on upgrade is a tool people pin and forget"
        ),
    )
    parser.add_argument(
        "--judgement",
        action="store_true",
        help=(
            "assess the judgement dimensions with two independent assessors and a "
            "judge. The only part that spends money"
        ),
    )
    parser.add_argument(
        "--judge-anyway",
        dest="judge_anyway",
        action="store_true",
        help=(
            "judge every review, including those the rubric's "
            "judgement_requires_any bar says record nothing to judge. The bar is "
            "a judgement about your documents, so you get to overrule it"
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
            return Exit.UNJUDGED
        result = preflight(
            list(configured_models()),
            ledger=Ledger(DEFAULT_PATH),
            caller="rca_agent --check",
        )
        print(result.render())
        return Exit.OK if result.ok else Exit.UNJUDGED

    if not args.corpus:
        print("--corpus is required unless running --check.", file=sys.stderr)
        return Exit.UNJUDGED

    rubric = load_rubric(args.rubric)
    try:
        corpus = load_corpus(args.corpus)
    except (OSError, ValueError) as exc:
        print(f"rca_agent: could not read the corpus: {exc}", file=sys.stderr)
        return Exit.UNJUDGED

    if not corpus:
        # Zero reviews is not a clean corpus, it is nothing to judge. This
        # exited 0 with an empty report, so a typo in a path produced a green
        # build, which is the shape of failure this repository objects to.
        print(
            f"rca_agent: no reviews found in {args.corpus}. An empty corpus is "
            "nothing to judge, not a clean bill of health",
            file=sys.stderr,
        )
        return Exit.UNJUDGED

    assessor = None
    models = None
    if args.judgement:
        missing = _needs_credentials()
        if missing:
            print(f"--judgement needs {' and '.join(missing)}.", file=sys.stderr)
            return Exit.UNJUDGED
        try:
            from ensemble.orchestrator import Rater
            from ensemble.preflight import preflight
            from ensemble.providers.litellm import LiteLLMProvider

            from .judgement import assess_judgement
        except ImportError:
            print('litellm not installed. pip install -e ".[providers]"', file=sys.stderr)
            return Exit.UNJUDGED

        rater_a, rater_b, judge_model = configured_models()

        # One cheap call each, before the expensive pass. Four separate
        # misconfigurations each cost a full run to discover before this existed.
        ledger = Ledger(DEFAULT_PATH)
        check = preflight(
            [rater_a, rater_b, judge_model], ledger=ledger, caller="rca_agent"
        )
        print(check.render(), file=sys.stderr)
        if not check.ok:
            print("Aborting before the run. Fix the above.", file=sys.stderr)
            return Exit.UNJUDGED

        from ensemble.progress import StderrProgress

        provider = LiteLLMProvider()
        raters = [Rater(provider, rater_a), Rater(provider, rater_b)]
        judge = Rater(provider, judge_model)
        progress = StderrProgress()
        models = (rater_a, rater_b, judge_model)

        def assessor(rca):  # noqa: F811
            return assess_judgement(
                rca, rubric, raters=raters, judge=judge, ledger=ledger,
                progress=progress,
            )

    defective: list[str] = []
    for rca in corpus:
        review = check_structure(rca, rubric, args.as_of)
        if review.defects:
            defective.append(rca.rca_id)

        # Checked before the assessor is called, never after, because the whole
        # point is the call that does not happen.
        unjudged = None if args.judge_anyway else below_bar(rca, rubric)
        grades = assessor(rca) if assessor and not unjudged else None

        print(
            render_review(
                review,
                grades,
                models=models if assessor else None,
                unjudged=unjudged if assessor else None,
            )
        )

    if args.completion:
        print(render_completion(report_completion(corpus, rubric, args.as_of)))

    if not args.fail_on_defects:
        return Exit.OK

    # The verdict goes to stderr so stdout stays the report. Only reviews that
    # actually failed a check are named: rca-hollow passes every structural
    # check and explains nothing, and naming it would tell a pipeline the free
    # layer caught something it did not.
    if defective:
        print(
            f"rca_agent: blocked. {len(defective)} of {len(corpus)} reviews carry a "
            f"structural defect: {', '.join(defective)}",
            file=sys.stderr,
        )
        return Exit.BLOCKED

    print(
        f"rca_agent: 0 of {len(corpus)} reviews carry a structural defect",
        file=sys.stderr,
    )
    return Exit.OK
