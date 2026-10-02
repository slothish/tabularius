# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant 4 (DESIGN.md §2):

**Never modify hand-written journal files.** Generated hledger entries go to
a dedicated include file. Adding a `doc:` tag to an existing transaction
requires explicit confirmation in the TUI.
"""

import pytest


@pytest.mark.xfail(strict=True, reason="not implemented: M4")
def test_generated_entries_only_in_docs_journal() -> None:
    """Recording a payable writes only to the dedicated include file (docs.journal)."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M4")
def test_hand_written_files_byte_identical() -> None:
    """After a full run of every journal-related command, all hand-written journal
    files are byte-identical.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M4")
def test_attach_without_confirmation_changes_nothing() -> None:
    """`attach` without explicit confirmation leaves every journal file unchanged."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M4")
def test_attach_with_confirmation_changes_only_the_tag() -> None:
    """A confirmed `attach` adds only the doc: tag to the chosen transaction; the rest
    of the file is unchanged.
    """
    raise NotImplementedError
