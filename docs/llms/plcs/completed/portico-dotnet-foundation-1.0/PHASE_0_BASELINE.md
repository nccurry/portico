# Phase 0 Baseline and Migration Inventory

## Purpose

This document records the active C# application before the .NET foundation
refactor. It turns the Phase 0 inventory requirement into a checkable migration
map. It does not implement a new parser, change a command, or make the old
configuration compatible with the new one.

The inventory was reviewed at commit
`31e53bb957837ed1baa5c30b59e3e1cd73020cea`. It covers active C# code and
fixtures only. [legacy/python](../../../../../legacy/python/README.md) is a
reference archive and is not a migration target.

## 1. Observed baseline

### Production project graph

The active project files define this graph:

    Portico.App -> Portico.Adapters, Portico.Dashboard, Portico.Finance, Roci
    Portico.Adapters -> Portico.Dashboard, Portico.Finance, Tomlyn
    Portico.Dashboard -> Portico.Finance
    Portico.Finance -> no Portico project

| Current project | Direct responsibility today | Target disposition | Owning phase |
| --- | --- | --- | --- |
| [Portico.Finance](../../../../../src/Portico.Finance/Portico.Finance.csproj) | Financial rules and the source-selection records `WorkbookSourceKind` and `DataSourceSettings`. | Keep financial rules. Move source selection out to Application-owned requests. | 2 |
| `Portico.Dashboard` (historical project) | Semantic reports, dashboard TOML grammar, and mutable presentation state. | Split semantic reports to Application and desktop presentation to Desktop. Delete the project only after its tests move. | 2 and 4 |
| `Portico.Adapters` (historical project) | TOML parsing, secrets, CSV, Google Sheets, and normalization. | Split into Configuration and Data, each implementing an Application-owned input interface. | 3 |
| [Portico.App](../../../../../src/Portico.App/Portico.App.csproj) | CLI parsing, output, adapter construction, Roci startup, and desktop rendering. | Keep only entry point and object wiring. Dispatch the typed `run` command to Application and Desktop. | 4 |

### Reviewed target project-reference matrix

