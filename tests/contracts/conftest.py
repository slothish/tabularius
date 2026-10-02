# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared helpers for contract tests: load the synthetic fixtures."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

FIXTURES = Path(__file__).parent.parent / "fixtures" / "contracts"

type Loader = Callable[[str], dict[str, Any]]


def _load(name: str) -> dict[str, Any]:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    data: dict[str, Any] = (
        json.loads(text) if name.endswith(".json") else yaml.safe_load(text)
    )
    return data


@pytest.fixture
def load() -> Loader:
    """Return a function that loads a fixture file into a fresh dict."""
    return _load
