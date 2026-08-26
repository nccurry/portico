# Quick start

## Try synthetic data

The demo uses committed synthetic CSV files and does not read Streamlit secrets
or contact Google Sheets.

```console
docker compose --profile demo up --build demo
```

Open <http://127.0.0.1:8501>. Stop the server with `Ctrl+C`.

## Connect a Tiller workbook

The app supports four Google Sheets tabs:

- Transactions
- Balance History
- Categories
- Accounts

Make each tab readable through its link. Copy the secrets template:

```console
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
```

Open each tab in Google Sheets and copy its complete URL into the matching
connection. Each URL must use `https://docs.google.com`, contain the workbook ID,
and include one numeric `gid` query value.

Check the configuration before starting the app:

```console
docker compose build live
docker compose --profile live run --rm --no-deps live python -m scripts.doctor
docker compose --profile live up --build live
```

The doctor reads each sheet, validates its basic schema, and returns a nonzero
status when a check fails. It does not print sheet URLs or financial rows.

## Sharing boundary

No service account is required. The app reads the workbook through link-readable
URLs and never writes to it. Anyone who obtains one of those URLs may be able to
read the matching sheet. Keep `.streamlit/secrets.toml` private and do not expose
the app directly to the public internet.

See [deployment.md](deployment.md) for detached operation, updates, health
status, LAN access, and the optional notifier.
