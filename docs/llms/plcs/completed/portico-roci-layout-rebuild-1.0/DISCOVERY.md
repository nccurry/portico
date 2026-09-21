# Discovery

## Goal

Before changing the UI, make a small, factual inventory of what Portico shows,
what the current Roci app shows, and what Roci can already compose. This keeps
the rebuild tied to the real app rather than to memory or a loose description.

## Sources To Inspect

| Source | What To Record |
| --- | --- |
| Streamlit Portico page modules | Navigation group, navigation label, page heading, controls, cards, charts, tables, tabs, empty states, and page-specific actions. |
| Streamlit screenshots | Dark colors, main widths, rail width, spacing, text hierarchy, chart height, and control placement. The committed screenshots are 1500 by 1000. |
| `dashboard.toml` and its C# types | Existing page IDs, widget IDs, filter keys, chart kinds, and fields that can be extended safely. |
| `PorticoDashboardScene.cs` and its tests | Current shell, direct layout code, current state flow, and the tests that must be rewritten or retained. |
| Roci layout, control, overlay, table, chart, and skin source | Exact fluent APIs already available for this app. |
| Roci samples and visual tests | The existing way to capture and compare a desktop screen. |

## Discovery Steps

1. Run the Streamlit reference with its demo data and save one image for every
   page at a fixed desktop size. Use 1500 by 1000 as the primary comparison
   size because that is the size of the committed reference images. Use 1024 by
   720 as the narrow-desktop check.
2. Run the current Roci app with the same demo data and save the same set of
   images.
3. Make a page inventory table. For each page, record its page ID, source file,
   group/order, navigation label, page heading, icon, left-to-right and
   top-to-bottom regions, controls, and reports or visible page state affected
   by each control.
   Include segmented choices, single selects, multi-selects, number inputs,
   sliders, toggles, tabs, expanders, row selection, reset actions, and
   popovers where the source page uses them.
4. Map each region to an existing Roci primitive: vertical stack, horizontal
   stack, panel, text, control, overlay, data grid, or chart.
5. Mark a gap only when a small composition of existing Roci primitives is
   awkward, cannot provide the interaction, or would force page-specific code
   into several pages.
6. Add a test-only capture host for Portico if the current desktop host cannot
   accept Roci capture arguments. It must create deterministic demo sessions,
   select named page states, enable Roci automation and capture, and accept the
   normal Roci capture arguments. Make `roci:visual` run the named cases
   serially. Reuse Roci's capture verifier rather than creating a new image
   comparison system.
7. Save the inventory, images, Roci API mapping, and open questions in this
   packet before Phase 1 starts.

## Starting Component Inventory

| UI need | Current direction | Status at planning time |
| --- | --- | --- |
| Rows, columns, gaps, wrapping, grow, shrink, and alignment | Use Roci stacks and flex settings. | Available. |
| Dark surface, text, borders, selected state, and chart colors | Add a Portico app skin using Roci skin/style slots. | Available foundation; app styling is incomplete. |
| Permanent left navigation | Build a local navigation rail from flex, buttons/menu items, and selected state. | Needs a local proof. |
| Page header, metric card, section panel, and filter bar | Build small local Portico pieces from panels and standard controls. | Needs local composition, not a Roci feature. |
| Single-select, segmented choice, toggle, number input, slider, and collapsible detail | Use existing Roci controls. | Available. |
| Filter that selects more than one value | Build a local multi-select from a button, popover, checkbox list, count badge, and clear action. | Confirmed required local component. |
| Tabbed detail views | Use Roci `TabPanel` and `Tab`; keep selected tab in page state only where the source page needs it. | Available. |
| Deterministic visual capture | Add a test-only capture host. The release host is fixed at 1280 by 820 and does not enable Roci automation/capture. | Required. |
| Tables, selected rows, and chart/table detail | Use DataGrid and the existing chart API. | Available; verify the exact Portico cases. |
| Tooltips, drop-down details, and dialogs | Use existing Roci overlays. | Available. |
| CSS-like `order` or reverse flex direction | Do not add it unless a named Portico screen truly needs it. | Not needed by the starting design. |

