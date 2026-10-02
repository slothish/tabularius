# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant 3 (DESIGN.md §2):

**Intake is idempotent.** The same file or email ingested twice yields one
original and the same documents.
"""

import pytest


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_same_bundle_twice_yields_one_original() -> None:
    """Ingesting the same bundle twice stores one original and yields the same document
    ids.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_same_file_in_two_bundles_yields_one_original() -> None:
    """The same scan arriving in two bundles (different intake ids) is stored once and
    maps to the same documents.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_reingest_after_interrupted_ingest() -> None:
    """An ingest interrupted at each step and rerun ends in the same state as an
    uninterrupted one.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M5")
def test_same_message_id_twice_yields_one_document() -> None:
    """An email with the same Message-ID delivered twice yields one original and one
    set of documents.
    """
    raise NotImplementedError
