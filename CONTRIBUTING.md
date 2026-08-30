# Contributing

Thank you for improving Portico.

## Prepare the repository

1. Fork and clone the repository.
2. Use one of the supported development setups below.
3. Run the demo with synthetic data.

### Dev Container

Open the repository in VS Code and choose **Dev Containers: Reopen in Container**.
The container prepares the locked development environment. Run `task demo` after
the setup command completes.

### uv

Install uv, then run:

```console
uv sync --locked --dev
uv run --locked python -m scripts.run_app --data-source=demo
```

Lint and test without Task:

```console
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest
```

### Task

The native bootstrap supports Linux and Windows development. It installs all
tools inside the repository, so it does not change your system Python.

On Linux, run:

```console
sh scripts/bootstrap.sh
.tools/bin/task demo
```

On Windows, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
.\.tools\bin\task.exe demo
```

The bootstrap installs the pinned Task binary first. Task then installs the
pinned uv and Python versions, synchronizes `uv.lock`, and validates imports.
You do not need mise for this workflow.

Do not put financial records, Google Sheet URLs, webhook URLs, or credentials in commits, issues, screenshots, or logs.

## Make a change

Keep each change focused. Add tests for changed behavior. Update the documentation when you change commands, configuration, or visible behavior.

Run these commands before you open a pull request:

```console
.tools/bin/task check
.tools/bin/task privacy:check
.tools/bin/task docs:check
.tools/bin/task pages:build
.tools/bin/task container:smoke
```

`check` runs linting and the unit and integration test suites. The other
commands cover repository privacy, documentation, the static demo, and the
production container. In PowerShell, replace `.tools/bin/task` with
`.\.tools\bin\task.exe`. Describe the user-visible result and the tests in the pull
request. Use demo data for screenshots.

CI runs the same Task commands in separate jobs inside the shared development
container. Two small jobs validate the native bootstraps. CI also smoke-tests
the production container on AMD64 and ARM64.
