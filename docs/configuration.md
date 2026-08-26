# Configuration

Application behavior is configured in TOML. Connection URLs and webhook values
remain in Streamlit secrets.

## Precedence

Settings are loaded in this order, from lowest to highest priority:

1. `config/defaults.toml`
2. Ignored `config/local.toml`, when present
3. Supported environment overrides

Create a local override without overwriting an existing file:

```console
.tools/bin/task config:init
```

Edit only the values you want to change. Unknown keys, wrong types, unsafe paths,
duplicate values, and out-of-range numbers cause a clear startup error.

## Supported environment values

| Variable | Purpose |
| --- | --- |
| `TILLER_CONFIG_PATH` | Use a different local TOML override file. |
| `TILLER_DATA_SOURCE` | Select `google_sheets` or `demo`. |

`task demo` sets the data source explicitly. Normal `task run` does not fall back
to demo data when Google Sheets configuration is missing.

Compose also accepts these deployment values:

| Variable | Purpose | Default |
| --- | --- | --- |
| `HOST_ADDRESS` | Select the host address that publishes the container port. | `127.0.0.1` |
| `PORT` | Select the published host port. | `8501` |
| `TILLER_IMAGE` | Select the local or published image name. | `ghcr.io/nccurry/tiller-streamlit:latest` |

Set `HOST_ADDRESS=0.0.0.0` only for a trusted LAN. The application has no login
screen.

## Settings groups

`config/defaults.toml` documents every supported key. The groups control:

- transaction and duplicate-detection thresholds;
- savings targets and report exclusions;
- discretionary-spending exclusions;
- subscription defaults and detection exclusions;
- financial-independence assumptions and included account groups;
- merchant-description aliases.

Numeric defaults must remain inside the ranges supported by the dashboard controls:

| Setting | Range |
| --- | --- |
| `thresholds.expense` | 1,000–100,000 |
| `thresholds.income` | 5,000–100,000 |
| `thresholds.duplicate_minimum` | 0–1,000 |
| `thresholds.duplicate_days` | 0–7 |
| `financial_independence.expected_return_rate` | 0–20 |
| `financial_independence.withdrawal_rate` | 0.5–10 |
| `financial_independence.projection_years` | 1–100 |

Keep household-specific category names, exact account names, and merchant aliases
in `config/local.toml`. Keep Google Sheet and Discord URLs in
`.streamlit/secrets.toml`.

Merchant aliases map one display name to one or more case-insensitive description
fragments. The longest matching fragment wins. Conflicting fragments are rejected.

```toml
[merchants.aliases]
"EXAMPLE MARKET" = ["EXAMPLE MARKET #", "EXAMPLE-MKT"]
```
