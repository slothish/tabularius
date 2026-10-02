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


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_move_between_shards_copies_and_verifies_before_git_rm() -> None:
    """Moving a confirmed document to another shard (issue date or type corrected,
    §7.2) copies into the new shard its blobs, its intake envelope, its sidecar
    and its payload file, and verifies each: blobs and envelope by hash, the
    payload (not in git) against payload_sha256. Only then are they removed from
    the old shard (git rm for the registry files). The move is recorded in both
    shards.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M2")
def test_blob_shared_by_two_shards_is_copied_into_each() -> None:
    """A blob needed by documents in two shards is copied into each shard's store and
    verified there; neither shard refers to the other's store (§7.2).
    """
    raise NotImplementedError
