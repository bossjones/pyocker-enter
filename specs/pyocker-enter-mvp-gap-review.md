# Plan: pyocker-enter MVP Gap Review

## Task Description

Review `specs/pyocker-enter-implementation.md` for gaps that would block an MVP from shipping, then capture the fixes as a concrete follow-up plan. The parent plan is thorough on happy-path architecture (Typer + Textual + docker SDK + structlog + `os.execvp`) and test strategy (unit + Pilot + docker-compose integration), but a close read surfaces a handful of issues that will either (a) make the tool fail under real conditions, (b) produce visibly broken output during live use, or (c) fail CI on day one. This plan enumerates those gaps and prescribes the exact edits to the parent plan and the codebase needed to close them.

## Objective

Produce an augmented spec and a task sequence such that, when executed by the team, `pyocker-enter` v0.1.0 ships with:

1. A display that does not corrupt itself when the TUI is running.
2. Graceful behaviour when invoked outside a real TTY.
3. Deterministic, unit-tested container-name resolution.
4. Consistent Python/ruff/ty version targeting across all config files.
5. A CI pipeline that exercises the unit suite on day one and has a manually-triggered integration-test job.
6. Pinned critical dependencies (textual specifically) so an API-breaking upstream release doesn't break a pinned version of pyocker-enter.
7. A reliable `docker compose` integration fixture that pulls images before waiting on healthchecks.
8. A single documented error-code taxonomy so the CLI behaves predictably in scripts.

## Problem Statement

The parent plan is buildable but has eight concrete risks:

