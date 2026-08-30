<p align="center">
  <img src="assets/brand/logo.svg" alt="Portico logo" width="180" />
</p>

<h1 align="center">Portico</h1>

<p align="center">
  <strong>A private, self-hosted dashboard for your Google Sheets-powered finances.</strong>
</p>

<p align="center">
  <a href="#try-the-demo">Try the demo</a>
  |
  <a href="#connect-google-sheets">Connect Google Sheets</a>
  |
  <a href="#run-portico-on-linux">Run on Linux</a>
  |
  <a href="#development">Develop</a>
</p>

<p align="center">
  <a href="https://github.com/nccurry/portico/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/nccurry/portico/actions/workflows/ci.yml/badge.svg" /></a>
  <a href="pyproject.toml"><img alt="Python 3.14" src="https://img.shields.io/badge/python-3.14-3776AB?logo=python&amp;logoColor=white" /></a>
  <a href="https://github.com/nccurry/portico/actions/workflows/ci.yml"><img alt="Code coverage: 90%" src="https://img.shields.io/badge/coverage-90%25-brightgreen" /></a>
  <a href="#try-the-demo"><img alt="Synthetic demo included" src="https://img.shields.io/badge/demo-synthetic_data-2DA44E?logo=streamlit&amp;logoColor=white" /></a>
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-blue.svg" /></a>
  <a href="https://github.com/nccurry/portico/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/nccurry/portico?display_name=tag&amp;sort=semver" /></a>
</p>

---

Portico turns a Google Sheets workbook into focused views for income, spending,
subscriptions, budgets, net worth, financial independence, and data health. The
app reads your sheets but does not change them.

