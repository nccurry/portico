# Portico Desktop and MCP Adapters 1.0 PLC Packet

## Lifecycle

- Status: Deferred
- Created: 2026-09-21
- Implementation status: Not started
- Prerequisite: Portico .NET Foundation 1.0 is complete
- Start condition: the foundation architecture tests, public Application
  outcomes, configuration/data contracts, and CLI E2E tests are all green

## Purpose

Improve the desktop experience and add an MCP adapter only after Portico has a
stable in-process Application API. This packet intentionally separates those
outer concerns from the foundation refactor so neither UI work nor MCP protocol
choices shape Finance, Configuration, or Data.

## Scope

### In scope after the prerequisite

- Desktop UX improvements driven by the stable Application outcomes.
- Clear loading, readiness, empty, cancellation, configuration, and data-error
  states.
- A versioned MCP adapter that calls Application operations.
- Headless report/query operations only if Application has a tested semantic
  report contract that genuinely needs an automation caller.
- Contract, integration, and retained visual tests for both adapters.

### Not in scope

- A remote HTTP or gRPC server.
- Direct MCP access to TOML, CSV, Google Sheets, Roci, or Finance internals.
- New finance calculations or source protocols.
- A generic dashboard designer or untyped tool registry.
- Restoring the archived Python application.

## Design rule

    Desktop and MCP -> Portico.Application -> Finance
                                      ^
                                      |
                         Configuration and Data implementations
                                      ^
                                      |
                                 Portico.App wiring

Desktop and MCP are peers. They may present the same Application outcome
differently, but neither owns a copy of the use case or directly references a
concrete configuration/data adapter.

The future MCP entry point is a local standard-input/output mode, portico mcp
serve. Portico.App starts that host after Portico.Cli has parsed the typed
command. It does not launch Desktop or introduce an HTTP or gRPC application
server.

## Packet files

- [SRD.md](SRD.md) defines required behavior once the foundation is ready.
- [SADD.md](SADD.md) records the adapter design and safety rules.
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) gives the future phased
  sequence.
- [TEST_PLAN.md](TEST_PLAN.md) defines the proof required before release.

## Why this packet is deferred

The current source does not yet have a stable Application API. Designing MCP
tools or a new desktop UX against the current mixed App/Dashboard/Adapter seams
would lock those seams in place. The foundation PLC removes that risk first.
