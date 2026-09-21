# Test Plan

## 1. Test Goal

Prove that the UI rebuild shows the right reports, reacts correctly to each
control, keeps finance calculations correct, and remains usable at the two
desktop sizes used for visual checks.

Use fixed local demo data for every automated test. Public Google Sheets URLs
remain covered by adapter tests, but screen and interaction tests must not rely
on a network request.

## 2. Test Levels

| Level | Location | Proves |
| --- | --- | --- |
| Finance unit tests | `tests/Portico.Finance.Tests` | Calculations remain correct for normal, boundary, negative, missing, and varied input data. |
| Dashboard unit tests | `tests/Portico.Dashboard.Tests` | Filter state produces the correct report/view data, values, series, rows, and warnings. |
| Adapter/configuration tests | `tests/Portico.Adapters.Tests` | CSV/sheet parsing and typed TOML validation work without a desktop window. |
| App/component tests | `tests/Portico.App.Tests` | Navigation, local UI state, controls, layout choices, and event wiring work. |
| Visual checks | Existing Roci path or narrow app-local harness chosen in Phase 0 | Page structure, bounds, and key states look like the reference at fixed sizes. |
| Manual check | Short checklist below | Keyboard behavior, readable hierarchy, and cases that cannot be made stable in image comparison. |

## 3. Required Fixtures

Keep the existing synthetic data set. Add small focused fixtures only when a
page needs a clear named edge case.

| Fixture | Needed for |
| --- | --- |
| Normal multi-month household data | All standard page and visual checks. |
| Empty result after a filter | Spending, merchants, transactions, subscriptions, and tables. |
| Single item | Cards, rankings, selected-row detail, and multi-select summary. |
| Many categories/merchants | Filter wrapping, ranking limits, and table scroll. |
| Negative cash flow or over-budget period | Budget, safety, and positive/negative metric styles. |
| Missing/stale/invalid data | Data Health, loading/error panels, and refresh failure. |
| Financial Independence boundaries | Input validation, reset, projections, and sensitivity result changes. |

Do not create a fixture that only makes a screen look good. Every fixture must
also state the value, row count, warning, or action that it proves.

## 4. Behaviour Tests

### Shell And Navigation

- All ten configured pages use the source group/order, label, heading, and icon:
  standalone Home, then Analyze, Plan, and Maintain.
- Selecting each rail item updates the source page heading and selected
  appearance.
- The selected page survives a current-page rebuild and navigation away/back.
- Rail controls remain available while the page body scrolls.
- Hide-values masks amounts in cards, chart labels/tooltips where applicable,
  tables, and details without changing underlying report values.
- Refresh covers loading, success, and failure. A failure leaves navigation and
  the last good page state usable.
- Demo mode shows the demo-data banner above page content. Normal data does not.

### Configuration

- Valid supplied TOML loads every configured page.
- Duplicate page, section, control, and widget keys fail with the named key.
- An unknown page group, control kind, option source, section reference, or
  widget/report pairing fails before a page is shown.
- A control fails configuration validation when it has no typed page state or
  action handler, input validation, or report input/display action. The test
  suite has a focused behavior or report test for every supplied control.
- A supported new section or widget placement is represented by typed settings,
  not an untyped object map.

### Shared Pieces

- Metric cards show a label, formatted value, and correct positive, negative,
  neutral, warning, and hidden states.
- Section panels preserve heading, helper text, action placement, and body
  order.
- The control bar wraps long controls without dropping a reset/clear action.
- Multi-select opens and closes normally, toggles values, clears
  values, summarizes selection, retains state after a page rebuild, and emits
  exactly one typed change event per user action.
- Tabs render and switch correctly on Income and Savings, Spending by Category,
  Spending by Merchant, and Financial Independence. A page retains its selected
  tab only when the source page retains it.
- Empty/error panels expose retry only when a retry callback exists.

### Page Controls And Reports

- Home 3M/6M/1Y/2Y/5Y/All selection changes the expected report range and every
  dependent view together.
