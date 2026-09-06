"""The herdr rail: what argv a row becomes, that an absent herdr is simply no
rail, and that nothing the display does can take a trial down."""

from __future__ import annotations

import pytest
from shea import display
from shea.display import herdr_rail, metadata_argv

ROW = {
    "kind": "trial",
    "round": 3,
    "pane": "lane-2",
    "config": {"model": "big", "coder": True},
    "trial": {"ok": True},
}


def test_row_becomes_report_metadata_argv():
    assert metadata_argv(ROW) == [
        "herdr",
        "pane",
        "report-metadata",
        "lane-2",
        "--source",
        "shea",
        "--state-label",
        "working=round-3",
        "--token",
        "model=big",
        "--token",
        "coder=True",
        "--ttl-ms",
        "600000",
    ]


def test_pane_falls_back_to_the_env_herdr_injects(monkeypatch):
    monkeypatch.setenv("HERDR_PANE_ID", "own-pane")
    assert metadata_argv({"round": 1})[3] == "own-pane"


def test_no_pane_anywhere_is_no_report(monkeypatch):
    monkeypatch.delenv("HERDR_PANE_ID", raising=False)
    assert metadata_argv({"round": 1}) is None


def test_non_scalar_config_values_are_dropped(monkeypatch):
    monkeypatch.setenv("HERDR_PANE_ID", "p")
    argv = metadata_argv({"config": {"model": "big", "rails": {"nested": 1}}})
    assert argv.count("--token") == 1
    assert "model=big" in argv


def test_a_state_outside_herdr_s_vocabulary_is_refused(monkeypatch):
    monkeypatch.setenv("HERDR_PANE_ID", "p")
    with pytest.raises(ValueError):
        metadata_argv(ROW, state="thinking")


def test_absent_herdr_is_no_rail(monkeypatch):
    monkeypatch.setattr(display.shutil, "which", lambda _: None)
    assert herdr_rail() is None


def test_the_rail_reports_the_row(monkeypatch):
    monkeypatch.setattr(display.shutil, "which", lambda _: "/usr/bin/herdr")
    seen = []
    monkeypatch.setattr(display.subprocess, "run", lambda argv, **kw: seen.append(argv))

    rail = herdr_rail()
    assert rail.hooks == frozenset({"after_round"})
    rail.handler(ROW)

    assert seen == [metadata_argv(ROW)]


def test_herdr_vanishing_mid_run_does_not_kill_the_trial(monkeypatch):
    monkeypatch.setattr(display.shutil, "which", lambda _: "/usr/bin/herdr")

    def gone(argv, **kw):
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(display.subprocess, "run", gone)
    herdr_rail().handler(ROW)  # no raise


def test_a_headless_row_never_shells_out(monkeypatch):
    monkeypatch.setattr(display.shutil, "which", lambda _: "/usr/bin/herdr")
    monkeypatch.delenv("HERDR_PANE_ID", raising=False)
    monkeypatch.setattr(
        display.subprocess, "run", lambda *a, **k: pytest.fail("shelled out")
    )
    herdr_rail().handler({"round": 1})
