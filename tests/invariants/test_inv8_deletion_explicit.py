# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant 8 (DESIGN.md §2):

**Deletion is explicit, coarse and logged.** Data leaves the archive only by
deleting a whole expired shard or by an explicit early deletion of one
document, each confirmed in the TUI and recorded in the deletion ledger
(§12.4). History is never rewritten as part of normal operation.
"""

import pytest


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_shard_deletion_needs_confirmation_and_ledger_entry() -> None:
    """A shard is removed only after explicit confirmation, and a ledger entry with the
    required facts is committed.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_shard_not_deletable_before_expiry_or_with_hold() -> None:
    """A shard before its deletable_from date, or holding a document on hold, cannot be
    deleted.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_early_deletion_of_one_document_is_logged() -> None:
    """Early deletion removes the document's payload and those of its blobs that no
    other document in the shard references (shared blobs are kept, §12.4),
    git-rms its sidecar, and writes a ledger entry. If it was the last document
    of its intake, the intake envelope is git-rm'd too, and container blobs that
    no remaining document references are deleted.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_ledger_holds_no_personal_data() -> None:
    """Ledger entries contain only ids, counts, dates, commits and actors; no field
    values or names.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M2")
def test_normal_operation_never_rewrites_history() -> None:
    """After normal operations every earlier registry commit is still an ancestor of
    HEAD.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_open_shard_history_rewrite_only_via_explicit_command() -> None:
    """git filter-repo on the open shard happens only through its explicit
    command, which asks for confirmation and records the rewrite in the
    deletion ledger (§12.4).
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_deletion_purges_index() -> None:
    """After any deletion (shard or single document) the deleted documents' OCR text
    and field values do not occur anywhere in the bytes of index.sqlite (§7.5).
    """
    raise NotImplementedError
