# SPDX-License-Identifier: GPL-3.0-or-later
"""Type profiles and templates (DESIGN.md §8.1, §8.2)."""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from hledger_tab.contracts.profile import (
    HledgerAction,
    Template,
    TemplateStatus,
    TypeProfile,
)

type Loader = Callable[[str], dict[str, Any]]


@pytest.fixture
def type_data(load: Loader) -> dict[str, Any]:
    return load("type_invoice.yaml")


@pytest.fixture
def template_data(load: Loader) -> dict[str, Any]:
    return load("template_example-invoice.yaml")


# --- Type profile -----------------------------------------------------------


def test_type_example_validates(type_data: dict[str, Any]) -> None:
    profile = TypeProfile.model_validate(type_data)
    assert profile.id == "invoice"
    assert profile.version == 2
    assert profile.retention == "P10Y"
    assert profile.issued_field == "issue_date"
    assert profile.on_confirm.hledger is HledgerAction.PAYABLE
    assert profile.sensitive_keys == frozenset()


def test_type_round_trip(type_data: dict[str, Any]) -> None:
    profile = TypeProfile.model_validate(type_data)
    assert TypeProfile.model_validate(profile.model_dump(mode="json")) == profile


def test_type_defaults(type_data: dict[str, Any]) -> None:
    del type_data["uniqueness"], type_data["on_confirm"]
    profile = TypeProfile.model_validate(type_data)
    assert profile.uniqueness == []
    assert profile.on_confirm.hledger is None


def test_open_retention(type_data: dict[str, Any]) -> None:
    type_data["retention"] = "open"
    assert TypeProfile.model_validate(type_data).retention == "open"


@pytest.mark.parametrize("retention", ["P0Y", "P10M", "10", "forever"])
def test_bad_retention_rejected(type_data: dict[str, Any], retention: str) -> None:
    type_data["retention"] = retention
    with pytest.raises(ValidationError):
        TypeProfile.model_validate(type_data)


def test_type_unknown_key_rejected(type_data: dict[str, Any]) -> None:
    type_data["owner"] = "club"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TypeProfile.model_validate(type_data)


def test_field_definition_unknown_key_rejected(type_data: dict[str, Any]) -> None:
    type_data["fields"]["ocr"]["checksum"] = "luhn"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TypeProfile.model_validate(type_data)


def test_type_schema_required(type_data: dict[str, Any]) -> None:
    del type_data["schema"]
    with pytest.raises(ValidationError, match="Field required"):
        TypeProfile.model_validate(type_data)


def test_sensitive_keys(type_data: dict[str, Any]) -> None:
    type_data["fields"]["holder"] = {"type": "text", "sensitive": True}
    assert TypeProfile.model_validate(type_data).sensitive_keys == {"holder"}


def test_no_issued_field_rejected(type_data: dict[str, Any]) -> None:
    del type_data["fields"]["issue_date"]["role"]
    with pytest.raises(
        ValidationError, match="exactly one field must have role: issued"
    ):
        TypeProfile.model_validate(type_data)


def test_two_issued_fields_rejected(type_data: dict[str, Any]) -> None:
    type_data["fields"]["due_date"]["role"] = "issued"
    with pytest.raises(ValidationError, match=r"found 2 \(issue_date, due_date\)"):
        TypeProfile.model_validate(type_data)


def test_issued_field_must_be_date(type_data: dict[str, Any]) -> None:
    del type_data["fields"]["issue_date"]["role"]
    type_data["fields"]["invoice_no"]["role"] = "issued"
    with pytest.raises(ValidationError, match="must be of type date"):
        TypeProfile.model_validate(type_data)


def test_identifier_needs_kind(type_data: dict[str, Any]) -> None:
    del type_data["fields"]["ocr"]["kind"]
    with pytest.raises(ValidationError, match="needs a kind"):
        TypeProfile.model_validate(type_data)


def test_kind_only_on_identifier(type_data: dict[str, Any]) -> None:
    type_data["fields"]["amount_due"]["kind"] = "ocr"
    with pytest.raises(ValidationError, match="kind is only allowed"):
        TypeProfile.model_validate(type_data)


def test_enum_options(type_data: dict[str, Any]) -> None:
    type_data["fields"]["period"] = {"type": "enum", "options": ["monthly", "yearly"]}
    assert TypeProfile.model_validate(type_data).fields["period"].options == [
        "monthly",
        "yearly",
    ]


@pytest.mark.parametrize("options", [None, [], ["a", "a"]])
def test_enum_needs_unique_options(type_data: dict[str, Any], options: object) -> None:
    type_data["fields"]["period"] = {"type": "enum", "options": options}
    with pytest.raises(ValidationError):
        TypeProfile.model_validate(type_data)


