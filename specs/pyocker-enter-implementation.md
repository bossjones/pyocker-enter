# Plan: pyocker-enter — Interactive TUI for entering running Docker containers

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Build a Python port of the old npm `docker-enter` package with an fzf-style interactive TUI that lists running containers, supports fuzzy search, lets the user pick a shell, and hands off the TTY to `docker exec -it` via `os.execvp`.

**Architecture:** Typer CLI entry point that either (a) execs directly into a container when a name/ID and shell are supplied as args, or (b) launches a Textual TUI for container selection + a modal shell picker. After the TUI exits cleanly, the CLI calls `os.execvp("docker", ["docker", "exec", "-it", ID, SHELL])` to replace the Python process so TTY ownership, signals, and readline behave correctly. All operational events are logged via `structlog` to a rotating JSON log file.

**Tech Stack:** Python 3.10+, `typer[all]`, `textual`, `rapidfuzz`, `docker` (SDK), `structlog`, pytest, ruff, ty. Scaffold already generated from `osprey-oss/cookiecutter-uv`.

---

## Task Description

Replace the placeholder `foo.py` in the existing `pyocker-enter` scaffold with a working application composed of:

1. A Typer CLI (`pyocker_enter.cli:app`) registered as console script `pyocker-enter`.
2. A Docker utilities module wrapping the `docker` SDK (list containers, probe available shells inside a container).
3. A Textual TUI with a `DataTable` of containers, a fuzzy-search `Input`, and a `ModalScreen` for shell selection.
4. A `structlog` configuration that renders JSON to a rotating log file and pretty text to the console (toggled by `LOG_FORMAT`).
5. An exec handoff function that uses `os.execvp` only after the TUI has cleanly exited.
6. Tests for docker_utils, the fuzzy matcher, structlog config, and TUI interactions using Textual's `Pilot`.

## Objective

Typing `pyocker-enter` launches a TUI listing running containers; the user fuzzy-searches by name/id, selects one, chooses a shell in a popup, and lands inside the container with a fully interactive TTY. Typing `pyocker-enter my-container --shell bash` skips the TUI entirely and execs straight in. All actions are written to a JSON log file for audit.

## Problem Statement

The npm `docker-enter` tool is unmaintained and requires Node.js. Users who work in Python-first environments want a modern, single-binary-ish (via `uv tool install`) replacement with a better UX: fuzzy search, a shell picker, JSON audit logging, and clean TTY handoff (no parent Python process interfering with signals or readline).

## Solution Approach

- **Typer** for the CLI because it gives us rich `--help` and positional+optional args with minimal code.
- **Textual** (not raw `rich`) because we need an interactive event loop, a reactive `DataTable`, modal screens, and keybindings. `rich` alone cannot do this.
- **`rapidfuzz.process.extract`** for fuzzy ranking of combined `"{name} {short_id} {image}"` strings so the filter feels like fzf instead of naive substring match.
- **`docker.from_env()`** over shelling out to the `docker` CLI for listing/probing — typed objects, no output parsing, works with `DOCKER_HOST`.
- **`os.execvp` after `app.exit()`** for the handoff — critically, we must let Textual restore the terminal before replacing the process. Calling `execvp` from inside an action handler leaves Textual's event loop dangling and produces garbled terminal state.
- **`structlog` with dual renderers** — `JSONRenderer` to a `RotatingFileHandler` for durable audit, `ConsoleRenderer` to stderr for pretty dev output. Toggle console format with `LOG_FORMAT=json` env var; file is always JSON.
- **Shell availability probe** before opening the modal — non-interactive `docker exec <id> sh -c 'command -v bash zsh sh'` to only show installed shells. Cheap (<100ms), prevents the most common footgun (picking bash on an Alpine container).

## Relevant Files

Existing scaffold files we'll touch or reference:

- `pyproject.toml` — add runtime deps (`typer[all]`, `textual`, `docker`, `rapidfuzz`, `structlog`) and dev deps (`textual-dev`, `pytest-asyncio`); add `[project.scripts]` entry point.
- `src/pyocker_enter/__init__.py` — bump `__version__` import, re-export `app`.
- `src/pyocker_enter/foo.py` — **delete**.
- `tests/test_foo.py` — **delete**.
- `README.md` — update "Getting started" with real usage once v1 works.
- `Makefile` — no changes required; existing `make check` / `make test` targets are sufficient.
- `ruff.toml` / `ty.toml` — keep as-is; rule tuning only if a false positive blocks a commit.

