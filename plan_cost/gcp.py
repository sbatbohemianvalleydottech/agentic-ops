"""One conversion from the Cloud Billing money representation into a Decimal.

Both billing APIs this tool reads, the Catalog and the Budget, express an
amount as an integer `units` plus an integer `nanos`, a billionth each. The
catalogue reader and the budget reader each need that conversion and each grew
its own private copy of it.

It lives here because it is a fact about the vendor's wire format rather than
about either feature, and because two copies of an arithmetic rule are two
places for it to drift.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

# A nano is a billionth, per the google.type.Money documentation both APIs use.
NANOS = Decimal(1_000_000_000)


def money_from_api(amount: Mapping[str, Any]) -> Decimal:
    """Turn `{"units": "12", "nanos": 250000000}` into `Decimal("12.25")`.

    An absent field and an explicit null both mean nothing, which is how the
    API omits a zero. Everything goes through `str` on the way in, so a price
    never passes through a float and a total is exact rather than close.
    """
    units = Decimal(str(amount.get("units", "0") or "0"))
    nanos = Decimal(str(amount.get("nanos", 0) or 0))
    return units + nanos / NANOS