- Analyze filters update metrics, charts, rankings, tables, and selected detail
  consistently; changing a filter clears a row selection only when that row no
  longer exists.
- Budget month/group controls and Adjust view update plan, actual, remaining,
  and detailed rows together.
- Financial Independence input changes, source adjustment, reset, and tabs
  produce known report results.
- Data Health settings, warnings, and counts match the synthetic invalid/missing
  fixtures.

### Phase 5.1 Spending Evidence

- The finance tests prove previous-period and last-year month alignment,
  empty/current/comparison-only cases, refunds, named views, merchant aliases,
  stable ranking, independent and combined adjustments, and the expense-limit
  boundary.
- The dashboard tests prove that one change updates Spending metrics, trend,
  ranking, overview, selected detail, and excluded rows together.
- The app tests prove pointer and keyboard use of Time frame, Compare with,
  Adjust view, multi-selects, editable terms, the large-expense setting,
  Reset defaults, selected rows, detail month, hide values, navigation, and
  the source empty state.
- Retained-layout checks cover horizontal bar orientation and axes, source
  regions/order, a compact Adjust button, a readable exclusion badge gap, and
  both required desktop sizes.

### Phase 5.2 Income And Year Over Year Evidence

- Income finance tests cover matched current and previous periods, zero-filled
  months, refunds, category and group exclusions, include and exclude terms,
  large-row boundaries, transfers, empty input, and incomplete prior history.
- Dashboard tests prove that the Income time frame does not change the shared
  lookback, Regular and Actual adjustments remain separate, excluded ledger
  rows remain visible when every current row is excluded, and unavailable
  configured defaults do not appear in a control.
- Year over year finance and dashboard tests cover source coverage months,
  zero fills, signed refunds, transfer removal from comparisons, stable preset
  ranking, raw single-entity choices, missing prior totals, and preset and
  single category or group views.
- App tests cover both desktop sizes, controls, popovers, multi-selects,
  number inputs, reset actions, details, empty states, retained page bounds,
  current-year visual emphasis, and the calendar-month chart axis.
- `task roci:visual` runs 48 named captures. It includes normal and adjusted
  views for the rebuilt Analyze and Plan pages, Data Health settings, and the
  selected loading, failed, unavailable, and hidden-value states at both
  desktop sizes.

### Phase 6 And 7 Plan And Data Health Evidence

- Finance tests cover Budget plan, actual, remaining, adjustment, refund,
  empty, and over-budget cases. They also cover Financial Independence input,
  funding, sensitivity, reset, and source-data cases.
- Budget tests prove that the history window starts at the first observed
  selected-group month. This prevents leading zero months from changing the
  source median and trend.
- Data Health tests cover uncategorized, incomplete, account-mapping, stale,
  duplicate, reversal, hidden-row, and empty-result cases.
- Dashboard tests prove that source-shaped Data Health compares staleness with
  the latest loaded date instead of the capture or display date. App tests
  prove that the settings slider keeps its visible minimum track length.
- App tests cover both desktop sizes, source-data and adjustment popovers,
  retained page state, Data Health settings, selected check detail, and the
  all-page navigation loop.
- The visual catalog has 24 scenarios at each size: Home, Home All, Income,
  adjusted Income, Spending, adjusted Spending, Year over year, one-category
  Year over year, Subscriptions, Subscription settings, Merchants, adjusted
  Merchants, Budget, adjusted Budget, Transactions, More filters, Financial
  Independence, source data, Data Health, Data Health settings, hidden Home,
  loading Spending, failed Budget refresh, and unavailable Data Health refresh.

## 5. Visual Checks

### Fixed Runs

Capture every page at:

- 1500 by 1000: primary desktop reference; this matches the committed Streamlit
  screenshots.
- 1024 by 720: narrow desktop check.

Use a test-only capture host with fixed date/time, local synthetic data, one
skin, and the same font setup for every run. It must enable Roci automation and
capture, accept the normal capture arguments, and report image paths or
comparison results in a predictable form.

### What To Check

