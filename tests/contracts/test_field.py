# SPDX-License-Identifier: GPL-3.0-or-later
"""Field records (DESIGN.md §8.5)."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from hledger_tab.contracts.field import (
    FieldRecord,
    FieldType,
    IdentifierField,
    MoneyField,
    UnknownField,
    is_sensitive,
)
from hledger_tab.contracts.primitives import Money, PayloadRef

type Loader = Callable[[str], dict[str, Any]]

RECORD = TypeAdapter[FieldRecord](FieldRecord)

# One valid value per type in the §8.5 vocabulary.
VALUES: dict[str, dict[str, Any]] = {
    "text": {"value": "Telia"},
    "longtext": {"value": "line one\nline two"},
    "number": {"value": "42.5"},
    "money": {"value": {"amount": "449.00", "currency": "SEK"}},
    "date": {"value": "2026-09-28"},
    "enum": {"value": "monthly", "options": ["monthly", "yearly"]},
    "bool": {"value": True},
    "identifier": {"value": "4410287733", "kind": "ocr"},
    "party": {"value": {"name": "Example AB", "orgnr": "556000-0000"}},
    "table": {"value": {"columns": ["item", "amount"], "rows": [["A", "1,00"]]}},
    "unknown": {"value": {"anything": [1, "two", None, {"three": 3.0}]}},
}


def record(type_: str, **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"key": "some_field", "type": type_, "origin": "profile"}
    data.update(VALUES[type_])
    data.update(overrides)
    return data


def test_vocabulary_is_complete() -> None:
    assert set(VALUES) == {t.value for t in FieldType}


def test_design_example_validates(load: Loader) -> None:
    parsed = RECORD.validate_python(load("field_money.json"))
    assert isinstance(parsed, MoneyField)
    assert parsed.value == Money(amount=Decimal("449.00"), currency="SEK")


@pytest.mark.parametrize("type_", list(VALUES))
def test_each_type_validates_and_round_trips(type_: str) -> None:
    parsed = RECORD.validate_python(record(type_))
    assert parsed.type == type_
    dumped = RECORD.dump_python(parsed, mode="json")
    assert RECORD.validate_python(dumped) == parsed


@pytest.mark.parametrize("type_", list(VALUES))
def test_each_type_accepts_payload_ref(type_: str) -> None:
    parsed = RECORD.validate_python(record(type_, value={"payload": True}))
    assert isinstance(parsed.value, PayloadRef)


@pytest.mark.parametrize("type_", list(VALUES))
def test_each_type_accepts_null_value(type_: str) -> None:
    assert RECORD.validate_python(record(type_, value=None)).value is None


@pytest.mark.parametrize("type_", list(VALUES))
def test_each_type_requires_value_key(type_: str) -> None:
    data = record(type_)
    del data["value"]
    with pytest.raises(ValidationError, match="Field required"):
        RECORD.validate_python(data)


@pytest.mark.parametrize("type_", list(VALUES))
def test_unknown_key_rejected(type_: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RECORD.validate_python(record(type_, note="x"))


def test_unknown_nested_key_rejected() -> None:
    data = record("money", source={"page": 1, "method": "regex", "zoom": 2})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RECORD.validate_python(data)


def test_unknown_type_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RECORD.validate_python(
            {"key": "x", "type": "colour", "value": "red", "origin": "profile"}
        )
    assert [e["type"] for e in exc_info.value.errors()] == ["union_tag_invalid"]


@pytest.mark.parametrize(
    ("type_", "value"),
    [
        ("text", 12),
        ("number", 1.5),  # float
        ("number", "NaN"),
        ("money", {"amount": "1", "currency": "kr"}),
        ("date", "28/09/2026"),
        ("bool", "yes"),
        ("bool", 1),
        ("identifier", 4410287733),  # must be a string: leading zeros matter
        ("party", {"orgnr": "556000-0000"}),  # name missing
        ("table", {"columns": ["a", "b"], "rows": [["only one"]]}),
        ("table", {"columns": [], "rows": []}),
    ],
)
def test_bad_value_rejected(type_: str, value: object) -> None:
    with pytest.raises(ValidationError):
        RECORD.validate_python(record(type_, value=value))


def test_unknown_preserves_raw_json() -> None:
    raw = {"nested": {"list": [1, 2.5, "x", None, True]}}
    parsed = RECORD.validate_python(record("unknown", value=raw))
    assert isinstance(parsed, UnknownField)
    assert parsed.value == raw


def test_unknown_with_non_boolean_payload_is_raw_json() -> None:
    # ``{payload: 1}`` is not a payload reference; it is kept as data.
    parsed = RECORD.validate_python(record("unknown", value={"payload": 1}))
    assert parsed.value == {"payload": 1}


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_out_of_range(confidence: float) -> None:
    with pytest.raises(ValidationError):
        RECORD.validate_python(record("text", confidence=confidence))


@pytest.mark.parametrize(
    "bbox", [[10, 0, 5, 0], [0, 10, 0, 5], [-1, 0, 0, 0], [0, 0, 0]]
)
def test_bad_bbox_rejected(bbox: list[int]) -> None:
    with pytest.raises(ValidationError):
        RECORD.validate_python(
            record("text", source={"page": 1, "bbox": bbox, "method": "llm"})
        )


def test_page_is_one_based() -> None:
    with pytest.raises(ValidationError):
        RECORD.validate_python(record("text", source={"page": 0, "method": "llm"}))


def test_identifier_needs_valid_kind() -> None:
    data = record("identifier")
    del data["kind"]
    with pytest.raises(ValidationError):
        RECORD.validate_python(data)
    with pytest.raises(ValidationError):
        RECORD.validate_python(record("identifier", kind="ssn"))


def test_enum_needs_options() -> None:
    data = record("enum")
    del data["options"]
    with pytest.raises(ValidationError):
        RECORD.validate_python(data)


def test_enum_value_outside_options_is_representable() -> None:
    # Membership is a validator's verdict, not a schema error (invariant 5).
    parsed = RECORD.validate_python(
        record(
            "enum", value="weekly", validation={"ok": False, "message": "not an option"}
        )
    )
    assert parsed.value == "weekly"


def test_key_must_be_snake_case() -> None:
    with pytest.raises(ValidationError):
        RECORD.validate_python(record("text", key="Amount Due"))


def test_date_value_is_a_date() -> None:
    assert RECORD.validate_python(record("date")).value == date(2026, 9, 28)


# --- is_sensitive (§7.3, §7.6) ----------------------------------------------


def _identifier(kind: str, key: str = "some_field") -> IdentifierField:
    parsed = RECORD.validate_python(record("identifier", kind=kind, key=key))
    assert isinstance(parsed, IdentifierField)
    return parsed


def test_personnummer_is_always_sensitive() -> None:
    assert is_sensitive(_identifier("personnummer"))
    discovered = RECORD.validate_python(
        record("identifier", kind="personnummer", origin="discovered")
    )
    assert is_sensitive(discovered)


def test_other_identifier_kinds_are_not_sensitive_by_default() -> None:
    assert not is_sensitive(_identifier("ocr"))
    assert not is_sensitive(_identifier("orgnr"))


def test_profile_marked_field_is_sensitive() -> None:
    text = RECORD.validate_python(record("text", key="member_name"))
    assert not is_sensitive(text)
    assert is_sensitive(text, frozenset({"member_name"}))


def test_profile_cannot_unmark_personnummer() -> None:
    # Whatever the profile marks, a personnummer stays sensitive.
    assert is_sensitive(_identifier("personnummer", key="pnr"), frozenset({"other"}))
