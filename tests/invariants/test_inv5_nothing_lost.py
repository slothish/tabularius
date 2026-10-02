# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant 5 (DESIGN.md §2):

**Nothing is lost.** Unknown formats, failed parses and unrecognised fields
go to quarantine or are kept as raw data — never silently dropped.
"""

import pytest


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_unknown_format_goes_to_quarantine() -> None:
    """A payload of unknown format ends in quarantine with its original stored, never
    discarded.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_broken_pdf_goes_to_quarantine() -> None:
    """A PDF failing `qpdf --check` is quarantined with the original kept and a
    quarantined event.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_failed_step_keeps_original_and_records_event() -> None:
    """A failure in any pipeline step (OCR, normalisation, split) keeps the original
    and records why.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M3")
def test_unrecognised_fields_kept_as_discovered() -> None:
    """Values the extractor finds outside the profile are kept as discovered or unknown
    field records.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M3")
def test_business_duplicate_is_flagged_not_dropped() -> None:
    """A document matching an earlier one by uniqueness key is flagged in review, not
    dropped.
    """
    raise NotImplementedError
