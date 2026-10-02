# SPDX-License-Identifier: GPL-3.0-or-later
"""Primitive types: hashes, UUIDv7, money, retention, payload references."""

import inspect
import json
import re
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
import yaml
from pydantic import BaseModel, TypeAdapter, ValidationError

import hledger_tab.contracts.document
import hledger_tab.contracts.envelope
import hledger_tab.contracts.events
import hledger_tab.contracts.field
import hledger_tab.contracts.primitives
import hledger_tab.contracts.profile
from hledger_tab.contracts.primitives import (
    DATE_PATTERN,
    DECIMAL_PATTERN,
    TIMESTAMP_PATTERN,
    UUID7_PATTERN,
    Confidence,
    ContractModel,
    DecimalValue,
    IsoDate,
    Money,
    NonNegativeStrictInt,
    PayloadRef,
    PositiveStrictInt,
    Retention,
    Sha256,
    ShardName,
    Timestamp,
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
        "0199A1C2-7B3E-7F10-9C41-2D8E5A6B0F11",  # uppercase
        "{0199a1c2-7b3e-7f10-9c41-2d8e5a6b0f11}",  # braces
        "urn:uuid:0199a1c2-7b3e-7f10-9c41-2d8e5a6b0f11",  # URN
        "0199a1c27b3e7f109c412d8e5a6b0f11",  # unhyphenated
        " 0199a1c2-7b3e-7f10-9c41-2d8e5a6b0f11",  # leading space
    ],
)
def test_uuidv7_rejects(value: str) -> None:
    with pytest.raises(ValidationError):
        UUID7.validate_python(value)
    with pytest.raises(ValidationError):
        UUID7.validate_json(json.dumps(value))


def test_uuidv7_rejects_bytes_and_ints() -> None:
    uuid = UUID("0199a1c2-7b3e-7f10-9c41-2d8e5a6b0f11")
    for value in (uuid.bytes, uuid.int):
        with pytest.raises(ValidationError):
            UUID7.validate_python(value)


def test_uuidv7_accepts_uuid_object() -> None:
    uuid = UUID("0199a1c2-7b3e-7f10-9c41-2d8e5a6b0f11")
    assert UUID7.validate_python(uuid) == uuid


def test_uuidv7_schema_pattern() -> None:
    assert UUID7.json_schema()["pattern"] == UUID7_PATTERN


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


@pytest.mark.parametrize(
    "amount", ["1e3", " 1.5 ", "1_000", "01.5", "1.", ".5", "+1", "--1", "1,5", ""]
)
def test_money_rejects_loose_decimal_strings(amount: str) -> None:
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": amount, "currency": "SEK"})


DECIMAL = TypeAdapter[Decimal](DecimalValue)
DECIMAL_SAMPLES: list[object] = [
    0, 7, -12, 10**30, True, False, 1.5, 2.0,
    "0", "-0", "449.00", "-1.5", "12500", "0.001",
    "1e3", " 1.5", "1.5 ", "1_000", "01", "00.5", "1.", ".5", "+1", "-", "",
    "NaN", "Infinity", "1,5", None, [], {},
]  # fmt: skip


def _schema_accepts(schema: dict[str, Any], value: object) -> bool:
    """Evaluate the published ``anyOf`` of integer / patterned string."""
    for option in schema["anyOf"]:
        if option["type"] == "integer" and type(value) is int:
            return True
        if (
            option["type"] == "string"
            and isinstance(value, str)
            and re.search(option["pattern"], value)
        ):
            return True
    return False


def test_decimal_schema_is_integer_or_patterned_string() -> None:
    assert DECIMAL.json_schema() == {
        "anyOf": [
            {"type": "integer"},
            {"type": "string", "pattern": DECIMAL_PATTERN},
        ]
    }


@pytest.mark.parametrize("value", DECIMAL_SAMPLES, ids=repr)
def test_decimal_schema_and_validator_agree(value: object) -> None:
    try:
        DECIMAL.validate_python(value)
    except ValidationError:
        accepted = False
    else:
        accepted = True
    assert accepted == _schema_accepts(DECIMAL.json_schema(), value)