### New Files

- `src/pyocker_enter/cli.py` — Typer app, arg parsing, routes to TUI or direct exec.
- `src/pyocker_enter/docker_utils.py` — `list_running_containers()`, `probe_available_shells(container_id)`, `enter_container(container_id, shell)` (wraps `os.execvp`).
- `src/pyocker_enter/fuzzy.py` — `rank(query, containers)` returning ordered list using `rapidfuzz.process.extract`.
- `src/pyocker_enter/logging_config.py` — `configure_logging(log_file: Path | None = None)` wiring stdlib logging → structlog with JSON file + console handlers.
- `src/pyocker_enter/tui/__init__.py` — package marker.
- `src/pyocker_enter/tui/app.py` — `PyockerEnterApp(App)` + `ContainerListScreen`.
- `src/pyocker_enter/tui/screens.py` — `ShellPickerModal(ModalScreen)`.
- `src/pyocker_enter/tui/styles.tcss` — Textual CSS for layout.
- `tests/test_docker_utils.py` — mocks `docker.from_env` and `os.execvp`.
- `tests/test_fuzzy.py` — pure-function tests.
- `tests/test_logging_config.py` — asserts file handler emits valid JSON lines.
- `tests/test_tui.py` — Textual `Pilot`-based tests.
- `tests/conftest.py` — fixtures (fake container objects, tmp log file).
- `tests/integration/__init__.py` — package marker for integration tests.
- `tests/integration/docker-compose.yml` — spins up three long-running dummy containers (see Integration Test Fixtures below).
- `tests/integration/conftest.py` — session-scoped pytest fixture that runs `docker compose up -d --wait` before the suite and `docker compose down -v` after.
- `tests/integration/test_integration_docker.py` — real-docker tests that exercise `list_running_containers`, `probe_available_shells`, and a mocked-execvp path against the compose fixtures.

## Implementation Phases

### Phase 1: Foundation
Scaffold cleanup, dependencies, logging, CLI skeleton. No TUI yet. After this phase a user can run `pyocker-enter --help` and `pyocker-enter <name> --shell bash` and the exec handoff works end-to-end.

### Phase 2: Core Implementation
Docker utilities, fuzzy ranking, Textual TUI with container list + search input + shell picker modal. After this phase `pyocker-enter` with no args launches the full TUI flow.

### Phase 3: Integration & Polish
Shell availability probing, README docs, log rotation sizing, docker-compose integration test suite against dummy containers, manual end-to-end test against a real docker daemon, verify `make check` + `make test` clean.

---

## Integration Test Fixtures

Integration tests run against real, short-lived containers started via `docker compose` from `tests/integration/docker-compose.yml`. Three services, each with `command: ["tail", "-f", "/dev/null"]` as the entrypoint-equivalent so they stay running with no real workload, and each named explicitly so tests can look them up deterministically:

| Service name          | Image              | Shells installed                | Purpose                                     |
|-----------------------|--------------------|---------------------------------|---------------------------------------------|
| `pyocker-test-sh`     | `alpine:3.20`      | `sh` only                       | Minimal container; exercises sh-only path   |
| `pyocker-test-bash`   | `ubuntu:24.04`     | `sh`, `bash`                    | Standard Ubuntu; exercises bash default     |
| `pyocker-test-zsh`    | `ubuntu:24.04` + `apt-get install -y zsh` (via a small inline `Dockerfile` built by the compose file) | `sh`, `bash`, `zsh` | Full shell menu; exercises zsh picker path |

`docker-compose.yml` sketch:

```yaml
services:
  pyocker-test-sh:
    image: alpine:3.20
    container_name: pyocker-test-sh
    command: ["tail", "-f", "/dev/null"]
    healthcheck:
      test: ["CMD", "sh", "-c", "true"]
      interval: 2s
      retries: 5
  pyocker-test-bash:
    image: ubuntu:24.04
    container_name: pyocker-test-bash
    command: ["tail", "-f", "/dev/null"]
    healthcheck:
      test: ["CMD", "bash", "-c", "true"]
      interval: 2s
      retries: 5
  pyocker-test-zsh:
    build:
      context: .
      dockerfile: Dockerfile.zsh
    container_name: pyocker-test-zsh
    command: ["tail", "-f", "/dev/null"]
    healthcheck:
      test: ["CMD", "zsh", "-c", "true"]
      interval: 2s
      retries: 5
```

