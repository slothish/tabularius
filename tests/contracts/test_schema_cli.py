# SPDX-License-Identifier: GPL-3.0-or-later
"""``hledger-tab schema [NAME]`` and the published JSON Schemas."""

import json
from typing import Any

import pytest

from hledger_tab.cli import main
from hledger_tab.contracts import CONTRACTS, json_schema

NAMES = ["envelope", "document", "field", "event", "type", "template"]


def test_registry_names() -> None:
    assert list(CONTRACTS) == NAMES


def test_schema_without_name_lists_contracts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["schema"]) == 0
    assert capsys.readouterr().out.split() == NAMES


@pytest.mark.parametrize("name", NAMES)
def test_schema_prints_json_schema(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["schema", name]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == json_schema(name)


def test_unknown_name_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["schema", "nope"])
    assert exc_info.value.code == 2
    assert "invalid choice: 'nope'" in capsys.readouterr().err


def _objects(node: Any) -> list[dict[str, Any]]:
    """Every JSON Schema object node that declares ``properties``."""
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if "properties" in node:
            found.append(node)  # pyright: ignore[reportUnknownArgumentType]
        for value in node.values():  # pyright: ignore[reportUnknownVariableType]
            found.extend(_objects(value))
    elif isinstance(node, list):
        for item in node:  # pyright: ignore[reportUnknownVariableType]
            found.extend(_objects(item))
    return found


@pytest.mark.parametrize("name", NAMES)
def test_every_schema_object_forbids_additional_properties(name: str) -> None:
    objects = _objects(json_schema(name))
    assert objects
    for obj in objects:
        assert obj.get("additionalProperties") is False, obj.get("title")


def test_schema_uses_wire_names() -> None:
    properties = json_schema("envelope")["properties"]
    assert "schema" in properties
    assert "from" in properties
    assert "schema_" not in properties
    assert "from_" not in properties
