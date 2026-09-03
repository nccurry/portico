# Portico architecture

## Purpose

Portico gives one person a clear view of personal finances stored in a
spreadsheet. It turns familiar spreadsheet data into focused reports without
changing the source.

The application values clear answers over a large feature count. A user must be
able to trace a displayed number back to its source rows and selected filters.
The code must remain small enough for one maintainer to understand and operate.

Portico uses useful defaults from the maintainer's workflow. The defaults stay
anonymous, visible, and configurable. A new user can start with the demo or a
compatible spreadsheet.

## Product principles

### Spreadsheet contract

Portico expects Transactions, Balance History, Categories, and Accounts tables
with the documented columns, value meanings, and amount signs. It reads those
tables from a remote spreadsheet or local CSV files and normalizes both sources
into the same DataFrames.

The table layout is compatible with the Tiller Foundation Template, but the
table contract is the application boundary. Portico is not a general
spreadsheet analysis platform or a source-plugin framework.

### Read-only

Portico reads financial data and never writes it back to a spreadsheet. It does
not edit transactions, categories, budgets, or account balances.

Read-only behavior keeps ownership clear. The spreadsheet owns the records.
Portico owns analysis and presentation.

### Personal and private

Portico is a self-hosted personal application. It has no user accounts, shared
workspaces, or login screen. Localhost is the default network boundary.

The project does not aim to become a hosted financial service. Features that
require multiple users, public access, or shared data need a separate design and
security review.

### Clear before clever

Financial calculations must be easy to read and inspect. Direct Pandas
operations and small Python functions are better than a general framework.

An abstraction must remove real duplication or protect a real boundary. The
project does not add factories, registries, adapters, or interfaces for possible
future use.

### Useful with no private data

The committed demo data is synthetic. It supports every page, integration
tests, and screenshots.

No test, screenshot, issue, or example can contain personal financial records.
If a feature changes the data contract, the demo must continue to work.

## Technology choices

### Streamlit-based user interface

Streamlit owns navigation, page state, controls, caching, and rendering. Altair
owns charts. Pandas DataFrames carry tabular data between the loading,
calculation, and presentation layers.

Portico does not use a separate browser application or API server. A feature
belongs in the current Streamlit application unless the framework cannot support
the required behavior.

Streamlit page files can contain layout, controls, formatting, and chart
construction. Financial rules and reusable calculations belong in `src`.

### Typed Python

The project uses modern Python with strict mypy checks. Public functions have
parameter and return annotations. Dataclasses describe validated configuration
and state. TypedDict classes describe stable summary and filter shapes.

DataFrame column types remain a runtime contract because Pandas does not enforce
them statically. Loading and scrubbing code validates required columns and
normalizes values before analysis.

New code must not bypass type errors with broad `Any` values or unexplained
casts. If a third-party library type is incomplete, a narrow cast is valid at
that boundary.

### uv-native development

`pyproject.toml` defines Python, project dependencies, development dependencies,
and tool settings. `uv.lock` records the complete dependency set.

uv is the package and Python environment manager. Direct `uv` commands are a
supported development path. Task provides short command names but does not own
dependency resolution.

The bootstrap scripts install the pinned Task binary. Task then installs the
pinned uv and Python versions and synchronizes the locked environment. The Dev
Container and CI use the same project files.

### Container-first deployment

The production artifact is a Linux container image. The image runs as a
non-root user and uses a read-only root filesystem. One container runs the
dashboard and, when enabled, the Discord schedule.

The application publishes on `127.0.0.1` by default. A user can opt into trusted
LAN access. Public access requires authentication and TLS outside Portico.

The Discord schedule is part of the container runtime. It is disabled by
default and enabled with environment variables. This keeps deployment to one
container without a host cron job, systemd unit, or second notifier container.

### Browser demo

GitHub Pages hosts a static interactive preview with synthetic data. Stlite
runs the Portico navigation, pages, calculations, settings, and synthetic data
in the visitor's browser. The demo cannot load secrets, connect to a remote
spreadsheet, or send Discord messages. It is a public preview, not a hosted Portico
service.

The browser runtime temporarily uses Streamlit 1.57. The demo bridge ignores
`persist_state`, `wrap`, loading skeleton calls, and serialized data caching.
A control can reset after its page or view changes, and reports recalculate
after a rerun. Remove the bridge after Stlite supports Streamlit 1.62, restores
cached datetime data, and the browser test opens every page twice.

The fixture covers May 1992 through April 1995. It uses varied accounts,
spending, subscriptions, and budgets so each report shows meaningful
changes instead of repeated values.

## Runtime design

The main data flow is:

```text
Remote spreadsheet                 Local CSV files
                  \                 /
                   load, validate, and scrub
                               |
                     normalized DataFrames
                               |
                    filters and calculations
                               |
                 typed summaries and result tables
                               |
               Streamlit pages, Altair charts, and tables
```

### Entry points