`tests/integration/Dockerfile.zsh`:

```dockerfile
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends zsh && rm -rf /var/lib/apt/lists/*
```

The session-scoped fixture in `tests/integration/conftest.py` runs `docker compose up -d --wait` (the `--wait` flag blocks until healthchecks pass) and `docker compose down -v` on teardown. All integration tests are gated behind a `@pytest.mark.integration` marker so they can be opted out of with `pytest -m "not integration"`. CI runs them only on Linux runners where Docker is available.

---

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. One commit per numbered task unless otherwise noted. Follow TDD: write the failing test first, run it to see it fail, implement, run it to see it pass, commit.

### 1. Remove scaffold placeholders and add dependencies

- Delete `src/pyocker_enter/foo.py` and `tests/test_foo.py`.
- Replace body of `src/pyocker_enter/__init__.py` with `__version__ = "0.0.1"` (keep it minimal until the CLI module exists).
- Run:
  ```bash
  uv add "typer[all]" "textual>=8.0,<9.0" docker rapidfuzz structlog
  uv add --dev textual-dev pytest-asyncio
  ```
- **Note:** `textual` is pinned to `>=8.0,<9.0` to guard against backward-incompatible minor releases.
- Add to `pyproject.toml`:
  ```toml
  [project.scripts]
  pyocker-enter = "pyocker_enter.cli:app"
  ```
- Add to `[tool.pytest.ini_options]`:
  ```toml
  asyncio_mode = "auto"
  ```
- Run `uv sync` then `make check` — expect failures from the now-missing `cli` module; that's fine, we wire it next.
- Commit: `chore: remove scaffold placeholder, add runtime deps`.

### 2. Implement `logging_config.py` with JSON file output

- Write failing test `tests/test_logging_config.py::test_file_handler_writes_json_lines` that:
  - Calls `configure_logging(log_file=tmp_path / "app.log")`.
  - Emits `structlog.get_logger().info("hello", key="value")`.
  - Reads the log file, asserts each line parses as JSON and contains `event == "hello"`, `key == "value"`, `level == "info"`, and an ISO timestamp.
- Write failing test `test_console_renderer_used_when_log_format_pretty` that monkeypatches `LOG_FORMAT=pretty` and asserts stderr output is NOT valid JSON (or asserts the console processor was selected — cleaner via a helper that returns the processors list).
- Implement `configure_logging(log_file: Path | None = None)`:
  - Default `log_file` to `Path(os.getenv("PYOCKER_LOG_FILE", Path.home() / ".local/state/pyocker-enter/pyocker-enter.log"))`.
  - Create parent dir with `mkdir(parents=True, exist_ok=True)`.
  - Use `logging.handlers.RotatingFileHandler(maxBytes=5 * 1024 * 1024, backupCount=3)` with a formatter that just passes the message through (structlog already serialized it).
  - A shared processor chain: `merge_contextvars`, `add_log_level`, `add_logger_name`, `TimeStamper(fmt="iso", utc=True)`, `StackInfoRenderer()`, `format_exc_info`.
  - File handler wrapped with `structlog.stdlib.ProcessorFormatter(processor=JSONRenderer())`.
  - Console handler wrapped with `structlog.stdlib.ProcessorFormatter(processor=JSONRenderer() if LOG_FORMAT=="json" else ConsoleRenderer())`.
  - Call `structlog.configure(...)` with `wrapper_class=BoundLogger`, `logger_factory=LoggerFactory()`, `cache_logger_on_first_use=True`.
- Expose a `suspend_console_logging()` context manager in `logging_config.py` that removes the `StreamHandler` targeting stderr for the duration of the `with` block and re-attaches it on exit. This prevents structlog's console renderer from writing ANSI frames on top of Textual's display while the TUI is running.
- Run tests → pass.
- Commit: `feat(logging): add structlog config with rotating JSON file handler`.

### 3. Implement `docker_utils.list_running_containers`

