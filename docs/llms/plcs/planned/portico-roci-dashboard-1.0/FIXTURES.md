# Portico Dashboard in Roci 1.0 Fixture Inventory

## Purpose

This inventory makes calculation correctness the first-class proof. The app is
not accepted because a chart has points or a screen looks plausible. Each finance
fixture has literal inputs and expected outputs. Visual fixtures then prove that
the already-tested result is presented and filtered correctly.

All fixture workbooks are invented data. No real sheet URL, account number,
merchant description, balance, or transaction row is checked in.

## Fixture Rules

- Amounts in source fixture files are decimal strings, not binary floating-point
  literals.
- Finance tests assert decimal values and DateOnly values. The renderer alone
  converts a final value to double for Roci.
- A fixed clock is injected into reports that need today. The standard fixture
  clock is 2026-04-15 unless a case states another date.
- Each sort assertion includes the secondary ordering rule. No result may depend
  on dictionary enumeration.
- Each malformed-row fixture identifies the logical source and row number but
  never copies private source values into a diagnostic snapshot.
- The C# expected values are literal test data. The test suite never runs the
  Python implementation as its oracle.
- Before the corresponding C# code is written, every fixture is checked against
  the current Portico Python tests and source convention. A disagreement updates
  this inventory before code changes land.

## Canonical Synthetic Workbooks

| Fixture | Purpose | Required facts |
| --- | --- | --- |
| minimal-ledger | Smallest complete transaction/balance/category/account set | Income, expense, refund, transfer, two months, an alias, one budget, one asset, one liability |
| calendar-edges | Period and date boundary behaviour | Month start/end, Feb 29, year boundary, missing month, fixed today |
| filter-sets | Named transaction-set and filter behaviour | Includes, excludes, group/category/account/merchant rules, description match, unknown name |
| balance-history | Net worth and account presentation | Multiple accounts, asset/liability signs, hidden account, date gaps, group ties |
| subscriptions | Lifecycle inference and charge history | Active/inactive, observed/inferred interval, one charge, repeat charges, current-date boundary |
| budget | Budget pulse and pace | Under budget, exact budget, over budget, no budget, typical value, daily pace |
| fi | Financial-independence projection and sensitivity | Positive/zero/negative return, spending change, funded/not funded, depletion/no depletion |
| data-health | Input warnings and queues | Missing category, duplicate, reversal, invalid date/amount, unmatched account |
| empty | Defined empty states | No transactions, no balances, no configured widgets removed by a filter |

### Minimal-ledger exact example

The following small case is required as an early C# theory case. It documents
the ordinary signed-cash-flow convention visible in the existing app:

| Date | Type | Group/category | Amount | Included in spending set |
| --- | --- | --- | ---: | --- |
| 2024-01-02 | Income | Salary | 1000.00 | No |
| 2024-01-04 | Expense | Food / Groceries | -250.00 | Yes |
| 2024-01-08 | Expense refund | Food / Groceries | 50.00 | Yes |
| 2024-01-09 | Transfer | Savings move | -500.00 | No |
| 2024-02-29 | Income | Salary | 1200.00 | No |
| 2024-02-29 | Expense | Housing / Rent | -600.00 | Yes |

The January expected result is income 1000.00, signed expense -200.00, displayed
spending 200.00, cash-flow surplus 800.00, and savings rate 80.00 percent. The
transfer does not affect the selected spending report. February proves leap-day
grouping. This fixture is not a replacement for the richer full workbook; it is
a readable calculation smoke case.

## Finance Calculation Matrix

Every ID below represents one or more individual named theory cases with a
literal expected output. The initial implementation must add at least the listed
cases, not collapse a whole row into one happy-path test.

### Classification, filters, and periods

| ID range | Cases | Expected proof |
| --- | --- | --- |
| FIN-CLASS-001 to 006 | Income, expense, transfer, refund, blank type, unsupported type | Correct signed type/group treatment or a clear validation finding |
| FIN-ALIAS-001 to 004 | Exact merchant alias, case/space normalization, no alias, duplicate alias target | Correct canonical merchant and stable original description |
| FIN-SET-001 to 010 | Include/exclude by group, category, account, merchant, transaction text, nested set, conflict, unknown set, empty set, duplicate criteria | Exact included transaction IDs and total |
| FIN-PERIOD-001 to 008 | Inclusive start/end, month start/end, leap day, year change, missing month, today window, lookback zero, invalid reversed range | Exact dates/month keys or explicit validation error |
| FIN-SORT-001 to 004 | Same amount, same date, same merchant, null/blank display field | Stable documented sort order |

