# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the ``hledger-tab`` command line entry point."""

import subprocess
import sys

import pytest

from hledger_tab import __version__
from hledger_tab.cli import main


def test_version_via_main(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    assert capsys.readouterr().out == f"hledger-tab {__version__}\n"


def test_version_matches_package_metadata() -> None:
    assert __version__ == "0.0.0"


def test_version_via_subprocess() -> None:
    # ``python -m`` with the running interpreter exercises the real process
    # boundary (argv parsing, stdout, exit code) without depending on where
    # the console script was installed or on ``uv`` being on PATH inside the
    # test run.
    result = subprocess.run(
        [sys.executable, "-m", "hledger_tab.cli", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == f"hledger-tab {__version__}\n"
    assert result.stderr == ""


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: hledger-tab" in capsys.readouterr().out