- Write failing test `tests/test_docker_utils.py::test_list_running_containers_returns_dataclass_records`:
  - Monkeypatch `docker.from_env` to return a fake client whose `.containers.list(filters={"status": "running"})` returns two fake `Container` objects with attrs `id`, `name`, `image.tags`, `status`, `attrs["State"]["StartedAt"]`.
  - Assert `list_running_containers()` returns a list of `ContainerRecord` dataclasses with fields `id`, `short_id` (12 chars), `name`, `image`, `status`, `started_at` (parsed to `datetime`).
- Implement `ContainerRecord` as a frozen `@dataclass` and the function. Guard against empty `image.tags` by falling back to `"<none>:<none>"`.
- Log `log.info("containers.listed", count=len(records))`.
- Run tests → pass.
- Commit: `feat(docker): list running containers via docker SDK`.

### 4. Implement `docker_utils.probe_available_shells`

- Write failing test `test_probe_available_shells_returns_only_found_shells`:
  - Mock `client.containers.get(id).exec_run("sh -c 'command -v bash zsh sh'", demux=False)` to return `(0, b"/bin/bash\n/bin/sh\n")`.
  - Assert result is `["bash", "sh"]` (ordered, no duplicates, no `zsh`).
- Implement the function. On `docker.errors.APIError` or `ContainerError`, log the error and return `["sh"]` as a safe fallback.
- Commit: `feat(docker): probe for installed shells inside a container`.

### 5. Implement `docker_utils.enter_container` (the execvp handoff)

- Write failing test `test_enter_container_calls_execvp_with_correct_args`:
  - Monkeypatch `os.execvp` with a `MagicMock`.
  - Call `enter_container("abcd1234", "bash")`.
  - Assert `os.execvp.assert_called_once_with("docker", ["docker", "exec", "-it", "abcd1234", "bash"])`.
- Implement. Log `log.info("exec.invoked", container_id=..., shell=...)` BEFORE the execvp call — after execvp nothing in Python runs.
- Validate `shell` is in `{"sh", "bash", "zsh"}` and raise `CLIError("shell not in allow-list", ExitCode.SHELL_UNAVAILABLE)` otherwise (import from `pyocker_enter.errors`).
- Commit: `feat(docker): exec handoff via os.execvp`.

### 6. Implement `fuzzy.rank`

- Write failing tests in `tests/test_fuzzy.py`:
  - `test_empty_query_returns_all_containers_in_original_order`.
  - `test_matching_query_ranks_by_partial_ratio` — given three fake `ContainerRecord`s with names `"web-api"`, `"web-db"`, `"cache"` and query `"web"`, the first two rank above `"cache"`.
  - `test_short_id_matches` — query matches 12-char short ids.
- Implement `rank(query: str, containers: list[ContainerRecord]) -> list[ContainerRecord]`:
  - If `query` is empty, return `containers` unchanged.
  - Build haystack `f"{c.name} {c.short_id} {c.image}"` per container.
  - Use `rapidfuzz.process.extract(query, haystack_dict, scorer=rapidfuzz.fuzz.partial_ratio, limit=None)`; drop entries below a threshold (e.g. `30`).
- Commit: `feat(fuzzy): rank containers with rapidfuzz`.

### 7. Build the Typer CLI skeleton (no TUI yet)

- Write failing test `tests/test_cli.py::test_cli_direct_exec_skips_tui`:
  - Monkeypatch `docker_utils.enter_container` with a `MagicMock`.
  - Monkeypatch `docker_utils.list_running_containers` to return one record with name `"web-api"`.
  - Invoke via `typer.testing.CliRunner`: `pyocker-enter web-api --shell bash`.
  - Assert `enter_container.assert_called_once_with("<the id>", "bash")`.
  - Assert TUI was NOT launched (patch `tui.app.PyockerEnterApp` with a `MagicMock` and assert `.called is False`).