### Income, spending, and annual comparisons

| ID range | Cases | Expected proof |
| --- | --- | --- |
| FIN-LEDGER-001 | minimal-ledger January | Income 1000.00; expense -200.00; spending 200.00; surplus 800.00; savings rate 80.00 percent |
| FIN-LEDGER-002 | minimal-ledger February | Leap-day rows belong to 2024-02; income 1200.00; spending 600.00 |
| FIN-LEDGER-003 to 006 | No income, no expense, refund exceeds expense, transfer-only month | Defined rate/value/no-data result; no divide-by-zero or hidden transfer |
| FIN-LEDGER-007 to 010 | Two sources of income, multiple categories, excluded rent, selected transaction set | Exact monthly totals and selected/nonselected totals |
| FIN-SPEND-001 to 006 | Category/group/merchant aggregate, category alias, uncategorized, zero share, tie, selected entity | Exact positive display spend, share, rank, and secondary sort |
| FIN-YOY-001 to 007 | Prior year, current partial year, missing month filled as zero, refund, no prior year, through-month boundary, tied entity | Exact series values, total, change, percentage or no-comparison result |
| FIN-TOP-001 to 005 | Largest expense, positive refund, transfer exclusion, selected category, tie | Correct transaction rows, signed/display amount, and ordering |

### Balances, safety, budget, subscriptions, FI, and health

| ID range | Cases | Expected proof |
| --- | --- | --- |
| FIN-NET-001 to 008 | Asset, liability, group total, hidden account, missing snapshot, date gap, zero balance, equal group totals | Exact signed net worth, group class, history point, and stable order |
| FIN-SAFETY-001 to 006 | Cash above/below target, zero target, no spending baseline, liability present, threshold boundary, missing group | Correct ratio/status/message/no-data state |
| FIN-BUDGET-001 to 010 | Under, exact, over, no budget, zero budget, refund, daily first/last day, leap month, typical value, category tie | Exact actual, remaining, variance, pace, and display status |
| FIN-SUB-001 to 010 | One charge, recurring charges, inferred lifecycle, observed lifecycle, active/inactive at fixed today, interval end boundary, multiple cadence, no history, duplicate merchant, alias | Exact status, first/last charge, interval start/end, charge count and ordering |
| FIN-FI-001 to 012 | Positive return, zero return, negative return, zero spending, funded, unfunded, depletion date, no depletion, annual spending change, return/spending sensitivity row/column, threshold boundary, missing balances | Exact projection point, funding amount, status, depletion value or none, and heatmap cell value |
| FIN-HEALTH-001 to 010 | Missing category, duplicate transaction, cash-flow reversal, invalid source row, missing account, stale balance, empty source, suppressed issue, sort tie, filter focus | Exact finding type, count, row identity, severity, and visible queue order |

The matrix supplies more than 100 named cases once each range is expanded.
Property/invariant tests may add more coverage, but they never replace these
literal expected-output cases.

## Configuration, Source, and CLI Fixtures

### TOML configuration

| ID | Fixture | Coverage |
| --- | --- | --- |
| CFG-001 | current-portico-config | Every supported existing finance section parses into typed records |
| CFG-002 | current-demo-config | Local source configuration loads with no secret file |
| CFG-003 | dashboard-all-pages | Ten ordered pages, configured titles/icons/layouts/widgets/filters |
| CFG-004 | dashboard-reordered-pages | Drawer uses TOML order rather than a hard-coded order |
| CFG-005 | dashboard-hidden-page | Hidden page has no drawer item or route |
| CFG-006 | duplicate-page-id | Fails before app start and names the duplicate ID |
| CFG-007 | duplicate-widget-id | Fails before app start and names page/widget location |
| CFG-008 | unknown-widget-kind | Fails with known-kind guidance |
| CFG-009 | incompatible-widget-bind | Fails when a widget binds a filter it does not support |
| CFG-010 | unknown-filter-kind | Fails before renderer construction |
| CFG-011 | invalid-default | Fails when a selected default is unavailable |
| CFG-012 | unsupported-schema-version | Fails with version and upgrade guidance |
| CFG-013 | legacy-weekly-summary | Loads finance/dashboard settings and reports a single ignored-feature notice |
| CFG-014 | override-precedence | CLI, secrets, config, and defaults merge in the documented order |
| CFG-015 | secret-redaction | URLs do not appear in parser exception, doctor text, or doctor JSON |
| CFG-016 | empty-dashboard | Fails if no visible page remains |
| CFG-017 | invalid-layout-for-widget | Fails before renderer construction |
| CFG-018 | missing-required-sheet-name | Fails safely with logical source name |

