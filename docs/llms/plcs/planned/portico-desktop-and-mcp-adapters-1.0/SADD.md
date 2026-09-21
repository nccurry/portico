# Software Architecture And Design Document

## 1. Preconditions

Do not start this packet until the foundation provides:

- Portico.Application requests, outcomes, PorticoProblem, and semantic reports;
- Application-only dependencies for Portico.Cli and Portico.Desktop;
- project-reference architecture tests;
- versioned configuration/data contracts;
- process E2E evidence for the CLI;
- typed Portico.App dispatch for commands that need an outer host; and
- a stable redaction policy.

If any prerequisite is missing, return that work to the foundation PLC rather
than recreating its boundary in an outer adapter.

## 2. Desktop design

Portico.Desktop remains a thin Roci adapter. It owns visual structure,
interaction state, dashboard.toml interpretation, and mapping from Application
outcomes to UI states. It does not calculate finance reports or open files.

Desktop state is explicit:

| State | Source | UX rule |
| --- | --- | --- |
| Opening | Application operation in progress | Show progress without claiming a stale report is fresh. |
| Ready | Opened workspace | Show the report and source status. |
| Empty | Valid input with no reportable result | Explain what is absent and retain navigation. |
| Fix configuration | Configuration problem | Name safe fields and the next action; do not show TOML parser internals. |
| Fix data | Data problem | Name the data contract issue without rows or URLs. |
| Cancelled | Cancellation result | State that no new workspace replaced the current one. |
| Unexpected | Host failure | Show a short safe failure with a diagnostic identifier. |

A UX discovery phase decides visual changes. Existing controls and pages remain
outside scope unless the reviewed design explicitly changes them.

## 3. MCP design

Portico.Mcp is an outer adapter. It references Portico.Application and the MCP
SDK only. Portico.App composes it with Application just as it composes CLI and
Desktop. A future portico mcp serve command is parsed by Portico.Cli and
dispatched by Portico.App to a local standard-input/output MCP host. That host
does not open Desktop.

    MCP request
      -> strict tool input validation
      -> Application operation
      -> Application success or PorticoProblem list
      -> MCP response schema

Standard output is reserved for MCP protocol messages. Standard error is for
safe diagnostics. This is a local child-process transport, not an HTTP or gRPC
application API.

MCP does not call a shell command, parse CLI JSON, inspect dashboard TOML, or
construct data readers. It receives the same configured Application service as
other callers for the lifetime of its host process.

Use a small static tool catalog. Do not build dynamic tool registration,
reflection-based command discovery, or a generic action framework.

## 4. Error and privacy policy

MCP and Desktop use the same underlying problem codes but format them for their
own audience. The outer adapter may add presentation wording, never a second
failure taxonomy.

Secrets, URLs, absolute private paths, exception stack traces, and financial
rows are prohibited in tool errors, logs intended for users, and desktop error
panels. Read-only operations are safe defaults. Any future mutating tool needs
a separate product decision and explicit confirmation design.

## 5. Report/query decision

The foundation deliberately omits report commands. This packet may add them
only after a semantic report API has clear names, input models, stable data
shapes, and no dependency on Roci view models. A report query must return
business/report data, not rendered widgets or a screenshot.

## 6. Alternatives rejected

| Alternative | Why it is rejected |
| --- | --- |
| Have MCP call the CLI executable. | It duplicates parsing, loses typed in-process outcomes, and makes failures depend on text/JSON transport. |
| Let MCP access adapters directly. | It bypasses finance policy, redaction, and future application rules. |
| Add an HTTP service for MCP. | There is no remote caller requirement. It adds security and lifetime work. |
| Build a generic command/tool framework. | The known tool set is small and should remain explicit. |