- Implement `cli.py`:
  - `app = typer.Typer(no_args_is_help=False, add_completion=False)`.
  - One command (use `@app.callback(invoke_without_command=True)`) accepting positional `container: str | None` and option `--shell / -s: str | None` with `click.Choice(["sh", "bash", "zsh"])`.
  - On startup: `configure_logging()`.
  - If `container` is provided: call `docker_utils.resolve_container(container, list_running_containers())` — see the resolve_container implementation which applies precedence: exact name → exact short_id → exact full_id → unique prefix of short_id → raise `CLIError(ExitCode.NO_MATCH)`.
  - **TTY guard:** Before calling `enter_container`, assert `sys.stdin.isatty() and sys.stdout.isatty()` via `_require_tty()` — if not, raise `CLIError('stdin/stdout is not a TTY', ExitCode.NOT_A_TTY)` and exit with code 4.
  - If `shell` is None, open the shell picker modal as a standalone Textual screen (implement in later task; for now, default to `sh` and note a TODO).
  - If no `container`: placeholder `typer.echo("TUI not implemented yet")` for this commit.
- Commit: `feat(cli): typer entry point with direct-exec path`.

### 8. Implement `ShellPickerModal`

- Write failing test `tests/test_tui.py::test_shell_picker_returns_selected_shell`:
  - Use Textual `Pilot`. Push `ShellPickerModal(available=["sh", "bash", "zsh"])`, press `down, enter`.
  - Assert `app.return_value == "bash"` (or whatever the second list item is).
- Implement `ShellPickerModal(ModalScreen[str])` in `tui/screens.py`:
  - Vertical layout with a `ListView` of `ListItem(Label(shell))` for each available shell.
  - `on_list_view_selected` → `self.dismiss(event.item.shell_name)`.
  - Key bindings: `escape` dismisses with `None`.
- Commit: `feat(tui): shell picker modal`.

### 9. Implement `ContainerListScreen` with fuzzy search

- Write failing `test_container_list_filters_on_input_change`:
  - Mount the screen with 3 fake containers.
  - Type `"web"` into the input. Assert only containers matching `"web"` remain in the `DataTable`.
- Implement `ContainerListScreen` in `tui/app.py`:
  - Compose: `Input(placeholder="fuzzy search…", id="search")` + `DataTable(id="containers")` + `Footer()`.
  - Columns: `ID`, `NAME`, `IMAGE`, `STATUS`, `UPTIME`.
  - `on_mount`: load containers, store in `self._all`, populate table.
  - `on_input_changed`: re-rank with `fuzzy.rank` and repopulate the table.
  - Binding: `enter` on a row → probe shells → push `ShellPickerModal` → on result, `self.app.exit(result=(container_id, shell))`.
- Commit: `feat(tui): container list screen with fuzzy search`.

### 10. Wire TUI into CLI and finalize the execvp handoff

- Write failing `test_cli_launches_tui_when_no_container_arg`:
  - Monkeypatch `PyockerEnterApp.run` to return `("abcd1234", "bash")`.
  - Invoke `pyocker-enter` with no args.
  - Assert `enter_container.assert_called_once_with("abcd1234", "bash")`.
- In `cli.py`: when `container` is None, instantiate `PyockerEnterApp()`, call `app.run()`, then AFTER it returns and the terminal is restored, call `enter_container(*result)`. The TUI branch must wrap `PyockerEnterApp().run()` with `suspend_console_logging()`:
  ```python
  with suspend_console_logging():
      result = PyockerEnterApp().run()
  if result:
      _require_tty()
      enter_container(*result)
  ```
  If the user pressed q or Ctrl-C, `result` will be `None` → just exit 0.
- Make `PyockerEnterApp(App[tuple[str, str]])` with `SCREENS = {"container_list": ContainerListScreen}` and `on_mount` pushing the initial screen.
- Commit: `feat(tui): wire TUI into CLI with clean execvp handoff`.

### 11. Add shell availability probe to the TUI flow

- Write failing `test_tui_only_offers_installed_shells`:
  - Mock `probe_available_shells` to return `["sh"]`.
  - Drive the pilot to selection; assert modal only shows `sh` (assert via `len(modal.query("ListItem"))`).
- In the `ContainerListScreen`'s `enter` action, call `probe_available_shells(container_id)` before pushing `ShellPickerModal`. If the list has length 1, skip the modal and return immediately.
- Commit: `feat(tui): probe and filter shells to those actually installed`.

### 12. Polish: styles, help text, error messages