### Source adapters

| ID | Fixture | Coverage |
| --- | --- | --- |
| SRC-001 | valid-google-tab-url | Extract document ID and numeric gid; form expected export request |
| SRC-002 | share-url-query-variants | Valid query/fragment variations retain correct gid |
| SRC-003 | missing-document-id | Reject before network call |
| SRC-004 | missing-or-nonnumeric-gid | Reject before network call |
| SRC-005 | non-HTTPS-or-non-Google-host | Reject before network call |
| SRC-006 | all-four-mocked-tabs | Four fake CSV responses normalize to same local snapshot |
| SRC-007 | one-HTTP-failure | No partial first snapshot; safe source failure |
| SRC-008 | malformed-CSV | No snapshot replacement; diagnostic code identifies logical tab |
| SRC-009 | missing-header | Expected schema error without row content leak |
| SRC-010 | invalid-money-or-date | Data-health/source error includes safe row location |
| SRC-011 | duplicate-identity | Normalizer rejects or records the same documented finding as Portico |
| SRC-012 | reload-cancellation | Cancelled result cannot replace newer snapshot |
| SRC-013 | reload-failure-after-success | Prior snapshot remains visible with stale-data notice |
| SRC-014 | local-and-remote-parity | Same report result from local and mocked remote data |

### CLI

| ID | Fixture | Coverage |
| --- | --- | --- |
| CLI-001 | no-command | Defaults to run command |
| CLI-002 | help-and-version | Exit 0; includes AI_CONTEXT help section |
| CLI-003 | local-doctor-text | Exit 0 and safe readable output |
| CLI-004 | local-doctor-json | One valid JSON document on stdout; diagnostics absent or on stderr |
| CLI-005 | invalid-argument | Exit 2 and clear option reason |
| CLI-006 | invalid-config | Exit 2 and safe config diagnostic |
| CLI-007 | bad-source | Exit 3 and logical source reason |
| CLI-008 | sheet-override | Named override wins only for named logical tab |
| CLI-009 | secret-redaction | URL does not occur in stdout/stderr/exception capture |
| CLI-010 | desktop-startup-failure | Exit 4 with safe next step |

## Session, Filter, and Interaction Fixtures

| ID | Fixture | Coverage |
| --- | --- | --- |
| UI-SESSION-001 | first-load-ready | Ready state has first visible page and configured defaults |
| UI-SESSION-002 | first-load-failed | Diagnostic state has no partial report |
| UI-SESSION-003 | reload-success | Whole snapshot revision replaces previous revision |
| UI-SESSION-004 | reload-failure | Prior snapshot remains and is marked stale |
| UI-NAV-001 | open-drawer | Menu intent opens exactly one drawer state |
| UI-NAV-002 | select-page | Selected configured page becomes active and drawer closes on narrow layout |
| UI-NAV-003 | dismiss-drawer | Dismiss leaves active page/filter state unchanged |
| UI-NAV-004 | hidden-page-intent | Invalid/hidden page cannot become active |
| UI-FILTER-001 | period-change | Rebuilds only widgets bound to period |
| UI-FILTER-002 | transaction-set-change | Rebuilds selected spending widgets; leaves unrelated card alone |
| UI-FILTER-003 | selected-month-control | Detail table updates from configured default/control selection |
| UI-FILTER-004 | selected-month-chart-hit | Same state/result as the matching control selection |
| UI-FILTER-005 | reset-default | Restores declared TOML default exactly |
| UI-FILTER-006 | invalid-option | State is unchanged and error is clear |
| UI-FILTER-007 | no-data-filter | Widget emits no-data record, not fake zero chart values |
| UI-RENDER-001 | stable-widget-IDs | TOML widget IDs become stable render/test names |
| UI-RENDER-002 | report-to-chart | Chart values, guides, labels, and categories equal its typed report result |

## Page and Visualization Inventory

Every row below requires a report fixture, one interaction/no-data fixture where
applicable, and wide/narrow visual evidence.

