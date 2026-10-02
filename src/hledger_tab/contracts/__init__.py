# SPDX-License-Identifier: GPL-3.0-or-later
"""Contracts: the pydantic models that define every shape Tabularius reads or
writes (DESIGN.md §14 "Contracts first", §15).

``CONTRACTS`` maps a public name to a validator for each top-level contract;
``hledger-tab schema NAME`` prints its JSON Schema.
"""

from typing import Any

from pydantic import TypeAdapter

from hledger_tab.contracts.document import Document
from hledger_tab.contracts.envelope import Envelope
from hledger_tab.contracts.events import Event
from hledger_tab.contracts.field import FieldRecord
from hledger_tab.contracts.profile import Template, TypeProfile

CONTRACTS: dict[str, TypeAdapter[Any]] = {
    "envelope": TypeAdapter(Envelope),
    "document": TypeAdapter(Document),
    "field": TypeAdapter(FieldRecord),
    "event": TypeAdapter(Event),
    "type": TypeAdapter(TypeProfile),
    "template": TypeAdapter(Template),
}
"""Top-level contracts by name, in the order ``hledger-tab schema`` lists them."""


def json_schema(name: str) -> dict[str, Any]:
    """The JSON Schema (validation mode) of the contract called ``name``.

    Raises ``KeyError`` for an unknown name.
    """
    return CONTRACTS[name].json_schema(mode="validation")
