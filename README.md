# Portico

Portico is being rebuilt as a local .NET personal-finance application. The
current C# dashboard remains available while the project establishes its new
foundation.

## Current status

The active application is the C# code under `src/Portico.*`. Its future design
is planned, not implemented, in the .NET foundation PLC:

- [Foundation PLC](docs/llms/plcs/planned/portico-dotnet-foundation-1.0/README.md)
- [Deferred Desktop and MCP PLC](docs/llms/plcs/planned/portico-desktop-and-mcp-adapters-1.0/README.md)

The current demo can be checked without opening a desktop window:

```powershell
dotnet run --no-build --no-restore --project src/Portico.App/Portico.App.csproj -- doctor
```

`portico-demo.toml`, `dashboard.toml`, and `demo/data` are active C# demo
fixtures. They remain at the repository root until the foundation work replaces
their configuration contract.

## Legacy Python reference

The former Streamlit application is archived under
[legacy/python](legacy/python/README.md). It is reference material only. It is
not the active runtime, supported deployment path, or normal test target.

## Architecture

[docs/architecture.md](docs/architecture.md) describes the active transition
state and points to the planned target design. Do not treat the planned project
boundaries as already implemented.
