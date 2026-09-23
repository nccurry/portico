# Software Architecture And Design Document

## 1. Design goals

The foundation has five rules:

1. Finance rules stay independent of infrastructure and presentation.
2. CLI and Desktop use Application for finance, main configuration, and source
   operations. Desktop alone owns its Roci and dashboard.toml presentation code.
3. Configuration and data readers are replaceable because their environments
   vary, not because every type needs an interface.
4. Expected operational failures are values with safe messages; programmer
   mistakes remain exceptions.
5. The executable composes the parts but does not become a second business
   layer.

## 2. Target modules

| Project | Owns | Must not own |
| --- | --- | --- |
| Portico.Finance | Financial records, policies, calculations, and invariants. | Source kinds, files, URLs, TOML, Roci, CLI output. |
| Portico.Application | Use cases, semantic reports, requests, outcomes, problems, and input interfaces. | Tomlyn, HTTP details, CSV parsing, Roci types, command parsing. |
| Portico.Configuration | portico.toml, secret-file parsing, validation, redaction, and configuration-to-domain mapping. | Report formatting, window state, source protocol calls. |
| Portico.Data | CSV and Google readers plus normalization into the finance snapshot. | CLI parsing, Roci state, finance presentation. |
| Portico.Cli | Command grammar, help, exit-code selection, text and JSON formatting. | TOML parsing, HTTP construction, data normalization. |
| Portico.Desktop | Current Roci startup adapter, dashboard TOML, view state, and error presentation. | Finance calculations, concrete source loading. |
| Portico.App | Program entry point and object wiring. | Reusable finance rules, command grammar, UI rendering, data parsing. |

The current Portico.Dashboard project splits by responsibility:

- semantic report building moves to Portico.Application;
- dashboard layout declarations, page state, and Roci presentation move to
  Portico.Desktop;
- Portico.Dashboard is removed only after all owning tests move.

No Common, Shared, Contracts, Service, or generic Infrastructure project is
planned. Each named project has a distinct reason to change.

## 3. Dependency policy

    Portico.App -> Cli, Desktop, Configuration, Data, Application
    Cli -> Application
    Desktop -> Application and Roci
    Configuration -> Application and Finance
    Data -> Application and Finance
    Application -> Finance
    Finance -> no Portico project

Application owns the interfaces that Configuration and Data implement. This is
the key inversion: configuration and loading are outer implementations even
though the application invokes them.

Architecture tests evaluate the ProjectReference items for each production
project in Debug and Release. That catches direct, conditional,
and imported references rather than only literal XML in one project file.
The Phase 1 suite checks the nine production projects. Its fixture adds a
Release-only imported reference to prove the evaluator catches it.

Finance source may not use TOML, file I/O, HTTP, Google, Roci, CLI, Desktop, or
console types. The source scan parses each build configuration with its evaluated
language version and preprocessor symbols.

### Phase 1 transition policy

The matrix above is the final design. Phase 1 must still keep the working
legacy projects available, so the architecture suite freezes these exact,
temporary edges rather than treating them as new target edges:

| Project | Temporary edge set | Removal phase |
| --- | --- | --- |
| Portico.App | Its current `Portico.Adapters`, `Portico.Dashboard`, and `Portico.Finance` references, plus its current Roci project-reference set, in addition to the final App edges. | 4 |
| Portico.Adapters | `Portico.Dashboard` and `Portico.Finance`. | 3 |
| Portico.Dashboard | `Portico.Finance`. | 4 |

The suite requires the full evaluated Portico and Roci sets to match this
policy exactly. It does not allow a new edge merely because the project is in
transition. From Phase 1, Portico.Desktop may reference only
Portico.Application and Roci.Core; no other external project reference is
allowed.

Finance has one separate temporary source-selection exception: only
`FinanceSettings.cs` may contain `WorkbookSourceKind` and
`DataSourceSettings`, and Phase 2 removes both types. Finance may not acquire
any other source-kind, TOML, file, HTTP, Google, Roci, CLI, or Desktop
dependency during that transition.

