# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep tests/invariants in step with DESIGN.md §2.

There is one file per invariant. Each module docstring quotes its invariant
verbatim (whitespace aside). A test that is still a stub (its body is
``raise NotImplementedError``) is a strict xfail naming the milestone that
will implement it; an implemented test has no xfail marker at all.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
INVARIANTS = Path(__file__).parent / "invariants"
SECTION_HEADING = "## 2. Invariants"
XFAIL_REASON = re.compile(r"^not implemented: M[1-9]\d*$")


def _normalise(text: str) -> str:
    return " ".join(text.split())


def parse_invariants(design: str) -> dict[int, str]:
    """The numbered items of DESIGN.md §2, by number, whitespace-normalised.

    An item runs from its ``<n>. `` line up to the next numbered item or a
    blank line; every line in between belongs to it, however indented.
    """
    lines = design.splitlines()
    assert SECTION_HEADING in lines, f"DESIGN.md has no heading {SECTION_HEADING!r}"
    start = lines.index(SECTION_HEADING) + 1
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith(("## ", "---"))),
        len(lines),
    )
    items: dict[int, list[str]] = {}
    current: int | None = None
    for line in lines[start:end]:
        match = re.match(r"^(\d+)\. (.*)$", line)
        if match:
            current = int(match.group(1))
            items[current] = [match.group(2)]
        elif not line.strip():
            current = None
        elif current is not None:
            items[current].append(line)
    return {n: _normalise(" ".join(parts)) for n, parts in items.items()}


@pytest.fixture(scope="module")
def invariants() -> dict[int, str]:
    return parse_invariants((ROOT / "DESIGN.md").read_text(encoding="utf-8"))


def _module(number: int) -> ast.Module:
    paths = list(INVARIANTS.glob(f"test_inv{number}_*.py"))
    assert len(paths) == 1, f"expected one test_inv{number}_*.py, found {paths}"
    return ast.parse(paths[0].read_text(encoding="utf-8"))


def _tests(module: ast.Module) -> list[ast.FunctionDef]:
    return [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]


def _is_stub(function: ast.FunctionDef) -> bool:
    body = function.body
    if ast.get_docstring(function) is not None:
        body = body[1:]
    return len(body) == 1 and ast.unparse(body[0]) == "raise NotImplementedError"


def _xfail_markers(function: ast.FunctionDef) -> list[ast.expr]:
    """Decorators that are ``pytest.mark.xfail`` or ``pytest.mark.xfail(...)``."""
    return [
        d
        for d in function.decorator_list
        if ast.unparse(d.func if isinstance(d, ast.Call) else d) == "pytest.mark.xfail"
    ]


def _valid_xfail(marker: ast.expr) -> bool:
    """Exactly ``pytest.mark.xfail(strict=True, reason="not implemented: M<n>")``."""
    if not isinstance(marker, ast.Call) or marker.args:
        return False
    keywords = {k.arg: k.value for k in marker.keywords}
    strict = keywords.get("strict")
    reason = keywords.get("reason")
    return (
        set(keywords) == {"strict", "reason"}
        and isinstance(strict, ast.Constant)
        and strict.value is True
        and isinstance(reason, ast.Constant)
        and isinstance(reason.value, str)
        and XFAIL_REASON.match(reason.value) is not None
    )


def _mentions_mark(node: ast.AST) -> bool:
    """Whether ``node`` refers to ``pytest.mark`` or a bare ``mark``."""
    text = ast.unparse(node)
    return "pytest.mark" in text or re.search(r"\bmark\b", text) is not None


IMPLEMENTED_DECORATORS = frozenset(
    {"pytest.mark.parametrize", "pytest.mark.usefixtures"}
)
"""Decorators an implemented invariant test may use, called and spelled out
in full through ``pytest.mark``."""


def _implemented_decorator(decorator: ast.expr) -> bool:
    return (
        isinstance(decorator, ast.Call)
        and ast.unparse(decorator.func) in IMPLEMENTED_DECORATORS
    )