1. **TUI/stderr collision** — `configure_logging` wires a stderr console handler (`ConsoleRenderer`) which will render ANSI frames on top of Textual's display while the TUI is running, producing a visibly broken UI. Once `app.run()` starts, stderr writes must stop or route into Textual's own log sink.
2. **No TTY check before `os.execvp`** — `docker exec -it` requires a real TTY on both stdin and stdout. If pyocker-enter is invoked from a non-interactive context (piped, launched by a non-TTY supervisor, or a CI job), `execvp` will succeed but `docker` will immediately error with `the input device is not a TTY` and the user gets a confusing docker-level message.
3. **Container resolver logic is hand-waved** — Task 7 says "resolve by name OR short_id" without specifying precedence, fallback, or ambiguity handling. This needs its own pure function with unit tests covering: exact-name match, exact short-id match, prefix-id match, multiple matches, zero matches.
4. **Python target version mismatch** — `ruff.toml` (at repo root) says `target-version = "py311"`, `pyproject.toml [tool.ruff]` says `"py310"`, and `[tool.ty.environment]` says `python-version = "3.10"`. `pyproject.toml` also declares `requires-python = ">=3.10,<4.0"`. The mismatch will silently let ruff accept syntax that fails on 3.10 when the CI matrix runs that row. One source of truth needed (`py310` everywhere).
5. **CI matrix tests 3.10–3.14 but no integration job exists** — GitHub Actions `main.yml` runs `make check` + unit tests on a 5-row python matrix. It does not run the docker-compose integration tests. Plan needs to choose: skip them in CI entirely (document as dev-host only), add a dedicated `integration` job on `ubuntu-latest` with Docker-in-Docker (works on GH's Linux runners out of the box), or gate behind `workflow_dispatch`.
6. **No version pin on `textual`** — Textual has had multiple backward-incompatible minor releases. `uv add textual` with no bound will let a future release break this project without warning. Pin to `textual>=0.80,<1.0` (or whatever current stable is when executing) plus an upper-bound.
7. **`docker compose up -d --wait` can fail on first run** due to image pulls racing healthcheck retries on slow CI links. Plan must `docker compose pull` first, then `up -d --wait`.
8. **No codified exit-code taxonomy** — Plan scatters `0 / 1 / 2 / 3` across edge cases but doesn't centralize them. Define `class ExitCode(IntEnum)` with `OK=0, NO_MATCH=1, DAEMON_UNREACHABLE=2, SHELL_UNAVAILABLE=3, NOT_A_TTY=4, USER_CANCELLED=130` and use it everywhere.

Minor issues that are worth addressing but don't block MVP: `image.tags` may be empty when a container was started from an image-id; deptry may false-positive on `docker` SDK; Typer pretty-tracebacks may look out of place — these are noted for v1.1.

## Solution Approach

- **Edit the parent plan in place** (`specs/pyocker-enter-implementation.md`) to add the eight fixes above as new or amended tasks. Don't rewrite — patch surgically so the existing task graph stays stable.
- **Add four modules** (or amend existing ones) to the codebase as part of those tasks:
  - `logging_config.py`: add `suspend_console_logging()` context manager (or a `tui_mode: bool` flag) that removes the stderr handler while the TUI is active.
  - `docker_utils.py`: add `resolve_container(query, records) -> ContainerRecord` with explicit precedence.
  - `cli.py`: add `sys.stdin.isatty() and sys.stdout.isatty()` check before `enter_container`; define and use `ExitCode` enum.
  - `pyproject.toml`: pin `textual`, align ruff `target-version`, standardize `[tool.ruff] target-version` on `"py310"`.
- **Normalize config** — remove root-level `ruff.toml` OR update it to `py310`; keep one source of truth. (Root file wins over `[tool.ruff]` in pyproject.toml per ruff's precedence rules, so the root file is likely what CI actually sees — fix it there.)
- **Update CI** — add an optional `integration` job to `.github/workflows/main.yml` that runs on `ubuntu-latest`, installs Docker (already present on GH runners), and runs `make test-integration`. Gate it behind `workflow_dispatch` plus a label on PRs to keep the default CI fast.

## Relevant Files

Files the team will modify, beyond what the parent plan already touches:

- `specs/pyocker-enter-implementation.md` — amend tasks 1, 2, 5, 7, 10, 13, and 14; add a new section "Error Taxonomy and TTY Handling".
- `ruff.toml` (repo root) — change `target-version = "py311"` → `"py310"` (or delete this file and rely on `[tool.ruff]` in `pyproject.toml` to avoid split config).
- `pyproject.toml` — pin `textual` with bounded range; confirm `[tool.ruff] target-version` stays `"py310"`.
- `.github/workflows/main.yml` — add `integration` job gated behind `workflow_dispatch`.

### New Files

- `src/pyocker_enter/errors.py` — `ExitCode(IntEnum)` and a `CLIError(Exception)` type carrying an exit code.
- `tests/test_resolver.py` — unit tests for `docker_utils.resolve_container`.
- `tests/test_tty_guard.py` — unit tests asserting the TTY guard in `cli.py` refuses `os.execvp` when stdin/stdout aren't TTYs.

## Implementation Phases

### Phase 1: Foundation
Normalize config (Python target version alignment, textual pin), define the `ExitCode` enum, and patch the parent spec so later tasks have one source of truth to work against. No runtime behaviour changes yet.

### Phase 2: Core Implementation
Write the three missing pieces of behaviour: (a) `resolve_container` with unit tests, (b) the TTY guard in `cli.py`, (c) the TUI-mode logging suspension. Wire them into the CLI flow so `pyocker-enter` fails predictably in every problem scenario.

### Phase 3: Integration & Polish
Harden the docker-compose fixture with a `pull` step, add the CI integration job, and run the full suite + a dry-run of the integration tests to confirm the gap list is closed.

## Team Orchestration

- You operate as the team lead and orchestrate the team to execute the plan.
- You're responsible for deploying the right team members with the right context to execute the plan.
- IMPORTANT: You NEVER operate directly on the codebase. You use `Task` and `Task*` tools to deploy team members to the building, validating, testing, deploying, and other tasks.
  - This is critical. You're job is to act as a high level director of the team, not a builder.
  - You're role is to validate all work is going well and make sure the team is on track to complete the plan.
  - You'll orchestrate this by using the Task* Tools to manage coordination between the team members.
  - Communication is paramount. You'll use the Task* Tools to communicate with the team members and ensure they're on track to complete the plan.
- Take note of the session id of each team member. This is how you'll reference them.

### Team Members

- Builder
  - Name: builder-config
  - Role: Normalize Python/ruff/ty target-version config, pin textual, define ExitCode enum, patch parent spec with gap fixes and cross-references. Foundation-only work, no runtime behaviour.
  - Agent Type: builder
  - Resume: true
- Builder
  - Name: builder-resolver
  - Role: Implement `docker_utils.resolve_container` with explicit precedence rules (exact name → exact short id → prefix id → ambiguous → no match) and a full unit-test suite. Update the parent spec's Task 7 to reference it.
  - Agent Type: builder
  - Resume: true
- Builder
  - Name: builder-tty-guard
  - Role: Implement TTY detection and the CLI guard that refuses to call `os.execvp` when stdin/stdout aren't TTYs, wire it into `cli.py`, and write unit tests that fake non-TTY streams.
  - Agent Type: builder
  - Resume: true
- Builder
  - Name: builder-tui-logging
  - Role: Amend `logging_config.py` to add a `suspend_console_logging()` context manager (or equivalent) so structlog's stderr handler is disabled while the Textual app is running. Integrate with `cli.py` so the TUI path wraps `app.run()` in the suspension.
  - Agent Type: builder
  - Resume: true
- Builder
  - Name: builder-ci-compose
  - Role: Add `docker compose pull` step to the integration fixture, add a `workflow_dispatch`-gated integration job to `.github/workflows/main.yml`, and verify the unit-only CI still passes.
  - Agent Type: builder
  - Resume: true
- Validator
  - Name: validator-mvp
  - Role: Read-only verification that every gap in the Problem Statement is addressed by the code changes and the parent spec amendments. Runs `make check`, `make test`, and `make test-integration` on a Docker-enabled host.
  - Agent Type: validator
  - Resume: false

## Step by Step Tasks

- IMPORTANT: Execute every step in order, top to bottom. Each task maps directly to a `TaskCreate` call.
- Before you start, run `TaskCreate` to create the initial task list that all team members can see and execute.

### 1. Normalize Python target-version and pin textual

- **Task ID**: config-normalize
- **Depends On**: none
- **Assigned To**: builder-config
- **Agent Type**: builder
- **Parallel**: false
- Edit `ruff.toml` at repo root: change `target-version = "py311"` to `target-version = "py310"` (matches `pyproject.toml`, `[tool.ty.environment]`, and the minimum row of the CI matrix). Alternative: delete the root `ruff.toml` and let `[tool.ruff]` in `pyproject.toml` be the sole source — prefer deletion to avoid config drift.
- Edit `pyproject.toml` runtime deps so `textual` has a bounded range (look up current latest stable with `uv pip index versions textual`; pin `textual>=<major.minor>,<<next major>.0`).
- Run `uv sync` and `uv run ruff check .` — expect clean output.
- Commit: `chore(config): align ruff target to py310, bound textual version`.

### 2. Add ExitCode enum and CLIError type

- **Task ID**: exit-code-taxonomy
- **Depends On**: config-normalize
- **Assigned To**: builder-config
- **Agent Type**: builder
- **Parallel**: false
- Create `src/pyocker_enter/errors.py`:
  ```python
  from enum import IntEnum

  class ExitCode(IntEnum):
      OK = 0
      NO_MATCH = 1
      DAEMON_UNREACHABLE = 2
      SHELL_UNAVAILABLE = 3
      NOT_A_TTY = 4
      USER_CANCELLED = 130  # SIGINT convention

  class CLIError(Exception):
      def __init__(self, message: str, exit_code: ExitCode) -> None:
          super().__init__(message)
          self.exit_code = exit_code
  ```
- Amend parent spec's "Edge cases to cover" list in Testing Strategy so every numeric exit code is a link to `ExitCode.<NAME>`.
- Commit: `feat(errors): central ExitCode enum and CLIError`.

### 3. Patch parent spec with gap-fix cross-references

- **Task ID**: spec-patch
- **Depends On**: exit-code-taxonomy
- **Assigned To**: builder-config
- **Agent Type**: builder
- **Parallel**: false
- In `specs/pyocker-enter-implementation.md`, amend:
  - **Task 1** — add `uv add typer[all] textual>=<pin>,<<bound> docker rapidfuzz structlog`; note `textual` is pinned.
  - **Task 2** — add a final bullet: "Expose `suspend_console_logging()` context manager that removes the `StreamHandler` targeting stderr for the duration of the `with` block; re-attaches on exit."
  - **Task 5** — replace ad-hoc `ValueError` with `CLIError(..., exit_code=ExitCode.SHELL_UNAVAILABLE)`.
  - **Task 7** — before "If container is provided: resolve by name OR short_id", add: "Call `docker_utils.resolve_container(query, list_running_containers())` — see Task 3b below." Also add TTY guard bullet: "Before returning control to `enter_container`, assert `sys.stdin.isatty() and sys.stdout.isatty()` — if not, raise `CLIError('stdin/stdout is not a TTY', ExitCode.NOT_A_TTY)`."
  - **Task 10** — wrap `PyockerEnterApp().run()` in `with suspend_console_logging():` to stop stderr writes from corrupting the display.
  - **Task 13** — add a bullet before `up -d --wait`: "Run `docker compose -f <path> pull` first so healthcheck retries aren't racing the image download."
  - **Task 14** — add a test `test_resolve_container_ambiguity_raises_cli_error` and a test `test_tty_guard_refuses_when_stdin_not_tty`.
- Add a new top-level section to the spec titled **"Error Taxonomy and TTY Handling"** citing `src/pyocker_enter/errors.py` and documenting the table of exit codes.
- Commit: `docs(spec): cross-reference MVP gap fixes in parent plan`.

### 3b. Implement `resolve_container` with unit tests

- **Task ID**: resolver-impl
- **Depends On**: spec-patch
- **Assigned To**: builder-resolver
- **Agent Type**: builder
- **Parallel**: true (can run alongside tty-guard and tui-logging)
- Write failing tests in `tests/test_resolver.py`:
  - `test_exact_name_wins_over_prefix_id` — two records `web-api`/`webabc1234567`, query `"web-api"` → returns the `web-api` record.
  - `test_exact_short_id_match` — query matches 12-char short_id.
  - `test_prefix_id_match` — query is 6-char unique prefix → returns the matching record.
  - `test_ambiguous_prefix_raises_cli_error` — two containers both prefixed `abc`, query `"abc"` → `CLIError(exit_code=ExitCode.NO_MATCH)` with candidate list in message.
  - `test_no_match_raises_cli_error` — unknown query → `CLIError(exit_code=ExitCode.NO_MATCH)`.
- Implement `docker_utils.resolve_container(query: str, records: list[ContainerRecord]) -> ContainerRecord` with precedence: exact name → exact short id → exact full id → unique prefix of short id → raise.
- Run `uv run pytest tests/test_resolver.py -v` — expect green.
- Commit: `feat(resolver): explicit container name/id resolution`.

### 3c. Implement TTY guard

- **Task ID**: tty-guard
- **Depends On**: spec-patch
- **Assigned To**: builder-tty-guard
- **Agent Type**: builder
- **Parallel**: true (can run alongside resolver-impl and tui-logging)
- Write failing test `tests/test_tty_guard.py::test_cli_refuses_exec_when_stdin_not_a_tty`:
  - Monkeypatch `sys.stdin.isatty` to return `False`.
  - Monkeypatch `docker_utils.list_running_containers` to return one record.
  - Monkeypatch `os.execvp` with a `MagicMock`.
  - Invoke `CliRunner().invoke(app, ["my-container", "--shell", "sh"])`.
  - Assert result `.exit_code == ExitCode.NOT_A_TTY`.
  - Assert `os.execvp` was NOT called.
- Implement a `_require_tty()` helper in `cli.py` that checks `sys.stdin.isatty() and sys.stdout.isatty()` and raises `CLIError(..., ExitCode.NOT_A_TTY)` otherwise. Call it right before every `enter_container(...)` call.
- Commit: `feat(cli): refuse exec when not running in a TTY`.

### 3d. Implement TUI-mode logging suspension

- **Task ID**: tui-logging
- **Depends On**: spec-patch
- **Assigned To**: builder-tui-logging
- **Agent Type**: builder
- **Parallel**: true (can run alongside resolver-impl and tty-guard)
- Amend `logging_config.py`:
  ```python
  from contextlib import contextmanager
  import logging

  @contextmanager
  def suspend_console_logging():
      """Detach the stderr StreamHandler while the TUI owns the terminal."""
      root = logging.getLogger()
      stderr_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)
                         and getattr(h, 'stream', None) is sys.stderr]
      for h in stderr_handlers:
          root.removeHandler(h)
      try:
          yield
      finally:
          for h in stderr_handlers:
              root.addHandler(h)
  ```
- Write test `test_logging_config.py::test_suspend_console_logging_detaches_stderr`:
  - After `configure_logging(log_file=tmp_path/"app.log")`, enter the context manager.
  - Assert `len([h for h in logging.getLogger().handlers if isinstance(h, logging.StreamHandler) and h.stream is sys.stderr]) == 0`.
  - On exit, assert the handler is back.
- In `cli.py`, the TUI branch must be:
  ```python
  with suspend_console_logging():
      result = PyockerEnterApp().run()
  if result:
      _require_tty()
      enter_container(*result)
  ```
- Commit: `feat(logging): suspend stderr handler while TUI is active`.

### 4. Harden docker-compose fixture and add CI integration job

- **Task ID**: ci-compose
- **Depends On**: resolver-impl, tty-guard, tui-logging
- **Assigned To**: builder-ci-compose
- **Agent Type**: builder
- **Parallel**: false
- Update `tests/integration/conftest.py` `compose_stack` fixture to run `docker compose -f <path> pull` before `up -d --wait`.
- Bump per-service healthcheck `retries: 5` → `retries: 15` and `interval: 2s` to 3s as a belt-and-braces guard.
- Append an `integration` job to `.github/workflows/main.yml` gated on `workflow_dispatch` and `pull_request` with label `run-integration`:
  ```yaml
  integration:
    if: github.event_name == 'workflow_dispatch' || contains(github.event.pull_request.labels.*.name, 'run-integration')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-python-env
      - name: Pull fixtures
        run: docker compose -f tests/integration/docker-compose.yml pull
      - name: Run integration tests
        run: make test-integration
  ```
- Commit: `ci: manually-gated integration test job`.

### 5. Final validation

- **Task ID**: validate-all
- **Depends On**: config-normalize, exit-code-taxonomy, spec-patch, resolver-impl, tty-guard, tui-logging, ci-compose
- **Assigned To**: validator-mvp
- **Agent Type**: validator
- **Parallel**: false
- Run `make check` — expect clean ruff/ty/deptry/pre-commit.
- Run `make test` — expect green, coverage ≥ 80%.
- Run `make test-integration` on a Docker-enabled host — expect green.
- Verify exit codes manually: `pyocker-enter nonexistent-container; echo $?` → `1`; `pyocker-enter < /dev/null my-real-container -s sh; echo $?` → `4`.
- Grep parent spec for each of the 8 gap headings in the Problem Statement above — each must be addressed.
- Report any residual issues back to team lead without writing code.

## Acceptance Criteria

- All eight gaps in the Problem Statement are addressed either in code or via an amendment to the parent spec cross-referenced from within.
- `ruff.toml` (root) and `[tool.ruff]` in `pyproject.toml` agree on `target-version = "py310"`, or only one exists.
- `textual` has a pinned upper bound in `pyproject.toml`.
- `src/pyocker_enter/errors.py` exists and is the sole source of exit codes used by `cli.py`.
- `docker_utils.resolve_container` exists, is covered by ≥ 5 unit tests, and handles exact/prefix/ambiguous/none cases explicitly.
- `cli.py` calls a TTY guard immediately before every `enter_container` call and the guard has a test that passes by asserting `ExitCode.NOT_A_TTY`.
- `logging_config.py` exposes `suspend_console_logging()` and the CLI's TUI branch uses it.
- `tests/integration/conftest.py` runs `docker compose pull` before `up -d --wait`.
- `.github/workflows/main.yml` has a manually-triggered `integration` job that runs `make test-integration`.
- `make check` and `make test` both pass cleanly.

## Validation Commands

Execute these commands to validate the task is complete:

- `rg "target-version" ruff.toml pyproject.toml` — assert all matches say `py310`.
- `uv pip tree | rg textual` — confirm version is within the pinned range.
- `uv run python -c "from pyocker_enter.errors import ExitCode; print(ExitCode.NOT_A_TTY)"` — prints `ExitCode.NOT_A_TTY`.
- `uv run pytest tests/test_resolver.py tests/test_tty_guard.py -v` — both green.
- `uv run pytest -k suspend_console_logging -v` — logging suspension test green.
- `rg -n "suspend_console_logging\|\n.*PyockerEnterApp\(\).run\(\)" src/pyocker_enter/cli.py` — confirm the TUI branch is wrapped in the suspension context manager.
- `make check` — clean.
- `make test` — green, ≥ 80% coverage.
- `make test-integration` — green on a Docker host.
- `rg -n "workflow_dispatch" .github/workflows/main.yml` — confirms the gate.
- Cross-check the parent spec: `rg -n "resolve_container\|suspend_console_logging\|ExitCode\|_require_tty\|docker compose.*pull" specs/pyocker-enter-implementation.md` — expect at least one hit per term, confirming the cross-references landed.

## Notes

- **Don't touch the parent spec's numbered task IDs** — other planning/tracking may reference them. Insert sub-tasks (e.g. `3b`, `3c`) and amend bullets within existing tasks instead of renumbering.
- **If deleting root `ruff.toml`**, make sure `.pre-commit-config.yaml`'s ruff hook still finds the pyproject config (it will — ruff walks up from the file under test).
- **Minor issues deferred to v1.1** (do NOT include in MVP): `image.tags` empty fallback beyond `"<none>:<none>"`, deptry tuning for `docker` SDK if it false-positives, Typer pretty-traceback styling, Windows support, `r` to refresh in TUI, `?` help modal, image pull progress UI, publishing to PyPI.
- **New dependencies required**: none — all fixes use stdlib + existing deps.
- **Time estimate**: builder-config ≈ 15 min (straight config edit); builder-resolver ≈ 45 min (TDD with 5 tests); builder-tty-guard ≈ 20 min; builder-tui-logging ≈ 30 min; builder-ci-compose ≈ 20 min; validator-mvp ≈ 15 min. Total ≈ 2½ hours of sequential work, or ≈ 1½ hours with the three Phase 2 tasks running in parallel.