Portico works with any Google Sheets workbook that has the required tabs and
columns. Its data model follows the
[Tiller Foundation Template](https://help.tiller.com/en/articles/3250724-what-is-the-tiller-foundation-template),
which is the recommended starting point.

The repository includes synthetic data. You can explore every dashboard without
a Tiller account or a Google Sheets workbook.

## Screenshots

These screenshots use the committed synthetic data. They contain no personal
financial records.

<p align="center">
  <img src="assets/screenshots/demo-overview.png" alt="Demo dashboard with net worth metrics, account groups, and a balance history chart" />
</p>

### Spending analysis

![Demo spending dashboard with category trends and rankings](assets/screenshots/demo-spending.png)

### Budget tracking

![Demo budget dashboard with plan status and monthly allocation](assets/screenshots/demo-budget.png)

### Financial independence

![Demo financial independence dashboard with progress and projection charts](assets/screenshots/demo-financial-independence.png)

### Data health

![Demo data health dashboard with quality checks and duplicate review](assets/screenshots/demo-data-health.png)

## Try the demo

Install Docker Engine and Docker Compose version 2. Then clone the repository and
start the demo:

```console
git clone https://github.com/nccurry/portico.git
cd portico
docker compose --profile demo up --build demo
```

Open <http://127.0.0.1:8501>. The demo accepts connections only from the local
computer. It does not load Streamlit secrets or contact Google Sheets.

Press `Ctrl+C` to stop the demo.

## Connect Google Sheets

Google Sheets is the only supported live data source. No service account is
required.

### Prepare the workbook

Create these four tabs:

- Transactions
- Balance History
- Categories
- Accounts

The Tiller Foundation Template already has these tabs and the expected columns.
Other workbooks work when their columns match the schema in this README.

For each tab, set **General access** to **Anyone with the link** and select the
**Viewer** role. Anyone who gets a sheet URL can read that sheet. Treat each URL
as private.

### Add the sheet URLs

Copy the secrets template:

```console
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
chmod 600 .streamlit/secrets.toml
```

The container runs as Linux user and group ID `1000`, which matches the first
normal user on most Linux systems. The file must be owned by that user so the
container can read it without making it public to other host users.

Open `.streamlit/secrets.toml`. Replace each example URL with the full URL for
the matching tab. Each URL must use `https://docs.google.com` and include the
numeric `gid` for that tab.

Never commit `.streamlit/secrets.toml`. Git ignores this file by default.

### Check and start Portico

Build the image and check the workbook:

```console
docker compose build live
docker compose --profile live run --rm --no-deps live python -m scripts.doctor
```

The check reads each sheet and validates its basic structure. It does not print
sheet URLs or financial rows.

Start Portico:

```console
docker compose --profile live up --build --detach live
```

Open <http://127.0.0.1:8501>.

## Google Sheets schema

Column names are case-sensitive. Portico ignores unknown columns.

### Transactions

Required columns:

`Date`, `Category`, `Amount`, `Account`, `Month`, `Week`, `Full Description`,
`Institution`, `Account #`, `Date Added`, and `Categorized Date`.

Dates must use a format that pandas can read. Amounts can contain dollar signs
and commas. Tiller normally records expenses as negative values and income as
positive values.

### Balance History

Required columns:

`Date`, `Time`, `Balance`, `Account`, `Account #`, `Account ID`, `Institution`,
`Class`, `Month`, `Week`, and `Date Added`.

Portico also reads account type, status, and group columns from standard Tiller
sheets when those columns exist.

### Categories

Required columns:

`Category`, `Group`, `Type`, and `Hide From Reports`.

Portico treats later columns with date names as monthly budget columns. Budget
values can contain dollar signs and commas.

### Accounts

The sheet must contain at least four columns. Portico treats the first four as
`Account`, `Class Override`, `Group`, and `Hide`. It ignores later columns.

## Run Portico on Linux

The container is the supported deployment method. It runs as a non-root user,
uses a read-only filesystem, and includes a health check.

### Common commands

Show service and health status:

```console
docker compose --profile live ps
```

Follow the logs:

```console
docker compose --profile live logs --follow live
```

Stop the containers:

```console
docker compose --profile demo --profile live down
```

Update Portico:

```console
git pull --ff-only
docker compose --profile live up --build --detach live
```

Portico stores no application data in the container. The update keeps the
secrets and local configuration files on the host.

### Network access

The default address is `127.0.0.1:8501`. Only the Linux host can connect to this
address.

To use a different host port, set `PORT`:

```console
PORT=8601 docker compose --profile live up --detach live
```

To accept connections from a trusted local network, set `HOST_ADDRESS`:

```console
HOST_ADDRESS=0.0.0.0 docker compose --profile live up --detach live
```

Portico has no login screen. Do not forward its port to the public internet. A
public deployment requires an authenticated TLS reverse proxy.

Copy `.env.example` to `.env` to keep the host address, port, and timezone
settings between commands.

## Configuration

Tracked defaults live in [`config/defaults.toml`](config/defaults.toml). The
defaults cover thresholds, report exclusions, subscription detection,
financial-independence assumptions, and merchant aliases.

Create an ignored local override:

```console
cp config/local.example.toml config/local.toml
```

Edit only the values that differ from the defaults. Portico stops with an error
for unknown keys, wrong types, unsafe paths, duplicate values, and values outside
the supported ranges.

These environment variables change the main application settings:

| Variable | Use |
| --- | --- |
| `PORTICO_CONFIG_PATH` | Select a different local TOML file. |
| `PORTICO_DATA_SOURCE` | Select `google_sheets` or `demo`. |

Compose also reads `HOST_ADDRESS`, `PORT`, `TZ`, and `PORTICO_IMAGE`.

Keep household category names, account names, and merchant aliases in
`config/local.toml`. Keep Google Sheets and Discord URLs in
`.streamlit/secrets.toml`.

## Optional Discord summary

Portico can send a weekly expense summary to a Discord channel. It reads the
Transactions and Categories tabs. You select which expense categories the
message follows.

The report includes:

- Spending for each selected category
- The change from its eight-week average
- The three largest vendors in each category
- A comparison between the latest four weeks and the prior four weeks
- Total expenses and the number of uncategorized transactions

### Create the Discord webhook

1. Open **Server Settings** in Discord.
2. Select **Integrations**, then **Webhooks**.
3. Create a webhook named `Portico`.
4. Select the private channel that will receive the report.
5. Copy the webhook URL.

Discord recommends an incoming webhook for a service that only sends messages.
Portico does not require a Discord bot or Discord application.

Add the URL and exact category names to `.streamlit/secrets.toml`:

```toml
[notifications.discord]
webhook_url = "https://discord.com/api/webhooks/<webhook-id>/<webhook-token>"
categories = ["Everyday Food", "Local Dining"]
```

Each category must exist in the Categories tab and use the `Expense` type.
Treat the webhook URL as a password.

### Preview and test the message

Build the notifier and check its configuration:

```console
docker compose build notifier
docker compose --profile notifier run --rm notifier check
```

Preview the report without contacting Discord:

```console
docker compose --profile notifier run --rm notifier preview
```

Send a test message that contains no financial data:

```console
docker compose --profile notifier run --rm notifier test
```

Send the latest completed weekly report:

```console
docker compose --profile notifier run --rm notifier send
```

The notifier stores sent periods in the `notifier-state` Docker volume. It skips
a period after a successful send.

### Example message

Discord displays the report as a colored embed. A report with synthetic values
looks like this:

```text
Weekly spending
Jul 26 - Aug 1, 2026

Watched categories
Everyday Food — $120.00 · $20.00 above usual
Top vendors: KROGER $80.00 · ALDI $40.00
Local Dining — $40.00 · $20.00 below usual
Top vendors: CAFE $40.00

Watched total: $160.00
4-week watched total: $680.00 · $20.00 less than prior 4 weeks
All expenses: $900.00
Needs categorization: 4 transactions
```

### Schedule the report with systemd

The example [service](deploy/systemd/portico-discord-summary.service) and
[timer](deploy/systemd/portico-discord-summary.timer) send the report each
Sunday at 9:00 AM in the host timezone. A missed run starts after the host comes
back online.

The unit expects the repository at `/opt/portico` and Docker at
`/usr/bin/docker`. If your paths differ, edit `WorkingDirectory` or `ExecStart`
in the service file. Keep `WorkingDirectory` unquoted.

Set `TZ` in `.env` to the host timezone. Then build and check the notifier before
you install the timer.

Install and start the timer:

```console
sudo cp deploy/systemd/portico-discord-summary.service /etc/systemd/system/
sudo cp deploy/systemd/portico-discord-summary.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now portico-discord-summary.timer
```

Show the next scheduled run:

```console
systemctl list-timers portico-discord-summary.timer
```

Read the logs from the last run:

```console
sudo journalctl -u portico-discord-summary.service
```

Change `OnCalendar` in the timer file to use another weekly time. Then run
`sudo systemctl daemon-reload` and restart the timer.

## Development

### Dev Container

The recommended setup is the repository Dev Container. Open the repository in
VS Code and choose **Dev Containers: Reopen in Container**. Then run:

```console
task demo
```

The container includes the pinned Python, uv, Task, Docker CLI, Buildx, and
development dependencies.

### Native bootstrap

The bootstrap installs all tools inside the repository. It does not change the
system Python installation.

On Linux:

```console
sh scripts/bootstrap.sh
.tools/bin/task demo
```

On Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
.\.tools\bin\task.exe demo
```

You do not need a system Python, uv, Task, or mise installation.

### Direct uv commands

Contributors who already use uv can run:

```console
uv sync --locked --dev
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest
uv run --locked python -m scripts.run_app --data-source=demo
```

### Checks

Task provides short names for the same local checks that CI runs:

```console
.tools/bin/task check
.tools/bin/task privacy:check
.tools/bin/task docs:check
.tools/bin/task pages:build
.tools/bin/task container:smoke
```

In PowerShell, replace `.tools/bin/task` with `.\.tools\bin\task.exe`.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before you submit a change. Community
participation follows the [Code of Conduct](CODE_OF_CONDUCT.md).
Read the [architecture guide](docs/architecture.md) before you design a feature.

## Security and scope

Portico is a personal application with no login screen. Source commands and
container ports use `127.0.0.1` by default. Read [SECURITY.md](SECURITY.md) before
you expose the app beyond the local computer.

This project is independent. Tiller Money does not endorse or maintain it.

## License

Copyright 2026 Nick Curry and contributors.

Portico uses the [Apache License 2.0](LICENSE).
