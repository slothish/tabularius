# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant tests must never be skipped (DESIGN.md §15).

Every way of not running an invariant check is turned into a failure:

- a skip at setup or call time (``@pytest.mark.skip``, ``skipif``,
  ``pytest.skip()`` in a fixture or test body);
- a whole module skipped at collection (``pytest.skip(...,
  allow_module_level=True)``, ``pytest.importorskip``);
- an imperative ``pytest.xfail()``;
- an xfail marker other than the one form allowed for unimplemented
  checks, exactly ``@pytest.mark.xfail(strict=True, reason="not implemented:
  M<n>")``: no condition and no other keyword (``run``, ``raises``). This
  applies however the marker is attached (decorator, module or class
  ``pytestmark``);
- an xfail whose test failed with anything but ``NotImplementedError``.
  "xfailed" therefore only ever means "still a stub": an implemented test
  that fails is reported as failed even if a marker was left behind, and
  ``strict=True`` turns one that passes into a failure too.

Deselection (``-k``, ``-m``, ``--deselect``) is refused by the
``pytest_deselected`` hook in ``tests/conftest.py``.
"""

import re
from collections.abc import Generator

import pytest

MESSAGE = "skipping is not allowed in tests/invariants (DESIGN.md §15)"
XFAIL_MESSAGE = "invalid xfail in tests/invariants (DESIGN.md §15)"
XFAIL_REASON = re.compile(r"^not implemented: M[1-9]\d*$")


def _reason(longrepr: object) -> str:
    # A skip's longrepr is a (path, lineno, reason) tuple.
    match longrepr:
        case (str(), int(), str() as reason):
            return reason
        case _:
            return str(longrepr)


def xfail_marker_problem(item: pytest.Item) -> str | None:
    """Why the item's xfail marker is not allowed, or None if it has no xfail
    marker or exactly the allowed one."""
    markers = list(item.iter_markers("xfail"))
    if not markers:
        return None
    if len(markers) > 1:
        return "more than one xfail marker"
    marker = markers[0]
    if marker.args:
        return "conditional xfail"
    other = sorted(set(marker.kwargs) - {"strict", "reason"})
    if other:
        return f"xfail keywords other than strict and reason: {', '.join(other)}"
    if marker.kwargs.get("strict") is not True:
        return "xfail without strict=True"
    reason = marker.kwargs.get("reason")
    if not (isinstance(reason, str) and XFAIL_REASON.fullmatch(reason)):
        return f"xfail reason must be 'not implemented: M<n>', got {reason!r}"
    return None


def _fail(report: pytest.TestReport | pytest.CollectReport, message: str) -> None:
    report.outcome = "failed"
    report.longrepr = message
    # pytest does not count a failed report that still carries ``wasxfail``
    # (session.testsfailed), so the run would exit 0; drop it.
    if hasattr(report, "wasxfail"):
        del report.wasxfail  # pyright: ignore[reportAttributeAccessIssue]


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    problem = xfail_marker_problem(item)
    if problem is not None and report.when == "setup":
        # Fail before the test runs, whatever the marker would have done.
        _fail(report, f"{XFAIL_MESSAGE}: {item.nodeid}: {problem}")
    elif call.excinfo is not None and call.excinfo.errisinstance(
        pytest.xfail.Exception
    ):
        _fail(report, f"{XFAIL_MESSAGE}: {item.nodeid}: imperative pytest.xfail()")
    elif (
        report.when == "call"
        and hasattr(report, "wasxfail")
        and not (
            call.excinfo is not None and call.excinfo.errisinstance(NotImplementedError)
        )
    ):
        _fail(
            report,
            f"{XFAIL_MESSAGE}: {item.nodeid}: an xfail test may only fail with "
            "NotImplementedError (a stub); this one is implemented and failing",
        )
    elif report.skipped and not hasattr(report, "wasxfail"):
        _fail(report, f"{MESSAGE}: {item.nodeid}: {_reason(report.longrepr)}")
    return report


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, pytest.CollectReport, pytest.CollectReport]:
    report = yield
    if report.skipped:
        _fail(report, f"{MESSAGE}: {collector.nodeid}: {_reason(report.longrepr)}")
    return report