def marker_problems(module: ast.Module) -> list[str]:
    """Every way ``module`` attaches markers other than the allowed form.

    Allowed: a stub decorated with exactly
    ``@pytest.mark.xfail(strict=True, reason="not implemented: M<n>")`` and
    nothing else; an implemented test decorated only with
    ``@pytest.mark.parametrize(...)`` and ``@pytest.mark.usefixtures(...)``.
    Refused: any other
    decorator (including an alias such as ``xf = pytest.mark.xfail(...)``
    then ``@xf``), module-level assignments of ``pytest.mark`` anything
    (``pytestmark`` included), ``from pytest import mark``, and classes.
    """
    problems: list[str] = []
    for node in module.body:
        if isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign):
            if node.value is not None and _mentions_mark(node.value):
                problems.append(f"module-level marker assignment: {ast.unparse(node)}")
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(ast.unparse(t) == "pytestmark" for t in targets):
                problems.append("module-level pytestmark")
        elif isinstance(node, ast.ImportFrom) and node.module == "pytest":
            problems.append(f"import from pytest: {ast.unparse(node)}")
        elif isinstance(node, ast.ClassDef):
            problems.append(f"class {node.name}: put tests in plain functions")
    for function in _tests(module):
        stub = _is_stub(function)
        for decorator in function.decorator_list:
            allowed = (
                _valid_xfail(decorator) if stub else _implemented_decorator(decorator)
            )
            if not allowed:
                problems.append(f"{function.name}: decorator @{ast.unparse(decorator)}")
        if stub and len(function.decorator_list) != 1:
            problems.append(
                f"{function.name}: a stub needs exactly "
                '@pytest.mark.xfail(strict=True, reason="not implemented: M<n>")'
            )
    return problems


# --- Parsing DESIGN.md --------------------------------------------------------


def test_design_has_eight_invariants(invariants: dict[int, str]) -> None:
    assert sorted(invariants) == list(range(1, 9))


def test_parser_reports_missing_heading() -> None:
    with pytest.raises(AssertionError, match="no heading"):
        parse_invariants("# Design\n\n## 2. Rules\n\n1. **A.** b\n")


def test_parser_keeps_continuation_lines_of_any_indentation() -> None:
    design = (
        "## 2. Invariants\n\n"
        "1. **One.** first line\n"
        "   indented continuation\n"
        "unindented continuation\n"
        "2. **Two.** second\n\n"
        "Not part of item two.\n"
        "---\n"
    )
    assert parse_invariants(design) == {
        1: "**One.** first line indented continuation unindented continuation",
        2: "**Two.** second",
    }


# --- The invariant files ------------------------------------------------------


def test_one_file_per_invariant(invariants: dict[int, str]) -> None:
    files = sorted(p.name for p in INVARIANTS.glob("test_*.py"))
    assert len(files) == len(invariants)
    for number in invariants:
        _module(number)


def test_no_skip_conftest_present() -> None:
    assert (INVARIANTS / "conftest.py").is_file()


@pytest.mark.parametrize("number", range(1, 9))
def test_docstring_quotes_invariant(invariants: dict[int, str], number: int) -> None:
    docstring = ast.get_docstring(_module(number))
    assert docstring is not None
    assert invariants[number] in _normalise(docstring)


@pytest.mark.parametrize("number", range(1, 9))
def test_at_least_two_checks_per_invariant(number: int) -> None:
    assert len(_tests(_module(number))) >= 2


@pytest.mark.parametrize("number", range(1, 9))
def test_markers_only_in_the_allowed_form(number: int) -> None:
    assert marker_problems(_module(number)) == []


# --- The checker itself -------------------------------------------------------


def _function(source: str) -> ast.FunctionDef:
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


VALID = '@pytest.mark.xfail(strict=True, reason="not implemented: M3")\n'


