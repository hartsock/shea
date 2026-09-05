# shea — task runner
#
# PIPELINE PARITY: `just check` is the local mirror of .github/workflows/ci.yml;
# .githooks/pre-push calls it. Keep all three in lock-step.
#
# Tools resolve from the active venv, else ~/venv (the workspace default).
# VIRTUAL_ENV is exported because `maturin develop` installs into it.

export VIRTUAL_ENV := env_var_or_default("VIRTUAL_ENV", env_var("HOME") / "venv")
PYBIN := VIRTUAL_ENV / "bin"

default:
    @just --list

# Build the native extension into the venv. Debug by default (the first build
# compiles newt from source — minutes); `just build release` for the lto build.
build profile="dev":
    {{PYBIN}}/maturin develop {{ if profile == "release" { "--release" } else { "" } }}

# Full local gate: format + lint + test. Zero warnings, all tests.
check: fmt lint test

fmt:
    {{PYBIN}}/black --check python tests
    cargo fmt --all -- --check

lint:
    {{PYBIN}}/ruff check python tests
    cargo clippy --all-targets -- -D warnings

test: build
    {{PYBIN}}/pytest -q

# Ratchet newt-agent and newtui (and everything else) forward to current main.
update:
    cargo update

# Wire .githooks/ as this repo's hooks path (commit-msg + pre-push).
install-hooks:
    git config core.hooksPath .githooks
    @echo "hooks installed: .githooks/commit-msg .githooks/pre-push"
