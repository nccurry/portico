# Portico Dashboard in Roci 1.0 Software Architecture And Design Document

## Document Control

- Lifecycle status: Planned
- PLC packet: [README.md](README.md)
- Owner: Portico and Roci maintainers
- Reviewers: Portico maintainer; Roci maintainer
- Last updated: 2026-09-04
- Related SRD: [SRD.md](SRD.md)
- Related implementation plan: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

## Executive Summary

Portico becomes a small C# solution with a pure finance layer, a typed dashboard
layer, adapters for TOML and CSV sources, and a Roci desktop host. The important
choice is to model each dashboard report in C# and let TOML select, arrange, and
label those reports. This preserves Portico's existing configuration-first
approach without adding a mini programming language to configuration.

The app is also a real Roci test case. It must not work around missing charts by
placing text over hand-drawn pixels or by converting dates into undocumented
numeric offsets. Reusable gaps are fixed on a companion Roci branch, with the
same fluent UiBuilder authoring language as Roci's existing charts.

The main rejected option is a generic dashboard/formula engine. It would make
the first version look flexible, but it would make financial logic harder to
read, validate, and evolve. A small catalog of named reports and widgets is a
better match for this finite dashboard.

## Goals, Non-Goals, And Design Drivers

### Goals

- Recreate the ten current Portico views with the same financial meaning.
- Load a public read-only Google Sheets workbook without OAuth.
- Make visible page layout, labels, controls, colors, and chart choices TOML
  driven.
- Keep money and period calculations independent from Roci, HTTP, TOML, and
  MonoGame.
- Exercise and improve Roci through normal reusable components.
- Make setup, build, test, and failure paths obvious to a developer or an
  automation agent.

### Non-goals

- No browser target, Docker image, Discord messages, OAuth, sheet editing,
  server process, database, account system, or multi-user state.
- No formula engine, script blocks, arbitrary data query strings, plugin host,
  or generic layout language.
- No promise of Native AOT in the first implementation. The project keeps a
  future self-contained publish path open and measures it later.

### Design drivers

- The current Portico TOML defines financial groups and defaults well, while
  the Python page files define much of the presentation.
- The current Roci chart model has numeric points and categorical bars, but no
  date data, category-aligned connected data, range bars, or heatmap series.
  It has `AnchorOverlay`, `Modal`, and `MenuList`, but no drawer primitive with
  a left slide, scrim dismissal, and input isolation.
- Personal-finance data is sensitive. Tests use synthetic data, and diagnostics
  never repeat URLs or cell values.
- The application needs to be easy to build on Windows first, with Linux
  self-contained publishing evaluated only after ordinary publishing works.

## Context And Scope

### Repository boundaries

The Portico app and the Roci framework are different products with different
review surfaces.

| Repository/worktree | Owns | Does not own |
| --- | --- | --- |
| ../portico-roci-rebuild on nccurry/roci-portico-plc | Solution, finance/report code, TOML/CSV adapters, CLI, Roci composition, app tests, app docs, demo data | Copies of Roci source or Portico-only UI primitives in the framework |
| ../roci-portico-components on nccurry/portico-roci-components | Reusable generic drawer and chart primitives, Roci samples, Roci tests, Roci documentation | Portico finance types, TOML schema, sheet adapters, dashboard business rules |

Create the companion from the reviewed Roci `main` commit
`2404411b80c65bcb2e0f07f59492a875456d6074` in a new clean worktree. The
default Roci checkout has unrelated untracked PLC work and is not an
implementation target:

    git -C ../roci worktree add -b nccurry/portico-roci-components \
        ../roci-portico-components 2404411b80c65bcb2e0f07f59492a875456d6074

If the intended Roci base changes before the command is run, record the new
commit in this packet first. Do not take untracked files from the default Roci
checkout into the companion worktree.

During development, the Portico solution uses an explicit, non-committed
RociSourceRoot MSBuild property to reference the companion Roci worktree. The
repository never commits an absolute local path. Once the Roci work is accepted,
the normal Roci package/reference policy replaces that development override.
The Portico app therefore stays a consumer, not a fork.

### Current dashboard inventory

The scope is Home plus these nine current Portico pages:

1. Income and Savings
2. Spending by Category
3. Year over Year
4. Subscriptions
5. Merchant Analysis
6. Budget
7. Top Transactions
8. Financial Independence
9. Data Health