- Author `tui/styles.tcss` with a readable two-pane layout (search on top, table below, modal centered).
- Update `typer` help strings for `--shell` and the positional to reflect real behavior.
- Handle `docker.errors.DockerException` at CLI entry with a friendly message (`Is the daemon running? Is DOCKER_HOST set?`) and exit code 2.
- Update `README.md` "Getting started" section to describe real usage: `pyocker-enter`, `pyocker-enter web-api`, `pyocker-enter web-api -s bash`, and the `PYOCKER_LOG_FILE` / `LOG_FORMAT` env vars.
- Commit: `docs: usage + polish TUI styles and error handling`.

### 13. Author docker-compose integration test fixtures

- Register the `integration` marker in `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  markers = ["integration: tests that require a running Docker daemon"]
  ```
- Create `tests/integration/Dockerfile.zsh`:
  ```dockerfile
  FROM ubuntu:24.04
  RUN apt-get update && apt-get install -y --no-install-recommends zsh && rm -rf /var/lib/apt/lists/*
  ```
- Create `tests/integration/docker-compose.yml` with the three services from the **Integration Test Fixtures** section (`pyocker-test-sh` / `pyocker-test-bash` / `pyocker-test-zsh`), each with `command: ["tail", "-f", "/dev/null"]` and per-service healthchecks so `--wait` can block until they're ready.
- Create `tests/integration/conftest.py` with a session-scoped `compose_stack` fixture that:
  - Run `subprocess.run(["docker", "compose", "-f", <path>, "pull"], check=True)` first so image pulls complete before healthcheck retries begin.
  - Bump per-service healthcheck `retries: 5` → `retries: 15` and `interval: 2s` → `interval: 3s` for CI link tolerance.
  - `subprocess.run(["docker", "compose", "-f", <path>, "up", "-d", "--wait"], check=True)` on entry.
  - `subprocess.run(["docker", "compose", "-f", <path>, "down", "-v"], check=True)` on exit.
  - Auto-skips (`pytest.skip("docker daemon not available")`) if `docker version` fails.
  - Applies `@pytest.mark.integration` to every test in the `integration/` subdir via `pytest_collection_modifyitems`.
- Commit: `test(integration): docker-compose fixtures with sh/bash/zsh containers`.

### 14. Write integration tests against the compose stack

- Write `tests/integration/test_integration_docker.py` that depends on `compose_stack`:
  - `test_list_running_containers_sees_all_three_fixtures` — asserts the three fixture names are present in `list_running_containers()`.
  - `test_probe_available_shells_on_alpine_returns_sh_only` — resolves `pyocker-test-sh` and asserts `probe_available_shells(id) == ["sh"]`.
  - `test_probe_available_shells_on_bash_container_returns_sh_and_bash` — resolves `pyocker-test-bash` and asserts `set(probe_available_shells(id)) == {"sh", "bash"}`.
  - `test_probe_available_shells_on_zsh_container_returns_all_three` — asserts `set(probe_available_shells(id)) == {"sh", "bash", "zsh"}`.
  - `test_enter_container_builds_correct_execvp_args_against_real_id` — monkeypatches `os.execvp`, calls `enter_container(real_id, "bash")` against `pyocker-test-bash`, asserts execvp was called with the real 64-char id.
  - `test_resolve_container_ambiguity_raises_cli_error` — two containers with names starting with `"abc"`, query `"abc"` → asserts `CLIError` raised with `exit_code == ExitCode.NO_MATCH`.
  - `test_tty_guard_refuses_when_stdin_not_tty` — monkeypatches `sys.stdin.isatty` to return `False`, asserts `os.execvp` not called and exit code is `ExitCode.NOT_A_TTY`.
- Add a Makefile target for convenience:
  ```make
  .PHONY: test-integration
  test-integration: ## Run integration tests against docker-compose fixtures
  	@uv run pytest tests/integration -v -m integration
  ```
- Run `make test-integration` — expect pass with all fixtures healthy.
- Commit: `test(integration): exercise docker_utils against real containers`.

### 15. Final validation

