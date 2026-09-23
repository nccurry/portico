# Portico

Portico is a local .NET personal-finance app. It reads CSV files or Google
Sheets, checks the data, and opens a desktop dashboard. It does not change the
source data. The included data is synthetic.

## Build from local source

Install the .NET 11 preview SDK pinned in [global.json](global.json) and the
`task` CLI. Portico builds directly against a sibling Roci source checkout at
`../roci`.
Set `ROCI_ROOT` if your checkout is elsewhere:

```powershell
$env:ROCI_ROOT = "C:\worktrees\roci"
task
```

`task` runs the normal non-visual .NET checks. `task visual` runs the opt-in
desktop capture tests. Continuous integration is deferred while Roci is a
local source dependency.

## Check data and open the dashboard

The checked-in [portico.toml](portico.toml) uses the synthetic CSV files in
[demo/data](demo/data). [dashboard.toml](dashboard.toml) supplies the desktop
layout and marks this example as demo data. From the repository root:

```powershell
task doctor
task run
```

For the complete command set and exit codes, run:

```powershell
dotnet run --project src/Portico.App/Portico.App.csproj -- --help
```

The headless checks are `config check`, `data check`, and `doctor`. Each accepts
`--output json` for scripts. `config check` reads configuration but not source
data; the other two load and validate it. `run` opens the desktop window and
does not support JSON output. No command is the same as `run`.

To use your own files, start with the [configuration cutover guide](docs/configuration.md).
The current configuration follows the `portico.toml` schema. Old
`config.toml` and `portico-demo.toml` document shapes are not accepted, even
when selected with `--config`.

## Code and plans

[Architecture](docs/architecture.md) shows the active .NET boundaries. The
[foundation PLC](docs/llms/plcs/completed/portico-dotnet-foundation-1.0/README.md)
tracks the remaining quality and documentation checks. Desktop feature changes
and MCP are deferred to the [next PLC](docs/llms/plcs/planned/portico-desktop-and-mcp-adapters-1.0/README.md).

The former Python/Streamlit app is archived under
[legacy/python](legacy/python/README.md). It is reference material, not an
active runtime or normal test target.
