"""The native extension links current newt and newtui and answers from Python.

One call per reused crate family: newt-core's router, newt-data's SQLite EDA,
and newtui's exhaustive explorer. If any of these stop importing or answering,
the from-source assembly has broken — that is the whole point of this file."""

from __future__ import annotations

import tempfile
from pathlib import Path

from shea._native import core, data, ui


def test_newt_core_router_answers():
    assert core.Router().classify("rename foo to bar") == core.Tier.Fast


def test_newt_data_ingests_and_queries_csv():
    with tempfile.TemporaryDirectory() as d:
        csv = Path(d) / "m.csv"
        csv.write_text("id,score\n1,1.0\n2,2.0\n")
        report = data.load_csv_to_sqlite(str(csv), str(Path(d) / "m.db"), "m")
        assert report.row_count == 2


def test_newtui_explorer_runs_in_process():
    clean, report = ui.smoke()
    assert clean, report
