# SPDX-License-Identifier: GPL-3.0-or-later
"""Retention arithmetic: expiry date, shard name, deletion date.

Pure functions, no I/O (DESIGN.md §8.1, §12.3):

- ``expires`` = 31 December of (year of the issue date + the type's
  retention in years); ``None`` for ``open`` retention.
- A document lives in the shard named after its expiry year, or ``open``.
- A shard may be deleted from 1 January of the year after its name.

This module is the single home of these rules, including the textual forms
of a retention (``P<n>Y`` / ``open``) and a shard name (``YYYY`` / ``open``).
The contracts import the patterns and ``shard_for`` from here. It must
therefore not import from ``hledger_tab.contracts``.
"""

import re
from datetime import date
from typing import Final

OPEN: Final = "open"
"""The retention, and the shard, of documents with no fixed end."""

RETENTION_YEARS_PATTERN: Final = r"^P([1-9][0-9]*)Y$"
"""A whole-year ISO 8601 duration ``P<n>Y``, n >= 1, e.g. ``P10Y``."""

SHARD_PATTERN: Final = r"^(open|[1-9][0-9]{3})$"
"""A shard name: a four-digit expiry year, e.g. ``2036``, or ``open``."""

_RETENTION_YEARS = re.compile(RETENTION_YEARS_PATTERN)
_SHARD = re.compile(SHARD_PATTERN)


def is_end_of_year(day: date) -> bool:
    """Whether ``day`` is a 31 December, the only possible expiry (§8.1)."""
    return day.month == 12 and day.day == 31


def retention_years(retention: str) -> int | None:
    """The number of years in ``P<n>Y``; ``None`` for ``open``.

    Raises ``ValueError`` for anything else.
    """
    if retention == OPEN:
        return None
    match = _RETENTION_YEARS.fullmatch(retention)
    if match is None:
        raise ValueError(f"not a retention (P<n>Y or open): {retention!r}")
    return int(match.group(1))


def expires(issued: date, retention: str) -> date | None:
    """The expiry date: 31 December of (``issued.year`` + n) for ``P<n>Y``;
    ``None`` for ``open`` (§8.1, §12.3).

    >>> expires(date(2026, 9, 28), "P10Y")
    datetime.date(2036, 12, 31)
    """
    years = retention_years(retention)
    if years is None:
        return None
    return date(issued.year + years, 12, 31)


def shard_for(expires: date | None) -> str:
    """The shard a document with this expiry belongs to: its expiry year,
    e.g. ``"2036"``, or ``"open"`` for no expiry (§7.2, §12.3).

    Raises ``ValueError`` if ``expires`` is not a 31 December, or is before
    the year 1000 (shard names have exactly four digits, ``SHARD_PATTERN``).
    """
    if expires is None:
        return OPEN
    if not is_end_of_year(expires):
        raise ValueError(f"expiry must be a 31 December, got {expires}")
    if expires.year < 1000:
        raise ValueError(f"expiry year must have four digits, got {expires.year}")
    return str(expires.year)


def deletable_from(shard: str) -> date | None:
    """The first day the shard may be deleted: 1 January of the year after
    its name; ``None`` for ``open``, which never expires as a whole (§12.3,
    §12.4).

    Raises ``ValueError`` for a malformed shard name, and for ``"9999"``,
    whose next year is outside ``datetime.date``.
    """
    if _SHARD.fullmatch(shard) is None:
        raise ValueError(f"not a shard name (YYYY or open): {shard!r}")
    if shard == OPEN:
        return None
    return date(int(shard) + 1, 1, 1)
