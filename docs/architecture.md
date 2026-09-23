# Portico architecture

## Current status

Portico is transitioning from its archived Python/Streamlit implementation to
a .NET application. The active C# code is still an interim design:

- `Portico.Finance` contains financial models and calculations, but no longer
  owns data-source selection.
- `Portico.Application` provides typed check and workspace operations and
  semantic reports alongside the old dashboard path.
- `Portico.Dashboard` contains both report building and some presentation
  state.
- `Portico.Adapters` contains TOML, CSV, and Google Sheets concerns.
- `Portico.App` contains CLI parsing, composition, Roci desktop startup, and
  presentation code.

That structure is useful working software, but it is not the target boundary
model. In particular, the CLI still constructs adapters directly, and dashboard
code still mixes application and desktop concerns. The new Application reports
are not yet wired into the desktop.

## Planned target

The target design is recorded in the
[.NET foundation PLC](llms/plcs/planned/portico-dotnet-foundation-1.0/README.md).
Its key rules are:

1. `Portico.Finance` contains financial rules only.
2. `Portico.Application` owns use cases, stable request/result types, and
   interfaces for outside inputs.
3. Configuration and data-loading projects implement those interfaces from the
   outside.
4. CLI and Desktop depend on Application, never on concrete adapters.
5. `Portico.App` remains the executable composition root and is the only
   project that knows every outer implementation. It dispatches the typed run
   command produced by CLI to Application and Desktop without duplicating CLI
   grammar.
6. Project-reference tests enforce the dependency direction.

The target is not complete until the foundation PLC's acceptance checks pass.
New work should not claim that it already exists.

## Product rules that remain true

- Portico reads personal-finance data and does not write it back.
- Demo data must remain synthetic.
- Secrets, URLs, and personal financial rows must not appear in diagnostics or
  test fixtures.
- Core financial rules must be testable without files, a network connection,
  Roci, or a command shell.
- Configuration stays declarative. TOML selects supported settings; it does not
  contain financial formulas or executable code.

## Legacy reference

The former Python app lives in [legacy/python](../legacy/python/README.md).
It is kept only as historical and behavior reference. `demo/data` remains at
the repository root because the current .NET demo uses it.