This matrix is the reviewed replacement for the graph above. It matches the
[PLC packet's implemented graph](README.md#implemented-project-graph) and is the
matrix Phase 1 architecture tests must evaluate from the effective MSBuild
project items, including imported references.

| Project | Allowed production references |
| --- | --- |
| `Portico.Finance` | None from Portico. |
| `Portico.Application` | `Portico.Finance`. |
| `Portico.Configuration` | `Portico.Application`, `Portico.Finance`. |
| `Portico.Data` | `Portico.Application`, `Portico.Finance`. |
| `Portico.Cli` | `Portico.Application`. |
| `Portico.Desktop` | `Portico.Application` and Roci only. |
| `Portico.App` | `Portico.Cli`, `Portico.Desktop`, `Portico.Configuration`, `Portico.Data`, and `Portico.Application`. |

`Portico.App` is the only production composition root. In particular, CLI and
Desktop must not reference Configuration or Data, and Finance must not regain a
Portico project reference or a source-kind type.

The table is the final target, not a claim that the legacy projects have
already moved. Phase 1 architecture tests freeze the transition set exactly:
App retains its current Adapters, Dashboard, Finance, and Roci references
through Phase 4; Adapters retains Dashboard and Finance through Phase 3; and
Dashboard retains Finance through Phase 4. The tests reject any added Portico
or external Roci reference while those temporary edges remain.

### Restored build, test, and doctor evidence

The following commands ran from a fresh linked worktree on the recorded commit.

| Command | Result |
| --- | --- |
| `task roci:restore` | Passed; restored all Portico production and test projects. |
| `task roci:build:strict` | Passed with zero warnings and zero errors. The .NET preview SDK emitted only its informational `NETSDK1057` notice. |
| `task roci:test` | Passed after restore and strict build: 57 Finance, 47 Dashboard, 16 Adapters, and 102 App tests; 222 non-visual tests total. |
| `task roci:doctor` | Passed against the synthetic demo data. |

Doctor output:

```text
Portico doctor: ready
Source: local-csv
Pages: 10
Transactions: 986
Balances: 432
Budgets: 1344
```

`roci:test` deliberately uses `--no-restore`. On a fresh worktree it is not
valid evidence by itself, because its project assets and outputs have not yet
been created. The new .NET-first default task must run restore, then build,
then the non-visual tests. A focused test lane may use `--no-restore` only
after that preparation step.

The separate retained visual test is intentionally excluded from the 222-test
routine baseline. It remains an opt-in Desktop evidence lane, not a default
task.

### Local Roci source decision

Portico compiles directly against the sibling `../roci` source checkout. Set
`ROCI_ROOT` to use another local checkout. The build must fail with a clear
setup error before restore or compilation when the expected Roci source is not
present. Only projects that reference Roci require that checkout; Finance and
other inner-layer test lanes stay independent of it.

`task test:roci-source` proves the sibling default, the `ROCI_ROOT` override,
the one-error missing-checkout path before solution restore, and Finance's
independence from Roci.

Continuous integration is intentionally deferred; it is not a Phase 0
completion condition. The protected `main` branch currently expects a `ci`
status, so a pull request cannot merge until that repository policy changes or
a suitable CI design is introduced. This is an external delivery constraint,
not a reason to couple inner layers to Roci.

The retained visual lane passed with 48 PNG captures from the synthetic demo.

## 2. Current public behavior

### CLI surface today

The baseline CLI was implemented in the removed `src/Portico.App/PorticoCli.cs`. Its default command
is `run`; it also supports `doctor` and help.

| Current item | Current behavior | Target disposition |
| --- | --- | --- |
| `portico run` or no command | Loads configuration, dashboard definition, and data, then opens the Roci dashboard. | Keep as `portico run`; move parsing to `Portico.Cli` and host dispatch to `Portico.App`. |
| `portico doctor` | Loads configuration, dashboard definition, and data. It writes text or one JSON object. | Keep, but make it an Application result and remove dashboard loading from the readiness check. |
| `--config PATH` | Defaults to `portico-demo.toml`. | Keep as a complete main-file selector; default becomes `./portico.toml`. |
| `--dashboard PATH` | Defaults to `dashboard.toml` for both `run` and `doctor`. | Keep only for `run`; default becomes the selected main file's sibling `dashboard.toml`. |
| `--secrets PATH` | Optionally supplies a TOML file with `[sheets]` URLs. There is no companion-file default. | Keep as a complete secret-file selector. When needed, default to the selected main file's sibling `portico.secrets.toml`. |
| `--source NAME` | Overrides config with `local-csv`/`local` or `google-sheets`/`remote`. | Reject as usage error. Source selection belongs in the selected main configuration. |
| `--data-dir PATH` | Overrides `data.directory`. | Reject as usage error. The data directory belongs in the selected main configuration. |
| `--sheet NAME=URL` | Repeatable override for a Google sheet URL. | Reject as usage error. URLs must never be command-line values. |
| `--output text|json` | Accepted by the parser; `run --output json` is rejected. Doctor JSON has no schema identifier. | Keep only on `config check`, `data check`, and `doctor`; use the versioned response envelope below. |
| Exit codes | `0` success, `2` command/configuration, `3` data, `4` cancellation/unexpected. | Replace with the documented `0`-`5` target table in [SRD.md](SRD.md#cli-exit-codes). |

The target command grammar is fixed:

```text
portico run [--config PATH] [--secrets PATH] [--dashboard PATH]
portico config check [--config PATH] [--secrets PATH] [--output text|json]
portico data check [--config PATH] [--secrets PATH] [--output text|json]
portico doctor [--config PATH] [--secrets PATH] [--output text|json]
```

`report show`, export, prompts, an agent switch, HTTP, gRPC, and MCP commands
are not part of this foundation.

### Current configuration and data loading

The former `Portico.Adapters/TomlConfigurationLoader.cs`
currently accepts the old finance document shape in `portico-demo.toml`. It has
no main-file schema version and does not reject unknown keys; the checked-in
`weekly_summary` table is therefore ignored by C# today.

For local data, `data.source = "local"` selects four files beneath
`data.directory`: `transactions.csv`, `balance_history.csv`, `categories.csv`,
and `accounts.csv`. For Google Sheets, `data.source = "remote"` or
`"google-sheets"` uses four same-named values from `[sheets]`. Both paths feed
the former `Portico.Adapters/WorkbookNormalizer.cs`
and produce a `PortfolioSnapshot`.

The current App resolves a relative `data.directory` from the selected
configuration file after applying command-line overrides. That resolution rule
is retained. The target moves it to Configuration so Application and Finance do
not need file-path logic.

## 3. Target file selection and response contracts

### File selection

These rules are the Phase 0 contract for Phase 3. A file-selection option
chooses a complete file; it never overrides one field in that file.

| Need | Default | Explicit option | Resolution rule |
| --- | --- | --- | --- |
| Main configuration | `./portico.toml` | `--config PATH` | A relative option path is resolved from the process working directory. No parent search. |
| Secrets, when the selected source needs them | `portico.secrets.toml` beside the selected main file | `--secrets PATH` | An explicit relative option path is resolved from the process working directory and replaces the one sibling location. |
| Desktop layout for `run` only | `dashboard.toml` beside the selected main file | `--dashboard PATH` | An explicit relative option path is resolved from the process working directory and replaces the one sibling location. |
| Local data directory declared in the main file | No implicit default | Not overridable on the command line | A relative value is resolved from the selected `portico.toml` directory. |

An explicit `--config config.toml` is allowed as a location choice. Its contents
must still satisfy the new schema; the old document shape is rejected. There is
no compatibility parser, automatic migration, overlay merge, or filename-based
fallback.

### Main and secret file shape

Both new files begin with `schema_version = 1`. The main file holds non-secret
finance policy and source selection. The secret file holds only Google Sheet
URLs. `dashboard.toml` remains a separate versioned Desktop file.

This concise local-source example names the complete public shape. The detailed
field dispositions below define each table's valid fields.

```toml
schema_version = 1

[data]
source = "local_csv" # or "google_sheets"
directory = "data"    # required only for local_csv

[lookback]
lookback_months = [3, 6, 12, 24]
default_lookback_months = 12

[thresholds]
expense = 3000
income = 20000
duplicate_minimum = 10
duplicate_days = 1

[merchants.aliases]
# "Canonical merchant" = ["input spelling"]

[transaction_sets.all]
label = "All spending"
groups = []
categories = []
accounts = []
merchants = []
transactions_like = []
includes = []
excludes = []

[filter_sets.spending]
options = ["all"]
default = "all"

[filter_sets.year_over_year]
options = ["all"]
default = "all"

[income_savings]
default_view = "regular"
target_rate = 20
exclude_categories = []
exclude_groups = []

[subscriptions]
known_categories = []
minimum_confidence = 80
stale_after_days = 45
default_exclude_categories = []
detection_excluded_categories = []

[budget]
history_months = 12

[data_health]
stale_account_days = 7
duplicate_require_same_account = true
duplicate_require_same_category = false
duplicate_require_same_description = true

[financial_safety]
emergency_fund_target_months = 6
emergency_fund_included_groups = []
emergency_fund_included_account_patterns = []
emergency_fund_spending_lookback_months = 6
emergency_fund_exclude_categories = []
emergency_fund_exclude_groups = []
debt_included_groups = []
debt_included_account_patterns = []
debt_baseline_date = ""

[financial_independence]
expected_return_rate = 7
withdrawal_rate = 4
target_amount = 1000000
spending_lookback_months = 12
projection_years = 50
included_account_patterns = []
included_groups = []
```

```toml
schema_version = 1

[sheets]
transactions = "https://docs.google.com/spreadsheets/d/REPLACE_ME/edit#gid=0"
balance_history = "https://docs.google.com/spreadsheets/d/REPLACE_ME/edit#gid=0"
categories = "https://docs.google.com/spreadsheets/d/REPLACE_ME/edit#gid=0"
accounts = "https://docs.google.com/spreadsheets/d/REPLACE_ME/edit#gid=0"
```

The Configuration reader validates both documents, aggregates independent
problems in a stable order, and returns safe `PorticoProblem` values. It must
not include a URL, credential, private file path, or financial row in a public
problem.

### JSON response envelope

Phase 4 owns CLI formatting, but Phase 3 must expose enough structured result
data to produce this fixed v1 envelope. Every JSON-capable command writes one
document to standard output after successful command parsing.

```json
{
  "schema": "portico.command-result.v1",
  "command": "doctor",
  "outcome": "success",
  "details": {
    "source": "local_csv",
    "transactions": 986,
    "balances": 432,
    "budgets": 1344
  },
  "problems": []
}
```

```json
{
  "schema": "portico.command-result.v1",
  "command": "config-check",
  "outcome": "failure",
  "details": null,
  "problems": [
    {
      "code": "config.unknown-key",
      "message": "The setting is not supported.",
      "field": "weekly_summary",
      "retryable": false
    }
  ]
}
```

`schema`, `command`, `outcome`, `details`, and `problems` are stable v1
property names. A problem has only `code`, `message`, `field`, and `retryable`.
`details` is command-specific and contains no secret or private source value.
Command syntax errors occur before this envelope, write a diagnostic to standard
error, and exit `2`.

### Explicit cutover decisions

- `weekly_summary` is rejected as an unknown top-level key. It has no target
  table, Application use case, or legacy shim.
- A legacy document shape is rejected even when the explicit config file is
  named `config.toml`.
- `--source`, `--data-dir`, and `--sheet NAME=URL` are not target CLI options.
  They fail command parsing with exit code `2`.
- Google URLs exist only in `portico.secrets.toml`; no text, JSON, or error
  response may echo them.

## 4. Field-by-field migration inventory

`Keep` preserves the user meaning at the stated target location. `Rename`
changes a name or value spelling while preserving the meaning. `Move` preserves
the setting but changes its owning module or file. `Reject` removes it from the
new schema and reports it as unsupported.

### Main configuration and source fields

| Current setting | Disposition | Target location and owner |
| --- | --- | --- |
| `data.source` (`local`, `remote`, or `google-sheets`) | Rename values | `portico.toml` → `data.source` with `local_csv` or `google_sheets`; Configuration validates it and maps it to an Application source request in Phase 3. |
| `data.directory` | Keep, move ownership | `portico.toml` → `data.directory`, required only for `local_csv`; Configuration resolves a relative path from the main file in Phase 3. |
| `[sheets].transactions` | Move | `portico.secrets.toml` → `sheets.transactions`; Configuration reads it only for `google_sheets` in Phase 3. |
| `[sheets].balance_history` | Move | `portico.secrets.toml` → `sheets.balance_history`; same owner and phase. |
| `[sheets].categories` | Move | `portico.secrets.toml` → `sheets.categories`; same owner and phase. |
| `[sheets].accounts` | Move | `portico.secrets.toml` → `sheets.accounts`; same owner and phase. |
| Fixed required local filenames and sheet names | Keep as a data contract, not a TOML setting | `Portico.Data` owns the four fixed inputs and normalizes them to `PortfolioSnapshot` in Phase 3. |

### Finance policy fields

| Current setting | Disposition | Target location and owner |
| --- | --- | --- |
| `lookback.lookback_months` | Keep | `portico.toml` → `lookback.lookback_months`; Configuration maps it to Finance in Phase 3. |
| `lookback.default_lookback_months` | Keep | `portico.toml` → `lookback.default_lookback_months`; Configuration validates membership in the declared choices. |
| `thresholds.expense` | Keep | `portico.toml` → `thresholds.expense`; Finance policy in Phases 2 and 3. |
| `thresholds.income` | Keep | `portico.toml` → `thresholds.income`; Finance policy in Phases 2 and 3. |
| `thresholds.duplicate_minimum` | Keep | `portico.toml` → `thresholds.duplicate_minimum`; Finance policy in Phases 2 and 3. |
| `thresholds.duplicate_days` | Keep | `portico.toml` → `thresholds.duplicate_days`; Finance policy in Phases 2 and 3. |
| `merchants.aliases.<canonical-merchant>` | Keep | `portico.toml` → dynamic `merchants.aliases` values; Configuration validates string arrays in Phase 3. |
| `transaction_sets.<key>.label` | Keep | `portico.toml` → same dynamic table; Finance transaction-set policy in Phases 2 and 3. |
| `transaction_sets.<key>.groups` | Keep | `portico.toml` → same dynamic table; Finance transaction-set policy in Phases 2 and 3. |
| `transaction_sets.<key>.categories` | Keep | `portico.toml` → same dynamic table; Finance transaction-set policy in Phases 2 and 3. |
| `transaction_sets.<key>.accounts` | Keep | `portico.toml` → same dynamic table; Finance transaction-set policy in Phases 2 and 3. |
| `transaction_sets.<key>.merchants` | Keep | `portico.toml` → same dynamic table; Finance transaction-set policy in Phases 2 and 3. |
| `transaction_sets.<key>.transactions_like` | Keep | `portico.toml` → same dynamic table; Finance transaction-set policy in Phases 2 and 3. |
| `transaction_sets.<key>.includes` | Keep | `portico.toml` → same dynamic table; Finance validates references in Phases 2 and 3. |
| `transaction_sets.<key>.excludes` | Keep | `portico.toml` → same dynamic table; Finance validates references in Phases 2 and 3. |
| `filter_sets.<key>.options` | Keep | `portico.toml` → same dynamic table; Configuration validates transaction-set references in Phase 3. |
| `filter_sets.<key>.default` | Keep | `portico.toml` → same dynamic table; Configuration validates membership in `options` in Phase 3. |
| `income_savings.default_view` | Keep | `portico.toml` → `income_savings.default_view`; Finance policy in Phases 2 and 3. |
| `income_savings.target_rate` | Keep | `portico.toml` → `income_savings.target_rate`; Finance policy in Phases 2 and 3. |
| `income_savings.exclude_categories` | Keep | `portico.toml` → `income_savings.exclude_categories`; Finance policy in Phases 2 and 3. |
| `income_savings.exclude_groups` | Keep | `portico.toml` → `income_savings.exclude_groups`; Finance policy in Phases 2 and 3. |
| `subscriptions.known_categories` | Keep | `portico.toml` → `subscriptions.known_categories`; Finance policy in Phases 2 and 3. |
| `subscriptions.minimum_confidence` | Keep | `portico.toml` → `subscriptions.minimum_confidence`; Finance policy in Phases 2 and 3. |
| `subscriptions.stale_after_days` | Keep | `portico.toml` → `subscriptions.stale_after_days`; Finance policy in Phases 2 and 3. |
| `subscriptions.default_exclude_categories` | Keep | `portico.toml` → `subscriptions.default_exclude_categories`; Finance policy in Phases 2 and 3. |
| `subscriptions.detection_excluded_categories` | Keep | `portico.toml` → `subscriptions.detection_excluded_categories`; Finance policy in Phases 2 and 3. |
| `budget.history_months` | Keep | `portico.toml` → `budget.history_months`; Finance policy in Phases 2 and 3. |
| `data_health.stale_account_days` | Keep | `portico.toml` → `data_health.stale_account_days`; Finance policy in Phases 2 and 3. |
| `data_health.duplicate_require_same_account` | Keep | `portico.toml` → `data_health.duplicate_require_same_account`; Finance policy in Phases 2 and 3. |
| `data_health.duplicate_require_same_category` | Keep | `portico.toml` → `data_health.duplicate_require_same_category`; Finance policy in Phases 2 and 3. |
| `data_health.duplicate_require_same_description` | Keep | `portico.toml` → `data_health.duplicate_require_same_description`; Finance policy in Phases 2 and 3. |
| `financial_safety.emergency_fund_target_months` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_safety.emergency_fund_included_groups` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_safety.emergency_fund_included_account_patterns` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_safety.emergency_fund_spending_lookback_months` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_safety.emergency_fund_exclude_categories` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_safety.emergency_fund_exclude_groups` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_safety.debt_included_groups` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_safety.debt_included_account_patterns` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_safety.debt_baseline_date` | Keep | `portico.toml` → same path; Configuration maps an empty value to no baseline in Phase 3. |
| `financial_independence.expected_return_rate` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_independence.withdrawal_rate` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_independence.target_amount` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_independence.spending_lookback_months` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_independence.projection_years` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_independence.included_account_patterns` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |
| `financial_independence.included_groups` | Keep | `portico.toml` → same path; Finance policy in Phases 2 and 3. |

### Desktop-only configuration grammar

Every setting loaded from the active `dashboard.toml` is retained as a
Desktop-only concern. It is not copied to `portico.toml`, and it is not exposed
through Application. Phase 4 moves this parser and its tests to
`Portico.Desktop` without a UI redesign.

| Current dashboard setting group | Disposition | Target location and owner |
| --- | --- | --- |
| `schema_version`, `app_title` | Keep | `dashboard.toml`; Desktop parser and validation in Phase 4. |
| `pages[].id`, `title`, `description`, `visible`, `group`, `order`, `rail_label`, `page_heading`, `icon` | Keep | `dashboard.toml`; finite page, navigation-group, and icon mappings remain in Desktop. |
| `pages[].filters[].id`, `label`, `kind`, `source`, `default`, `options` | Keep | `dashboard.toml`; Desktop validates the finite report-input mapping in Phase 4. |
| `pages[].sections[].id`, `title`, `description`, `layout`, `order` | Keep | `dashboard.toml`; Desktop layout declaration in Phase 4. |
| `pages[].controls[].id`, `label`, `kind`, `source`, `option_source`, `options`, `default`, `defaults`, `minimum`, `maximum`, `step`, `width`, `section` | Keep | `dashboard.toml`; Desktop control grammar and finite C# control mapping in Phase 4. |
| `pages[].widgets[].id`, `title`, `kind`, `report`, `span`, `description`, `bar_series`, `section`, `x_axis_title`, `y_axis_title` | Keep | `dashboard.toml`; Desktop widget grammar and Application semantic-report binding in Phase 4. |

### Explicitly rejected settings

| Current setting | Disposition | Required target behavior |
| --- | --- | --- |
| `weekly_summary.watched_transaction_sets` | Reject | Report `config.unknown-key` for `weekly_summary`; do not silently ignore it. |
| `weekly_summary.average_weeks` | Reject | Same unsupported-key result. |
| `weekly_summary.rolling_weeks` | Reject | Same unsupported-key result. |
| `weekly_summary.top_merchant_count` | Reject | Same unsupported-key result. |
| Legacy main-document shape | Reject | Reject by schema content, even if the file name is `config.toml`. |
| `--source`, `--data-dir`, `--sheet NAME=URL` | Reject | Fail command parsing with usage exit code `2`; do not add a compatibility alias. |

## 5. Behavior-to-replacement-test trace

The 222-test count is not a permanent quota. Each active behavior belongs to an
owning replacement lane below. A source test may be removed only after its row
has an equivalent or stronger replacement test and the phase review records the
change.

| Existing behavior and current proof | Replacement owner and test lane | Phase |
| --- | --- | --- |
| Cash flow, spending, transaction-set matching, aliases, portfolio, safety, financial independence, date boundaries, and stable ordering: `FinanceCalculatorTests`, `SpendingAnalysisTests`, `IncomeSavingsAnalysisTests`, `PlanAnalysisTests`, `AdvancedAnalyzeAnalysisTests`, `DataHealthAnalysisTests`, and `YearOverYearAnalysisTests` (57 tests). | `Portico.Finance.Tests`: deterministic in-memory unit tests for financial rules and invariants. | 2 |
| Semantic report building, home range, income report details, year-over-year views, and report defaults: `DashboardReportBuilderTests`, `DashboardIncomeSavingsTests`, and `DashboardYearOverYearTests`. | `Portico.Application.Tests`: in-memory Application use-case and semantic-report tests. | 2 |
| Dashboard grammar, typed control mapping, defaults, ranges, and session behavior: `DashboardPresentationTests`. | `Portico.Desktop.Tests`: dashboard TOML grammar and Desktop state tests; Application contract fakes replace direct Finance/Adapter access. | 4 |
| CSV parsing, required tabs, normalization, Google URL validation, HTTP failures, existing finance TOML ranges, and dashboard TOML loader behavior: `AdapterTests` (16 tests). | `Portico.Configuration.Tests` for versioned config/secrets, path resolution, unknown keys, and redaction; `Portico.Data.Tests` for CSV/Google/normalization. | 3 |
| Current parser, doctor text/JSON, redaction, command errors, and dashboard binding validation: `PorticoCliTests`. | `Portico.Cli.Tests` for the final four-command grammar, per-command options, stdout/stderr, JSON envelope, and exit-code precedence; `Portico.EndToEnd.Tests` for the published executable. | 4 and 5 |
| Navigation, retained UI state, each page's interactions, empty/error states, presentation components, and layout bounds: `PorticoDashboardNavigationTests`, `PorticoDashboardSceneTests`, `PorticoAnalyzePagesTests`, `PorticoIncomeSavingsPageTests`, `PorticoSpendingPageTests`, `PorticoYearOverYearPageTests`, `PorticoPlanPagesTests`, `PorticoDataHealthPageTests`, and `PorticoPresentationComponentsTests`. | `Portico.Desktop.Tests`: preserve the existing desktop behavior while rewiring it to Application. | 4 |
| Capture catalog, named visual scenarios, and viewport checks: `PorticoCaptureCatalogTests`. | `Portico.Desktop.Tests` plus the retained visual lane. | 4 and 5 |
| PNG capture at both reference sizes: `PorticoCaptureVisualTests` (the separate opt-in visual test). | `dotnet:test:visual` with the same synthetic scenarios and documented reference sizes. | 5 |
| No current direct proof for effective project-reference policy, published-process contracts, versioned main/secret schemas, unknown-key rejection, or rejected `weekly_summary`. | New `Portico.Architecture.Tests`, Configuration, CLI, and published-binary E2E tests named in [TEST_PLAN.md](TEST_PLAN.md). | 1, 3, 4, and 5 |

## 6. Phase 0 completion checks supported by this document

- Every active C# configuration setting is classified above.
- The project-reference matrix is explicit and ready for Phase 1 architecture
  tests.
- The 222-test non-visual baseline and doctor output are recorded from a
  restore-first run.
- The `portico.toml`, `portico.secrets.toml`, file-selection, rejection, and
  JSON-envelope contracts are explicit enough for Phase 3 and Phase 4 tests.
- UI and MCP behavior remain out of this inventory and unchanged.
- `task check` passed the 222-test normal suite and the local-Roci build
  contract. `task doctor` passed against the synthetic demo data. `task visual`
  passed and retained 48 PNG captures.
- The focused structure, behavior, and hygiene re-audits passed after their
  findings were resolved.
