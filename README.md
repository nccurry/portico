# Tiller Streamlit

## Setup

This project bootstraps its own pinned developer tools and Python runtime. You do
not need Python, uv, or Task installed before running bootstrap.

### Windows

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

### macOS or Linux

```shell
sh scripts/bootstrap.sh
```

Bootstrap installs the pinned Task version from `pyproject.toml`, then runs
`task setup`. Task installs the pinned uv and Python versions, creates `.venv`,
and syncs the app plus development dependencies from `uv.lock`.

## Dependencies

`pyproject.toml` is the source of truth for direct app dependencies, direct dev
dependencies, and bootstrap tool versions. `uv.lock` pins the full resolved
environment, including transitive dependencies.

Useful package tasks:

| Command | Description |
|---------|-------------|
| `task pkg:check` | Check for outdated installed packages |
| `task pkg:update` | Update direct dependencies to latest exact pins |
| `task setup` | Install pinned tools and dependencies |
| `task deps:install` | Install pinned Task, uv, Python, and project dependencies |

## Test Fixtures

Integration tests use anonymized CSV fixtures under `tests/data/fixtures/`.
If those CSVs are missing, integration tests skip with a generator message.
The formulas, sign conventions, and supporting tests are cataloged in
[`docs/calculation-audit.md`](docs/calculation-audit.md).

To regenerate fixtures from a local Tiller export:

```shell
task fixtures:generate
```

The source workbook is read from `example_data/tillder_data_v2.0.xlsx` and is
not committed.

## Configure Streamlit

The app reads four sheets from your Tiller spreadsheet: Transactions, Balance
History, Categories, and Accounts. Each needs its own connection with the
appropriate `gid` parameter.

```shell
mkdir -p .streamlit

SPREADSHEET_ID="" # e.g. 1xJ7CTtL3cKBmNYayrDMim13keuqnDWrD312UIu6ZAjE
TRANSACTIONS_GID="" # gid from the Transactions sheet tab URL
BALANCE_HISTORY_GID="" # gid from the Balance History sheet tab URL
CATEGORIES_GID="" # gid from the Categories sheet tab URL
ACCOUNTS_GID="" # gid from the Accounts sheet tab URL

cat <<EOF >> .streamlit/secrets.toml
[connections.transactions]
type = "gsheets"
spreadsheet = "https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/edit?gid=${TRANSACTIONS_GID}"

[connections.balance_history]
type = "gsheets"
spreadsheet = "https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/edit?gid=${BALANCE_HISTORY_GID}"

[connections.categories]
type = "gsheets"
spreadsheet = "https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/edit?gid=${CATEGORIES_GID}"

[connections.accounts]
type = "gsheets"
spreadsheet = "https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}/edit?gid=${ACCOUNTS_GID}"
EOF
```

## Development with Task

This project uses [Task](https://taskfile.dev) as a task runner. After bootstrap,
run `task --list` if Task is available globally, or use `.tools/bin/task --list`.

| Command | Description |
|---------|-------------|
| `task test` | Run all tests |
| `task test:unit` | Run unit tests |
| `task test:integration` | Run integration tests |
| `task test:verbose` | Run tests with verbose output |
| `task test:file -- test_spreadsheet.py` | Run tests for a specific file |
| `task test:match -- test_filter` | Run tests matching a pattern |
| `task test:coverage` | Run tests with coverage report |
| `task lint` | Check code with ruff and mypy |
| `task lint:fix` | Auto-fix ruff issues and run mypy |
| `task check` | Run lint and tests |
| `task run` | Run the Streamlit app |

## Create PyCharm Configuration

Configure PyCharm to run the following command:

* Script: `../tiller-streamlit/.venv/Scripts/streamlit.exe`
* Script Parameters: `run Home.py`

Based on [Run streamlit from PyCharm](https://discuss.streamlit.io/t/run-streamlit-from-pycharm/21624).

## Google Sheets Setup

The app reads the `Categories` and `Accounts` sheets and joins them in Python to
populate derived columns. This means you do not need VLOOKUP formulas in your
Google Sheet. Maintain the Categories and Accounts sheets as normal through
Tiller.

- `Transactions` are joined with `Categories` on `Category` to populate `Group`, `Type`, and `Hide From Reports`
- `Balance History` is joined with `Accounts` using a composite key (`Account - Account # (last 4 of Account ID)`) to populate `Group` and `Hide`