## Phase 0 Source And Roci Record

This record covers the discovery and capture baseline completed on 2026-09-04.
It is based on the checked-in Streamlit source, the current C# dashboard, and
the current Roci component worktree. The test-only capture host and current
Roci baseline images are now part of this completed phase. Typed controls and
configuration mappings remain later Phase 3 work.

### Shared Shell Facts

- `Home.py` owns the source navigation. `Home` is a standalone rail item, not
  a group. Its page heading is `Accounts and net worth`.
- `render_demo_banner()` runs before source page content. It is a banner above
  the page heading when demo data is active.
- Every source page calls `render_data_refresh_controls()` for the sidebar
  load timestamp and `Refresh data` action. `Home.py` adds the global
  hide-values control after navigation is built.
- The Streamlit Deploy/menu frame is not dashboard content and is not part of
  the desktop target.

### Source Navigation To Dashboard Configuration

The existing C# `DashboardPageId` values already identify all ten source
pages. The next TOML schema must add a typed navigation group, order, rail
label, page heading, and icon instead of treating the current `title` value as
all of them.

| Order | C# page ID / TOML ID | Rail group | Rail label | Page heading | Source file | Source icon |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `Home` / `home` | Standalone | Home | Accounts and net worth | `Home.py` | `:material/home:` |
| 2 | `IncomeSavings` / `income_savings` | Analyze | Income and savings | Income and savings | `app_pages/1_Income_and_Savings.py` | `:material/savings:` |
| 3 | `Merchants` / `merchants` | Analyze | Spending by merchant | Spending by merchant | `app_pages/6_Merchant_Analysis.py` | `:material/storefront:` |
| 4 | `Spending` / `spending` | Analyze | Spending by category | Spending by category | `app_pages/2_Spending_by_Category.py` | `:material/category:` |
| 5 | `YearOverYear` / `year_over_year` | Analyze | Year over year | Year over year | `app_pages/3_Year_over_Year.py` | `:material/compare_arrows:` |
| 6 | `Subscriptions` / `subscriptions` | Analyze | Subscriptions | Subscriptions | `app_pages/5_Subscriptions.py` | `:material/subscriptions:` |
| 7 | `TopTransactions` / `top_transactions` | Analyze | Transactions | Transactions | `app_pages/8_Top_Transactions.py` | `:material/receipt_long:` |
| 8 | `Budget` / `budget` | Plan | Budget | Budget | `app_pages/7_Budget.py` | `:material/account_balance_wallet:` |
| 9 | `FinancialIndependence` / `financial_independence` | Plan | Financial independence | Financial independence | `app_pages/9_Financial_Independence.py` | `:material/monitoring:` |
| 10 | `DataHealth` / `data_health` | Maintain | Data health | Data health | `app_pages/10_Data_Health.py` | `:material/health_and_safety:` |

The current `dashboard.toml` page `title` field cannot serve as both the rail
label and the page heading. The source values that differ are:

- `Home` needs rail label `Home` and page heading `Accounts and net worth`.
- `Income and Savings`, `Spending by Category`, and `Year over Year` need
  `Income and savings`, `Spending by category`, and `Year over year`.
- `Merchant Analysis` needs `Spending by merchant`; `Top Transactions` needs
  `Transactions`.
- `Financial Independence` and `Data Health` need `Financial independence`
  and `Data health`.

The current page order also places Spending by category before Spending by
merchant and Transactions after Budget. The source order in the table is the
required order.

### Page Inventory

Each control below states whether it changes report data or only visible page
state. The Phase 3 typed-control work must turn these statements into C# state
fields, validation, report/display mappings, and focused tests.