- Run `make check` — expect pass (ruff, ty, deptry, pre-commit all clean).
- Run `make test` — unit suite passes with coverage report. Integration tests are skipped by marker in the default run; use `make test-integration` to include them.
- Run `make test-integration` — all integration tests pass against the compose fixtures.
- Manual smoke test against a real docker daemon:
  1. `docker compose -f tests/integration/docker-compose.yml up -d --wait`.
  2. `uv run pyocker-enter pyocker-test-sh -s sh` — should drop into an Alpine shell; `exit` returns to host.
  3. `uv run pyocker-enter pyocker-test-zsh -s zsh` — should drop into zsh; `exit` returns to host.
  4. `uv run pyocker-enter` — launches TUI; search `pyocker-test`, select `pyocker-test-bash`, modal shows `sh` + `bash`, pick `bash`, drops into container.
  5. `cat ~/.local/state/pyocker-enter/pyocker-enter.log` — verify each line is valid JSON with `event`, `level`, `timestamp`, and per-event fields.
  6. `docker compose -f tests/integration/docker-compose.yml down -v`.
- No commit unless issues are fixed in this step.

---

## Testing Strategy

- **Unit tests** for pure modules (`fuzzy`, `docker_utils`) with mocked `docker.from_env` and `os.execvp`. These cover the vast majority of logic and run in milliseconds.
- **Logging tests** write to a `tmp_path` log file and parse the lines as JSON to verify the format contract.
- **TUI tests** use Textual's `App.run_test()` → `async with app.run_test() as pilot:` pattern. Drive interactions with `pilot.press(...)` and `pilot.click(...)` and inspect DOM via `app.query_one(...)`. Requires `pytest-asyncio` with `asyncio_mode = "auto"`.
- **CLI tests** use `typer.testing.CliRunner` with `mix_stderr=False` so we can assert separately on stdout/stderr.
- **Integration tests** (tasks 13 + 14) run against a `docker compose` stack of three dummy containers (`pyocker-test-sh` on Alpine, `pyocker-test-bash` and `pyocker-test-zsh` on Ubuntu), each with `tail -f /dev/null` as the long-running command. These exercise `list_running_containers` and `probe_available_shells` against a real daemon, and assert `os.execvp` (mocked in-process) is called with the correct real 64-char ID. Gated behind `@pytest.mark.integration` so the default `make test` stays fast and hermetic.
- **Manual end-to-end** (task 15) is the only test that actually exercises `os.execvp` for real — mocking covers arg shape but only a real handoff catches TTY issues.
- **Edge cases to cover**:
  - Zero running containers → TUI shows an empty-state message, not a crash.
  - Container name ambiguity (two containers with the same name — rare but possible) → prefer exact short_id match, otherwise error with the list of candidates.
  - Docker daemon unreachable → friendly error message, exit 2.
  - Shell not installed when user passes `--shell bash` to an Alpine container → probe first, return a helpful error listing what IS installed, exit 3.
  - User kills TUI with `Ctrl-C` → clean exit, no execvp, exit 0.
  - `--shell` value not in the allowed set → Typer catches it, exit 2 with help output.

## Acceptance Criteria

- `uv tool install --from . pyocker-enter` installs the `pyocker-enter` command on PATH.
- `pyocker-enter --help` shows sensible usage text.
- `pyocker-enter <name-or-id> --shell <sh|bash|zsh>` execs straight into the container (TTY correct: Ctrl-C, tab completion, and readline all work).
- `pyocker-enter` with no args launches a Textual TUI; typing in the search box filters the table fuzzy-match-style; pressing Enter on a row opens a shell picker (unless only one shell is installed); choosing a shell exits the TUI cleanly and execs into the container.
- Every event (containers listed, container selected, shell chosen, exec invoked, errors) is written as one JSON line to the rotating log file at `~/.local/state/pyocker-enter/pyocker-enter.log` (or the path in `PYOCKER_LOG_FILE`).
- `make check` passes (ruff, ty, deptry, pre-commit).
- `make test` passes; coverage ≥ 80% on `src/pyocker_enter/` excluding the Textual CSS and any `if __name__ == "__main__"` guards.
- `make test-integration` passes on a host with Docker: all three dummy containers (`pyocker-test-sh`, `pyocker-test-bash`, `pyocker-test-zsh`) come up healthy, and `probe_available_shells` reports `["sh"]`, `{"sh","bash"}`, and `{"sh","bash","zsh"}` respectively.
- No reference to the `foo` placeholder remains in source or tests.

## Validation Commands

Execute these to validate the task is complete:

