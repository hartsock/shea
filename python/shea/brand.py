"""The shea brand, applied through newt's runtime rebrand seam.

newt reads five ``NEWT_BRAND_*`` variables at runtime — ``NAME``, ``TAGLINE``,
``LOGO_DIR``, ``LOGO_PREFIX``, ``PLUGINS`` (newt-tui ``brand.rs``; the harness
qualifier in commit attribution comes from ``newt-core`` ``build_info.rs``).
Setting them before exec'ing ``newt`` re-skins the splash, crawl header, and
the ``Co-authored-by`` harness qualifier without a fork or a recompile.
gilamonster-agent does this from Rust (``set_brand_defaults``); this is the
same thing from Python.
"""

from __future__ import annotations

import os
import shutil
import sys

NAME = "shea"
TAGLINE = "Shawn Hartsock's Experimental Agent"

BRAND = {
    "NEWT_BRAND_NAME": NAME,
    "NEWT_BRAND_TAGLINE": TAGLINE,
    # LOGO_DIR / LOGO_PREFIX stay unset until shea has art; newt falls back
    # to its own logo gracefully.
}


def apply_brand(env: dict[str, str]) -> dict[str, str]:
    """Fill shea's brand into ``env`` wherever the operator left a hole.

    An explicit ``NEWT_BRAND_*`` in the incoming env always wins — the same
    set-only-if-unset rule gilamonster-agent uses.
    """
    return {**BRAND, **env}


def main(argv: list[str] | None = None) -> None:
    """``shea [newt args...]`` — run ``newt`` wearing the shea brand."""
    newt = shutil.which("newt")
    if newt is None:
        sys.exit("shea: `newt` not on PATH (cargo install --path newt-agent/newt-cli)")
    args = sys.argv[1:] if argv is None else argv
    os.execve(newt, [newt, *args], apply_brand(dict(os.environ)))
