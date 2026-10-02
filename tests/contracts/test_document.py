# SPDX-License-Identifier: GPL-3.0-or-later
"""The document sidecar (DESIGN.md §7.3)."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from hledger_tab.contracts.document import Document, Status
from hledger_tab.contracts.primitives import PayloadRef

type Loader = Callable[[str], dict[str, Any]]


@pytest.fixture
def data(load: Loader) -> dict[str, Any]:
    return load("document.yaml")


def test_example_validates(data: dict[str, Any]) -> None:
    doc = Document.model_validate(data)
    assert doc.status is Status.CONFIRMED
    assert doc.issued == date(2026, 9, 28)
    assert doc.expires == date(2036, 12, 31)
    assert doc.shard == "2036"
    assert isinstance(doc.fields[1].value, PayloadRef)
    assert [e.type for e in doc.events] == [
        "received",
        "confirmed",
        "payable_recorded",
        "shred_ok",
    ]


def test_example_has_every_design_key(data: dict[str, Any]) -> None:
    # Every key of the §7.3 example is present in the fixture and the model.
    keys = {
        "id", "schema", "intake", "container", "source", "classification",
        "fields", "status", "issued", "expires", "shard", "hold",
        "payload_sha256", "events", "links",
    }  # fmt: skip
    assert set(data) == keys
    assert {f.alias or name for name, f in Document.model_fields.items()} == keys


def test_round_trip_is_lossless(data: dict[str, Any]) -> None:
    doc = Document.model_validate(data)
    dumped = doc.model_dump(mode="json", exclude_none=False)
    assert Document.model_validate(dumped) == doc
    assert Document.model_validate_json(doc.model_dump_json()) == doc


STAGING = ["received", "needs_review", "quarantined"]


@pytest.mark.parametrize("status", STAGING)
def test_staging_document_has_no_shard(data: dict[str, Any], status: str) -> None:
    data.update(status=status, issued=None, expires=None, shard=None)
    data["classification"] = None
    assert Document.model_validate(data).shard is None


@pytest.mark.parametrize("status", STAGING)
def test_staging_document_may_have_provisional_expiry(
    data: dict[str, Any], status: str
) -> None:
    data.update(status=status, shard=None)
    assert Document.model_validate(data).expires == date(2036, 12, 31)


@pytest.mark.parametrize("shard", ["2036", "open"])
@pytest.mark.parametrize("status", STAGING)
def test_staging_document_rejects_shard(
    data: dict[str, Any], status: str, shard: str
) -> None:
    data.update(status=status, shard=shard)
    with pytest.raises(ValidationError, match="shard must be null in staging"):
        Document.model_validate(data)


@pytest.mark.parametrize("status", ["confirmed", "filed"])
def test_assigned_document_needs_shard(data: dict[str, Any], status: str) -> None:
    data.update(status=status, shard=None)
    with pytest.raises(ValidationError, match="shard must be set"):
        Document.model_validate(data)


def test_container_is_optional(data: dict[str, Any]) -> None:
    del data["container"]
    assert Document.model_validate(data).container is None


@pytest.mark.parametrize(
    "key",
    [
        "id", "schema", "intake", "source", "classification", "fields", "status",
        "issued", "expires", "shard", "hold", "payload_sha256", "events", "links",
    ],
)  # fmt: skip
def test_required_key_missing(data: dict[str, Any], key: str) -> None:
    del data[key]
    with pytest.raises(ValidationError, match="Field required"):
        Document.model_validate(data)


def test_unknown_key_rejected(data: dict[str, Any]) -> None:
    data["collection"] = "personal"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Document.model_validate(data)


@pytest.mark.parametrize(
    "path",
    [
        ("source", "original"),
        ("source", "archive"),
        ("classification",),
        ("links",),
    ],
)
def test_unknown_nested_key_rejected(
    data: dict[str, Any], path: tuple[str, ...]
) -> None:
    target = data
    for part in path:
        target = target[part]
    target["unexpected"] = {"x": 1}
    with pytest.raises(ValidationError):
        Document.model_validate(data)


def test_archive_tools_is_an_open_mapping(data: dict[str, Any]) -> None:
    # ``tools`` maps tool name -> version; any tool name is data, not a key.
    data["source"]["archive"]["tools"]["veraPDF"] = "1.28"
    doc = Document.model_validate(data)
    assert doc.source.archive is not None
    assert doc.source.archive.tools["veraPDF"] == "1.28"


@pytest.mark.parametrize("status", ["submitted", "expired", "deleted"])
def test_removed_statuses_rejected(data: dict[str, Any], status: str) -> None:
    data["status"] = status
    with pytest.raises(ValidationError):
        Document.model_validate(data)


def test_hold_parses(data: dict[str, Any]) -> None:
    data["hold"] = {"reason": "tax audit", "since": date(2031, 3, 1), "by": "andreas"}
    doc = Document.model_validate(data)
    assert doc.hold is not None
    assert doc.hold.since == date(2031, 3, 1)


# --- Model-level checks -----------------------------------------------------


@pytest.mark.parametrize(
    "expires", [date(2036, 12, 30), date(2036, 1, 1), date(2036, 6, 30)]
)
def test_expires_must_be_31_december(data: dict[str, Any], expires: date) -> None:
    data["expires"] = expires
    with pytest.raises(ValidationError, match="31 December"):
        Document.model_validate(data)


@pytest.mark.parametrize(
    ("expires", "shard"),
    [
        (date(2036, 12, 31), "2035"),
        (date(2036, 12, 31), "open"),
        (None, "2036"),
    ],
)
def test_shard_must_match_expires(
    data: dict[str, Any], expires: date | None, shard: str
) -> None:
    data.update(expires=expires, shard=shard)
    with pytest.raises(ValidationError, match="does not match expires"):
        Document.model_validate(data)


def test_open_shard_iff_no_expiry(data: dict[str, Any]) -> None:
    data.update(expires=None, shard="open")
    assert Document.model_validate(data).shard == "open"


@pytest.mark.parametrize(
    "expires", [date(2026, 12, 31), date(2025, 12, 31)], ids=["same-year", "earlier"]
)
def test_expires_must_be_after_issue_year(data: dict[str, Any], expires: date) -> None:
    data.update(expires=expires, shard=str(expires.year))
    with pytest.raises(ValidationError, match="must be in a later year"):
        Document.model_validate(data)


def test_expires_next_year_is_fine(data: dict[str, Any]) -> None:
    data.update(expires=date(2027, 12, 31), shard="2027")
    assert Document.model_validate(data).shard == "2027"


# --- Strict numbers and dates -------------------------------------------------


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("source", "original", "pages"), [True]),
        (("source", "original", "pages"), ["2"]),
        (("source", "original", "pages"), [2.0]),
        (("source", "original", "dpi"), True),
        (("source", "original", "dpi"), "300"),
        (("source", "original", "dpi"), 300.0),
        (("classification", "confidence"), True),
        (("classification", "confidence"), "0.5"),
        (("issued",), 1728000000),
        (("issued",), "1728000000"),
        (("issued",), 1728000000.0),
        (("issued",), True),
        (("expires",), 2085000000),
        (("hold",), {"reason": "audit", "since": 1900000000, "by": "andreas"}),
    ],
)
def test_lax_numbers_and_dates_rejected(
    data: dict[str, Any], path: tuple[str, ...], value: object
) -> None:
    target = data
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        Document.model_validate(data)


def test_dates_accept_iso_strings(data: dict[str, Any]) -> None:
    data.update(issued="2026-09-28", expires="2036-12-31")
    data["hold"] = {"reason": "audit", "since": "2031-03-01", "by": "andreas"}
    doc = Document.model_validate(data)
    assert doc.issued == date(2026, 9, 28)
    assert doc.hold is not None
    assert doc.hold.since == date(2031, 3, 1)


def test_classification_confidence_accepts_int(data: dict[str, Any]) -> None:
    data["classification"]["confidence"] = 1
    doc = Document.model_validate(data)
    assert doc.classification is not None
    assert doc.classification.confidence == 1.0


@pytest.mark.parametrize("status", ["confirmed", "filed"])
def test_issued_required_from_confirm_on(data: dict[str, Any], status: str) -> None:
    data.update(status=status, issued=None)
    with pytest.raises(ValidationError, match="issued must be set"):
        Document.model_validate(data)


@pytest.mark.parametrize("status", STAGING)
def test_issued_may_be_unknown_before_confirm(
    data: dict[str, Any], status: str
) -> None:
    data.update(status=status, issued=None, shard=None)
    assert Document.model_validate(data).issued is None


def test_duplicate_field_keys_rejected(data: dict[str, Any]) -> None:
    data["fields"].append(dict(data["fields"][0]))
    with pytest.raises(ValidationError, match="duplicate field keys"):
        Document.model_validate(data)


def test_personnummer_value_never_inline(data: dict[str, Any]) -> None:
    data["fields"][1]["value"] = "19121212-1212"  # synthetic
    with pytest.raises(ValidationError, match="is sensitive"):
        Document.model_validate(data)


def test_personnummer_without_value_allowed(data: dict[str, Any]) -> None:
    data["fields"][1]["value"] = None
    assert Document.model_validate(data).fields[1].value is None


def test_payload_ref_requires_payload_sha256(data: dict[str, Any]) -> None:
    data["payload_sha256"] = None
    with pytest.raises(ValidationError, match="payload_sha256 is null"):
        Document.model_validate(data)


def test_no_payload_without_payload_refs(data: dict[str, Any]) -> None:
    data["fields"] = data["fields"][:1]
    data["payload_sha256"] = None
    assert Document.model_validate(data).payload_sha256 is None


def test_original_pages_must_not_repeat(data: dict[str, Any]) -> None:
    data["source"]["original"]["pages"] = [1, 1]
    with pytest.raises(ValidationError, match="pages must not repeat"):
        Document.model_validate(data)


def test_original_pages_keep_document_order(data: dict[str, Any]) -> None:
    data["source"]["original"]["pages"] = [3, 1, 2]
    assert Document.model_validate(data).source.original.pages == [3, 1, 2]


def test_amount_as_float_rejected(data: dict[str, Any]) -> None:
    # The §7.3 example writes ``amount: 12500.00``; unquoted it is a YAML float.
    data["fields"][0]["value"]["amount"] = 12500.00
    with pytest.raises(ValidationError, match="floats are not accepted"):
        Document.model_validate(data)
