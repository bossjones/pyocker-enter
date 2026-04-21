# pyocker-enter

[![Release](https://img.shields.io/github/v/release/bossjones/pyocker-enter)](https://img.shields.io/github/v/release/bossjones/pyocker-enter)
[![Build status](https://img.shields.io/github/actions/workflow/status/bossjones/pyocker-enter/main.yml?branch=main)](https://github.com/bossjones/pyocker-enter/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/bossjones/pyocker-enter/branch/main/graph/badge.svg)](https://codecov.io/gh/bossjones/pyocker-enter)
[![Commit activity](https://img.shields.io/github/commit-activity/m/bossjones/pyocker-enter)](https://img.shields.io/github/commit-activity/m/bossjones/pyocker-enter)
[![License](https://img.shields.io/github/license/bossjones/pyocker-enter)](https://img.shields.io/github/license/bossjones/pyocker-enter)

Interactive TUI for entering running Docker containers

- **Github repository**: <https://github.com/bossjones/pyocker-enter/>
- **Documentation** <https://bossjones.github.io/pyocker-enter/>

## Getting started

### Install

```bash
uv tool install --from . pyocker-enter
# or, inside a clone for development:
make install
```

### Usage

Launch the interactive TUI (fuzzy search + shell picker):

```bash
pyocker-enter
```

Skip the TUI and exec straight into a container by name, short-id, or unique
short-id prefix. When `--shell` is omitted, the CLI probes the container for
installed shells and prefers `bash`:

```bash
pyocker-enter web-api
pyocker-enter web-api --shell bash
pyocker-enter web-api -s sh
```

Allowed shells: `sh`, `bash`, `zsh`. Values outside that allow-list are
rejected before `docker exec` is invoked.

### Exit codes

| Code | Meaning                                               |
|------|-------------------------------------------------------|
| 0    | Clean exit or user cancelled the TUI                  |
| 1    | No running container matched, or query is ambiguous   |
| 2    | Docker daemon not reachable                           |
| 3    | Requested shell not installed in the target container |
| 4    | stdin/stdout is not a TTY                             |
| 130  | Process received SIGINT                               |

### Environment

- `PYOCKER_LOG_FILE` — override the default log path
  (`~/.local/state/pyocker-enter/pyocker-enter.log`). The file handler always
  writes one JSON object per line (5 MB × 3 rotating backups).
- `LOG_FORMAT=json|pretty` — console/stderr renderer. Default is the pretty
  Rich-based renderer; set to `json` for machine-readable stderr.

### Development

```bash
make install           # uv sync + pre-commit install
make check             # ruff + ty + deptry + pre-commit
make test              # unit tests with coverage (integration suite skipped)
make test-integration  # spins up docker-compose fixtures; requires Docker
```

---

## Releasing a new version



---

Repository initiated with [osprey-oss/cookiecutter-uv](https://github.com/osprey-oss/cookiecutter-uv).
