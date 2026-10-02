# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant 2 (DESIGN.md §2):

**Single writer.** Only the core service writes to the archive. The TUI, CLI
and agent go through the core API. Users have no write access to archive
files.
"""

import pytest


@pytest.mark.xfail(strict=True, reason="not implemented: M1")
def test_archive_not_writable_by_other_users() -> None:
    """Nothing in the archive is writable by anyone but the core user."""
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M2")
def test_cli_mutations_go_through_core_api() -> None:
    """Every mutating CLI command fails with the core service stopped and makes no
    change to the archive.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M2")
def test_tui_and_cli_never_write_archive_paths() -> None:
    """Static check: the tui and cli packages contain no file writes to archive paths;
    they only call the API.
    """
    raise NotImplementedError


@pytest.mark.xfail(strict=True, reason="not implemented: M2")
def test_agent_token_cannot_mutate() -> None:
    """Every mutating API call with the read-only agent token is refused and changes
    nothing.
    """
    raise NotImplementedError