`Home.py` configures Streamlit, builds navigation, and renders the accounts and
net-worth page. Files in `app_pages/` provide the remaining dashboards.
Keeping them outside the legacy `pages/` directory prevents automatic page
discovery from overriding the explicit navigation contract.

Local Task commands start Streamlit directly. `src/discord_notifier.py` is also
the command-line entry point for the headless Discord notifier.

`scripts/container_entrypoint.py` starts Streamlit and owns the optional
Discord scheduler. Streamlit remains the main service. A notifier failure is
logged and does not stop the dashboard.

### Data sources

The default `remote` source uses `st-gsheets-connection` and URLs in
`.streamlit/secrets.toml`. The `local` source reads a directory of CSV exports.
[`portico-demo.toml`](../portico-demo.toml) selects the committed files in
`demo/data`. Both sources create the same spreadsheet classes and normalized
DataFrames. Pages and calculations must not contain source-specific behavior.

The browser demo selects the local source and packages `Home.py`, every page,
the required source modules, settings, and the same CSV files. It has no
browser-specific financial calculations. Relative reports anchor to the latest
date in the loaded data. The demo banner is inferred only when the selected
configuration file is named `portico-demo.toml`.

### State and caching

Portico has no application database. The configured spreadsheet remains the
source of truth. Demo CSV files are the source of truth for demo mode.

Streamlit session state stores control selections for one browser session.
Streamlit caches loaded data and deterministic calculations. This state is
temporary and can be rebuilt from the configured source.

The running container stores successful Discord delivery periods in a Docker
volume. This small state record prevents duplicate messages. It does not store
financial rows.

### Loading and scrubbing

`src/spreadsheet.py` owns the four spreadsheet objects and their cached loaders.
Each object keeps the raw DataFrame and the scrubbed DataFrame.

`src/scrubbing.py` validates and normalizes Transactions and Categories data.
The spreadsheet classes normalize Accounts and Balance History data. Cross-sheet
joins add category metadata to transactions and account metadata to balances.

Scrubbing is the trust boundary. Later code can rely on canonical dates, numeric
amounts, groups, types, and visibility fields. Unknown or missing required data
must stop with a clear error near this boundary.

Streamlit caches loaded spreadsheet objects for five minutes. The refresh
control clears the Streamlit data and resource caches.

### Configuration and secrets

`config.toml` is the one complete normal application configuration. It is both
the tracked field reference and the file users edit or mount directly. Portico
does not merge another configuration file. The
optional `PORTICO_CONFIG_PATH` selects another complete file only for explicit
uses such as the synthetic demo.

`portico-demo.toml` is the complete public configuration for synthetic data.
The demo banner is derived from that exact filename, not from a configuration
field. `src/config.py` rejects unknown keys, validates ranges, and returns
frozen typed settings. New settings need a visible default and runtime
validation.

Configuration owns initial control values and named transaction selections. This
includes shared lookback choices, named transaction sets, page filter sets,
discretionary and regular-report exclusions, budget history, subscription
discovery, data-health thresholds, emergency-fund and debt policy, FI funding
goals and assumptions, weekly summary windows, and merchant aliases. The same
named transaction set must mean the same thing on every page. In particular, the
spending, merchant, and year-over-year Discretionary views resolve the same
`[transaction_sets.discretionary]` policy.

Configuration does not own spreadsheet column meanings, financial formulas,
Transfer handling, chart layout, colors, widget safety limits, or validation
rules. Those are application behavior and stay in typed Python code.

Remote spreadsheet URLs and Discord webhook URLs are secrets. They belong in
the ignored `.streamlit/secrets.toml` file. They never belong in tracked
configuration, logs, fixtures, or error messages.

### Filters and calculations

`src/filters.py` owns shared Streamlit filter controls and transaction filter
application. Page-specific controls stay in their page modules.

`src/analysis` owns report calculations for budgets, spending, income,
subscriptions, merchants, net worth, financial safety, data health, and
financial independence.
These modules return DataFrames or typed summaries instead of rendered UI.

Some existing calculations still accept spreadsheet wrappers or read settings
directly. If explicit inputs make a function easier to test, new calculation
code accepts DataFrames and typed values.

### Pages and presentation

Each page follows the same general flow:

1. Load the required spreadsheet objects.
2. Render controls and build typed filter values.
3. Call calculation functions.
4. Render metrics, charts, tables, and transaction details.
5. Handle empty results with a clear message.

Pages can cache expensive deterministic calculations with `st.cache_data`.
Cached functions must return the same result for the same input values.

`src/value_visibility.py` masks values in metrics, tables, and chart axes. This
feature protects a screen from casual viewing. It is not encryption or access
control.

### Discord notifier

`src/discord_notifier.py` loads notifier configuration, reads the required
remote spreadsheet tables through the current Google Sheets connection, formats
Discord embeds, sends webhooks, and records delivery state.

`src/weekly_expenses.py` owns the weekly expense calculations. Those
calculations are independent from Discord transport and message formatting.

