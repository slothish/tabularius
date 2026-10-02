# SPDX-License-Identifier: GPL-3.0-or-later
"""Retention arithmetic (DESIGN.md §8.1, §12.3)."""

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

from hledger_tab.contracts.primitives import Retention, ShardName
from hledger_tab.core.retention import (
    deletable_from,
    expires,
    is_end_of_year,
    retention_years,
    shard_for,
)

# --- The DESIGN example -----------------------------------------------------


def test_design_example() -> None:
    # §7.3 / §8.1: issued 2026-09-28, retention P10Y.
    expiry = expires(date(2026, 9, 28), "P10Y")
    assert expiry == date(2036, 12, 31)
    assert shard_for(expiry) == "2036"
    assert deletable_from("2036") == date(2037, 1, 1)


# --- expires ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("issued", "retention", "expected"),
    [
        (date(2026, 1, 1), "P10Y", date(2036, 12, 31)),  # first day of year
        (date(2026, 12, 31), "P10Y", date(2036, 12, 31)),  # last day of year
        (date(2024, 2, 29), "P1Y", date(2025, 12, 31)),  # leap day, to non-leap
        (date(2024, 2, 29), "P4Y", date(2028, 12, 31)),  # leap day, to leap
        (date(2026, 9, 28), "P1Y", date(2027, 12, 31)),
        (date(2026, 9, 28), "P7Y", date(2033, 12, 31)),
    ],
)
def test_expires(issued: date, retention: str, expected: date) -> None:
    assert expires(issued, retention) == expected


def test_expires_open() -> None:
    assert expires(date(2026, 9, 28), "open") is None


def test_expires_depends_only_on_the_issue_year() -> None:
    assert expires(date(2026, 1, 1), "P10Y") == expires(date(2026, 12, 31), "P10Y")
    assert expires(date(2026, 12, 31), "P10Y") != expires(date(2027, 1, 1), "P10Y")


@pytest.mark.parametrize(
    "retention", ["P0Y", "P01Y", "P10M", "P1Y6M", "10", "", "Open"]
)
def test_expires_rejects_bad_retention(retention: str) -> None:
    with pytest.raises(ValueError, match="not a retention"):
        expires(date(2026, 9, 28), retention)


def test_expires_past_year_9999_raises() -> None:
    with pytest.raises(ValueError):
        expires(date(9990, 1, 1), "P10Y")


# --- shard_for --------------------------------------------------------------


def test_shard_for() -> None:
    assert shard_for(date(2036, 12, 31)) == "2036"
    assert shard_for(None) == "open"


@pytest.mark.parametrize(
    "day", [date(2036, 12, 30), date(2036, 1, 1), date(2037, 1, 1)]
)
def test_shard_for_requires_31_december(day: date) -> None:
    with pytest.raises(ValueError, match="31 December"):
        shard_for(day)


# --- deletable_from ---------------------------------------------------------


def test_deletable_from() -> None:
    assert deletable_from("2036") == date(2037, 1, 1)
    assert deletable_from("open") is None


@pytest.mark.parametrize("shard", ["36", "02036", "Open", "2036-12-31", ""])
def test_deletable_from_rejects_bad_shard(shard: str) -> None:
    with pytest.raises(ValueError, match="not a shard name"):
        deletable_from(shard)


def test_deletable_from_last_representable_shard() -> None:
    # "9999" is a well-formed shard, but 10000-01-01 is not a date.
    with pytest.raises(ValueError, match="out of range"):
        deletable_from("9999")


# --- Properties -------------------------------------------------------------

retention_strings = st.integers(min_value=1, max_value=200).map(lambda n: f"P{n}Y")
issue_dates = st.dates(min_value=date(1900, 1, 1), max_value=date(2700, 12, 31))


@given(issued=issue_dates, retention=retention_strings)
def test_property_expiry_chain(issued: date, retention: str) -> None:
    years = retention_years(retention)
    assert years is not None
    expiry = expires(issued, retention)
    assert expiry is not None
    # Expiry is the end of the calendar year, n years after the issue year.
    assert is_end_of_year(expiry)
    assert expiry.year == issued.year + years
    assert expiry > issued
    # The shard is named after the expiry year ...
    shard = shard_for(expiry)
    assert shard == str(expiry.year)
    # ... and may be deleted from the day after expiry.
    assert deletable_from(shard) == expiry + timedelta(days=1)


@given(issued=issue_dates)
def test_property_open_stays_open(issued: date) -> None:
    expiry = expires(issued, "open")
    assert expiry is None
    assert shard_for(expiry) == "open"
    assert deletable_from(shard_for(expiry)) is None


# --- Agreement with the contracts -------------------------------------------
# The contracts take their patterns from core.retention; these tests check
# that what one side accepts, the other side accepts too.

RETENTION = TypeAdapter[str](Retention)
SHARD = TypeAdapter[str](ShardName)


@given(st.one_of(retention_strings, st.just("open"), st.text(max_size=8)))
def test_property_contract_and_retention_agree(text: str) -> None:
    try:
        RETENTION.validate_python(text)
    except ValidationError:
        contract_ok = False
    else:
        contract_ok = True
    try:
        retention_years(text)
    except ValueError:
        function_ok = False
    else:
        function_ok = True
    assert contract_ok == function_ok


@given(
    st.one_of(st.integers(1000, 9998).map(str), st.just("open"), st.text(max_size=6))
)
def test_property_shard_contract_and_function_agree(text: str) -> None:
    try:
        SHARD.validate_python(text)
    except ValidationError:
        contract_ok = False
    else:
        contract_ok = True
    try:
        deletable_from(text)
    except ValueError:
        function_ok = False
    else:
        function_ok = True
    assert contract_ok == function_ok
