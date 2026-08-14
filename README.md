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

Copy the tracked example file, then replace each placeholder URL:

### Windows

```powershell
Copy-Item .streamlit/secrets.example.toml .streamlit/secrets.toml
```

### macOS or Linux

```shell
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
```

Use the URL from each Google Sheets tab. Each URL must include its numeric
`gid`. The sheet must be readable through its link because the app does not use
a Google service account.

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

## Weekly Discord summaries

The optional Discord notifier posts one weekly expense summary to a private
text channel. It uses outbound HTTPS only. It does not open a port on the
Raspberry Pi, and the Streamlit dashboard does not need to run.

### Requirements

- A private Discord text channel
- Permission to manage webhooks in that channel
- A webhook created for that channel
- Link-readable Transactions and Categories tabs
- Exact expense names from the Categories sheet's `Category` column
- A 64-bit Raspberry Pi OS host with `systemd`, `sudo`, and outbound HTTPS
- The correct local timezone on the Raspberry Pi

Create the webhook under **Channel Settings > Integrations > Webhooks**. Copy
its URL into `.streamlit/secrets.toml`. Discord documents webhook behavior in
its [webhook API reference](https://discord.com/developers/docs/resources/webhook).

WARNING: Treat the webhook URL as a password. If it is exposed, delete or
rotate the webhook in Discord.

Add the notifier configuration to the local secrets file:

```toml
[notifications.discord]
webhook_url = "https://discord.com/api/webhooks/<webhook-id>/<webhook-token>"
categories = ["<exact Category value>", "<another Category value>"]
```

Each configured value must match the `Category` column exactly, including case,
spaces, and punctuation. Do not configure `Group` values. The notifier reads
`Group` and `Type` from the Categories sheet and requires `Type = "Expense"`.

The tracked example contains neutral placeholders. Keep personal category
names, spreadsheet URLs, and the real webhook URL only in the ignored
`.streamlit/secrets.toml` file.

### Check and preview

Run the configuration check first. This command installs the pinned runtime
dependencies. It reads both sheets and checks the webhook without posting:

```shell
sh scripts/bootstrap.sh discord:check
```

Review the exact financial summary locally:

```shell
sh scripts/bootstrap.sh discord:preview
```

Send a connection message that contains no financial data:

```shell
sh scripts/bootstrap.sh discord:test
```

The test message says that the notifier is connected. It does not update the
delivery state for a financial report.

### Install the weekly timer

Check the Raspberry Pi timezone before installation:

```shell
timedatectl
```

If the timezone is wrong, configure the correct `Region/City` value with
`timedatectl`. The timer uses the host's local timezone.

Install and enable the timer:

```shell
sh scripts/bootstrap.sh discord:install
```

The timer runs each Sunday at 8:00 PM. It reports the seven completed days from
the previous Sunday through Saturday. `Persistent=true` starts a missed timer
after the Raspberry Pi returns from an outage.

The report contains:

- One total for each configured Category value, with its top three vendors for
  the reporting week
- Dollar changes from the average of the previous eight completed weeks
- Four-week cumulative totals for each configured category and their combined
  total, compared with the preceding four weeks
- A plain-language count of transactions that still need a category
- The reporting-week combined configured-category total
- The total for all transactions whose joined `Type` is `Expense`

Normal Tiller expenses have negative amounts. The report shows them as positive
spending. Positive refund amounts reduce the total. Dashboard filters,
`Hide From Reports`, and large-transaction thresholds do not apply.

A transaction needs categorization when its Category, Group, or Type metadata
is missing, or when its joined Group is `Uncategorized`. The count covers the
complete Transactions sheet, so older items remain visible until they are
categorized.

The notifier stores successful periods in `.local/discord-weekly-state.json`.
A repeated run skips a period that was sent successfully.

### Operate the notifier

| Command | Description |
|---------|-------------|
| `.tools/bin/task discord:status` | Show the next run and the last service result |
| `.tools/bin/task discord:logs` | Follow notifier logs without financial values |
| `.tools/bin/task discord:preview` | Print the current summary without posting |
| `.tools/bin/task discord:send` | Send the current completed period now |
| `.tools/bin/task discord:test` | Send a connection message without financial data |

For a controlled backfill, specify a completed Saturday:

```shell
.tools/bin/task discord:send PERIOD_END=2026-08-01
```

If that period is already recorded, explicitly force another message:

```shell
.tools/bin/task discord:send PERIOD_END=2026-08-01 FORCE=true
```

Add `OUTPUT=json` to `discord:check`, `discord:preview`, `discord:test`, or
`discord:send` for machine-readable output.

If configuration, source data, or Discord access is invalid, the command exits
with a nonzero status and does not record a delivery.

### Update or uninstall

Update the checkout explicitly, then reinstall the idempotent timer:

```shell
git pull --ff-only
sh scripts/bootstrap.sh discord:install
```

Remove only the Discord service and timer:

```shell
.tools/bin/task discord:uninstall
```

Uninstalling preserves the checkout, runtime dependencies, local secrets, and
delivery state. The dashboard's `install` and `uninstall` tasks remain separate.

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
| `task discord:check` | Check the Discord summary configuration without posting |
| `task discord:preview` | Preview the weekly summary locally |
| `task discord:test` | Send a connection message without financial data |
| `task discord:install` | Install the weekly Discord systemd timer |

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