| Area | Required evidence |
| --- | --- |
| Shell | Permanent rail, grouped items, selected state, scroll boundary, page padding. |
| Header/control area | Title hierarchy, optional actions, filter position, no clipped controls. |
| Summary rows | Card count/order, readable labels, correct wrapping at narrow width. |
| Charts and tables | Reference order, intended split, chart height, table bounds, no overlap. |
| Details and overlays | Popover anchored to its control, close behavior, no content hidden behind rail. |
| Special states | Hidden values, empty result, warning/error, loading/refresh failure. |

Compare Roci images only with baseline images captured on the same platform.
Use Streamlit screenshots as manual references, not cross-renderer image
baselines. Retained UI-tree or bounds tests must fail on missing main regions,
a rail that disappears, wrong region order, overlap, clipping, or a control
outside the window.

## 6. Manual Desktop Checklist

Run this once after each page phase and once in Phase 8:

1. Start the app with local demo data using the normal CLI.
2. Visit every rail item with mouse and keyboard.
3. Change every visible control and confirm all linked reports update.
4. Open and close every visible detail, popover, expander, and selected-row
   view.
5. Turn hide-values on and off from at least Home, Spending, Budget, and
   Financial Independence.
6. Test a failed refresh and return to a normal page without restarting.
7. Check 1500 by 1000 and 1024 by 720 for horizontal clipping, vertical overlap, and
   unusable focus order.
8. Compare every final page with its Streamlit reference image using the
   discovery inventory, not memory.

## 7. Task Commands

The current commands remain the base. Phase 0 adds `roci:visual` only if it is
not already available.

```text
task roci:restore
task roci:format
task roci:lint
task roci:build:strict
task roci:test:finance
task roci:test:adapters
task roci:test:desktop
task roci:test
task roci:visual
task roci:doctor -- --output json
task roci:run -- --config portico-demo.toml --dashboard dashboard.toml
task roci:publish:win-x64
task roci:publish:linux-x64
```

`roci:visual` first builds the matching configuration and its test/capture
host. It then runs all test-only `Portico.CaptureHost` cases serially with Roci
automation and capture. The command writes 48 PNG files to
`artifacts/visual/portico-current`: 24 fixed scenarios at 1500 by 1000 and
1024 by 720. The scenarios include every normal page plus Home All, hidden
values, adjusted Analyze and Plan pages, settings/source-data popovers, and
loading, failed, and unavailable states. A direct host run accepts normal Roci
arguments such as
`--start-state`, `--scenario`, `--capture-size`, `--capture-frame`, and
`--capture`.

## 8. Phase Proof Matrix

| Phase | Minimum automated proof | Minimum visual/manual proof |
| --- | --- | --- |
| 0 | Test-only capture host, baseline capture command, and focused tests. | All reference/current page images saved at both sizes. |
| 1 | Shell/state tests and strict build. | Rail/main split at both sizes. |
| 2 | Navigation, privacy, and refresh interaction tests. | Selected/focus/loading/failure rail states. |
| 3 | Config, typed-control, local component, and tab tests. | Wrapped control bar and multi-select. |
| 4 | Home report and interaction tests. | Home comparison at both sizes. |
| 5 | Per-page Analyze filter/report tests. | Each Analyze page comparison. |
| 6 | Budget/FI calculation and interaction tests. | Each Plan page comparison plus warning state. |
| 7 | Cross-page state and navigation loop tests. | Data Health and special-state images. |
| 8 | Full command set and diff check. | Final page-by-page comparison and manual checklist. |

## 9. Failure Rules

- A calculation mismatch is a P1: stop page layout work and fix or restore the
  calculation boundary before continuing.
- A broken control, missing page region, privacy leak, crash, overlap, or
  clipped primary control is a P1/P2: fix it in the current phase.
- A small color, spacing, or renderer difference is a P3: fix it when cheap or
  record it with a reference image and a reason.
- Do not bless a failing visual image by replacing the baseline until the cause
  is understood and the discovery record explains the intended change.
