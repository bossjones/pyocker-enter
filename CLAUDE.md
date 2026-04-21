# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This is a **scaffold in pre-implementation state**. `src/pyocker_enter/` currently contains only a placeholder `foo.py` from the `osprey-oss/cookiecutter-uv` template. The real application is fully specified in `specs/pyocker-enter-implementation.md` and is meant to be built task-by-task from that plan. **Read `specs/pyocker-enter-implementation.md` before writing any feature code** — it defines the modules, TDD order, commit boundaries, and acceptance criteria. Don't improvise architecture; follow the plan.

## Target architecture (from the spec)

`pyocker-enter` is a Python port of the npm `docker-enter` package: an interactive TUI for `docker exec`-ing into running containers.

The runtime flow has a deliberately unusual handoff:

1. **Typer CLI** (`pyocker_enter.cli:app`, registered as console script `pyocker-enter`) parses args and decides between direct-exec and TUI paths.
2. **Textual TUI** (`pyocker_enter.tui.app:PyockerEnterApp`) renders a `DataTable` of containers with a `rapidfuzz`-backed search input and a `ShellPickerModal` for shell selection.
3. After the TUI cleanly exits (`app.run()` returns), the CLI calls `os.execvp("docker", ["docker", "exec", "-it", id, shell])` to **replace the Python process**. This is load-bearing: `subprocess.run` would keep Python as the parent and break TTY/signal handling. The execvp call must happen *after* Textual restores the terminal, never from inside an event handler.
4. **Docker access** uses the `docker` SDK (`docker.from_env()`) — not shelling out — for `list_running_containers()` and `probe_available_shells()`. Shell probing runs before the modal so only installed shells appear.
5. **Logging** is `structlog` with dual renderers: `JSONRenderer` to a `RotatingFileHandler` (always), `ConsoleRenderer` to stderr (toggle with `LOG_FORMAT=json`). Default log path: `~/.local/state/pyocker-enter/pyocker-enter.log`, overridable via `PYOCKER_LOG_FILE`.
6. **Shell allow-list:** `{"sh", "bash", "zsh"}` validated before `execvp` — never pass user input into a shell string.

Module layout the spec mandates: `cli.py`, `docker_utils.py`, `fuzzy.py`, `logging_config.py`, `tui/app.py`, `tui/screens.py`, `tui/styles.tcss`.

## Common commands

Tooling is `uv` (not pip/poetry), `ruff` (format + lint), `ty` (type check, Astral's type checker — not mypy), `deptry` (unused-dep audit), `pytest`, `pre-commit`.

```bash
make install          # uv sync + pre-commit install
make check            # uv lock --locked, pre-commit run -a, ty check, deptry src
make test             # pytest with coverage (XML report)
make test-integration # (planned, per spec task 14) integration tests against docker-compose fixtures
make build            # build wheel via pyproject-build
make docs             # mkdocs serve
make docs-test        # mkdocs build -s (strict, warnings-as-errors)
```

Run a single test:

```bash
uv run pytest tests/test_fuzzy.py::test_short_id_matches -v
```

Integration tests (once implemented) are gated behind `@pytest.mark.integration`; `make test` runs unit tests only, `make test-integration` spins up the compose stack in `tests/integration/`.

Cross-Python validation via `tox` (3.10–3.14). CI matrix also runs all five versions; codecov uploads only on 3.11.

## Python version notes

- `pyproject.toml` and `[tool.ruff] target-version` say `py310`.
- `ruff.toml` overrides `target-version = "py311"`.
- `[tool.ty.environment] python-version = "3.10"`.

Write code compatible with 3.10 (use `from __future__ import annotations` when you need newer syntax). Don't "fix" the ruff/pyproject target mismatch without a reason — the spec calls out 3.10 as the floor for install compatibility.

## Claude Code configuration

`.claude/settings.json` wires every hook event (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `SessionStart`, etc.) to Python scripts under `.claude/hooks/` executed via `uv run`. The status line is also a `uv run` script. If hook changes surprise you, read the hook script before assuming it's broken — these emit structured logs to `logs/` that can help diagnose misbehavior. `.mcp.json` registers the ElevenLabs MCP server; `.mcp.json.sample` is the template without the secret.

## Implementation discipline from the spec

- **TDD per task:** each numbered step in `specs/pyocker-enter-implementation.md` writes the failing test first, then the implementation, then commits. One commit per task with the message prefix the spec provides.
- **Delete `foo.py` and `tests/test_foo.py` in task 1** — they're scaffold placeholders, not targets for extension.
- **Logging is not optional:** every significant event (`containers.listed`, `exec.invoked`, errors) must be logged as structured JSON. The audit trail is an acceptance criterion. Log `exec.invoked` *before* calling `os.execvp` — after execvp, no more Python runs.
- **Textual tests** use `async with app.run_test() as pilot:` and require `pytest-asyncio` with `asyncio_mode = "auto"` in `[tool.pytest.ini_options]`.