| ID | Page | Visualization or UI result | Required test proof |
| --- | --- | --- | --- |
| PAGE-HOME-001 | Home | Net-worth date history with zero guide/area or line layers | Date values and net-worth totals match report fixture |
| PAGE-HOME-002 | Home | Account/group attribution horizontal bars | Asset/liability signs, labels, and stable rank |
| PAGE-HOME-003 | Home | Account cards with sparklines | Per-account series and no-data card |
| PAGE-HOME-004 | Home | Financial safety metric/progress cards | Threshold status/text and non-colour cue |
| PAGE-INC-001 | Income and Savings | Monthly income/spending bars and cash-flow category line | Shared month identity, totals, zero guide |
| PAGE-INC-002 | Income and Savings | Savings-rate history/target | Rate, target, zero-income behaviour |
| PAGE-INC-003 | Income and Savings | Selected month control and detail view | Control/chart-hit parity |
| PAGE-SPEND-001 | Spending by Category | Monthly multi-series trend | Named transaction-set/filter result |
| PAGE-SPEND-002 | Spending by Category | Ranked category/group horizontal bars | Positive display amount and tie order |
| PAGE-SPEND-003 | Spending by Category | Category/group history bar and comparison line | Shared category labels and selection |
| PAGE-SPEND-004 | Spending by Category | Tables with sparklines | Report values, no-data state, stable rows |
| PAGE-YOY-001 | Year over Year | Annual line/point comparison with zero guide | Missing-month fill and current-year partial window |
| PAGE-SUB-001 | Subscriptions | Active/inactive metric and inventory | Fixed-clock status, sort, no history |
| PAGE-SUB-002 | Subscriptions | Observed/inferred date range timeline | Interval category/start/end and current-date guide |
| PAGE-SUB-003 | Subscriptions | Charge history bars/lines and table | Monthly totals, cadence, alias grouping |
| PAGE-MER-001 | Merchant Analysis | Merchant rank bars | Alias, tie order, selected merchant |
| PAGE-MER-002 | Merchant Analysis | Merchant monthly history/comparison | Month/category identity and selection |
| PAGE-MER-003 | Merchant Analysis | Merchant table/sparklines | Stable rows and empty state |
| PAGE-BUD-001 | Budget | Budget pulse bars with target/typical guide | Actual/budget/typical exact values |
| PAGE-BUD-002 | Budget | Daily actual versus ideal pace lines | Fixed days, leap date, no current-day data |
| PAGE-BUD-003 | Budget | Monthly actual/budget comparison and tables | Month order, variance, configured filters |
| PAGE-TOP-001 | Top Transactions | Date scatter with zero guide | Date/amount identity and transfer exclusion |
| PAGE-TOP-002 | Top Transactions | Category breakdown bars and grid | Selected focus and stable rows |
| PAGE-FI-001 | Financial Independence | Balance projection and depletion point | Fixed clock/projection/depletion result |
| PAGE-FI-002 | Financial Independence | Funding horizontal bars | Required/current/funding gap values |
| PAGE-FI-003 | Financial Independence | Sensitivity heatmap with cell labels | X/Y categories, cell value, color scale, hit |
| PAGE-FI-004 | Financial Independence | Supporting spending cards/bars | Shared finance report result |
| PAGE-HEALTH-001 | Data Health | Summary metric cards | Finding counts/severity |
| PAGE-HEALTH-002 | Data Health | Issue queue and filterable grids | Filter state, safe sort, empty queue |

## Roci Component Fixtures

The following live in the companion Roci branch. Portico consumes them but does
not own their core test coverage.

### Navigation drawer

| ID | Coverage |
| --- | --- |
| ROC-DRAWER-001 | A name-only drawer opens with zero or more items and ends through EndNavigationDrawer |
| ROC-DRAWER-002 | Per-item selected/visible/label state maps to retained drawer state |
| ROC-DRAWER-003 | Open, dismiss, item selection, escape/close route, and click routing are correct |
| ROC-DRAWER-004 | Narrow overlay and wide layout retain correct bounds and content input isolation |
| ROC-DRAWER-005 | Invalid drawer item state fails before mutation |
| ROC-DRAWER-006 | Fluent compiled consumer composes drawer with ordinary layout/style calls |
| ROC-DRAWER-007 | Focused sample capture covers closed, open, selected, and narrow states |

### Category and date chart data

