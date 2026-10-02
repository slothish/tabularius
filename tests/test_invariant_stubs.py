# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep tests/invariants in step with DESIGN.md §2.

There is one file per invariant. Each module docstring quotes its invariant
verbatim (whitespace aside). Every test that is not yet implemented is a
strict xfail naming the milestone that will implement it.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
INVARIANTS = Path(__file__).parent / "invariants"
XFAIL_REASON = re.compile(r"^not implemented: M[1-9]$")


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _design_invariants() -> dict[int, str]:
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    section = design.split("## 2. Invariants", 1)[1].split("\n---", 1)[0]
    items: dict[int, list[str]] = {}
    current = 0
    for line in section.splitlines():
        match = re.match(r"^(\d+)\. (.*)$", line)
        if match:
            current = int(match.group(1))
            items[current] = [match.group(2)]
        elif current and line.startswith("   ") and line.strip():
            items[current].append(line.strip())
    return {n: _normalise(" ".join(lines)) for n, lines in items.items()}


DESIGN_INVARIANTS = _design_invariants()


def _module(number: int) -> ast.Module:
    (path,) = INVARIANTS.glob(f"test_inv{number}_*.py")
    return ast.parse(path.read_text(encoding="utf-8"))


def test_design_has_eight_invariants() -> None:
    assert sorted(DESIGN_INVARIANTS) == list(range(1, 9))


def test_one_file_per_invariant() -> None:
    files = sorted(p.name for p in INVARIANTS.glob("test_*.py"))
    assert len(files) == 8
    for number in DESIGN_INVARIANTS:
        assert len(list(INVARIANTS.glob(f"test_inv{number}_*.py"))) == 1


def test_no_skip_conftest_present() -> None:
    assert (INVARIANTS / "conftest.py").is_file()


@pytest.mark.parametrize("number", range(1, 9))
def test_docstring_quotes_invariant(number: int) -> None:
    docstring = ast.get_docstring(_module(number))
    assert docstring is not None
    assert DESIGN_INVARIANTS[number] in _normalise(docstring)


def _xfail_reason(function: ast.FunctionDef) -> str | None:
    """The reason of a ``@pytest.mark.xfail(strict=True, reason=...)``
    decorator, or None if there is no such decorator."""
    for decorator in function.decorator_list:
        if not (
            isinstance(decorator, ast.Call)
            and ast.unparse(decorator.func) == "pytest.mark.xfail"
        ):
            continue
        keywords = {k.arg: k.value for k in decorator.keywords}
        strict = keywords.get("strict")
        reason = keywords.get("reason")
        if (
            isinstance(strict, ast.Constant)
            and strict.value is True
            and isinstance(reason, ast.Constant)
            and isinstance(reason.value, str)
        ):
            return reason.value
    return None


@pytest.mark.parametrize("number", range(1, 9))
def test_stubs_are_strict_xfail_with_milestone(number: int) -> None:
    tests = [
        node
        for node in _module(number).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assert 2 <= len(tests) <= 5
    for function in tests:
        body = function.body
        if ast.get_docstring(function) is not None:
            body = body[1:]
        is_stub = len(body) == 1 and ast.unparse(body[0]) == "raise NotImplementedError"
        if not is_stub:
            continue  # implemented: no longer a stub
        reason = _xfail_reason(function)
        assert reason is not None, f"{function.name}: missing strict xfail"
        assert XFAIL_REASON.match(reason), f"{function.name}: {reason!r}"