| Dashboard ID | Key regions in source order | Controls and affected state | Tabs, expanders, and popovers | Roci or local direction |
| --- | --- | --- | --- | --- |
| `home` | Net worth history metrics and chart; What changed chart; account groups; Financial safety cards; global account status. | `Time frame` segmented choice (`3M`, `6M`, `1Y`, `2Y`, `5Y`, `All`) changes the balance-report range. | Each account group has an `Account details (...)` expander. Page links open Data health and FI. | Native `SegmentedControl`, `Collapsible`, charts, and data grid; local metric card and section panel. |
| `income_savings` | Summary metrics; Monthly cash flow chart; selected-month detail; Monthly totals. | `Time frame` and `Calculation` change report data. `Adjust calculation` changes income/expense filters and the savings-rate target. `Month detail` and chart selection change visible detail data. | `Adjust calculation` popover has `Reset defaults`, category/group multi-selects, editable transaction-name lists, two toggles, conditional limits, and `Savings rate target`. Selected-month tabs are `Included (...)` and `Excluded (...)`. `Monthly totals` is an expander. | Native segmented control, number input, toggle, tab panel, collapsible, chart, and grid. Local multi-select is required; use native text input with the local control for editable transaction-name lists. |
| `merchants` | Summary metrics; Where the money went search/ranking/table; selected-merchant metrics and history; selected-merchant details. | `Time frame`, `View`, `Compare with`, and `Adjust view` change report data. `Find a merchant` narrows the ranking. Table row and `Detail month` change selected detail. | `Adjust view` popover has reset, multi-selects, editable transaction-name lists, a toggle, and conditional limit. Detail tabs are `Breakdown`, `Descriptions`, and `Transactions`. | Native segmented control, text input, tab panel, chart, and grid; local multi-select, metric card, and detail panel. |
| `spending` | Summary metrics; Where the money went trend and ranking; overview table; selected-entity metrics, chart, and detail tables. | `Time frame`, `View`, `Compare with`, `Adjust view`, and `Breakdown` change report data. Table row, chart selection, and `Detail month` select detail data. | `Adjust view` popover has the shared spending filters. `Excluded from this view (...)` is an expander. Group detail has `Categories`, `Merchants`, and `Transactions` tabs; category detail has `Merchants` and `Transactions` tabs. | Native segmented control, select/dropdown, tab panel, collapsible, charts, and grid; local multi-select and selected-detail panel. |
| `year_over_year` | One comparison card for each selected preset category, or one selected group/category comparison; metrics, year chart, and detail table. | `View` changes the comparison mode. `Choose categories` changes report inputs for preset views. The group/category select changes report data for a single view. | `Choose categories` is a popover with a `Categories` multi-select. Each comparison has a `Details` expander. | Native segmented control, select/dropdown, popover, collapsible, chart, and grid; local multi-select. |
| `subscriptions` | Summary metrics; Active subscriptions with row detail; Subscription history charts; Potential subscriptions with row detail; Inactive subscriptions with row detail. | `Subscription settings` changes the inventory and discovery report. History `Lookback` and `Timeline scope` change history charts only. Each inventory table row changes the shown merchant detail. | `Subscription settings` is an expander with `Subscription categories`, `Additional discovery exclusions`, and `Minimum discovery confidence`. Merchant detail includes `Monthly totals` and `Individual charges` expanders. | Native slider, segmented control, collapsible, charts, and grid; local multi-select and selected-detail panel. |
| `top_transactions` | Summary metrics; Transactions over time chart; breakdown chart; Matching transactions table. | `Time frame`, `Type`, `Focus`, search, and `More filters` change report data. `Summarize by` changes the breakdown chart. `Download CSV` is an action. | `More filters` popover has group, category, and account multi-selects plus minimum, maximum, and result-count inputs. | Native segmented control, text input, number input, popover, charts, and grid; local multi-select. `Download CSV` is deliberately deferred: later app work needs an export policy and file path. |
| `budget` | Summary metrics; daily pace chart; This month against the plan chart/table; selected-group detail; Year-to-date position. | `Month`, multi-choice `Budget groups` pills, `Adjust view`, selected group, and `Transactions` category select change report or detail data. `Open spreadsheet` is an external-link action when a sheet URL exists. | `Adjust view` popover has multi-selects, editable transaction-name lists, a toggle, and conditional maximum expense. `Year-to-date position` is an expander. | Native select/dropdown, toggle, number input, popover, collapsible, charts, and grid; local multi-select and selected-detail panel. `Open spreadsheet` is deliberately deferred: later app work needs an external-link/browser policy. |
| `financial_independence` | Scenario inputs; summary metrics; Portfolio runway chart; Annual funding chart; Runway sensitivity chart; Source details. | Six scenario number inputs change the FI projection. `Reset to source data` resets scenario state. `Adjust source data` changes source portfolio/spending inputs. | `Adjust source data` popover contains included-account and filter multi-selects, spending-history select, toggle, and conditional maximum expense. `Source details` is an expander with `Accounts`, `Spending`, and `Transactions` tabs. | Native number input, popover, tab panel, collapsible, charts, and grid; local multi-select, metric card, and scenario panel. |
| `data_health` | Summary metrics; Health checks queue; selected-check detail. | `Check settings` changes data-health report inputs. `Inspect check` changes the visible detail only. | `Check settings` popover contains `Stale account threshold` slider, duplicate-detection number inputs, and three toggles. | Native slider, number input, toggle, popover, select/dropdown, and grid; local metric and detail panels only. |

