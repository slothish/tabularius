# SPDX-License-Identifier: GPL-3.0-or-later
"""Primitive types: hashes, UUIDv7, money, retention, payload references."""

import inspect
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

import hledger_tab.contracts.document
import hledger_tab.contracts.envelope
import hledger_tab.contracts.events
import hledger_tab.contracts.field
import hledger_tab.contracts.primitives
import hledger_tab.contracts.profile
from hledger_tab.contracts.primitives import (
    ContractModel,
    Money,
    PayloadRef,
    Retention,
    Sha256,
    ShardName,
    UUIDv7,
)

CONTRACT_MODULES = [
    hledger_tab.contracts.primitives,
    hledger_tab.contracts.envelope,
    hledger_tab.contracts.field,
    hledger_tab.contracts.events,
    hledger_tab.contracts.document,
    hledger_tab.contracts.profile,
]


def _all_models() -> list[type[BaseModel]]:
    models: list[type[BaseModel]] = []
    for module in CONTRACT_MODULES:
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseModel) and obj.__module__ == module.__name__:
                models.append(obj)
    return models


@pytest.mark.parametrize("model", _all_models(), ids=lambda m: m.__name__)
def test_every_model_forbids_extra_keys(model: type[BaseModel]) -> None:
    # Invariant 5: no silent dropping of unknown keys.
    assert issubclass(model, ContractModel)
    assert model.model_config.get("extra") == "forbid"


# --- Sha256 -----------------------------------------------------------------

SHA256 = TypeAdapter[str](Sha256)


def test_sha256_accepts_lowercase_hex() -> None:
    assert SHA256.validate_python("0" * 63 + "a") == "0" * 63 + "a"


@pytest.mark.parametrize(
    "value",
    ["A" * 64, "0" * 63, "0" * 65, "g" * 64, "0" * 64 + "\n", ""],
    ids=["uppercase", "short", "long", "non-hex", "trailing-newline", "empty"],
)
def test_sha256_rejects(value: str) -> None:
    with pytest.raises(ValidationError):
        SHA256.validate_python(value)


# --- UUIDv7 -----------------------------------------------------------------

UUID7 = TypeAdapter[Any](UUIDv7)


def test_uuidv7_accepts_version_7() -> None:
    assert UUID7.validate_python("0199a1c2-7b3e-7f10-9c41-2d8e5a6b0f11").version == 7


@pytest.mark.parametrize(
    "value",
    [
        "0199a1c2-7b3e-4f10-9c41-2d8e5a6b0f11",  # version 4
        "0199a1c2-7b3e-7f10-0c41-2d8e5a6b0f11",  # not the RFC variant
        "not-a-uuid",
    ],
)
def test_uuidv7_rejects(value: str) -> None:
    with pytest.raises(ValidationError):
        UUID7.validate_python(value)


# --- Money ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("449.00", Decimal("449.00")),
        (12, Decimal(12)),
        (Decimal("-1.5"), Decimal("-1.5")),
    ],
)
def test_money_amount_is_decimal(amount: object, expected: Decimal) -> None:
    money = Money.model_validate({"amount": amount, "currency": "SEK"})
    assert isinstance(money.amount, Decimal)
    assert money.amount == expected


def test_money_keeps_trailing_zeros() -> None:
    assert str(Money(amount=Decimal("449.00"), currency="SEK").amount) == "449.00"


def test_money_rejects_python_float() -> None:
    with pytest.raises(ValidationError, match="floats are not accepted"):
        Money.model_validate({"amount": 449.0, "currency": "SEK"})


def test_money_rejects_json_number_with_fraction() -> None:
    # A JSON number with a fraction arrives as a float.
    with pytest.raises(ValidationError, match="floats are not accepted"):
        Money.model_validate_json('{"amount": 449.00, "currency": "SEK"}')


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity", "abc", True])
def test_money_rejects_non_finite_and_non_numbers(amount: object) -> None:
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": amount, "currency": "SEK"})


@pytest.mark.parametrize("currency", ["sek", "SE", "SEKK", "S1K", ""])
def test_money_rejects_bad_currency(currency: str) -> None:
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": "1", "currency": currency})


def test_money_dumps_amount_as_string_in_json() -> None:
    money = Money(amount=Decimal("12500.00"), currency="SEK")
    assert money.model_dump(mode="json") == {"amount": "12500.00", "currency": "SEK"}


# --- Retention --------------------------------------------------------------

RETENTION = TypeAdapter[str](Retention)


@pytest.mark.parametrize("value", ["open", "P1Y", "P7Y", "P10Y", "P100Y"])
def test_retention_accepts(value: str) -> None:
    assert RETENTION.validate_python(value) == value


@pytest.mark.parametrize(
    "value", ["P0Y", "P01Y", "P10M", "P1Y6M", "P1.5Y", "10", "PY", "Open", "p10y", ""]
)
def test_retention_rejects(value: str) -> None:
    with pytest.raises(ValidationError):
        RETENTION.validate_python(value)


# --- Shard names ------------------------------------------------------------

SHARD = TypeAdapter[str](ShardName)


@pytest.mark.parametrize("value", ["open", "2036", "1999"])
def test_shard_name_accepts(value: str) -> None:
    assert SHARD.validate_python(value) == value


@pytest.mark.parametrize("value", ["036", "20360", "0999", "Open", "staging"])
def test_shard_name_rejects(value: str) -> None:
    with pytest.raises(ValidationError):
        SHARD.validate_python(value)


def test_shard_name_rejects_integer() -> None:
    # An unquoted YAML ``shard: 2036`` is an int and must not be coerced.
    with pytest.raises(ValidationError):
        SHARD.validate_python(2036)


# --- PayloadRef -------------------------------------------------------------


def test_payload_ref_accepts_true() -> None:
    assert PayloadRef.model_validate({"payload": True}).payload is True


@pytest.mark.parametrize(
    "data",
    [
        {"payload": 1},
        {"payload": "true"},
        {"payload": False},
        {},
        {"payload": True, "x": 1},
    ],
)
def test_payload_ref_rejects(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PayloadRef.model_validate(data)