| ID | Coverage |
| --- | --- |
| ROC-COORD-001 | Category connected series accepts owned category values and retains exact identities |
| ROC-COORD-002 | Bar and line peers share ordered categories and use one compatible category axis |
| ROC-COORD-003 | Mismatched/duplicate/blank categories reject atomically with no state change |
| ROC-COORD-004 | Date points retain DateOnly through axis ticks, tooltips, and hit result |
| ROC-COORD-005 | Date guide accepts DateOnly and aligns with date axis |
| ROC-COORD-006 | Numeric/category/date series conflicts reject before mutation |
| ROC-COORD-007 | Input arrays/lists are copied once on ordinary fluent authoring and later caller mutation is isolated |
| ROC-COORD-008 | Existing numeric/category-bar paths keep their prior visual baseline |
| ROC-COORD-009 | Focused samples cover monthly bar/line overlay and date net-worth line |

### Range bars and heatmaps

| ID | Coverage |
| --- | --- |
| ROC-RANGE-001 | Date range has nonblank category and ordered inclusive start/end |
| ROC-RANGE-002 | Range series layout/hit/tooltip retains category and endpoints |
| ROC-RANGE-003 | Observed/inferred peer series retain independent labels/styles and shared axes |
| ROC-RANGE-004 | Invalid range, axis mismatch, or guide conflict fails atomically |
| ROC-RANGE-005 | Focused timeline sample covers range, endpoint, current-date guide, and no-data |
| ROC-HEAT-001 | Heatmap cells retain X category, Y category, value, and optional label |
| ROC-HEAT-002 | Duplicate/blank/misaligned cells fail clearly before mutation |
| ROC-HEAT-003 | Color scale, cell label, tooltip, and hit map to the same cell identity |
| ROC-HEAT-004 | Empty/missing/non-finite values follow documented no-data rendering |
| ROC-HEAT-005 | Focused FI-neutral sample covers two category axes and positive/negative cells |
| ROC-PERF-001 | Static coordinate/range/heatmap inputs are not enumerated or allocated per frame |
| ROC-PERF-002 | Existing chart benchmarks/captures show no unrelated regression |

## Visual Fixture Rules

| ID | Fixture | Required states |
| --- | --- | --- |
| VIS-001 | Home | wide, narrow, drawer open, drawer closed, no data |
| VIS-002 | Income and Savings | default, selected month, changed transaction set, no data |
| VIS-003 | Spending by Category | default, selected category, changed period, no data |
| VIS-004 | Year over Year | normal, partial year, no comparison |
| VIS-005 | Subscriptions | active/inactive mix, range timeline, no subscriptions |
| VIS-006 | Merchant Analysis | default, selected merchant, empty result |
| VIS-007 | Budget | under/exact/over, month edge, empty result |
| VIS-008 | Top Transactions | default, selected focus, empty result |
| VIS-009 | Financial Independence | funded, unfunded/depletion, heatmap |
| VIS-010 | Data Health | findings, filtered queue, clean state |
| VIS-011 | Loading and source errors | first load, stale after reload error, safe diagnostic text |
| VIS-012 | Roci component samples | each new component wide/narrow where applicable |

Captures use fixed window sizes, fixed scale, synthetic data, fixed clock, and
documented skin. A capture mismatch is investigated as a defect; a golden update
is allowed only after a reviewed intended presentation change.

## Suggested Test Homes

| Area | Proposed test project/folder |
| --- | --- |
| Finance calculations | tests/Portico.Finance.Tests |
| Report/filter/config model | tests/Portico.Dashboard.Tests |
| TOML, CSV, source, and CLI | tests/Portico.Adapters.Tests |
| Session/render intent behaviour | tests/Portico.App.Tests |
| Portico visual captures | tests/Portico.Visual.Tests or the established Roci-style capture harness |
| Roci public/core/render/sample components | Existing focused Roci.Ui, Roci.Ui.Rendering, API, and sample test projects |

## Acceptance Gate

Before a phase is accepted:

1. Run the focused Task test command for its fixture IDs.
2. Run task lint and task build:strict.
3. Run the appropriate broad task test command.
4. Run visual evidence when the phase changes a screen or Roci renderer.
5. Run git diff --check.
6. Record the command, result, and any approved visual change in the PLC.

No test only verifies that an exception did not occur. A financial test states
what amount, date, category, status, interval, grid cell, or report row must
result. A UI test states what state and rendered data change. A Roci test states
what component state, geometry, hit, or retained behaviour must result.

