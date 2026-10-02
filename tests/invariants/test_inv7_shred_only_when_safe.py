# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant 7 (DESIGN.md §2):

**Shred only when proven safe.** "Shred OK" means: confirmed in review *and*
the configured backup verifier confirms the original's hash is held in a
backup off this machine (§12.2). No verifier, no shred OK.

"The original's hash" means every original blob the document references:
the original file *and* its container (e.g. the ``.eml`` it came in), if
any. shred_ok is set only when the verifier confirms all of them.
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
    """A verifier that confirms only some of the document's original blobs (e.g. the
    original but not its container .eml), or prints another hash, leads to no
    shred_ok.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_verifier_fails_closed() -> None:
    """Each of these verifier runs gives no shred_ok, even if every requested hash
    was printed: a non-zero exit after printing, a crash partway through, a
    timeout, malformed output lines, and extra or unrequested hashes.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M7")
def test_shred_ok_records_verifier_answer() -> None:
    """The shred_ok event records, for every original blob of the document (original
    and container), its sha256 and the backup reference the verifier printed.
    """
    raise NotImplementedError