@pytest.mark.parametrize("value", DECIMAL_SAMPLES, ids=repr)
def test_decimal_json_input_agrees_with_schema(value: object) -> None:
    text = json.dumps(value)
    try:
        DECIMAL.validate_json(text)
    except ValidationError:
        accepted = False
    else:
        accepted = True
    assert accepted == _schema_accepts(DECIMAL.json_schema(), json.loads(text))


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


# --- Strict numbers, dates and timestamps -----------------------------------

POSITIVE = TypeAdapter[int](PositiveStrictInt)
NON_NEGATIVE = TypeAdapter[int](NonNegativeStrictInt)
CONFIDENCE = TypeAdapter[float](Confidence)
ISO_DATE = TypeAdapter[date](IsoDate)
TIMESTAMP = TypeAdapter[datetime](Timestamp)


@pytest.mark.parametrize("value", [True, "2", 2.0, 0, -1, None])
def test_positive_strict_int_rejects(value: object) -> None:
    with pytest.raises(ValidationError):
        POSITIVE.validate_python(value)


@pytest.mark.parametrize("text", ["true", '"2"', "2.0", "0"])
def test_positive_strict_int_rejects_json(text: str) -> None:
    with pytest.raises(ValidationError):
        POSITIVE.validate_json(text)


def test_strict_ints_accept_ints() -> None:
    assert POSITIVE.validate_python(2) == 2
    assert POSITIVE.validate_json("2") == 2
    assert NON_NEGATIVE.validate_python(0) == 0


@pytest.mark.parametrize("value", [False, "0", -1, 2.0])
def test_non_negative_strict_int_rejects(value: object) -> None:
    with pytest.raises(ValidationError):
        NON_NEGATIVE.validate_python(value)


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0, 0, 1])
def test_confidence_accepts(value: float) -> None:
    assert CONFIDENCE.validate_python(value) == value


@pytest.mark.parametrize("value", [True, False, "0.5", -0.1, 1.1, 2])
def test_confidence_rejects(value: object) -> None:
    with pytest.raises(ValidationError):
        CONFIDENCE.validate_python(value)


def test_confidence_rejects_json_bool_and_string() -> None:
    for text in ("true", '"0.5"'):
        with pytest.raises(ValidationError):
            CONFIDENCE.validate_json(text)


def test_iso_date_accepts_strings_and_dates() -> None:
    assert ISO_DATE.validate_python("2026-09-28") == date(2026, 9, 28)
    assert ISO_DATE.validate_python(date(2026, 9, 28)) == date(2026, 9, 28)
    assert ISO_DATE.validate_json('"2026-09-28"') == date(2026, 9, 28)


@pytest.mark.parametrize(
    "value", [1728000000, 1728000000.0, True, 0, "1728000000", "0", "28/09/2026"]
)
def test_iso_date_rejects_numbers_and_timestamps(value: object) -> None:
    with pytest.raises(ValidationError):
        ISO_DATE.validate_python(value)


def test_iso_date_rejects_json_number() -> None:
    with pytest.raises(ValidationError):
        ISO_DATE.validate_json("1728000000")


def test_timestamp_accepts_iso_strings_and_datetimes() -> None:
    expected = datetime(2026, 10, 2, 9, 12, tzinfo=UTC)
    assert TIMESTAMP.validate_python("2026-10-02T09:12:00Z") == expected
    assert TIMESTAMP.validate_python(expected) == expected
    assert TIMESTAMP.validate_json('"2026-10-02T09:12:00Z"') == expected


@pytest.mark.parametrize(
    "value", [0, 1728000000, 1728000000.5, True, "0", "1728000000", "2026-10-02T09:12"]
)
def test_timestamp_rejects_numbers_and_naive(value: object) -> None:
    with pytest.raises(ValidationError):
        TIMESTAMP.validate_python(value)