- `uv sync` — dependencies installed, lock file up to date.
- `uv run pyocker-enter --help` — CLI registered and help text renders.
- `uv run python -m py_compile $(find src tests -name '*.py')` — everything compiles.
- `make check` — ruff/ty/deptry/pre-commit all clean.
- `make test` — pytest suite green with coverage ≥ 80% (integration tests skipped by marker).
- `uv run pytest tests/test_tui.py -v` — Textual pilot tests specifically.
- `make test-integration` — spins up the compose stack, runs integration tests, tears down. Requires Docker available.
- `docker compose -f tests/integration/docker-compose.yml up -d --wait && uv run pyocker-enter pyocker-test-bash -s bash` (then `exit`, then `docker compose -f tests/integration/docker-compose.yml down -v`) — real end-to-end handoff against a fixture container.
- `python -c "import json, pathlib; [json.loads(l) for l in pathlib.Path.home().joinpath('.local/state/pyocker-enter/pyocker-enter.log').read_text().splitlines()]"` — every log line is valid JSON.

## Notes

- **Scaffold is already generated** — skip the cookiecutter step from the Claude Desktop draft. The existing `pyproject.toml` targets `>=3.10,<4.0` (not 3.12 as the draft suggested); stick with 3.10 for maximum install compatibility and gate any newer-syntax on `from __future__ import annotations`.
- **Dependencies to add (final list):**
  ```bash
  uv add "typer[all]" textual docker rapidfuzz structlog
  uv add --dev textual-dev pytest-asyncio
  ```
- **Why `os.execvp`, not `subprocess.run`:** `subprocess.run` keeps Python as a parent process. The child's TTY is the same tty as the Python process, but signal forwarding and terminal mode restoration on exit are awkward, and behaviors around job control (Ctrl-Z, fg/bg) are subtly broken. `os.execvp` replaces the process image so the shell inherits the tty directly — same as the npm `docker-enter` does it with `execvp(3)`.
- **Why Textual over raw `rich`:** `rich` has no event loop, no input widgets, no modal screens. You'd end up reimplementing half of Textual.
- **Log file location:** follows XDG state dir convention on Linux; on macOS it lands at `~/.local/state/pyocker-enter/pyocker-enter.log` which is fine. Overridable via `PYOCKER_LOG_FILE`.
- **Rotation policy:** 5 MB per file × 3 backups = 20 MB max. Cheap audit trail, bounded disk use.
- **Security:** validate `--shell` against a strict allow-list (`sh`/`bash`/`zsh`) before it reaches `os.execvp`; never pass user input to a shell string.
- **Out of scope for v1:** attaching to exited containers, running arbitrary one-off commands instead of a shell, multi-container broadcast, custom shell binaries outside the allow-list. Add as `--exec CMD` and `--any-shell PATH` flags in v2 only if users actually ask.

---

## Error Taxonomy and TTY Handling

All exit codes are defined in `src/pyocker_enter/errors.py` as `ExitCode(IntEnum)`. Every code path in `cli.py` that exits non-zero must use one of these values — never bare integer literals.

| Code | Name | Meaning |
|------|------|---------|
| 0 | `OK` | Clean exit or user cancelled TUI without selecting |
| 1 | `NO_MATCH` | No running container matched the query, or query is ambiguous |
| 2 | `DAEMON_UNREACHABLE` | Docker daemon not reachable (`docker.errors.DockerException`) |
| 3 | `SHELL_UNAVAILABLE` | Requested shell not installed in the target container |
| 4 | `NOT_A_TTY` | `stdin` or `stdout` is not a TTY; `docker exec -it` would fail |
| 130 | `USER_CANCELLED` | Process received SIGINT (Ctrl-C convention) |

### TTY Guard

`cli.py` must call `_require_tty()` before every `enter_container(...)` call. `_require_tty()` checks `sys.stdin.isatty() and sys.stdout.isatty()` and raises `CLIError('stdin/stdout is not a TTY', ExitCode.NOT_A_TTY)` if either is false. This prevents the confusing `the input device is not a TTY` error from Docker.

### TUI Logging Suspension

While Textual owns the terminal, `logging_config.suspend_console_logging()` removes the stderr `StreamHandler` so structlog's `ConsoleRenderer` does not write ANSI escape sequences on top of Textual's display. The handler is re-attached when the context manager exits (i.e., after `app.run()` returns).
