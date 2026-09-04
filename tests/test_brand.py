"""One check per branch: the brand fills holes, yields to the operator, and
actually reaches newt's attribution seam when a `newt` binary is present."""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from shea.brand import BRAND, apply_brand


def test_brand_fills_holes_and_yields_to_operator():
    assert apply_brand({})["NEWT_BRAND_NAME"] == "shea"
    assert apply_brand({"NEWT_BRAND_NAME": "custom"})["NEWT_BRAND_NAME"] == "custom"
    assert set(BRAND) <= set(apply_brand({"PATH": "/bin"}))


@pytest.mark.skipif(shutil.which("newt") is None, reason="newt binary not on PATH")
def test_newt_attribution_wears_the_brand():
    # Strip any operator brand so the assertion is about shea's defaults.
    clean = {k: v for k, v in os.environ.items() if not k.startswith("NEWT_BRAND_")}
    out = subprocess.run(
        ["newt", "identity"],
        env=apply_brand(clean),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout
    assert "(shea v" in out, out
