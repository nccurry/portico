<div align="center">

# Tiller Streamlit

**A private, self-hosted dashboard for exploring Tiller-powered personal finances.**

[Demo](#try-the-demo) · [Deployment](docs/deployment.md) · [Google Sheets setup](docs/quickstart.md) · [Contributing](CONTRIBUTING.md)

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/python-3.14-3776AB.svg)](pyproject.toml)

</div>

Tiller Streamlit turns a Tiller workbook into focused views for income, spending,
subscriptions, budgets, net worth, financial independence, and data health. It is
read-only: the app analyzes your sheets but does not change them.

The repository includes synthetic data, so you can explore every dashboard
without a Tiller account or Google Sheet.

## Try the demo

On Linux, clone the repository and run:

```console
docker compose --profile demo up --build demo
```

Open <http://127.0.0.1:8501>. The demo binds only to your computer, makes no
Google Sheets connection, and displays a banner whenever synthetic data is in
use.

Stop the demo with `Ctrl+C`. See [the quick start](docs/quickstart.md) when you
are ready to connect a Tiller workbook.

## What is included

- Income, savings-rate, and spending trends
- Category and merchant analysis
- Recurring-subscription detection
- Budget performance and transaction drill-downs
- Net-worth and financial-independence projections
- Duplicate, stale-account, and mapping checks
- A global control that hides financial values on screen
- Validated settings with tracked defaults and ignored local overrides

## Live Google Sheets

Google Sheets is the only supported live data source. The app reads four
link-readable Tiller tabs: Transactions, Balance History, Categories, and
Accounts. No service account is required.

```console
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
docker compose build live
docker compose --profile live run --rm --no-deps live python -m scripts.doctor
docker compose --profile live up --build live
```

Add each tab URL, including its numeric `gid`, before running the doctor. Anyone
with a link-readable sheet URL may be able to read that sheet, so treat the URLs
as private and never commit `.streamlit/secrets.toml`.

See [the quick start](docs/quickstart.md), [Linux deployment guide](docs/deployment.md),
[configuration reference](docs/configuration.md), and [data schema](docs/data-schema.md).

## Development

Bootstrap the source environment before development:

```console
sh scripts/bootstrap.sh
```

The main local checks are:

```console
.tools/bin/task privacy:check
.tools/bin/task lint
.tools/bin/task test
```

Use `.tools/bin/task demo` for a source-based demo. Use
`.tools/bin/task run:lan` only on a trusted network.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contributor workflow and
[CHANGELOG.md](CHANGELOG.md) for notable changes.

## Security and scope

Tiller Streamlit is a personal application with no login screen. The default
source and container commands publish to `127.0.0.1`. Do not expose the app
directly to the public internet. See [SECURITY.md](SECURITY.md).

This project is an independent community project. It is not affiliated with,
endorsed by, or maintained by Tiller Money.

## License

Copyright 2026 Nick Curry and contributors.

Licensed under the [Apache License 2.0](LICENSE).
