# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant 1 (DESIGN.md §2):

**Originals are write-once.** Once stored, an original is never modified or
overwritten. It is copied, its hash verified, and only then is the source
copy removed (inbox → staging → shard). Never move-then-verify.
"""

import pytest


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_stored_original_is_read_only() -> None:
    """A stored original has mode 0444 and is owned by the core user."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_storing_existing_hash_never_overwrites() -> None:
    """Storing a blob whose hash is already present leaves the existing file's bytes,
    inode and mtime untouched.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_source_removed_only_after_copy_hash_verified() -> None:
    """With the copy corrupted between write and verify, ingest fails and the inbox
    source is still there.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_crash_between_copy_and_verify_keeps_source() -> None:
    """Killing the core after the copy but before verification leaves the source in the
    inbox; a rerun completes.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M2")
def test_confirm_copies_and_verifies_before_removing_staging() -> None:
    """Confirm copies blobs, envelope and sidecar into the shard, verifies hashes and
    commits before deleting the staging copies.
    """
    raise NotImplementedError
