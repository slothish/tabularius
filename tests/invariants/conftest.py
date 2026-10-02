# SPDX-License-Identifier: GPL-3.0-or-later
"""Invariant tests must never be skipped (DESIGN.md §15).

Any skip in this directory is turned into a failure:

- a test skipped at setup or call time (``@pytest.mark.skip``,
  ``@pytest.mark.skipif``, ``pytest.skip()`` in a fixture or test body);
- a whole module skipped at collection (``pytest.skip(...,
  allow_module_level=True)``, ``pytest.importorskip``).

``xfail`` stays allowed: an unimplemented invariant test is an expected
failure that becomes a hard error (strict xfail) once it starts passing.
"""

from collections.abc import Generator

import pytest

MESSAGE = "skipping is not allowed in tests/invariants (DESIGN.md §15)"


def _reason(longrepr: object) -> str:
    # A skip's longrepr is a (path, lineno, reason) tuple.
    match longrepr:
        case (str(), int(), str() as reason):
            return reason
        case _:
            return str(longrepr)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if report.skipped and not hasattr(report, "wasxfail"):
        report.outcome = "failed"
        report.longrepr = f"{MESSAGE}: {item.nodeid}: {_reason(report.longrepr)}"
    return report


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, pytest.CollectReport, pytest.CollectReport]:
    report = yield
    if report.skipped:
        report.outcome = "failed"
        report.longrepr = f"{MESSAGE}: {collector.nodeid}: {_reason(report.longrepr)}"
    return report