### Current Dashboard And Roci Findings

| Finding | Evidence | Phase direction |
| --- | --- | --- |
| The C# presentation model cannot hold the source navigation mapping. | Completed in Phase 2: `DashboardPageDefinition` and `dashboard.toml` now carry a validated group, order, rail label, heading, and typed icon ID for each page. | Keep page-specific controls separate from this small navigation model. |
| The C# control model cannot express the source controls. | Completed first slice in Phase 3: a finite typed grammar and C# mapping registry now cover select, segmented choice, multi-select, number input, slider, toggle, tab choice, and reset. Home and Income and savings use it in the default TOML. | Add each later source page's real report mapping when that page is rebuilt; do not make display-only placeholders calculate data. |
| The current desktop shell is not the source shell. | Completed in Phases 1 and 2: `PorticoDashboardScene` now uses a dark shell row with a fixed permanent rail and scrolling main body. | Keep new page layout inside the shell; do not reintroduce a top bar or overlay drawer. |
| The current release host cannot make the required captures. | `PorticoDashboardGame` fixes a normal window at 1280 by 820. The test-only `Portico.CaptureHost` now calls the argument-aware host with `GameRunFeatures.Automation | GameRunFeatures.Capture`. | Phase 0 added the capture host without changing normal release-host behaviour. |

### Verified Roci Component Direction

| Source need | Verified Roci support | Decision for this PLC |
| --- | --- | --- |
| Normal rows, columns, wrapping, grow, shrink, alignment, and scroll | `HStack`, `VStack`, flex setters, and scroll support. | Use normal flex composition. |
| Single choice, segmented choice, numeric input, slider, toggle, search text, menu item, and popover | `Dropdown`, `ChoiceGroup<T>`, `SegmentedControl`, `NumberInput`, `Slider`, `ToggleButton`, `TextInput`, `MenuList`, and `Popover`. | Use native controls. |
| Collapsed details and tabs | `Collapsible`, `TabPanel`, and `Tab`. | Use native controls for every source expander and tab set. |
| Tables and charts | `DataGrid`, Cartesian charts, timeline series, heatmap series, hover details, and sparklines. | Use native chart/grid primitives behind local page panels. |
| More than one selected value | There is no `MultiSelect` type or builder in the checked Roci UI source. `ChoiceGroup<T>` stores one selected value. `Checkbox` and `Popover` are available. | Build the required Portico-local multi-select from a popover and checkboxes in Phase 3. |

The source also has editable transaction-name lists through Streamlit
`multiselect(..., accept_new_options=True)`. Roci has `TextInput`, but this
record does not name a second missing Roci component. Phase 3 must prove the
small app-local composition for that source behavior before proposing any
additional component.

### Completion Status

- Complete: source navigation, headings, source files, source control labels,
  page regions, Roci component directions, deterministic current Roci images,
  the test-only capture host, and `roci:visual`.