def test_timestamp_rejects_json_number() -> None:
    with pytest.raises(ValidationError):
        TIMESTAMP.validate_json("0")


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 10, 2, tzinfo=UTC),
        datetime(2026, 10, 2),
        "2026-10-02T00:00:00Z",
        "2026-10-02T00:00:00",
        "2026-10-02 00:00",
        "2026-9-28",
        "2026-09-28 ",
        "20260928",
    ],
    ids=repr,
)
def test_iso_date_rejects_non_canonical(value: object) -> None:
    with pytest.raises(ValidationError):
        ISO_DATE.validate_python(value)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-10-02T09:12:00Z", datetime(2026, 10, 2, 9, 12, tzinfo=UTC)),
        (
            "2026-10-02T11:12:00+02:00",
            datetime(2026, 10, 2, 11, 12, tzinfo=timezone(timedelta(hours=2))),
        ),
        (
            "2026-10-02T09:12:00.123456Z",
            datetime(2026, 10, 2, 9, 12, 0, 123456, tzinfo=UTC),
        ),
        ("2026-10-02T09:12:00.5-05:00", None),
    ],
)
def test_timestamp_accepts_rfc3339(text: str, expected: datetime | None) -> None:
    parsed = TIMESTAMP.validate_python(text)
    if expected is not None:
        assert parsed == expected


@pytest.mark.parametrize(
    "text",
    [
        "2026-10-02 09:12:00Z",  # space instead of T
        "2026-10-02t09:12:00Z",  # lowercase t
        "2026-10-02T09:12:00z",  # lowercase z
        "2026-10-02T09:12Z",  # no seconds
        "2026-10-02T09:12:00+0200",  # offset without colon
        "2026-10-02T09:12:00+02",  # offset without minutes
        "2026-10-02T09:12:00.1234567Z",  # 7 fractional digits
        "2026-10-02T09:12:00.Z",  # empty fraction
        "2026-10-02",  # date only
    ],
)
def test_timestamp_rejects_non_canonical(text: str) -> None:
    with pytest.raises(ValidationError, match="RFC 3339"):
        TIMESTAMP.validate_python(text)
    with pytest.raises(ValidationError):
        TIMESTAMP.validate_json(json.dumps(text))


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 10, 2, 9, 12, tzinfo=UTC),
        datetime(2026, 10, 2, 9, 12, 0, 1, tzinfo=timezone(timedelta(hours=-5))),
        datetime(
            2026, 10, 2, 9, 12, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))
        ),
    ],
)
def test_timestamp_dumps_in_canonical_form(value: datetime) -> None:
    dumped = TIMESTAMP.dump_python(value, mode="json")
    assert re.fullmatch(TIMESTAMP_PATTERN, dumped), dumped
    assert TIMESTAMP.validate_python(dumped) == value


def test_iso_date_dumps_in_canonical_form() -> None:
    dumped = ISO_DATE.dump_python(date(2026, 9, 28), mode="json")
    assert dumped == "2026-09-28"
    assert re.fullmatch(DATE_PATTERN, dumped)


def test_date_and_timestamp_schemas_publish_patterns() -> None:
    assert ISO_DATE.json_schema()["pattern"] == DATE_PATTERN
    assert TIMESTAMP.json_schema()["pattern"] == TIMESTAMP_PATTERN


# --- Decimal serialisation ----------------------------------------------------

EXPONENT_DECIMALS = ["1E+3", "0E-7", "1.5E-10", "-2.50E+2", "1E+30", "-0"]


@pytest.mark.parametrize("text", EXPONENT_DECIMALS)
def test_decimal_dumps_in_plain_notation(text: str) -> None:
    value = Decimal(text)
    dumped = DECIMAL.dump_python(value, mode="json")
    assert re.fullmatch(DECIMAL_PATTERN, dumped), dumped
    assert DECIMAL.dump_json(value) == json.dumps(dumped).encode()
    assert DECIMAL.validate_python(dumped) == value


@pytest.mark.parametrize("text", EXPONENT_DECIMALS)
def test_money_with_exponent_round_trips(text: str) -> None:
    money = Money(amount=Decimal(text), currency="SEK")
    assert Money.model_validate(money.model_dump(mode="json")) == money
    assert Money.model_validate_json(money.model_dump_json()) == money
    reloaded = yaml.safe_load(yaml.safe_dump(money.model_dump(mode="json")))
    assert Money.model_validate(reloaded) == money


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