## 4. Runtime flows

### Config check

    CLI command
      -> Application CheckConfiguration
      -> injected Configuration reader
      -> typed configuration result
      -> CLI text or JSON formatter

No source data is loaded.

### Data check and doctor

    CLI command
      -> Application CheckData or Doctor
      -> Configuration reader
      -> Data reader selected from validated settings
      -> shared normalizer
      -> typed readiness result
      -> CLI formatter

Application sees stable configuration and snapshot types. It does not see a
Tomlyn document, CSV row object, HttpResponseMessage, or Google URL.

### Desktop run hand-off

    Portico.Cli parser
      -> typed Run command
      -> Portico.App dispatcher
      -> Application OpenWorkspace
      -> Configuration and Data input interfaces
      -> Workspace with finance policy and semantic reports
      -> Desktop adapter
      -> existing Roci pages

The Desktop adapter maps Application results to existing display states. This
PLC does not change page layout, controls, chart choices, or navigation.
Portico.Cli never references Desktop. Portico.App dispatches the typed run
command by kind only; it does not parse flags or duplicate CLI help, output, or
exit-code policy.

## 5. Application outcomes and problems

Use the explicit success/failure style already proven in Roci. Each important
boundary operation has a closed outcome shape, such as opened versus failed or
checked versus failed. A failure contains an ordered list of PorticoProblem
values.

PorticoProblem has these public fields:

| Field | Meaning |
| --- | --- |
| Code | Stable machine-readable identifier, such as config.invalid-source. |
| Message | Short, safe explanation for a person. |
| Field | Optional configuration path or command option. |
| Retryable | True only for an operation that may work without a config change. |

Expected problem groups are command input, configuration, missing secret, data
contract, source unavailable, cancellation, and unexpected failure at the outer
host boundary.

Do not use a result type for an invalid argument inside a finance calculator or
a broken internal invariant. Those remain ordinary exceptions and fail tests.
Do not return raw exceptions in a public outcome. The host may log a safe
diagnostic identifier, but the public response must not include secrets,
filesystem details that reveal private locations, URLs, or financial rows.

C# 15 union types are appropriate for these closed outcomes. Collection
expressions and modern pattern matching are welcome where they improve clarity.
Preview-only features must not spread through ordinary domain code merely
because they are available.

## 6. Configuration design

### Files and precedence

| Selection | Source |
| --- | --- |
| Main configuration | ./portico.toml by default, or one explicit --config path. |
| Secrets | Sibling portico.secrets.toml when needed, or one explicit --secrets path. |
| Desktop only | Sibling dashboard.toml for run, or one explicit --dashboard path. |
| Product defaults | Explicit documented values only. |

File-selection options change only the complete file location. There are no
per-field source/data overrides, command-line sheet URLs, compatibility reader,
implicit parent search, or overlay merge.

Explicit file paths are resolved from the process working directory. Relative
paths declared inside portico.toml are resolved from the selected main
configuration file.

The main file begins with a schema version. It contains finance policy and a
source selection, but not URLs or credentials. Relative paths are resolved from
the main configuration file location. Configuration validation aggregates
independent issues, reports them in deterministic order, and rejects unknown
keys.

The old document shape does not migrate automatically. An explicit config path
may have any file name, including config.toml, but legacy content is rejected by
the new schema. weekly_summary is unsupported and must be reported as an
unknown key if present.

dashboard.toml remains a separate typed Desktop configuration. It controls
known pages, sections, controls, labels, and display choices. It must not
contain formulas, code fragments, arbitrary type names, or raw rendering maps.

### Configuration models

Keep source selection outside Finance. Configuration maps finance-policy fields
to immutable Finance records and maps source fields to an Application-owned
source request. That request describes a supported source without exposing a
TOML table or client type.

A configuration reader interface is justified because TOML files are an outer
effect. A separate generic configuration framework is not justified.

## 7. Data-loading design

Data owns two concrete readers:

- local CSV; and
- Google Sheets.

Both feed a shared normalizer that produces the one trusted PortfolioSnapshot
contract used by Finance and Application. Normalization owns required-column
checks, type conversion, cross-table consistency, and data-contract problems.

The data module receives an Application source request and returns a typed
snapshot outcome. It does not expose CsvHelper rows, HTTP response objects, or
Google-specific types to Application.

Portico.App owns the configured HttpClient lifetime and gives the Google reader
the client it needs. No command parser constructs a new HttpClient or a source
reader directly.

## 8. CLI design

Portico.Cli has a narrow job:

- parse the command and options;
- call one Application operation for each terminal check command;
- write human text or a versioned JSON document;
- map a typed result to a documented exit code.

Successful data belongs on standard output. Diagnostics belong on standard
error. JSON responses have an explicit schema name, use stable property names,
and contain a problems array for failures. Commands do not prompt.

The command grammar is finite:

    portico run [--config PATH] [--secrets PATH] [--dashboard PATH]
    portico config check [--config PATH] [--secrets PATH] [--output text|json]
    portico data check [--config PATH] [--secrets PATH] [--output text|json]
    portico doctor [--config PATH] [--secrets PATH] [--output text|json]

Help includes a compact AI_CONTEXT section that states JSON availability, exit
codes, configuration file names, and that run starts an interactive desktop
window.

Output defaults to text. After a JSON-capable command parses successfully with
--output json, every Application outcome produces exactly one versioned response
document on standard output. It contains a schema identifier and stable problems
array. A syntax error that prevents command parsing writes a diagnostic to
standard error and exits 2. Exit selection is usage (2), configuration or
missing secret (3), permanent source/data failure (4), cancellation or
retryable/transient source failure (5), then unexpected host failure (1).

## 9. Composition and Desktop transition

Portico.App stays the executable and manually composes the application, readers,
CLI, and Desktop host. Portico.Cli parses every command to a typed command. For
config check, data check, and doctor it calls Application and formats terminal
results. For run, Portico.App receives the typed command, calls Application,
and hands the outcome to Desktop. It uses CLI-supplied result/exit policy if a
desktop host cannot start; it does not reimplement command grammar. A
dependency-injection container is not required unless manual composition becomes
unclear after the real objects exist.

The transition is inside out:

1. Create Application types and tests while the old code still works.
2. Move Finance types and report semantics behind that boundary.
3. Add Configuration and Data adapters.
4. Make CLI call Application rather than adapters, then make App dispatch the
   typed run command to Desktop.
5. Make the Roci Desktop call Application rather than DashboardSession.
6. Delete old paths only when tests cover the replacement.

At no point may Desktop or CLI reference Configuration or Data directly.

## 10. Testing design

The test boundary mirrors the production boundary:

    Finance.Tests
    Application.Tests
    Configuration.Tests
    Data.Tests
    Cli.Tests
    Desktop.Tests
    App.Tests
    EndToEnd.Tests
    Architecture.Tests

The first five lanes use fixed in-memory data, temporary file roots, or fake
HTTP handlers. Desktop retains its current interaction and visual lanes.
Fast host-process tests may help local development, but the required E2E lane
launches the published executable against disposable fixtures. Architecture
tests inspect evaluated project references and prohibited source dependencies.

## 11. Alternatives rejected

| Alternative | Why it is rejected now |
| --- | --- |
| Keep one App project and use folders only. | Folders cannot stop a CLI or UI change from importing concrete adapters. |
| Add a generic plugin/configuration framework. | The product has two known data sources and a typed finite dashboard grammar. A framework would create indirection without a current use. |
| Add HTTP or gRPC now. | CLI, Desktop, and future MCP are local consumers. A network server adds lifetime, security, and deployment work before it has a caller. |
| Keep old config.toml compatibility. | The user chose a clean new configuration contract rather than an indefinite dual-parser burden. |
| Make every method return Result. | It would hide programmer errors and make finance code harder to read. |
