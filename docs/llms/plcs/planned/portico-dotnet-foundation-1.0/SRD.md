# Software Requirements Document

## 1. Objective

Refactor Portico into a .NET application whose finance rules, use cases,
configuration, data loading, CLI, and desktop host have clear responsibilities
and one-way dependencies. The foundation must make future Desktop and MCP work
additive rather than forcing another cross-layer rewrite.

## 2. Users and main flows

### Interactive desktop user

1. Writes portico.toml and, if needed, portico.secrets.toml.
2. Runs portico doctor to confirm the app can load the configured data.
3. Runs portico run to open the existing desktop dashboard.
4. Sees safe, actionable configuration or data errors instead of a stack trace.

### Automation user

1. Runs portico config check --output json before deployment or scheduling.
2. Runs portico data check --output json to validate a chosen data source.
3. Uses the documented exit code and versioned JSON response without parsing
   human prose.

## 3. Required behavior

| ID | Requirement | Acceptance check |
| --- | --- | --- |
| FND-001 | Finance contains financial rules and domain types only. | Finance has no Portico project reference and no TOML, HTTP, file-system, Roci, CLI, or source-kind dependency. |
| FND-002 | Application owns use cases, request/result models, and interfaces for outside inputs. | Application's public types expose no Tomlyn, CSV, Google, or Roci types. CLI uses only Application; Desktop has no main Configuration or Data reference and uses Roci only inside its presentation project. |
| FND-003 | Configuration and data loading are separate outer modules. | TOML/secret parsing and CSV/Google reading are independently testable and implement Application-owned input interfaces. |
| FND-004 | Expected boundary failures use typed safe outcomes. | Configuration, source, data-contract, and cancellation tests assert stable problem codes and no secret leaks. |
| FND-005 | Portico.App is the only composition root. | It is the only Portico project allowed to reference concrete CLI, Desktop, Configuration, and Data implementations together. |
| FND-006 | The new main configuration is portico.toml. | The default is ./portico.toml; the parser requires a schema version, rejects the legacy document shape, resolves relative paths from its file, does not parent-search, and does not accept weekly_summary. |
| FND-007 | Secrets remain separate and safe. | portico.secrets.toml is ignored, its values are redacted from text/JSON/errors, and missing secrets identify only the required setting. |
| FND-008 | Data sources normalize to one finance snapshot contract. | Local CSV and Google fixtures produce the same normalized snapshot or equivalent typed problem. |
| FND-009 | The CLI has stable non-interactive behavior. | run, config check, data check, and doctor accept only their documented options, use stdout/stderr correctly, support JSON where applicable, never accept a source URL on the command line, and return stable exit codes. |
| FND-010 | Existing desktop behavior survives the wiring change. | Existing report, interaction, and visual tests remain green without a UI redesign. |
| FND-011 | The dependency direction cannot regress silently. | Architecture tests inspect evaluated production project references, fail for imported or direct forbidden references, and reject forbidden Finance dependencies. |
| FND-012 | Core and Application have strong direct tests. | The agreed coverage gate and scenario matrix pass without real files, network access, or Roci. |
| FND-013 | The repository becomes .NET-first. | Active docs and task commands name .NET paths first; Python remains clearly archived and is not part of normal CI. |
| FND-014 | The configuration cutover is explicit. | Active samples and documentation use portico.toml; the release notes explain the breaking change and no old parser or implicit fallback remains. |

## 4. Public surfaces

### CLI

| Command | Result | JSON support | Accepted options |
| --- | --- | --- | --- |
| portico run | Loads the workspace and opens the existing desktop app. | No | --config PATH, --secrets PATH, --dashboard PATH |
| portico config check | Validates main and secret configuration without loading financial data. | Yes | --config PATH, --secrets PATH, --output text\|json |
| portico data check | Loads, normalizes, and validates the configured source. | Yes | --config PATH, --secrets PATH, --output text\|json |
| portico doctor | Performs both checks and reports readiness. | Yes | --config PATH, --secrets PATH, --output text\|json |

