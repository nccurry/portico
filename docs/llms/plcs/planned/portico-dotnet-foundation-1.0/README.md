# Portico .NET Foundation 1.0 PLC Packet

## Lifecycle

- Status: In progress
- Created: 2026-09-21
- Owner: Portico maintainers
- Implementation status: Phases 0 through 3 are complete. The project
  boundaries, semantic Application reports, versioned Configuration reader,
  and typed CSV/Google Data reader are in place. Phase 4 (CLI, App, and
  Desktop rewire) is next.
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
| Roci dependency | Compile directly against the sibling `../roci` checkout. `ROCI_ROOT` may select another local checkout; CI is deferred. |

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
- [PHASE_0_BASELINE.md](PHASE_0_BASELINE.md) records the measured C# baseline,
  setting inventory, target configuration contract, and behavior-test trace.

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

Phase 1 keeps three exact transition exceptions while the existing code moves:
App retains its current Adapters, Dashboard, Finance, and Roci references
through Phase 4; Adapters retains Dashboard and Finance through Phase 3; and
Dashboard retains Finance through Phase 4. Architecture tests freeze those
sets and reject added Portico or external Roci references. These exceptions do
not change the final graph above.

## Phase order

| Phase | Result |
| --- | --- |
| 0 | Measured baseline, .NET-first repository rules, and a migration inventory. |
| 1 | New projects, project-reference policy, and architecture tests. |
| 2 | Pure finance types plus Application use cases and typed outcomes. |
| 3 | New configuration and data-loading implementations with safe diagnostics. |
| 4 | Mature CLI, Portico.App composition, and a no-redesign Desktop rewire. |
| 5 | Full test lanes, task commands, docs, and final migration proof. |

## Phase 1 verification (2026-09-23)

The combined Phase 1 changes passed `task check` with the clean local Roci
checkout at `../roci-ui-focus-outline-containment` (`c814b027`), selected through
`ROCI_ROOT`. Formatting, the strict build, all 235 nonvisual tests, and the local
Roci source contract passed. `task doctor` reported ready. Architecture tests
covered all nine production projects in Debug and Release.

The default sibling `../roci` was on a separate, dirty Roci branch at
`7511540e` during verification. Its `Roci.Ui` project failed to compile with two
CS1503 errors in data-grid code. The same errors reproduced in a clean Roci
worktree at that commit. The default checkout is therefore not counted as a
passing build; no Roci source was changed for this PLC.

## Phase 2 verification (2026-09-23)

The combined Phase 2 changes passed `task check` against the same clean local
Roci checkout: formatting, strict build, 342 nonvisual tests, and the local
Roci source contract passed. `task doctor` reported ready with the local CSV
demo source, 10 pages, 986 transactions, 432 balances, and 1344 budgets.

The built-in coverage collector measured the named `Portico.Finance` package
at 97.13% lines and 90.20% branches and `Portico.Application` at 98.56% lines
and 93.80% branches. Both exceed the 95%/90% PLC target. The local failing
coverage task remains due by 2026-09-30; Phase 5 cannot pass without it.

## Phase 3 verification (2026-09-23)

The new Configuration and Data readers work together through Application with
the synthetic root `portico.toml`, even when the caller's working directory
differs from the config file's directory. The new reader accepts the existing
demo workbook's `Hide` marker and reports source dates before 1900-01-01 as
typed data problems. It does not call the old Adapters implementation.

After the Phase 3 audit fixes, `task check` passed against the same clean local
Roci checkout: formatting, strict build with zero warnings, all 418 nonvisual
tests, and the local Roci source contract. The existing `task doctor` remained
ready with unchanged demo counts. The aggregate 11-gate audit passed after
fixing blank text-array entries and testing all required CSV headers. The old
App/Adapters route remains only until the Phase 4 rewire.

## Completion condition

The packet is complete only when the new graph is enforced by tests, the core
does not depend on outer layers, expected failures have stable safe results,
the declared CLI/configuration contracts work from a published process, and
the existing desktop experience still passes its retained UI and visual checks.

The later [Desktop and MCP PLC](../portico-desktop-and-mcp-adapters-1.0/README.md)
may start only after these conditions are met.