def test_options_only_on_enum(type_data: dict[str, Any]) -> None:
    type_data["fields"]["amount_due"]["options"] = ["a"]
    with pytest.raises(ValidationError, match="options are only allowed"):
        TypeProfile.model_validate(type_data)


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("supplier", "no field 'supplier'"),
        ("correspondent.vat", "only party fields have sub-keys"),
        ("invoice_no.value", "only party fields have sub-keys"),
    ],
)
def test_bad_uniqueness_path(
    type_data: dict[str, Any], path: str, message: str
) -> None:
    type_data["uniqueness"] = [path]
    with pytest.raises(ValidationError, match=message):
        TypeProfile.model_validate(type_data)


def test_field_description(type_data: dict[str, Any]) -> None:
    text = "The total the supplier asks for, including VAT"
    type_data["fields"]["amount_due"]["description"] = text
    profile = TypeProfile.model_validate(type_data)
    assert profile.fields["amount_due"].description == text
    assert profile.fields["ocr"].description is None


def test_field_key_must_be_snake_case(type_data: dict[str, Any]) -> None:
    type_data["fields"]["Due date"] = {"type": "date"}
    with pytest.raises(ValidationError):
        TypeProfile.model_validate(type_data)


# --- Template ---------------------------------------------------------------


def test_template_example_validates(template_data: dict[str, Any]) -> None:
    template = Template.model_validate(template_data)
    assert template.type == "invoice@2"
    assert template.status is TemplateStatus.ACTIVE
    assert template.extract["ocr"].pattern == r"(\d{6,25})"


def test_template_round_trip(template_data: dict[str, Any]) -> None:
    template = Template.model_validate(template_data)
    assert Template.model_validate(template.model_dump(mode="json")) == template


@pytest.mark.parametrize("pattern", ["([0-9]+", "*abc", r"(?P<x>a)(?P<x>b)"])
def test_pattern_must_compile(template_data: dict[str, Any], pattern: str) -> None:
    template_data["extract"]["ocr"]["pattern"] = pattern
    with pytest.raises(ValidationError, match="not a valid regular expression"):
        Template.model_validate(template_data)


@pytest.mark.parametrize(
    "pattern",
    [r"\d{6,25}", r"(?:OCR)\s*\d+", r"(\d+)-(\d+)", r"((\d+))"],
    ids=["no-group", "non-capturing-only", "two-groups", "nested-groups"],
)
def test_pattern_needs_exactly_one_group(
    template_data: dict[str, Any], pattern: str
) -> None:
    template_data["extract"]["ocr"]["pattern"] = pattern
    with pytest.raises(ValidationError, match="exactly one capturing group"):
        Template.model_validate(template_data)


@pytest.mark.parametrize("pattern", [r"(\d+)", r"(?:OCR:)\s*(\d+)", r"(?P<ocr>\d+)"])
def test_pattern_with_one_group_accepted(
    template_data: dict[str, Any], pattern: str
) -> None:
    template_data["extract"]["ocr"]["pattern"] = pattern
    assert Template.model_validate(template_data).extract["ocr"].pattern == pattern


@pytest.mark.parametrize(
    "type_ref", ["invoice", "invoice@0", "invoice@v2", "Invoice@2"]
)
def test_type_ref_needs_version(template_data: dict[str, Any], type_ref: str) -> None:
    template_data["type"] = type_ref
    with pytest.raises(ValidationError):
        Template.model_validate(template_data)


@pytest.mark.parametrize("status", ["draft", "submitted", ""])
def test_bad_template_status(template_data: dict[str, Any], status: str) -> None:
    template_data["status"] = status
    with pytest.raises(ValidationError):
        Template.model_validate(template_data)


def test_template_match_needs_a_criterion(template_data: dict[str, Any]) -> None:
    template_data["match"] = {}
    with pytest.raises(ValidationError, match="at least one identifier or keyword"):
        Template.model_validate(template_data)


def test_template_match_identifier_kind_checked(template_data: dict[str, Any]) -> None:
    template_data["match"]["identifiers"] = {"ssn": "x"}
    with pytest.raises(ValidationError):
        Template.model_validate(template_data)


def test_extract_rule_needs_anchor(template_data: dict[str, Any]) -> None:
    del template_data["extract"]["ocr"]["anchor"]
    with pytest.raises(ValidationError, match="Field required"):
        Template.model_validate(template_data)


def test_template_unknown_key_rejected(template_data: dict[str, Any]) -> None:
    template_data["extract"]["ocr"]["flags"] = "i"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Template.model_validate(template_data)
