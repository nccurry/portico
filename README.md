# Tiller Streamlit

## Development Setup

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
| `task deps` | Check dependency metadata and outdated packages |
| `task deps:update` | Update direct dependencies to latest exact pins |
| `task setup` | Install pinned tools and dependencies |
| `task deps:install` | Install pinned Task, uv, Python, and project dependencies |

The previous `pkg:check` and `pkg:update` names remain available as aliases.

## Test Fixtures

Integration tests use fully synthetic CSV fixtures under `tests/data/fixtures/`.
Do not replace them with data derived from a personal Tiller export.

For local troubleshooting, you can generate anonymized data from a local
Tiller export:

```shell
task fixtures:generate
```

The source workbook is read from `example_data/tillder_data_v2.0.xlsx`. Output
is written to `.local/test-fixtures/`. Both locations are ignored by Git. The
output still preserves personal financial patterns and must not be committed.

## Configure Streamlit

The app reads four sheets from your Tiller spreadsheet: Transactions, Balance
History, Categories, and Accounts. Each needs its own connection with the
appropriate `gid` parameter.

```shell
mkdir -p .streamlit

SPREADSHEET_ID="" # ID from your Google Sheet URL
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

## Install on a Raspberry Pi

The systemd installation requires a 64-bit Raspberry Pi OS installation,
`systemd`, and a non-root user with `sudo` access. The service runs directly
from the clone, so do not move or delete the checkout while it is installed.

Clone the repository and create `.streamlit/secrets.toml` using the configuration
above. To copy an existing secrets file from another computer, first create the
target directory in the clone on the Pi, then run:

```shell
scp .streamlit/secrets.toml <pi-user>@<pi-host>:~/tiller-streamlit/.streamlit/secrets.toml
```

From the repository root on the Pi, install the pinned runtime dependencies and
the system service:

```shell
sh scripts/bootstrap.sh install
```

Bootstrap installs the repository-local Task binary, and `task install` installs
runtime-only dependencies from `uv.lock`, writes
`/etc/systemd/system/tiller-streamlit.service`, enables it at boot, and starts
it. The service runs as the user who performed the installation and listens on
port 8501 on the home network by default:

```text
http://<pi-ip-address>:8501
```

Override the bind address or port when installing:

```shell
sh scripts/bootstrap.sh install ADDRESS=127.0.0.1 PORT=8601
```

Use the repository-local Task binary to manage the service:

| Command | Description |
|---------|-------------|
| `.tools/bin/task service:status` | Show service status |
| `.tools/bin/task service:logs` | Follow the latest service logs |
| `.tools/bin/task service:restart` | Restart the service |
| `.tools/bin/task service:stop` | Stop the service |
| `.tools/bin/task service:start` | Start the service |

To update the installed checkout, pull explicitly and rerun the idempotent
installer:

```shell
git pull --ff-only
sh scripts/bootstrap.sh install
```

Uninstall only the systemd unit with:

```shell
.tools/bin/task uninstall
```

Uninstalling preserves the checkout, `.tools`, `.venv`, and
`.streamlit/secrets.toml`.

The application does not provide authentication. Keep port 8501 on a trusted
private network and do not expose it through public port forwarding. Use a
private VPN or an authenticated reverse proxy for remote access.

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
| `task format` | Auto-fix ruff issues and run mypy |
| `task check` | Run lint and tests |
| `task run` | Run the Streamlit app |
| `task run:production` | Run with the systemd production settings |

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
