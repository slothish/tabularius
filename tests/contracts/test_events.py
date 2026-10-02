# SPDX-License-Identifier: GPL-3.0-or-later
"""Document events (DESIGN.md §7.3)."""

from datetime import datetime
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from hledger_tab.contracts.events import Event, MovedEvent

EVENT = TypeAdapter[Event](Event)

SHA = "41aa" + "0" * 59 + "7"
SHA2 = "9f2c" + "0" * 57 + "ee1"

EXAMPLES: dict[str, dict[str, Any]] = {
    "received": {"via": "scanner"},
    "confirmed": {"by": "andreas"},
    "payable_recorded": {"txn": "V2026-0042"},
    "shred_ok": {
        "backups": [
            {"sha256": SHA, "backup": "backup-host:tank/archive/docs@monthly"},
            {"sha256": SHA2, "backup": "backup-host:tank/archive/docs@monthly"},
        ]
    },
    "moved": {"from_shard": "2036", "to_shard": "open", "by": "andreas"},
    "hold_set": {"by": "andreas", "reason": "tax audit"},
    "hold_released": {"by": "andreas"},
    "quarantined": {"reason": "qpdf --check failed"},
}


def event(type_: str, **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"at": "2026-10-02T09:12:00Z", "type": type_}
    data.update(EXAMPLES[type_])
    data.update(overrides)
    return data


@pytest.mark.parametrize("type_", list(EXAMPLES))
def test_each_event_validates_and_round_trips(type_: str) -> None:
    parsed = EVENT.validate_python(event(type_))
    assert parsed.type == type_
    assert parsed.at.utcoffset() is not None
    assert EVENT.validate_python(EVENT.dump_python(parsed, mode="json")) == parsed


@pytest.mark.parametrize("type_", list(EXAMPLES))
def test_naive_at_rejected(type_: str) -> None:
    with pytest.raises(ValidationError, match="RFC 3339"):
        EVENT.validate_python(event(type_, at="2026-10-02T09:12:00"))
    with pytest.raises(ValidationError, match="timezone"):
        EVENT.validate_python(event(type_, at=datetime(2026, 10, 2, 9, 12)))


def test_shred_ok_rejects_duplicate_hashes() -> None:
    backups = [{"sha256": SHA, "backup": "a"}, {"sha256": SHA, "backup": "b"}]
    with pytest.raises(ValidationError, match="sha256 twice"):
        EVENT.validate_python(event("shred_ok", backups=backups))


def test_shred_ok_old_single_form_rejected() -> None:
    data = {"at": "2026-10-03T03:10:00Z", "type": "shred_ok", "sha256": SHA}
    with pytest.raises(ValidationError):
        EVENT.validate_python(data | {"backup": "b"})


@pytest.mark.parametrize("at", [0, 1728000000, 1728000000.5, True, "0"])
@pytest.mark.parametrize("type_", list(EXAMPLES))
def test_numeric_at_rejected(type_: str, at: object) -> None:
    with pytest.raises(ValidationError):
        EVENT.validate_python(event(type_, at=at))


@pytest.mark.parametrize("type_", list(EXAMPLES))
def test_at_required(type_: str) -> None:
    data = event(type_)
    del data["at"]
    with pytest.raises(ValidationError, match="Field required"):
        EVENT.validate_python(data)


@pytest.mark.parametrize("type_", list(EXAMPLES))
def test_unknown_key_rejected(type_: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EVENT.validate_python(event(type_, actor="x"))


@pytest.mark.parametrize("type_", ["submitted", "expired", "deleted", ""])
def test_unknown_event_type_rejected(type_: str) -> None:
    with pytest.raises(ValidationError):
        EVENT.validate_python({"at": "2026-10-02T09:12:00Z", "type": type_})


def test_move_must_change_shard() -> None:
    with pytest.raises(ValidationError, match="must change the shard"):
        EVENT.validate_python(event("moved", to_shard="2036"))


def test_move_parses() -> None:
    assert isinstance(EVENT.validate_python(event("moved")), MovedEvent)


@pytest.mark.parametrize(
    ("type_", "key", "value"),
    [
        ("received", "via", "fax"),
        ("payable_recorded", "txn", "V 2026"),
        ("shred_ok", "backups", []),
        ("shred_ok", "backups", [{"sha256": "not-a-hash", "backup": "b"}]),
        ("shred_ok", "backups", [{"sha256": SHA, "backup": ""}]),
        ("shred_ok", "backups", [{"sha256": SHA, "backup": "b", "note": "x"}]),
        ("moved", "to_shard", "2036-12-31"),
        ("confirmed", "by", "two words"),
    ],
)
def test_bad_value_rejected(type_: str, key: str, value: object) -> None:
    with pytest.raises(ValidationError):
        EVENT.validate_python(event(type_, **{key: value}))
