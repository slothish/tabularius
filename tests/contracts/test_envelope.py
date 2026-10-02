# SPDX-License-Identifier: GPL-3.0-or-later
"""The intake envelope (DESIGN.md §5.2)."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from hledger_tab.contracts.envelope import Channel, Envelope

type Loader = Callable[[str], dict[str, Any]]


@pytest.fixture
def data(load: Loader) -> dict[str, Any]:
    return load("envelope.json")


def test_example_validates(data: dict[str, Any]) -> None:
    envelope = Envelope.model_validate(data)
    assert envelope.channel is Channel.MAILDIR
    assert envelope.from_ == "faktura@example.se"
    assert envelope.received_at.utcoffset() is not None


def test_json_round_trip_is_lossless(data: dict[str, Any]) -> None:
    envelope = Envelope.model_validate(data)
    assert envelope.model_dump(mode="json") == data
    assert Envelope.model_validate_json(envelope.model_dump_json()) == envelope


def test_optional_from_and_subject(data: dict[str, Any]) -> None:
    del data["from"], data["subject"]
    envelope = Envelope.model_validate(data)
    assert envelope.from_ is None
    assert envelope.subject is None


@pytest.mark.parametrize("key", ["collection_hint", "from_", "schema_", "unexpected"])
def test_unknown_top_level_key_rejected(data: dict[str, Any], key: str) -> None:
    data[key] = "x"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Envelope.model_validate(data)


def test_unknown_file_key_rejected(data: dict[str, Any]) -> None:
    data["files"][0]["size"] = 123
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Envelope.model_validate(data)


@pytest.mark.parametrize(
    "key",
    ["intake_id", "schema", "channel", "adapter", "received_at", "source_ref", "files"],
)
def test_required_key_missing(data: dict[str, Any], key: str) -> None:
    del data[key]
    with pytest.raises(ValidationError, match="Field required"):
        Envelope.model_validate(data)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema", "envelope/2"),
        ("channel", "email"),
        ("adapter", "no-version"),
        ("received_at", "2026-10-02T08:14:03"),  # naive
        ("received_at", 0),
        ("received_at", 1728000000),
        ("received_at", "1728000000"),
        ("intake_id", "0199B2C4-1A2B-7C3D-8E4F-000000000001"),  # uppercase
        ("intake_id", "0199b2c41a2b7c3d8e4f000000000001"),  # unhyphenated
        ("intake_id", "0199b2c4-1a2b-4c3d-8e4f-000000000001"),  # UUIDv4
        ("files", []),
    ],
)
def test_bad_value_rejected(data: dict[str, Any], key: str, value: object) -> None:
    data[key] = value
    with pytest.raises(ValidationError):
        Envelope.model_validate(data)


@pytest.mark.parametrize("name", ["envelope.json", "..", ".", "a/b.pdf", ""])
def test_bad_file_name_rejected(data: dict[str, Any], name: str) -> None:
    data["files"][0]["name"] = name
    with pytest.raises(ValidationError):
        Envelope.model_validate(data)


def test_duplicate_file_names_rejected(data: dict[str, Any]) -> None:
    data["files"].append(dict(data["files"][0]))
    with pytest.raises(ValidationError, match="duplicate file names"):
        Envelope.model_validate(data)


def test_validates_from_json_text(load: Loader) -> None:
    text = json.dumps(load("envelope.json"))
    assert Envelope.model_validate_json(text).schema_ == "envelope/1"