- Complete: typed source navigation configuration, a selectable grouped rail,
  privacy masking, demo state, and truthful source-check states. The rail uses
  an app-local ASCII glyph mapping because this Roci font path has no Material
  icon primitive.
- Complete: app-local headers, control bars, metric cards, section and state
  panels; typed sections and controls; and the first native tab and composed
  multi-select proof. The multi-select retains state but cannot restore focus
  directly to a checkbox because the current Roci Checkbox API has no focus
  configuration.
- Complete: all ten source pages have typed control/report mappings,
  page-specific calculations, and desktop tests. Budget, Financial
  Independence, and Data Health use source-shaped layouts and controls.
- Complete: the visual catalog has 48 captures. It covers 24 fixed scenarios
  at each required desktop size.
- Deferred: `Download CSV` and `Open spreadsheet`. They are source actions
  outside this visualization and UI experiment. They need explicit export and
  external-link policies before an app implements them.
- The companion Roci worktree adds generic timeline and heatmap charts. The
  Portico app uses them for subscription lifecycle and FI sensitivity views.
  The release CLI keeps its normal startup path.

## Local Component Rule

All first versions live under the Portico app UI folder. Each has a small set
of public builder methods that reads like an existing Roci control: set data,
selection, label, size, style, and event handler through named fluent methods.
The component must not accept a general dictionary of drawing options or make
callers know its internal child tree.

The first confirmed local component is a multi-select. It must support a
label, list of typed items, selected values, clear action, summary text, and a
selection-change event. The navigation rail, metric card, and section panel
start as local compositions too; they are not automatically candidates for
Roci.

## Decision Record To Fill During Phase 0

| Item | Evidence needed | Decision |
| --- | --- | --- |
| Visual test method | A sample capture and one stable comparison run. | Completed: use `GameRunCaptureCatalog` and Roci's capture verifier. Cross-renderer pixel comparisons remain out of scope. |
| Capture host | A test-only host that accepts capture arguments and enables Roci automation/capture. | Completed: `Portico.CaptureHost` accepts normal Roci capture arguments and runs fixed demo sessions. |
| Navigation rail | A local proof with selected page, keyboard focus, and narrow-window behavior. | Completed in Phase 2: exact TOML-backed rail, selected state, pointer/keyboard navigation, focus retention, fixed rail, and 28 visual captures. |
| Multi-select | A local proof used by at least two real page filters. | Complete. Income, Spending, Merchants, Budget, and Financial Independence use it. Keep it in Portico until its focus and keyboard model has a general Roci design. |
| Typed page controls | A table that maps each source control to state, report/display behavior, and a test. | Complete. Every visible source page has its own typed mapping and app test. |
| Any chart gap | A named Streamlit chart and the smallest attempted Roci composition. | Timeline and heatmap now have generic Roci APIs. Horizontal bars are available. Per-category bar fills remain a separate Roci candidate. |
| Page configuration fields | Current TOML types plus one representative page loaded through them. | Completed in Phase 3: validated sections, typed controls, C# mapping routes, and Home/Income configurations. |

### Phase 5.1 Spending Findings

- The source Spending page is feasible with normal Roci flex rows, panels,
  controls, charts, tables, tabs, collapsibles, and a Portico-local
  multi-select. Its controls are TOML-selected but route through typed C#
  settings and state.
- `HorizontalBars()` with a linear X axis and category Y axis expresses the
  source ranking. The first local result was vertical because the app renderer
  set the axes before it declared horizontal bars. This was an app dispatch
  error, not a missing Roci chart feature. A retained-tree test now checks the
  orientation and both axes.
- A one-series ranking cannot give every category its trend color: Roci's bar
  style is currently per series, not per bar value. The local page keeps a
  single teal series rather than creating a chart-specific workaround. This is
  a candidate for an app-first experiment and then a separate Roci proposal.
- The native numeric axis accepts a formatter. The page now sets the source
  axis title, while compact currency ticks such as `$2k` remain an app
  formatting follow-up rather than a Roci API gap.