@pytest.mark.parametrize(
    "decorator",
    [
        "@pytest.mark.xfail\n",
        '@pytest.mark.xfail(reason="not implemented: M3")\n',
        '@pytest.mark.xfail(strict=False, reason="not implemented: M3")\n',
        '@pytest.mark.xfail(True, strict=True, reason="not implemented: M3")\n',
        '@pytest.mark.xfail(strict=True, run=False, reason="not implemented: M3")\n',
        '@pytest.mark.xfail(strict=True, reason="later")\n',
        '@pytest.mark.xfail(strict=True, reason="not implemented: M0")\n',
        '@pytest.mark.xfail(strict=True, reason="not implemented: M01")\n',
    ],
)
def test_checker_rejects_other_xfail_forms(decorator: str) -> None:
    function = _function(decorator + "def test_x():\n    raise NotImplementedError\n")
    (marker,) = _xfail_markers(function)
    assert not _valid_xfail(marker)


def test_checker_accepts_the_allowed_form() -> None:
    function = _function(VALID + "def test_x():\n    raise NotImplementedError\n")
    assert _is_stub(function)
    (marker,) = _xfail_markers(function)
    assert _valid_xfail(marker)


def test_checker_sees_implemented_test_with_xfail() -> None:
    function = _function(VALID + "def test_x():\n    assert 1 + 1 == 2\n")
    assert not _is_stub(function)
    assert _xfail_markers(function)


STUB = "def test_x():\n    raise NotImplementedError\n"


@pytest.mark.parametrize(
    ("source", "problem"),
    [
        (
            'xf = pytest.mark.xfail(strict=True, reason="not implemented: M1")\n'
            "@xf\n" + STUB,
            "module-level marker assignment",
        ),
        (
            'xf = pytest.mark.xfail(strict=True, reason="not implemented: M1")\n'
            "@xf\n" + STUB,
            "decorator @xf",
        ),
        ("m = pytest.mark\n" + VALID + STUB, "module-level marker assignment"),
        (
            "pytestmark = pytest.mark.xfail(strict=True,"
            ' reason="not implemented: M1")\n' + STUB,
            "module-level pytestmark",
        ),
        ("from pytest import mark\n" + VALID + STUB, "import from pytest"),
        (
            "@pytest.mark.parametrize('x', [1])\n" + VALID + STUB,
            "decorator @pytest.mark.parametrize",
        ),
        (
            "@pytest.mark.skip\ndef test_x():\n    assert True\n",
            "decorator @pytest.mark.skip",
        ),
        (
            "@pytest.mark.usefixtures\ndef test_x():\n    assert True\n",
            "decorator @pytest.mark.usefixtures",
        ),
        (
            "p = pytest.mark.parametrize('x', [1])\n@p\ndef test_x(x):\n    assert x\n",
            "decorator @p",
        ),
        ("@pytest.mark.skip\n" + STUB, "decorator @pytest.mark.skip"),
        (STUB, "a stub needs exactly"),
        (VALID + "def test_x():\n    assert True\n", "decorator"),
        ("class TestX:\n    pass\n", "class TestX"),
    ],
    ids=[
        "alias-assignment",
        "alias-decorator",
        "mark-alias",
        "pytestmark",
        "from-pytest-import-mark",
        "parametrize-on-stub",
        "skip-on-implemented",
        "uncalled-usefixtures",
        "aliased-parametrize",
        "skip-decorator",
        "stub-without-marker",
        "implemented-with-marker",
        "class",
    ],
)
def test_marker_problems_found(source: str, problem: str) -> None:
    problems = marker_problems(ast.parse("import pytest\n" + source))
    assert any(problem in p for p in problems), problems


def test_marker_problems_accepts_the_allowed_forms() -> None:
    source = "import pytest\n" + VALID + STUB + "def test_y():\n    assert True\n"
    assert marker_problems(ast.parse(source)) == []


@pytest.mark.parametrize(
    "decorators",
    [
        "@pytest.mark.parametrize('x', [1, 2])\n",
        "@pytest.mark.usefixtures('tmp_path')\n",
        "@pytest.mark.parametrize('x', [1])\n@pytest.mark.usefixtures('tmp_path')\n",
    ],
    ids=["parametrize", "usefixtures", "both"],
)
def test_implemented_test_may_parametrize_and_use_fixtures(decorators: str) -> None:
    source = "import pytest\n" + decorators + "def test_x(x=1):\n    assert x\n"
    assert marker_problems(ast.parse(source)) == []
