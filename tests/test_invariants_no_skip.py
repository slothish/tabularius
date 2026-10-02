# SPDX-License-Identifier: GPL-3.0-or-later
"""Prove that tests/invariants/conftest.py turns every kind of skip into a
failure, while xfail stays allowed (DESIGN.md §15)."""

from pathlib import Path

import pytest

CONFTEST = Path(__file__).parent / "invariants" / "conftest.py"


@pytest.fixture
def suite(pytester: pytest.Pytester) -> pytest.Pytester:
    """A throwaway test directory that uses the real invariants conftest."""
    pytester.makeconftest(CONFTEST.read_text(encoding="utf-8"))
    return pytester


def _assert_rejected(result: pytest.RunResult) -> None:
    assert result.ret != pytest.ExitCode.OK
    assert result.parseoutcomes().get("skipped", 0) == 0
    result.stdout.fnmatch_lines(["*skipping is not allowed in tests/invariants*"])


def test_control_without_conftest_skip_passes(pytester: pytest.Pytester) -> None:
    # Without the conftest, a skip is just a skip: the run succeeds.
    pytester.makepyfile("import pytest\n@pytest.mark.skip\ndef test_x(): pass\n")
    result = pytester.runpytest()
    assert result.ret == pytest.ExitCode.OK
    result.assert_outcomes(skipped=1)


@pytest.mark.parametrize(
    "source",
    [
        "@pytest.mark.skip(reason='later')\ndef test_x(): pass\n",
        "@pytest.mark.skipif(True, reason='never')\ndef test_x(): pass\n",
        "def test_x():\n    pytest.skip('in body')\n",
        "@pytest.fixture\ndef f():\n    pytest.skip('in fixture')\n"
        "def test_x(f): pass\n",
    ],
    ids=["skip-marker", "skipif-marker", "skip-in-body", "skip-in-fixture"],
)
def test_test_level_skip_fails(suite: pytest.Pytester, source: str) -> None:
    suite.makepyfile("import pytest\n" + source)
    result = suite.runpytest()
    _assert_rejected(result)
    assert result.ret == pytest.ExitCode.TESTS_FAILED


@pytest.mark.parametrize(
    "source",
    [
        "pytest.skip('whole module', allow_module_level=True)\n",
        "pytest.importorskip('a_module_that_does_not_exist_0199')\n",
    ],
    ids=["module-level-skip", "importorskip"],
)
def test_collection_level_skip_fails(suite: pytest.Pytester, source: str) -> None:
    suite.makepyfile("import pytest\n" + source + "def test_x(): pass\n")
    _assert_rejected(suite.runpytest())


def test_strict_xfail_is_allowed(suite: pytest.Pytester) -> None:
    suite.makepyfile(
        "import pytest\n"
        "@pytest.mark.xfail(strict=True, reason='not implemented: M1')\n"
        "def test_x():\n    raise NotImplementedError\n"
        "def test_y():\n    pytest.xfail('imperative')\n"
        "def test_z(): pass\n"
    )
    result = suite.runpytest()
    assert result.ret == pytest.ExitCode.OK
    result.assert_outcomes(passed=1, xfailed=2)


def test_strict_xfail_that_passes_fails(suite: pytest.Pytester) -> None:
    # Once a check is implemented, its xfail marker must be removed.
    suite.makepyfile(
        "import pytest\n"
        "@pytest.mark.xfail(strict=True, reason='not implemented: M1')\n"
        "def test_x(): pass\n"
    )
    result = suite.runpytest()
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.assert_outcomes(failed=1)