Source selection, data locations, and Google URLs live only in the selected
configuration and secret files. Command options select complete files; they do
not override individual source settings. The source, data-directory, and sheet
URL options are not part of the new contract. Unknown or inapplicable options
exit with code 2.

Output defaults to text. After a JSON-capable command parses successfully with
--output json, every Application outcome writes exactly one versioned response
document to standard output. That document has a schema identifier, stable
property names, and a problems array for failures. A syntax error that prevents
command parsing writes a diagnostic to standard error and exits 2. Expected
result data is not duplicated on standard error; standard error is reserved for
host diagnostics.

report show, export, mutation, prompts, and an --agent switch are not part of
this PLC.

### CLI exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success; warnings may be present. |
| 1 | Unexpected internal failure. |
| 2 | Invalid command or option. |
| 3 | Invalid configuration or missing secret. |
| 4 | Permanent source/data-contract failure. |
| 5 | Cancellation or retryable/transient source failure. |

Exit selection follows the first failed stage: usage (2), configuration or
missing secret (3), permanent source/data validation (4), cancellation or
retryable source failure (5), then an unexpected host failure (1).

### Application API

Application exposes a small in-process C# API. Its initial operations are
configuration checking, data checking, workspace opening, and semantic report
creation needed by Desktop. It is not an HTTP, gRPC, or MCP endpoint.

Every expected failure returns an explicit success-or-failure result. A failure
contains one or more PorticoProblem values with a code, safe message, and
optional configuration field. It does not contain exception text, URLs,
credentials, or private financial rows.

### Configuration

| File | Purpose |
| --- | --- |
| portico.toml | Versioned, non-secret finance policy and source selection. |
| portico.secrets.toml | Secret source values such as Google Sheet URLs. |
| dashboard.toml | Versioned, typed Desktop-only layout and control declaration. |

The default main file is ./portico.toml. The default secret file is the sibling
portico.secrets.toml when the selected configuration needs secrets; an explicit
--secrets path replaces that one location. Run similarly uses a sibling
dashboard.toml by default or its explicit --dashboard path. There is no
compatibility reader, implicit parent search, hidden overlay stack, per-field
command override, TOML expression, or formula language.

An explicit --config path may use any file name. Compatibility is determined by
the document schema, not by a filename: an archived legacy document is rejected
because it does not satisfy the new schema.

Explicit file paths are resolved from the process working directory. Relative
data paths inside portico.toml are resolved from the selected main file.

### Desktop and MCP compatibility

The foundation only changes Desktop wiring. It does not change page layout or
add MCP. Future outer adapters must call Application and must not access finance
or concrete adapters directly.

## 5. Quality requirements

- Core and Application behavior must be deterministic with in-memory fixtures.
- Configuration errors must report all independent errors in stable order.
- Text and JSON output must be deterministic for the same inputs.
- Normal tests must not require Google, credentials, or an interactive window.
- Finance plus Application target at least 95% line coverage and 90% branch
  coverage after the new baseline is established. Scenario coverage remains the
  primary proof.
- Use .NET 11 and C# 15 where the pinned SDK supports them. Use C# 15 union
  types for closed boundary results, not for ordinary calculations. Do not set
  LangVersion to latest.

## 6. Out of scope

This PLC does not add a remote API, MCP server, report CLI, data editing,
notifications, Python support, new data sources, OAuth, or a desktop redesign.

## 7. Traceability

| Requirement group | Main phase | Main evidence |
| --- | --- | --- |
| FND-001 through FND-005 | 1 and 2 | Architecture and Application tests |
| FND-006 through FND-008 | 3 | Configuration and adapter fixtures |
| FND-009 and FND-010 | 4 | CLI contracts and retained Desktop tests |
| FND-011 through FND-014 | 1 and 5 | Architecture suite, task lanes, docs, E2E suite |
