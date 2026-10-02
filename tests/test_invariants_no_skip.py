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
        "def test_z(): pass\n"
    )
    result = suite.runpytest()
    assert result.ret == pytest.ExitCode.OK
    result.assert_outcomes(passed=1, xfailed=1)


STUB_BODY = "def test_x():\n    raise NotImplementedError\n"


@pytest.mark.parametrize(
    ("source", "problem"),
    [
        (
            "@pytest.mark.xfail(strict=True, run=False, reason='not implemented: M1')\n"
            + STUB_BODY,
            "run=False",
        ),
        (
            "@pytest.mark.xfail(strict=False, reason='not implemented: M1')\n"
            + STUB_BODY,
            "without strict=True",
        ),
        (
            "@pytest.mark.xfail(reason='not implemented: M1')\n" + STUB_BODY,
            "without strict=True",
        ),
        (
            "@pytest.mark.xfail(strict=False, reason='not implemented: M1')\n"
            "def test_x(): pass\n",
            "without strict=True",
        ),
        (
            "@pytest.mark.xfail(True, strict=True, reason='not implemented: M1')\n"
            + STUB_BODY,
            "conditional xfail",
        ),
        (
            "@pytest.mark.xfail(strict=True, reason='flaky')\n" + STUB_BODY,
            "reason must be",
        ),
        ("@pytest.mark.xfail(strict=True)\n" + STUB_BODY, "reason must be"),
        (
            "@pytest.mark.xfail(strict=True, reason='not implemented: M1')\n"
            "@pytest.mark.xfail(strict=True, reason='not implemented: M2')\n"
            + STUB_BODY,
            "more than one xfail marker",
        ),
        ("def test_x():\n    pytest.xfail('later')\n", "imperative pytest.xfail()"),
        (
            "@pytest.fixture\ndef f():\n    pytest.xfail('later')\n"
            "def test_x(f): pass\n",
            "imperative pytest.xfail()",
        ),
        (
            "@pytest.mark.xfail(strict=True, reason='not implemented: M1')\n"
            "def test_x():\n    pytest.xfail('not implemented: M1')\n",
            "imperative pytest.xfail()",
        ),
    ],
    ids=[
        "run-false",
        "strict-false-failing",
        "strict-missing",
        "strict-false-passing",
        "conditional",
        "bad-reason",
        "no-reason",
        "two-markers",
        "imperative-in-body",
        "imperative-in-fixture",
        "imperative-under-valid-marker",
    ],
)
def test_other_xfail_forms_fail(
    suite: pytest.Pytester, source: str, problem: str
) -> None:
    suite.makepyfile("import pytest\n" + source)
    result = suite.runpytest()
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    outcomes = result.parseoutcomes()
    assert outcomes.get("xfailed", 0) == 0
    assert outcomes.get("xpassed", 0) == 0
    assert outcomes.get("passed", 0) == 0
    result.stdout.fnmatch_lines([f"*invalid xfail in tests/invariants*{problem}*"])


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


# --- Deselection (tests/conftest.py) ------------------------------------------

ROOT_CONFTEST = Path(__file__).parent / "conftest.py"


@pytest.fixture
def tree(pytester: pytest.Pytester) -> pytest.Pytester:
    """A root conftest (the real tests/conftest.py) with an invariants
    directory and another test directory next to it."""
    pytester.makeconftest(ROOT_CONFTEST.read_text(encoding="utf-8"))
    pytester.mkpydir("invariants")
    pytester.mkpydir("other")
    (pytester.path / "invariants" / "test_inv.py").write_text("def test_a(): pass\n")
    (pytester.path / "other" / "test_other.py").write_text("def test_b(): pass\n")
    return pytester


@pytest.mark.parametrize(
    "args",
    [
        ["-k", "test_b"],
        ["-m", "slow"],
        ["--deselect", "invariants/test_inv.py::test_a"],
    ],
    ids=["-k", "-m", "--deselect"],
)
def test_deselecting_invariants_fails(tree: pytest.Pytester, args: list[str]) -> None:
    result = tree.runpytest(*args)
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*invariant tests must not be deselected*"])


def test_deselecting_elsewhere_is_fine(tree: pytest.Pytester) -> None:
    result = tree.runpytest("other", "-k", "not test_b")
    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED


def test_selecting_by_path_and_ignore_are_fine(tree: pytest.Pytester) -> None:
    tree.runpytest("other").assert_outcomes(passed=1)
    tree.runpytest("--ignore=invariants").assert_outcomes(passed=1)
    tree.runpytest().assert_outcomes(passed=2)
