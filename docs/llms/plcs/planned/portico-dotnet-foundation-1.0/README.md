# Portico .NET Foundation 1.0 PLC Packet

## Lifecycle

- Status: Planned
- Created: 2026-09-21
- Owner: Portico maintainers
- Implementation status: Not started
- Depends on: the completed Python archive move in legacy/python

## Purpose

Build the .NET foundation that Portico needs before more desktop UX or MCP work.
The result is a small set of clear modules, a stable in-process application API,
a configuration and data-loading boundary, a useful CLI, and tests that prevent
the layers from drifting back together.

Portico.App remains the executable project. Its job changes: it becomes the
composition root instead of owning finance workflow, CLI parsing, data-source
construction, and desktop rendering together.

## Decisions already made

| Decision | Chosen direction |
| --- | --- |
| Executable name | Keep Portico.App. |
| Application API | In-process C# API only. No HTTP or gRPC server. |
| CLI reports | Defer headless report show commands. |
| Main configuration | Use new portico.toml; do not support the old config.toml contract. |
| Weekly Discord summary | Do not migrate it in this PLC. |
| Python app | Archive it under legacy/python and use it only as reference. |
| UI and MCP | Defer feature work until this foundation is complete. |
| Language | Target .NET 11 and use C# 15 features only where they make a boundary clearer. |

## Scope

### In scope

- A project-reference-enforced dependency direction, backed by architecture
  tests.
- A pure finance core and a transport-neutral application layer.
- Separate configuration and data-loading modules.
- Typed success and failure results for expected configuration, source, and
  cancellation outcomes.
- A command-line interface for run, config check, data check, and doctor.
- A new versioned portico.toml, portico.secrets.toml, and preserved
  desktop-only dashboard.toml boundary.
- Unit, architecture, CLI contract, adapter, process E2E, and retained desktop
  visual test lanes.
- .NET-first task and documentation design.

### Not in scope

- A new desktop visual design, new pages, or new dashboard controls.
- MCP tools or a remote API server.
- Headless report or export commands.
- Python compatibility, Python deployment, Docker/Compose replacement, or
  Python feature parity.
- Migration of weekly_summary, Discord notifications, write-back, OAuth, or
  new data sources.

## Packet files

- [DISCOVERY.md](DISCOVERY.md) records the observed starting point and risks.
- [SRD.md](SRD.md) states the required public behavior and acceptance checks.
- [SADD.md](SADD.md) defines target boundaries, flows, and contracts.
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) gives the phased delivery
  order.
- [TEST_PLAN.md](TEST_PLAN.md) defines the evidence required for completion.

## Proposed project graph

    Portico.App -> Portico.Cli, Portico.Desktop, Portico.Configuration,
                   Portico.Data, Portico.Application
    Portico.Cli -> Portico.Application
    Portico.Desktop -> Portico.Application + Roci
    Portico.Configuration -> Portico.Application + Portico.Finance
    Portico.Data -> Portico.Application + Portico.Finance
    Portico.Application -> Portico.Finance
    Portico.Finance -> no Portico project

The arrows are compile-time references. At runtime, Portico.App creates the
configuration and data-loading implementations and gives them to Application.
The core never calls outward into TOML, files, Google Sheets, Roci, or the CLI.
Portico.Cli parses a typed command. For run, Portico.App dispatches that typed
command to Application and then Desktop, so Portico.Cli never references
Desktop.

## Phase order

| Phase | Result |
| --- | --- |
| 0 | Measured baseline, .NET-first repository rules, and a migration inventory. |
| 1 | New projects, project-reference policy, and architecture tests. |
| 2 | Pure finance types plus Application use cases and typed outcomes. |
| 3 | New configuration and data-loading implementations with safe diagnostics. |
| 4 | Mature CLI, Portico.App composition, and a no-redesign Desktop rewire. |
| 5 | Full test lanes, task commands, docs, and final migration proof. |

## Completion condition

The packet is complete only when the new graph is enforced by tests, the core
does not depend on outer layers, expected failures have stable safe results,
the declared CLI/configuration contracts work from a published process, and
the existing desktop experience still passes its retained UI and visual checks.

The later [Desktop and MCP PLC](../portico-desktop-and-mcp-adapters-1.0/README.md)
may start only after these conditions are met.
