# SPDX-License-Identifier: GPL-3.0-or-later
"""The core service: ingest, pipeline, persistence, API (DESIGN.md §3, §15).

This ``__init__`` must stay import-free: the contracts import
``hledger_tab.core.retention``, and anything imported here would be loaded
(and could import the contracts back) whenever they do.
"""