The detailed report and visualization mapping is in
[Page reports and rendering](#page-reports-and-rendering) and
[FIXTURES.md](FIXTURES.md#page-and-visualization-inventory).

### External interfaces

- Explicit public Google Sheets document tab URLs.
- Google CSV export endpoints derived from those URLs.
- Local CSV directory for demo data and deterministic development.
- Existing `config.toml` or `portico-demo.toml`, new `dashboard.toml`,
  `portico.secrets.toml`, and command-line overrides.
- Roci and MonoGame DesktopGL host.

## Alternatives Considered

| Option | Summary | Strengths | Weaknesses | Decision |
| --- | --- | --- | --- | --- |
| Port the Streamlit pages line by line into Roci code | Keep all visual choices in C# page builders | Fast-looking first screen | Fails the configuration-driven requirement and makes every presentation edit a code change | Rejected |
| Build a generic formula/dashboard engine | TOML describes arbitrary data transforms and drawing | Maximum apparent flexibility | Hard to test financial logic, unclear errors, broad attack/maintenance surface | Rejected |
| Use numeric epoch values and custom formatters for all dates | Adapt current Roci numeric chart support | Avoids framework work initially | Loses type safety, makes interactions awkward, and hides a Roci gap | Rejected |
| Add Portico-only custom drawing for timelines/heatmaps | Finish pages without Roci changes | Localized application work | Leaves reusable framework holes and produces a second chart language | Rejected |
| Use Roci's existing charts plus small reusable component additions | Build real reports; improve only proven gaps | Clear ownership, reusable result, no dashboard DSL | Requires coordinated app/framework work | Chosen |
| Use Google Sheets API/OAuth | Official worksheet API | Rich metadata and private sheet access | Requires credentials and is outside agreed scope | Deferred |
| Start with Native AOT/single-file static builds | Chase final packaging early | Potential easy distribution later | Risks blocking UI work on native graphics details | Deferred |

## Chosen Design

### Solution shape

The solution has four production projects and focused test projects. This is
the smallest split that keeps domain work free of UI and external I/O.

    Portico.App  ----------------> Portico.Dashboard ----> Portico.Finance
         |                                  ^
         |                                  |
         +----> Portico.Adapters -----------+
         |
         +----> Roci.Ui and MonoGame DesktopGL

    Portico.Adapters -------------> Portico.Finance

- Portico.Finance: records for normalized finance data and pure calculations.
  It references only .NET base libraries.
- Portico.Dashboard: named report builders, filter state, typed dashboard
  configuration model, and presentation-neutral result records. It references
  Portico.Finance, not Roci, HTTP, filesystem, or a TOML package.
- Portico.Adapters: TOML parsing/validation, source selection, HTTP CSV
  loading, local CSV loading, and normalization. It references Finance and
  Dashboard to produce their typed input/configuration records.
- Portico.App: the CLI, composition root, background loading coordinator, Roci
  host, and renderer that maps dashboard result records to fluent Roci calls.
  It is the only project that references Roci and MonoGame.

No Common, Utils, generic service locator, or untyped data bag is created. An
interface exists only at the true external source boundary:
IPortfolioSnapshotSource.LoadAsync(SourceRequest, CancellationToken). The local
and public-sheet sources both implement it.

### Building blocks

| Building block | Responsibility | Owned data/lifetime | Public surface | Dependencies | Tests |
| --- | --- | --- | --- | --- | --- |
| PortfolioSnapshot | Immutable normalized workbook data and normalization notices | One complete in-memory load | Typed records/collections | .NET only | Equal snapshot/invalid-row tests |
| Portico.Finance calculators | Money, periods, groups, savings, budgets, subscriptions, safety, and FI calculations | Stateless; accepts records and settings | Named pure methods/records | .NET only | Table-driven exact expected values |
| DashboardDefinition | Typed page, widget, control, layout, and text configuration | Immutable validated config | PageDefinition and typed widget/filter records | Finance settings types | Parser semantic tests |
| Report builders | Convert snapshot + settings + page filters to one page result | Short-lived result per filter/data revision | Named Build...Report methods | Finance/Dashboard | Report/filter tests |
| GoogleSheetsSnapshotSource | Validate URLs and fetch four CSV exports | HttpClient and cancellation only | LoadAsync | Adapters | Fake-handler URL/status/CSV tests |
| LocalCsvSnapshotSource | Read a known four-file local source | File reads during load only | LoadAsync | Adapters | Temp fixture tests |
| TomlConfigurationLoader | Load, validate, and redact separate finance, dashboard, and secret inputs | One validated settings snapshot | Load(...) | TOML package at adapter edge | Parse/precedence/error tests |
| DashboardSession | Holds selected page, filter values, drawer state, data revision, and load status | Desktop-process state | Intent methods, immutable state snapshots | Dashboard | State transition tests |
| RociDashboardRenderer | Render one typed page result and controls | No finance/source ownership; only widget references | Render(UiBuilder, DashboardSession) | App/Roci | UI interaction/capture tests |

## Runtime And Data Flow

### Startup and load path

    CLI arguments + finance TOML + dashboard TOML + secret URLs
                  |
                  v
          validated settings
                  |
                  v
         selected snapshot source ----> CSV fetch/read ----> normalize all four tabs
                  |                                            |
                  |                                            v
                  +-------- failure state             PortfolioSnapshot
                                                               |
                                                               v
                                                     named page report builder
                                                               |
                                                               v
                                                    typed page result + filters
                                                               |
                                                               v
                                                    fluent Roci widget tree

1. The CLI selects a config file, optional secrets file, and source overrides.
2. The configuration loader parses each file, merges documented precedence, and
   validates all IDs and cross-references before a window starts.
3. The source loader validates the four logical sheet URLs, resolves each CSV
   export URL, loads all four sources with cancellation, and normalizes them.
4. A load succeeds only when the complete snapshot is valid. On reload failure,
   a previously valid snapshot remains visible with a safe stale-data notice;
   on first-load failure, the diagnostic screen appears instead of a partial
   dashboard.
5. A report builder receives the snapshot, validated settings, and selected
   filter values. It returns a typed result. The renderer never re-parses CSV
   or recalculates finance rules inside a frame.
6. Controls and chart hits emit small intents such as SelectPage, SetFilter,
   SelectMonth, OpenDrawer, or DismissDrawer. The session validates the intent,
   updates state, and rebuilds only the affected report.

Fetch and CSV parsing run outside the render loop. Snapshot/session replacement
happens on the UI-safe application path. All chart data is converted to Roci
data only after report calculation; no network, TOML parsing, or transaction
scan occurs per frame.

## Configuration And CLI

### File layout and precedence

    config.toml           existing checked-in financial settings
    portico-demo.toml     existing checked-in local-demo financial settings
    dashboard.toml        checked-in desktop page and widget settings
    portico.secrets.toml  ignored; public Google Sheets URLs only
    demo/data/            checked-in synthetic CSV fixture data

The selected finance file and `dashboard.toml` are separate complete inputs.
The C# app does not append a dashboard table to the existing finance file:
`src/config.py` rejects unknown top-level tables and the Python app must remain
able to read its current files. For each setting, precedence is CLI override,
secrets file for a URL, its own selected TOML file, then a documented safe
default. A source override does not silently merge rows from a different
source. URLs supplied through --sheet are allowed for quick setup but help text
recommends the ignored secrets file so shell history does not retain them.

The existing calculation sections keep their names and shape where practical:
data, lookback, thresholds, merchants.aliases, transaction_sets.*,
filter_sets.*, income_savings, subscriptions, budget, data_health,
financial_safety, and financial_independence. weekly_summary is parsed only to
recognize an existing Portico config; it has no dashboard effect and produces
one concise notice because Discord work is out of scope.

The separate versioned `dashboard.toml` owns presentation. It uses a small set
of known widget and filter kinds, not arbitrary nested property names or
formulas.

    schema_version = 1

    [dashboard]
    title = "Portico"
    initial_page = "home"

    [dashboard.navigation]
    drawer_width = 288

    [[dashboard.pages]]
    id = "income-savings"
    title = "Income and Savings"
    icon = "chart"
    visible = true

    [[dashboard.pages.filters]]
    id = "period"
    kind = "period-range"
    label = "Period"
    default = "lookback.default_lookback_months"

    [[dashboard.pages.filters]]
    id = "transaction-set"
    kind = "transaction-set"
    label = "Transactions"
    source = "filter_sets.spending"

    [[dashboard.pages.widgets]]
    id = "monthly-cash-flow"
    kind = "monthly-cash-flow"
    title = "Monthly cash flow"
    layout = "wide"
    binds = ["period", "transaction-set"]
    show_zero_rule = true

    [[dashboard.pages.widgets]]
    id = "savings-rate"
    kind = "savings-rate-history"
    title = "Savings rate"
    layout = "wide"
    binds = ["period"]
    target = "income_savings.target_rate"

The `[sheets]` URL section belongs only in `portico.secrets.toml`, not a
checked-in file. Page ID, kind, layout, binds, and field names are validated
against typed C# records. For example, monthly-cash-flow selects the named
report and chart renderer; it cannot contain an expression that transforms
money. A page definition can order or hide existing widgets, but a new widget
kind requires a deliberate report/renderer/test change. The `transaction-set`
control above gets its default and valid options from the existing named
`filter_sets.spending` definition; it does not repeat them in dashboard TOML.

### CLI contract

    portico run [--config PATH] [--dashboard PATH] [--secrets PATH]
                [--source google-sheets|local-csv] [--data-dir PATH]
                [--sheet NAME=URL]

    portico doctor [--config PATH] [--dashboard PATH] [--secrets PATH]
                   [--source google-sheets|local-csv] [--data-dir PATH]
                   [--sheet NAME=URL] [--output text|json]

- run is the default command when no command is supplied. It opens the desktop
  app after both TOML files validate. `--dashboard` defaults to `dashboard.toml`
  beside the selected finance file; `--config` keeps its existing default.
- doctor checks configuration, source selection, URL shape, and input headers
  without creating a graphics window. It may make a network request only when
  explicitly given a Google source; tests use a fake handler instead.
- Sheet names are exactly transactions, balance-history, categories, and
  accounts.
- --help contains a short AI_CONTEXT section explaining input precedence,
  output mode, and stable exit codes.
- doctor --output json writes exactly one machine-readable result to stdout;
  progress and diagnostics go to stderr. Raw URL values and data values are
  redacted in either output form.
- Exit code 0 means valid, 2 means argument/configuration error, 3 means
  source/CSV validation error, and 4 means unexpected application startup
  failure. Help/version use 0.

## Data Loading And Normalization

GoogleSheetsSnapshotSource accepts only explicit HTTPS Google Sheets document
URLs with a document ID and numeric gid. It turns each into the same direct
CSV-export form used by the current Portico loader. It does not inspect or
scrape the undocumented Google viewer HTML to discover tabs.

The source loads the four required logical tabs: Transactions, Balance History,
Categories, and Accounts. Each parser validates expected headers, row shape,
money/date fields, and required identities. It reports logical sheet names and
row counts, not data values or raw URLs. The normalizer applies aliases and
produces one immutable PortfolioSnapshot plus typed data-quality findings.

The local source reads the corresponding four deterministic CSV files. It uses
the same CSV parser and normalizer as the remote source. This is important:
there is no separate demo calculation path that can drift from the real one.

Source load has these failure rules:

- A malformed URL, missing tab URL, bad response, duplicate key, missing
  header, invalid date/amount, or incompatible CSV stops the proposed snapshot.
- A first load shows a diagnostic screen with the logical failure and a
  suggested doctor command.
- A reload preserves the last complete snapshot until a new complete snapshot
  replaces it.
- Cancellation stops outstanding fetches and does not replace the session.

## Financial Calculation Design

Finance code uses decimal for amounts and ratios where it performs money math,
DateOnly for calendar data, and explicit named period boundaries. double appears
only in the chart adapter after a value has been computed. Formatting and
currency rounding happen at the presentation boundary; internal totals retain
the source precision defined by the existing Portico logic.

Before porting any calculator, its sign convention and period rule are written
as a named test. The C# code preserves the Python meaning; it does not guess
that an expense should be positive or negative because a chart looks better.

Named calculator families include:

- transaction classification, aliases, named transaction sets, and exclusions;
- monthly income, spending, cash flow, and savings rate;
- category, merchant, account, and year-over-year aggregates;
- balances, net worth, asset allocation, and safety metrics;
- subscription lifecycle/charge summaries;
- budget actual-versus-target/typical/ideal-day values;
- top transaction and data-health findings;
- FI spending baseline, projection, funding gap, and sensitivity grid.

Each calculator returns an intentional report record, not an anonymous tuple or
UI widget. A calculation never reaches into TOML or reads a global singleton.

## Filter State And Interaction

DashboardSession owns one immutable state record:

- active page ID;
- whether the navigation drawer is open;
- each configured filter's selected typed value;
- linked chart/table selection such as a selected month;
- current data revision and load status.

DashboardDefinition declares filters and widgets. A widget lists its binds; a
control change only invalidates reports that bind that filter. A page can have
period range, named transaction-set, category/group, account, merchant, month,
or compare-period controls. The allowed filter kinds are enumerated in C#;
unknown kinds fail config validation.

Chart callbacks report a stable category or date identity supplied by Roci. The
application maps that to a typed intent, then updates the same filter state as
the matching button/menu control. For example, selecting a month in cash flow
sets selected-month, which updates the selected-month breakdown but does not
change the global transaction set.

There is no hidden shared mutable filter object in a page renderer. The session
state is passed in, and a page report is rebuilt from that state. This makes
linked interactions easy to unit test.

## Desktop Shell And Navigation

Portico.App starts Roci's normal MonoGame DesktopGL host. Its root layout has a
compact top bar with a menu button and page title, a content region, and a left
navigation drawer. On small widths the drawer overlays content and blocks only
the area it covers; on larger widths it may remain open while still using the
same left-slide animation and selection semantics.

The page list is defined by the ordered dashboard.pages TOML entries. The
renderer gives each page a stable ID, title, optional icon, selected state, and
callback. It does not hard-code an enum-sized navigation switch merely to draw
the menu.

Cards, charts, tables, and controls use a normal responsive flex/grid layout.
The configuration supports a small layout vocabulary: full, wide, half, third,
and card-row. Values are checked against each widget kind. It does not expose
raw pixel coordinates or an arbitrary box tree. Each widget has a stable TOML
ID which becomes its Roci widget name and visual-test identity.

## Page Reports And Rendering

The renderer consumes report records and uses regular Roci fluent composition.
It does not carry a second chart-builder layer. Existing charts use calls such
as CartesianChart, LineSeries, AreaSeries, BarSeries, ReferenceLine, Sparkline,
DataGrid, controls, and EndChart. New Roci features use the same name-only
opener, per-item verb, and EndWidget pattern.

| View | Report output and configured controls | Visual forms | Roci need |
| --- | --- | --- | --- |
| Home | Net worth, allocation, account cards, safety inputs | Date line/area, attribution bars, sparklines, metric/progress cards | Date axis; existing area/bar/sparkline |
| Income and Savings | Monthly income/spending/cash flow, savings-rate history, selected month | Category bars with line overlay, guides, detail table | Category-aligned connected series |
| Spending by Category | Monthly trend, rank, group/category history, selected category | Lines, horizontal bars, category bar/line comparison, sparklines, tables | Category-aligned connected series |
| Year over Year | Annual group/category comparisons | Lines and points with zero guide | Existing numeric charts |
| Subscriptions | Current subscriptions, observed/inferred lifecycle, charge history | Date range timeline, endpoint/current-date guide, bars/lines, grids | Date ranges and date guide |
| Merchant Analysis | Merchant rank, history, breakdown | Horizontal bars, comparison chart, sparklines, grid | Existing plus category overlay where needed |
| Budget | Pulse, daily pace, monthly actual/budget, category details | Bars with target/typical guide, date lines, bar/line overlay, sparklines | Date/category data and guides |
| Top Transactions | Largest amounts and category split | Date scatter with zero guide, bars, grid | Date points |
| Financial Independence | Projection, funding, sensitivity, supporting spending | Date area/line/depletion point, horizontal bars, heatmap, cards | Date points and heatmap |
| Data Health | Counts, issue queue, raw/problem rows | Metric cards, filter controls, data grids | Existing controls/grids |

An empty or filtered-away report uses a clear no-data card in the widget's
configured space. It does not draw misleading zero-valued finance charts.

## Roci Work Owned By The Companion Branch

The companion branch adds only components that the Portico inventory proves
necessary. Names below are the proposed public direction; the exact overload
names are reviewed against Roci's API language guide before merge. The fluent
shape is not optional: collection widgets open a container, add items/series
through per-item verbs, and close with the matching End method.

### 1. Drawer proof before a new component

First build the Portico shell from `AnchorOverlay`, `MenuList`, and `MenuItem`.
That reuses Roci's current menu selection and command-routing behaviour. If it
cleanly provides a left slide, scrim dismissal, input isolation, focus return,
and narrow/wide presentation, no drawer API is added to Roci.

If that proof needs app-side overlay or input code, add a generic `Drawer` to
Roci. It owns only side placement, visibility, slide/overlay behaviour, and
dismissal. Portico continues to compose its page list through the existing
`MenuList`; it does not add a `NavigationItem` or a Portico page concept to
Roci. The likely fluent shape is:

    ui.Drawer("pages")
        .Open(session.IsDrawerOpen)
        .Left()
        .Width(288)
        .OnDismiss(DismissDrawer)
        .MenuList()
            .MenuItem(page.Title, () => SelectPage(page.Id))
        .EndMenuList()
    .EndDrawer();

The exact callback and style verbs follow the Roci API guide. What must remain
true is one ordinary UiBuilder, a generic name-only drawer opener, regular
child composition, and an explicit end. It supports open/close state,
focus/input routing, overlay dismissal, left-side placement, and the same
event path on narrow/wide layouts.

### 2. Typed category and date chart coordinates

Roci currently has numeric ChartPoint data for connected series and
ChartCategoryValue only for bars. Portico needs a line to share the exact
month/category axis used by bars, plus date values that retain a DateOnly
identity through labels, tooltips, and hits.

The framework work adds a category-backed connected series input, reusing or
carefully extending ChartCategoryValue, and a ChartDatePoint(DateOnly, double)
input. Fluent calls are explicit, for example:

    ui.CartesianChart("monthly-cash-flow")
        .BarSeries("income").Bars(income)
        .BarSeries("spending").Bars(spending)
        .LineSeries("cash-flow").CategoryValues(cashFlow)
        .ReferenceLine(ChartAxis.Y, 0d)
    .EndChart();

    ui.LineChart("net-worth")
        .DatePoints(netWorth)
        .XAxis("Date")
    .EndChart();

Roci infers the compatible category/date axis and rejects a conflicting series
or guide before retained state changes. A date chart has date-aware tick
formatting and hit results; it does not force callers to reverse a numeric epoch
back into a date. A date guide has an equally typed date input.

### 3. Range bars for timelines

Subscription lifecycles need horizontal intervals with distinct observed and
inferred series, endpoint points, and a current-date rule. The framework adds
a range-bar series with a generic date/category record such as
ChartDateRange(category, start, end). It validates non-empty categories and
ordered inclusive ranges, retains stable identities for hits, and composes on a
date/category Cartesian chart.

    ui.CartesianChart("subscription-lifecycle")
        .RangeBarSeries("observed").DateRanges(observed)
        .RangeBarSeries("inferred").DateRanges(inferred)
        .ReferenceDateLine(ChartAxis.X, today)
    .EndChart();

This is not a Portico SubscriptionTimeline widget. A generic range-bar component
is useful wherever data has category-labelled time intervals.

### 4. Heatmap cells

FI sensitivity is a categorical two-axis grid of calculated values. The
framework adds a heatmap series/cell model with stable X/Y category labels,
numeric value, configurable color scale, optional label formatting, and normal
tooltip/hit behaviour.

    ui.CartesianChart("fi-sensitivity")
        .HeatmapSeries("projection")
            .Cells(cells)
            .ColorScale(scale)
            .CellLabels()
    .EndChart();

It is a normal chart series, not an application-side texture or custom drawing
fallback. Its fluent `Cells` input follows Roci's normal copied-snapshot
authoring path, like `Points` and `Bars`.

### Framework correctness and performance rules

- New chart inputs use immutable public state and validated candidate
  replacement before mutation, consistent with Roci chart authoring.
- Ordinary fluent inputs are copied once, then retained as owned snapshots.
  Lower-level borrowed inputs, if added, use an explicit `BorrowedData`-style
  contract. Neither path enumerates or allocates input data per frame.
- Axis inference, series compatibility, category matching, guides, layout,
  hit testing, tooltips, and input handling are tested without depending only
  on visuals.
- Roci samples demonstrate each new widget in isolation and Portico provides a
  realistic consumer composition. Neither substitutes for the other.
- No Portico finance type, TOML enum, color name, or subscription concept is
  added to Roci.

## APIs, Schemas, And Diagnostics

### Report Data Passed To The Renderer

Page builders return a small typed union/record family: metric cards, tables,
chart series, guides, selectable values, and no-data/error states. The contract
uses finance-domain terms such as MonthlyCashFlowReport and BudgetPulseReport
rather than Dictionary<string, object>. The Roci renderer maps these values to
widget calls in one place.

Widget TOML is parsed into a corresponding typed discriminator model. Unknown
or incompatible combinations fail during setup. For example, a heatmap widget
cannot bind a selected-month control if its named report does not declare that
filter.

### Diagnostics

DoctorResult is a stable typed result that includes:

- finance/dashboard paths and schema version, without secret values;
- selected logical source type;
- logical sheet names and validation status;
- recognized pages/widgets/filter IDs;
- warnings such as ignored weekly_summary settings;
- a stable diagnostic code and safe message for each failure.

Runtime loading uses the same diagnostic facts in its error screen. The app may
show data-health rows inside the private local UI because that is the
dashboard's purpose, but it does not write their contents to logs or CLI
diagnostics.

## Cross-Cutting Concepts

### Privacy and failure handling

Raw URL strings, CSV rows, transaction descriptions, balances, and secret-file
contents are never written to normal logs, exceptions, doctor output, or test
failure snapshots. Error messages identify the logical input and category of
problem. Debug capture fixtures use only synthetic data.

### Data ownership and cancellation

Each successful source load creates one immutable snapshot. Page reports do not
retain mutable CSV readers. A reload has its own cancellation token and cannot
replace a newer successful revision. Static chart data is recreated only after
a data/filter/config revision, then handed to Roci through its ordinary owned
data path.

### Accessibility and input

Controls have visible labels. The drawer has a focusable open control, selected
page indication, dismissal by the standard close/escape route where Roci
supports it, and no hidden click target over content once closed. Colour is not
the only difference for budget/safety status; text and values remain visible.

### Determinism

The app injects a clock into reports that need today, particularly subscriptions
and FI projections. Tests use a fixed date. Sorting rules specify their
tie-breaker so a grid or bar order does not change with dictionary order.

## Package Boundaries And Public API Language

Portico.Finance exposes plain named calculations and records. It never leaks
Roci types. Portico.Dashboard exposes report/configuration records but no
parser-specific TOML nodes. Portico.Adapters is the only owner of HTTP,
filesystem, CSV, and TOML implementation types. Portico.App is the only Roci
consumer and composition root.

New Roci APIs belong in Roci.Ui, use Roci terminology, and follow the current
API language guide. In particular, there is no PorticoChartBuilder, no one-shot
DashboardOptions item list, and no mutable public chart state. If the drawer
proof produces a Roci component, `Drawer` owns the container and callers
compose ordinary child widgets inside it; a chart opens, adds named
series/cells/guides one at a time, and closes with EndChart.

## Readability And Documentation

- Names use the existing Portico words when they carry financial meaning:
  transaction set, budget, safety, subscription, and financial independence.
- Code comments explain unusual source conventions, sign rules, and Roci
  ownership constraints. They do not paraphrase obvious C#.
- Every public config kind and CLI diagnostic has a concise user-facing
  explanation in the setup guide.
- The app README includes a minimal local-demo path before a public-sheets path.
- Roci documentation and samples explain the reusable component without
  mentioning Portico except as a consumer reference.
- Replaced prototype renderers, duplicate report arithmetic, and dead config
  aliases are deleted in the phase that supersedes them.

## Quality Attribute Design

| Requirement | Design response | Validation |
| --- | --- | --- |
| REQ-004, REQ-007 | Typed discriminated TOML records preserve existing finance sections and reject unsupported dashboard configuration before UI startup. | Configuration fixture tests and doctor. |
| REQ-005, REQ-006, REQ-018 | One source interface with remote/local implementations shares normalization and redacted diagnostics. | Fake HTTP/local CSV/redaction tests. |
| REQ-008 | Immutable session state plus declared widget bindings makes each filter effect explicit. | Report and UI intent tests. |
| REQ-009, REQ-010 | Page-proven Roci components cover each missing visualization type. | Roci API/core/sample tests plus Portico captures. |
| REQ-011, REQ-012, REQ-016 | Decimal/DateOnly pure calculator layer with table-driven expected results. | Finance fixture matrix. |
| REQ-013, REQ-015 | Small CLI and Task/mise command surface with documented input/output behaviour. | CLI parsing/exit-code and clean-checkout Task checks. |
| REQ-014 | One-direction project graph and renderer-only Roci reference. | Build/source review. |
| REQ-017 | Stable widget IDs, fixed synthetic fixtures, and wide/narrow captures. | Visual comparison and interaction suites. |
| REQ-019 | No absolute path or browser assumption in project layout; publish is isolated at the app edge. | Runtime-specific publish smoke tests. |

## Implementation Phases

| Phase | Code areas | Requirements | Exit criteria |
| --- | --- | --- | --- |
| 0. Foundation | Solution files, Task/mise, config schema/parser, CLI doctor, demo fixture skeleton | 001, 004, 013-015, 018, 020 | A clean checkout validates the synthetic local configuration and returns redacted text/JSON diagnostics. |
| 1. Data and calculation core | Finance, adapters, local/mocked Google sources, report records, calculation fixtures | 005-007, 011-012, 016 | Exact report fixtures pass without Roci or a network connection. |
| 2. Roci baseline additions | Existing overlay/menu drawer proof or companion generic Drawer, typed date/category chart coordinates, tests/samples | 003, 009-010, 017 | The selected drawer approach and date/category overlay samples compile, interact, and capture correctly. |
| 3. Dashboard shell and Home | App/session/renderer, configured shell, Home | 002-004, 008-009, 014, 017 | Desktop app opens Home with configured drawer, correct report values, and wide/narrow capture evidence. |
| 4. Standard dashboard pages | Income/Savings, Spending, YoY, Merchant, Budget, Top Transactions, Data Health | 002, 004, 008-009, 017 | Seven configured standard pages have correct reports, filters, and captures. |
| 5. Advanced Roci and dashboard pages | Companion range bars, date guides, heatmap, Subscriptions, FI, tests/samples/docs | 002, 008-010, 017, 020 | All ten views render from the same config/source and use native Roci components. |
| 6. Hardening and publish proof | Full docs, Task gates, visual suite, publish profiles, final audit | 015-020 | Broad validation passes and packaging results/deferred limits are recorded. |

## Test Architecture

Tests use synthetic, non-sensitive CSV workbooks. They never fetch a real
public finance workbook in CI.

| Test layer | Purpose | Examples |
| --- | --- | --- |
| Finance unit tests | Exact calculation behaviour | monthly signs, savings-rate zero income, leap month, refund, alias, FI grid cell |
| Dashboard/report tests | Filter binding and page-shaped output | selected month updates only its detail widget; sorting/tie rules; no-data state |
| Adapter tests | TOML, URL, CSV, source failures | config merge, unknown widget, malformed gid, fake 403, missing header, redaction |
| CLI tests | User and automation contract | command/default parsing, exit codes, JSON stdout, stderr diagnostics, secret redaction |
| Desktop behaviour tests | Intent/session/renderer mapping | drawer open/select/dismiss, configured control callback, linked chart selection |
| App visual tests | Real page composition | each page wide/narrow, drawer states, selected/filter states, no-data/error screen |
| Roci API/core/rendering/sample tests | Framework component correctness | fluent compile consumers, atomic invalid configurations, layout/hits/input, sample captures |

The detailed IDs and boundary cases are in [FIXTURES.md](FIXTURES.md). A test
that needs to prove finance arithmetic asserts the expected amount/date/group;
it does not only assert that a chart has a nonzero number of points.

## Tooling, Packaging, And Diagnostics

Phase 0 copies the relevant Roci project conventions: the checked-in .NET SDK
selection, mise.toml for Task, and a root Taskfile.yml. The exact SDK is kept
aligned with the Roci worktree at implementation time rather than guessed in
this PLC.

The intended task surface is:

    task format             format source
    task lint               verify formatting/analyzers
    task build              normal build
    task build:strict       warnings treated as errors
    task test               all non-visual tests
    task test:finance       finance and report tests
    task test:adapters      config/source/CLI tests
    task test:desktop       session and renderer tests
    task visual-test        approved Portico visual comparisons
    task doctor             run local-demo doctor command
    task publish:win-x64    later self-contained publish proof
    task publish:linux-x64  later self-contained publish proof

task test does not open a normal desktop window or use a live network source.
Focused tasks run before broad gates. Roci component work uses the actual Roci
commands `task lint`, `task build:strict`, `task test`, `task test:visual`, and
`task samples:visual-test`, plus narrow component tests. The default Roci
checkout is not used for those commands; the clean companion worktree is.

The first publish target is the ordinary .NET desktop output. The later publish
tasks try self-contained win-x64 and linux-x64, record executable and native
dependency behaviour, and only then decide whether a single-file bundle is
acceptable. Native AOT is a measured follow-up because MonoGame and its native
graphics libraries may rule it out.

## Framework And External Notes

- The current Portico sheet_config.py creates direct Google CSV export URLs
  from document ID and gid. Preserve that simple contract for explicit URLs.
- Google viewer htmlview metadata is undocumented and may shift gid mapping when
  parsed naively. This design deliberately requires user-supplied tab URLs
  instead of using viewer HTML discovery.
- Current Roci fluent chart composition already provides layered lines/areas,
  scatter plots, categorical bars, guides, interaction, and sparklines. Reuse
  those paths before adding features.
- Current Roci ChartCategoryValue represents a category plus one numeric value
  for bars, while connected chart data uses only numeric ChartPoint.
  Category-aligned connected data is therefore a real framework change, not a
  presentation choice.
- Roci samples are validation evidence, not a dumping ground for Portico
  dashboard code. Portico has its own app-level visual checks.

## Decisions, Risks, And Deferred Work

| Item | Type | Impact | Resolution |
| --- | --- | --- | --- |
| Keep finance math in C# instead of TOML formulas | Decision | Tests name every financial rule and output | Accepted; configuration selects reports and values only. |
| Require explicit tab URLs | Decision | Slightly more initial setup | Accepted; avoids fragile page scraping and matches current Portico. |
| Parse legacy weekly_summary but do not act on it | Decision | Existing config is familiar; no notification feature appears | Accepted; emit a one-time dashboard-only notice. |
| Keep dashboard TOML separate from finance TOML | Decision | The existing Python loader rejects unknown tables | Accepted; `dashboard.toml` owns desktop presentation and `--dashboard` selects it. |
| Companion branch uses live Roci source reference while features are under review | Decision | App build has a local development dependency | Accepted; no absolute path is committed, and final dependency follows Roci policy. |
| Roci component API could reveal another chart rule | Risk | Framework phase may need adjustment | Use focused API/core/rendering tests before app migration; update this packet before changing the public shape. |
| A chart visual can look plausible while totals are wrong | Risk | Financial trust | Treat report/finance expected-output tests as the primary oracle; captures are secondary. |
| Self-contained single-file or Native AOT publishing may not work with graphics dependencies | Deferred | Distribution convenience | Record tested publish facts in Phase 6; never block dashboard correctness on it. |
| OAuth/private workbooks and notifications | Deferred | Some current/future users may need them | Separate PLC after the dashboard proves its value. |

## Glossary

| Term | Meaning |
| --- | --- |
| Portfolio snapshot | One complete, normalized in-memory read of the four input tabs. |
| Report | A typed calculation result for a page/widget, before it is rendered by Roci. |
| Widget kind | A finite, validated TOML name for a known report/renderer pair. It is not executable code. |
| Transaction set | Existing Portico named inclusion/exclusion configuration for a subset of transactions. |
| Drawer | A generic left or right slide-out presentation container. Portico places its page items inside it with a MenuList. |
| Category-aligned series | A bar/line/area series whose X coordinate is the same stable category identity as peer series. |
| Date range bar | A horizontal interval with a category, start date, and end date. |
| Companion branch | The separate Roci branch/worktree that owns reusable framework changes. |
