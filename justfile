# shea — task runner
#
# PIPELINE PARITY: `just check` is the local mirror of .github/workflows/ci.yml;
# .githooks/pre-push calls it. Keep all three in lock-step.
#
# Tools resolve from the active venv, else ~/venv (the workspace default).

PYBIN := env_var_or_default("VIRTUAL_ENV", env_var("HOME") / "venv") / "bin"

default:
    @just --list

# Full local gate: format + lint + test. Zero warnings, all tests.
check: fmt lint test

fmt:
    {{PYBIN}}/black --check src tests

lint:
    {{PYBIN}}/ruff check src tests

test:
    {{PYBIN}}/pytest -q

# Wire .githooks/ as this repo's hooks path (commit-msg + pre-push).
install-hooks:
    git config core.hooksPath .githooks
    @echo "hooks installed: .githooks/commit-msg .githooks/pre-push"