The notifier reuses the normal scrubbing functions. It uses direct CSV export
requests because it runs without the Streamlit connection runtime.

The container scheduler accepts a five-field cron expression and uses the `TZ`
environment variable. The scheduler is disabled unless
`PORTICO_DISCORD_ENABLED=true`. It calls the same notifier code as the manual
command and relies on delivery state to prevent duplicates.

## Source ownership

| Path | Responsibility |
| --- | --- |
| `Home.py` | Application shell, navigation, and home page |
| `app_pages/` | Streamlit page layout, controls, and charts |
| `src/analysis/` | Financial and data-quality calculations |
| `src/spreadsheet.py` | Sheet loading, spreadsheet objects, and cached loaders |
| `src/scrubbing.py` | Required columns and normalized data contracts |
| `src/config.py` | Typed configuration loading and validation |
| `src/custom_types.py` | Shared TypedDict classes and type aliases |
| `src/filters.py` | Shared filters and filter controls |
| `src/page_helpers.py` | Small shared Streamlit presentation helpers |
| `src/value_visibility.py` | Display masking for financial values |
| `src/weekly_expenses.py` | Weekly expense report calculations |
| `src/discord_notifier.py` | Discord configuration, transport, formatting, and state |
| `scripts/container_entrypoint.py` | Container process and optional Discord schedule |
| `scripts/generate_demo_data.py` | Regenerates all four date-based synthetic workbook CSV files |
| `scripts/` | Bootstrap, diagnostics, local commands, and build tools |
| `config.toml` | Complete normal application configuration and field reference |
| `portico-demo.toml` | Complete configuration for the committed synthetic demo |
| `demo/data/` | Canonical synthetic workbook data |
| `tests/unit/` | Direct behavior tests for functions and pages |
| `tests/integration/` | Cross-sheet pipelines and Streamlit AppTest coverage |

## Testing rules

Financial correctness is the highest testing priority. Move calculations into
small functions with explicit inputs and outputs before adding complex page
code.

No test suite can guarantee correctness or test every possible value. Portico
requires strong evidence through direct tests of each important input class and
exact output.

A calculation test set must cover the cases that apply:

- Normal values
- Empty data
- Zero values
- Positive and negative amounts
- Date and period boundaries
- Missing or invalid input
- Filters and exclusions
- Ties, duplicates, refunds, and uncategorized rows
- A known regression case for each fixed defect

Tests must assert financial totals, rows, columns, types, and error behavior.
Snapshot-only tests are not enough for financial calculations.

Unit tests isolate small calculations and presentation helpers. Integration
tests run the four synthetic sheets through the real scrub and join pipeline.
Streamlit AppTest tests load every page and exercise important control states.

The latest date in the committed demo data is fixed. Date-sensitive tests use
that date instead of the current clock. Tests select the committed demo
configuration so a maintainer's edits to `config.toml` cannot change results.

CI enforces strict typing, linting, unit tests, integration tests, and container
smoke tests. Coverage must be at least 90% for `src`
and 80% for `src` and `app_pages` combined. Local Task commands call the same
underlying tools.

## Security and privacy rules

Portico handles sensitive financial data even though it is a personal project.
The design uses a small and clear security boundary:

- The application is read-only.
- The default network address is loopback.
- Secrets stay in ignored files and read-only container mounts.
- The production container runs as a non-root user.
- The container root filesystem is read-only.
- Demo data and screenshots are synthetic.
- The public browser demo contains only synthetic data.
- Error messages do not print financial rows or secret URLs.

The Hide values control does not replace these rules. It changes presentation
only.

## Non-goals

Portico does not aim to provide:

- Direct bank connections
- Transaction or budget editing
- Remote spreadsheet writeback
- A database that copies the workbook
- Multiple users or shared accounts
- A public hosted service for personal data
- A source-plugin framework
- A separate frontend and backend
- Corporate identity, service-account, or role-management systems

A proposal that adds one of these capabilities changes the product boundary. It
needs an explicit architecture decision before implementation.

## Rules for future changes

These rules define a feature that fits Portico:

1. It answers a clear personal-finance question from spreadsheet data.
2. It keeps the configured spreadsheet read-only.
3. It works with the synthetic demo data.
4. It puts financial rules in typed, testable Python functions.
5. It keeps Streamlit code focused on controls and presentation.
6. It validates new data or configuration at the boundary.
7. It covers normal, empty, boundary, invalid, and regression cases.
8. It preserves value hiding for displayed financial values.
9. It does not expose secrets, financial rows, or private URLs.
10. It reuses a suitable existing dependency or pattern.
11. It adds only abstractions required by current code.
12. It updates the README, demo, and this document for each public behavior change.

When two designs work, choose the design with fewer moving parts. Prefer a small
function over a new class. Prefer an explicit call over a registry. Prefer a
validated setting over a hidden constant. Prefer a direct test over a large
mock.
