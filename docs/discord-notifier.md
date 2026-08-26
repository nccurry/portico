# Discord notifier

The optional notifier creates a weekly expense summary. It uses the same
link-readable Transactions and Categories tabs as the dashboard.

## Configure the notifier

Add the Discord values to `.streamlit/secrets.toml`:

```toml
[notifications.discord]
webhook_url = "https://discord.com/api/webhooks/<webhook-id>/<webhook-token>"
categories = ["Example Expense Category"]
```

Treat the webhook URL as a password. Use exact, case-sensitive Category values.

Set `TZ` in `.env` to the Linux timezone for your location. The notifier uses
this timezone to select the latest completed Saturday.

## Validate the configuration

```console
docker compose build notifier
docker compose --profile notifier run --rm notifier check
```

This command reads the configured sheets and validates the webhook. It does not
create a Discord message.

## Preview and send

Show the report without contacting Discord:

```console
docker compose --profile notifier run --rm notifier preview
```

Send a connection message without financial data:

```console
docker compose --profile notifier run --rm notifier test
```

Send the current completed period:

```console
docker compose --profile notifier run --rm notifier send
```

The notifier stores successful delivery periods in the `notifier-state` Docker
volume. A second command skips a period that was sent successfully.

For a controlled backfill, specify a completed Saturday:

```console
docker compose --profile notifier run --rm notifier send --period-end=2026-08-01
```

If you intend to send the same period again, add `--force`.

The container does not include a scheduler. Run these one-shot commands manually.
