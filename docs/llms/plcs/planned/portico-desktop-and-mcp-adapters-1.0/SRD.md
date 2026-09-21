# Software Requirements Document

## 1. Objective

After the .NET foundation is complete, make Portico easy to use from the
existing desktop application and safe to use from an MCP client. Both adapters
must rely on the same in-process Application API and preserve the privacy and
read-only rules of the product.

## 2. Required behavior

| ID | Requirement | Acceptance check |
| --- | --- | --- |
| ADP-001 | Desktop uses Application outcomes rather than direct configuration/data calls. | Desktop has no concrete Configuration or Data project reference. |
| ADP-002 | Desktop shows meaningful operational states. | Loading, ready, empty, invalid configuration, unavailable source, cancellation, and unexpected failure states have focused behavior tests. |
| ADP-003 | Existing visual behavior remains a baseline, not an accidental casualty. | Visual capture and interaction tests show intended changes and preserve unaffected pages. |
| ADP-004 | MCP tools call Application only. | Portico.Mcp has no Finance, Configuration, Data, Roci, Tomlyn, direct HttpClient, or CSV parser reference. |
| ADP-005 | MCP tools have explicit versioned input/output schemas. | Contract tests reject unknown/invalid input and compare stable success/failure shapes. |
| ADP-006 | MCP never leak secrets or private finance rows in diagnostic fields. | Redaction tests cover every error class and tool response. |
| ADP-007 | MCP work is safe and read-only by default. | No tool writes a spreadsheet, config, secret file, or source data unless a later separately approved design adds it. |
| ADP-008 | Headless reports are added only when a semantic Application query exists. | A tool maps one Application report result directly; it does not scrape desktop models or dashboard TOML. |
| ADP-009 | The adapter work remains local. | No HTTP/gRPC service is introduced. |
| ADP-010 | MCP has a local protocol entry point. | portico mcp serve runs MCP over standard input/output, writes protocol data only to standard output, writes diagnostics only to standard error, and does not launch Desktop. |

## 3. Expected user experiences

### Desktop user

A person runs portico run, sees a concise readiness state while the workspace
opens, and receives a safe explanation when configuration or data must be
fixed. Existing page layout is changed only where a reviewed UX design calls
for it.

### MCP user

An MCP client starts portico mcp serve, invokes a named read-only tool with a
documented input object, and receives a typed result or problem list. It does
not need to parse console text, know source URLs, or call a hidden HTTP
endpoint.

## 4. Public MCP surface

The exact first tool list is intentionally deferred to the Phase 0 inventory.
Likely candidates are configuration checking, data checking, readiness, and
semantic report queries. Tool names must be based on stable Application
operations, not current Desktop page names.

Every tool requires:

- a plain-English description;
- a strict input schema;
- a versioned response shape;
- safe problem mapping;
- deterministic ordering where a collection is returned; and
- contract tests.

### Transport and startup

The first MCP transport is local standard input/output. The future command is:

    portico mcp serve [--config PATH] [--secrets PATH]

Its standard output contains only MCP protocol messages. Diagnostics, including
safe startup failures, go to standard error. The command does not accept an
HTTP listen address, does not open a Desktop window, and is not part of the
foundation CLI contract.

## 5. Out of scope

This packet does not add source write-back, secrets editing, OAuth, a network
server, a browser frontend, Python compatibility, or a generic plugin system.
