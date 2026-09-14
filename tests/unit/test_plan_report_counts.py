"""The coverage line counts in English.

"1 resource changes, 1 accounted for." Found on the first real Terraform plan
put through the tool, because real plans are frequently one resource and both
shipped fixtures have twelve. A report that cannot count invites the reader to
wonder what else it cannot count, and this one's entire job is to be trusted
about arithmetic.

Same defect, same week, as the one the cost analyser had. Fixed there first;
nobody looked here.
"""

import pytest

from plan_cost.report import _coverage_line


@pytest.mark.parametrize(
    "total,counted,expected",
    [
        (1, 1, "1 resource change, 1 accounted for."),
        (2, 2, "2 resource changes, 2 accounted for."),
        (12, 12, "12 resource changes, 12 accounted for."),
        (3, 1, "3 resource changes, 1 accounted for."),
        (0, 0, "0 resource changes, 0 accounted for."),
    ],
)
def test_the_coverage_line_counts_in_english(total, counted, expected):
    assert expected in _coverage_line(total, counted)


def test_the_line_is_still_indented_like_the_rest_of_the_block():
    assert _coverage_line(1, 1).startswith("  ")