- Render-only badge content needs an explicit minimum height in retained flex
  layout. The local page uses the existing `SetMinSize` API and a tested gap;
  no new Roci component is needed.
- The local multi-select now has a second real use: Spending group and category
  exclusions. It remains a candidate for final promotion review after more
  pages use it.

### Phase 5.2 Income And Year Over Year Findings

- Income and savings uses a normal Roci Cartesian chart with two bar series and
  one surplus line. Its savings-rate chart uses two line series and a zero
  reference line. The page did not need a new chart component.
- Year over year needs each source year to occupy the same January-to-December
  positions. Mapping each report point to the equivalent month in the year
  2000 lets a normal Roci date axis align the lines and format its labels as
  month names. This is page composition, not a missing Roci API.
- Source Regular defaults only select configured categories and groups that are
  available in the loaded data. The desktop session now applies that rule to
  each Income adjustment control before the page is drawn. This prevents an
  invisible configured value from appearing as a selected filter.
- Per-category bar fills remain the only chart API candidate from Phase 5.1.
  Income uses one color per series, which is already supported.

### Phase 6 And 7 Plan And Data Health Findings

- Budget, Financial Independence, and Data Health use the same source order,
  typed control routes, and retained page state as the Analyze pages.
- Timeline and heatmap charts became generic Roci APIs in the companion
  worktree. Subscriptions uses the timeline. Financial Independence uses the
  heatmap.
- Data Health panels and tables use normal Portico compositions. Retained
  panels use explicit minimum sizes so the flex layout keeps visible space.
- Data Health must compare stale balances with the latest date in the loaded
  sheet, not a fixed capture or display date. Otherwise an old but internally
  consistent demo sheet falsely marks every balance as stale.
- A slider in a bounded popover needs an explicit minimum track length. The
  Data Health settings label also shows its selected day count, so the control
  stays understandable when space is tight.
- The all-page navigation test changes one control on every page, leaves the
  page, and returns. Each changed value remains selected.

### Phase 4 Home Findings

- The six Home choices are report inputs, not display state. Their source day
  counts are 90, 180, 365, 730, and 1,825. `All` starts at the first visible
  balance. A requested start before that balance is clipped to it.
- Home history contains the effective start, every Sunday through the effective
  end, and the end. Each point uses the latest visible balance for each account
  at that date.
- Overall net worth keeps accounts with a blank group. Group cards, What
  changed, and account details omit them because the source does not display a
  blank group.
- Liability cards show debt magnitude and treat a lower debt balance as a
  positive change. What changed keeps the signed net-worth contribution so debt
  paydown remains a positive contribution.
- What changed uses `HorizontalBars()` with a linear X axis and category Y
  axis. The zero guide uses the numeric X axis. The generic renderer now makes
  this axis choice for every horizontal bar chart.

## Phase 0 Exit Check

- The inventory lists all ten current pages and exact source navigation text:
  Home; Income and savings; Spending by merchant; Spending by category; Year
  over year; Subscriptions; Transactions; Budget; Financial independence; and
  Data health.
- Every page has a reference image and a list of its interactive controls.
- The default TOML has a tested mapping for page ID, group/order, navigation
  label, page heading, and icon.
- Every source control has a typed page-state field or action handler,
  validation rule, report input or display action, and focused test.
- Every named layout region maps to a Roci primitive or a documented local
  component proof.
- `task roci:visual` runs named test-only capture cases at 1500 by 1000 and
  1024 by 720, even before the UI changes.
- No Roci code has changed.

### Phase 0 Evidence

`task roci:visual` passed with twenty current-dashboard captures: ten named
page/control states at each required desktop size. The command uses fixed demo
data and a fixed report date. The captured Roci images live under
`artifacts/visual/portico-current` when the command retains output.

The Streamlit screenshots remain manual visual references. They are not image
comparison goldens because a browser and Roci render text and charts
differently. The source inventory supplies the page-by-page comparison list
for later visual phases.
