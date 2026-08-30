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

Run `sh scripts/bootstrap.sh` on Linux, or `scripts\bootstrap.ps1` in PowerShell.
Then run `.tools/bin/task demo` on Linux, or `.\.tools\bin\task.exe demo` in
PowerShell. The bootstrap installs the pinned local copies of uv, Task, and
Python.

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
