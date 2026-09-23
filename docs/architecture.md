# Portico architecture

## Active .NET design

Portico's finance rules, use cases, input readers, and user interfaces live in
separate projects. A reference arrow means the project on the left may use the
project on the right:

```text
Portico.App           -> Cli, Desktop, Configuration, Data, Application
Portico.Cli           -> Application
Portico.Desktop       -> Application, Roci
Portico.Configuration -> Application, Finance
Portico.Data          -> Application, Finance
Portico.Application   -> Finance
Portico.Finance       -> no other Portico project
```

`Portico.App` is the executable and the only place that wires all the outer
parts together. `Portico.Cli` parses commands and formats terminal results.
`Portico.Desktop` owns the Roci window, dashboard layout, controls, and display
text. Neither project reads main configuration or source data directly.

`Portico.Application` owns the in-process operations, semantic reports,
workspace, and interfaces for reading configuration and a portfolio. It
receives the reader implementations from `Portico.App`; it does not know TOML,
CSV, Google Sheets, or Roci. `Portico.Finance` owns financial records, policy,
and calculations, with no Portico project dependency. The Configuration and
Data projects implement the Application input interfaces. Project-reference
tests enforce this direction in Debug and Release builds.

`Portico.App` asks CLI to parse the command, then calls Application.
`config check` stops after configuration validation. `data check` and `doctor`
also load and normalize the source. For `run`, App passes the opened workspace
to Desktop; Desktop does not recalculate reports from files. Expected failures
return typed, safe problems. CLI selects text or a versioned JSON result and
assigns stable exit codes. The Application API is in-process only; there is no
HTTP, gRPC, or MCP service.

## Files and ownership

- `portico.toml` selects the source and sets financial policy and report
  defaults. `Portico.Configuration` reads it.
- `portico.secrets.toml` holds Google Sheet URLs when that source is selected.
  It is ignored by Git. `Portico.Configuration` reads it without echoing its
  values in diagnostics.
- `dashboard.toml` defines desktop pages, controls, and widgets.
  `Portico.Desktop` reads it when `run` starts. Its optional `demo_data` flag
  controls the synthetic-data banner; it does not change calculations.

See the [configuration guide](configuration.md) for file selection and the
deliberate break from the old configuration format.

## Rules for new work

- Keep finance calculations independent of files, network access, Roci, and
  command parsing. Put new business operations in Application, then add outer
  readers or presenters only where needed.
- Configuration is declarative. TOML selects supported settings; it does not
  contain formulas or executable code.
- Portico reads personal-finance data and does not write it back. Use synthetic
  data in examples and tests. Never include secrets, URLs, or personal rows in
  diagnostics.
- Keep Desktop and CLI dependent on Application, not Configuration or Data.
  Add direct layer tests and update the architecture test if a boundary changes.

The [.NET foundation PLC](llms/plcs/completed/portico-dotnet-foundation-1.0/README.md)
records the phased migration and remaining completion checks. The former
Python app remains in [legacy/python](../legacy/python/README.md) as a behavior
reference only.
