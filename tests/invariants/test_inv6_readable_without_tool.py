# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant 6 (DESIGN.md §2):

**Readable without the tool.** The archive is plain files and plain text. A
person with no copy of Tabularius can understand it from the files and the
README at the archive root.
"""

import pytest


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_archive_root_readme_describes_layout() -> None:
    """The archive root has a README.md that explains every top-level entry that
    exists.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_registry_files_are_plain_utf8_text() -> None:
    """Every envelope and sidecar is UTF-8 JSON/YAML that a generic parser reads
    without Tabularius.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_index_rebuilds_from_files_alone() -> None:
    """Deleting index.sqlite and rebuilding it gives the same query results."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M2")
def test_shard_has_readme() -> None:
    """Every shard directory has a README.md."""
    raise NotImplementedError
