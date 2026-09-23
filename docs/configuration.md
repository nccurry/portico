# Configure Portico

Portico uses a versioned `portico.toml` for source selection and financial
settings. Start with the checked-in [synthetic example](../portico.toml). The
desktop layout lives separately in [dashboard.toml](../dashboard.toml).

## Clean cutover from the old configuration

Create a new `portico.toml` from the example and carry over only settings that
match its supported fields. There is no converter, fallback parser, or
`config.toml` compatibility mode. The old `portico-demo.toml` format is also
unsupported. An explicit `--config` may name any file, but its contents must
follow the new schema. Unsupported fields, including `weekly_summary`, fail
validation. Do not put formulas or executable code in TOML.

The checked-in example points to `demo/data` relative to its own location.
If you copy it elsewhere, change `[data].directory` to your CSV folder or copy
the synthetic files with it. Portico does not search parent directories for a
configuration file.

## Choose a source

For local CSV, keep these settings in `portico.toml`:

```toml
schema_version = 1

[data]
source = "local_csv"
directory = "demo/data"
```

The directory must contain `transactions.csv`, `balance_history.csv`,
`categories.csv`, and `accounts.csv` in the expected workbook format. The
other sections in the [complete example](../portico.toml) are also required;
this snippet only shows source selection.

For Google Sheets, set `source = "google_sheets"` in `[data]` and remove
`directory`. Copy [portico.secrets.example.toml](../portico.secrets.example.toml)
to `portico.secrets.toml`. Fill its four `[sheets]` values with HTTPS Google
Sheets tab URLs that have a numeric `gid` and can be fetched as CSV. Keep this
file private; Git ignores `portico.secrets.toml`. Portico reads the selected
secret file only for the Google Sheets source, and reports missing values by
setting name without printing their URLs.

## Select files and check them

From the directory containing `portico.toml`, run the executable or use
`dotnet run --project src/Portico.App/Portico.App.csproj --` from the repository
root. The commands below show the executable form:

```text
portico config check [--config PATH] [--secrets PATH] [--output text|json]
portico data check   [--config PATH] [--secrets PATH] [--output text|json]
portico doctor       [--config PATH] [--secrets PATH] [--output text|json]
portico run          [--config PATH] [--secrets PATH] [--dashboard PATH]
```

With no command, Portico runs the desktop. `config check` validates settings
without loading financial data. `data check` and `doctor` both load and
validate the source, then report its row counts. `run` loads a workspace and
opens the desktop. `--dashboard` applies only to `run`; `--output` applies only
to checks. Options select whole files, not individual source fields or URLs.

The default main file is `./portico.toml`, relative to the process working
directory. If Google Sheets is selected, the default secret file is
`portico.secrets.toml` beside the selected main file. `run` likewise uses
`dashboard.toml` beside the selected main file. Explicit file paths are
relative to the process working directory; relative data directories inside
`portico.toml` are relative to that file. There is no parent search or hidden
configuration overlay.

Checks default to text. For scripts, add `--output json` to get one
`portico.command-result.v1` object on standard output after successful command
parsing. A successful config check looks like this:

```json
{"schema":"portico.command-result.v1","command":"config-check","outcome":"success","details":{"source":"local_csv"},"problems":[]}
```

Data check and doctor add `transactions`, `balances`, and `budgets` counts to
`details`. An expected failure sets `outcome` to `failure`, `details` to `null`,
and supplies a `problems` array with `code`, `message`, `field`, and
`retryable`. Expected results go to standard output; invalid command syntax
and unexpected host errors go to standard error. Neither output includes
configured URLs or private rows.

| Exit code | Meaning |
| --- | --- |
| 0 | Ready; warnings may be present. |
| 1 | Unexpected internal failure. |
| 2 | Invalid command or option. |
| 3 | Invalid configuration, dashboard file, or missing secret. |
| 4 | Permanent source or data failure. |
| 5 | Cancelled operation or retryable source failure. |

The `dashboard.toml` file controls presentation only. Its optional
`demo_data = true` marks the checked-in synthetic dashboard. Omit it or set it
to `false` for real data; it does not select the source or affect calculations.
