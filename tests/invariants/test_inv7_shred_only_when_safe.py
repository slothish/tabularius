# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant 7 (DESIGN.md §2):

**Shred only when proven safe.** "Shred OK" means: confirmed in review *and*
the configured backup verifier confirms the original's hash is held in a
backup off this machine (§12.2). No verifier, no shred OK.
"""

import pytest


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_no_verifier_never_sets_shred_ok() -> None:
    """Without a configured backup verifier no document ever gets shred_ok, and the
    reason is reported.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_unconfirmed_document_never_shred_ok() -> None:
    """A document that is not confirmed never gets shred_ok, whatever the verifier
    says.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_hash_not_confirmed_means_no_shred_ok() -> None:
    """A verifier that does not print the original's hash (or prints another hash)
    leads to no shred_ok.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_shred_ok_records_verifier_answer() -> None:
    """The shred_ok event records the original's sha256 and the backup reference the
    verifier printed.
    """
    raise NotImplementedError
