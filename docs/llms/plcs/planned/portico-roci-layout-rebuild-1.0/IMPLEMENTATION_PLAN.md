# Implementation Plan

## Working Rules

- Work only in `../portico-roci-rebuild` on `nccurry/roci-portico-plc`.
- Do not change `../roci-portico-components` during these phases.
- Keep each phase reviewable on its own. Finish its checks before beginning the
  next phase.
- Add or update tests in the same phase as the behaviour they protect.
- Use the existing Taskfile commands. Add only the smallest new Task command
  required for repeatable visual checks.

## Phase 0: Discover And Set A Baseline

### Work

1. Read every Streamlit page module, the current Roci scene, `dashboard.toml`,
   Roci layout/control/overlay APIs, and the Roci visual-test examples.
2. Produce the completed inventory described in [DISCOVERY.md](DISCOVERY.md).
3. Capture every current Streamlit and Roci page at 1500 by 1000 and 1024 by
   720 using fixed demo data.
4. Add a test-only capture host because the current release host does not
   accept Roci capture arguments or enable Roci automation/capture. The host
   must create deterministic demo sessions, select named page/control states,
   accept normal Roci capture arguments, and run capture cases serially through
   `roci:visual`.
5. Write the exact source-to-TOML navigation table: page ID, source file,
   group/order, navigation label, page heading, and icon.
6. Write a control map. Each source control must name its C# state field or
   action handler, validation, report input or display action, and test.
7. Make a short component decision record: compose existing Roci controls,
   build a local Portico component, or defer the question. Do not change Roci.

### Deliverable

A factual UI inventory, baseline images, an updated discovery record, and a
repeatable visual command that runs against the current app.

### Checks

- The discovery exit check passes.
- `task roci:visual` produces useful baseline evidence.
- `task roci:test:desktop` passes.

### Exit

Every required page and control is known, every major UI region has a planned
Roci mapping, and the team knows exactly which local component proofs Phase 3
must build.

## Phase 1: Build The Skin And Flex Foundation

### Work

1. Add the Portico dark skin and named styles listed in the SADD.
2. Replace the current light, generic root arrangement with the shell flex
   tree, using temporary placeholder content where a later section is not yet
   built.
3. Set rail width, main-content growth, page padding, section gaps, panel
   surfaces, readable type sizes, and intentional chart heights.
4. Add a narrow-desktop layout rule for card and chart rows.
5. Remove direct page-builder colors and spacing that the skin replaces.

### Deliverable

A dark, correctly sized shell that can show placeholder page regions without
clipping, overlap, or accidental absolute positioning.

### Checks

- Unit tests cover the shell layout state and named style selection.
- Visual captures at 1500 by 1000 and 1024 by 720 show the rail, main area,
  scroll boundary, and a wrapped content row.
- `task roci:format`, `task roci:lint`, `task roci:build:strict`, and the
  focused desktop tests pass.

### Exit

The app has a stable dark base. Future pages can use named styles and normal
stacks without needing to decide global layout again.

## Phase 2: Add The Navigation Rail And Global State

### Work

1. Build the local navigation rail from Roci layout and standard controls.
2. Show Home as a standalone item, then Analyze, Plan, and Maintain groups in
   the exact source order. Use the source navigation labels and icons, not the
   current near-match labels.
3. Bind page selection, hide-values, data-load status, and refresh to the app
   state.
4. Keep the rail visible while the main page scrolls.
5. Implement safe loading, failed-refresh, unavailable-data, and demo-data
   banner states. Do not reproduce Streamlit's Deploy/menu chrome.

### Deliverable

A usable permanent left rail that switches existing pages and displays the
global actions and status.

### Checks

- Interaction tests select every configured page and assert the selected item
  and visible title.
- Tests prove hide-values changes display formatting without changing report
  values.
- Tests cover refresh success and failure while a page remains selectable.
- Visual captures show selected, focused, and disabled/load states.

### Exit

The shell behaves like a real application frame. No page needs its own
navigation or global privacy logic.

## Phase 3: Add Shared Pieces And Typed Page Layout Settings

### Work

1. Add local page header, control bar, metric card, section panel, and
   empty/error panel pieces.
2. Implement the local multi-select from existing Roci popover and checkbox
   controls. Give it focused behavior tests now; use it in at least two real
   source filters during Phase 5.
3. Give all local pieces small fluent builders that match nearby Roci naming
   and event patterns.
4. Add the fixed set of typed controls: single select, segmented choice,
   multi-select, number input, slider, toggle, tab choice, and action/reset.
   Give every controlled page its own typed state record. Add a typed report
   request where the control changes data, and a C# mapping for validation and
   display-only or action behavior.
5. Extend `dashboard.toml` with known navigation groups, separate rail labels and
   page headings, icons from a fixed C# list, sections, supported controls, and
   display choices. TOML selects a known control; it cannot define a formula.
6. Validate TOML references and C# mappings before the first page tries to
   draw. Reject a control without page state or an action handler, validation,
   and a report input or display action. Add a focused report or interaction
   test for every configured control.
7. Use existing Roci `TabPanel` and `Tab` controls for source tabs. Do not make
   a local tab widget.
8. Refactor the current generic scene path so pages can use a common builder
   sequence without hiding report-specific layout in a large switch statement.

### Deliverable

A tested local UI kit and typed configuration path that supports the first
reference page without custom low-level panel trees.

### Checks

- Component tests cover selection, clear, popover dismissal, and retained
  state for multi-select.
- Component tests cover selected navigation state, metric positive/negative/
  warning/hidden state, and section header/action placement.
- TOML tests reject duplicate keys, invalid control kinds, invalid section
  references, unsupported option sources, unknown navigation labels/icons, and
  a control that has no typed page-state/report mapping.
- Tests cover each supported control kind and selected-tab retention where a
  source page has tabs.
- Visual capture shows a filter/control row with long values wrapping cleanly.

### Exit

Each new shared piece has a working use and focused tests. By the end of Phase
5, every shared piece intended for reuse appears on at least two source pages.
The page code can request an ordinary card, section, or control bar without
knowing its child layout.

## Phase 4: Rebuild Home

### Work

1. Rebuild the "Accounts and net worth" heading and its 3M/6M/1Y/2Y/5Y/All
   time control from the new shell and control bar.
2. Build the net-worth view with its metric band and reference chart treatment.
3. Add safety cards, account group sections, inventory rows, and the detail
   treatment shown in the Streamlit reference.
4. Wire all Home filters and details to the existing typed report data.
5. Fix shared pieces only when Home proves a real repeated need; do not add
   Home-only policy to a shared component.

### Deliverable

A full Home page that is the reference implementation for the rest of the
desktop rebuild.

### Checks

- Report tests prove each time-control value selects the expected date range.
- Interaction tests cover time changes, hidden values, detail opening, and
  navigation away/back.
- Visual captures compare Home at both desktop sizes against the Phase 0
  reference checklist.
- Finance tests pass without change to finance rules.

### Exit

Home has the same main reading order and control placement as Streamlit. The
team can name which parts are reusable before the Analyze pages begin.

## Phase 5: Rebuild Analyze Pages

### Phase 5.1: Spending By Category

Build Spending by Category with its time, view, comparison, breakdown, and
Adjust view controls; metric deck; category/time chart; ranking; table; and
selected detail. Use the multi-select with a real data set where the source
needs it.

Exit: Spending by Category matches its reference regions and filter changes
update every related metric, chart, and row set together.

### Phase 5.2: Income And Year Over Year

Build Income and Savings, then Year over Year. Reuse the control bar, metric
cards, chart panels, and comparison tables. Use the tabs on Income and Savings
and the Choose categories popover and Details expander on Year over Year. Keep
period comparison rules in the dashboard layer.

Exit: Both pages work at fixed desktop sizes, preserve their own filter state,
and have visual evidence for the reference layout.

### Phase 5.3: Subscriptions, Spending By Merchant, And Transactions

Build Subscriptions, Spending by Merchant, and Transactions from the same
shared pieces, adding only a local view piece when at least two of these pages
need it. Include the Subscription settings expander, Spending by Merchant
Adjust view popover, Transactions More filters popover, required multi-selects,
ranking or table detail, and page controls.

Exit: All six Analyze pages work through the permanent rail, have no copied
control-bar implementation, and pass focused report, interaction, and visual
checks.

### Checks For All Analyze Work

- Test each filter independently and in combination where the page supports
  combinations.
- Test no-result, one-result, and many-result fixtures.
- Test selection/detail state after a filter changes or selected row disappears.
- Capture every page at 1500 by 1000 and 1024 by 720.
- Run `task roci:test:desktop` and `task roci:visual` after each sub-phase.

## Phase 6: Rebuild Plan Pages

### Phase 6.1: Budget

Build month and group controls, Adjust view popover, summary values,
plan-versus-actual display, dense budget detail, and the Year-to-date position
expander. Use a bounded table/panel layout so the page stays readable with many
budget rows.

Exit: Month/group changes update all Budget content, and the table can show
empty, partial, and over-budget states clearly.

### Phase 6.2: Financial Independence

Build the editable scenario inputs, Adjust source data popover, reset action,
metric cards, projection, funding view, sensitivity view, and Source details
expander with tabs. Keep every calculation in the existing typed
finance/dashboard layer.

Exit: Each scenario input, reset, and sensitivity choice has an interaction
test with known expected results. The page keeps the reference reading order at
both desktop sizes.

### Checks For Both Plan Pages

- Finance fixtures cover normal, boundary, negative, and missing-data cases
  used by the display.
- Interaction tests cover input validation and reset behavior.
- Visual captures cover normal and warning/empty states.
- Run the focused finance, dashboard, desktop, and visual commands.

## Phase 7: Rebuild Data Health And Finish Cross-Page States

### Work

1. Rebuild Data Health with its Check settings popover, summary, warnings,
   counts, and details from the reference.
2. Make loading, stale, empty, invalid, hidden-value, and refresh-failure
   states use the shared status pieces across every page.
3. Check page-control/tab state retention, focus movement, keyboard navigation,
   chart/table labels, and narrow-desktop wrapping across all pages.
4. Remove superseded generic layout code and duplicate page styling as each
   replacement is covered by tests.

### Deliverable

All ten pages use the same shell, configuration path, and shared state rules.

### Checks

- Tests cover every shared data state on at least one chart page and one table
  page.
- A navigation loop test visits all pages, changes a control where present, and
  returns to verify retained state.
- Full visual capture run covers all pages and the named special states.
- Run the full existing test suite.

### Exit

No page uses the old generic top bar or a one-off fallback for routine data
states. There are no known overflow, overlap, or focus traps at the two desktop
sizes.

## Phase 8: Prove The Result And Decide Future Roci Work

### Work

1. Run all formatting, lint, strict build, unit, interaction, visual, and
   publish checks that apply to the app.
2. Compare the final captures with the Streamlit captures page by page. Record
   intentional renderer differences and remaining defects.
3. Audit the changed code for repeated styling, copied layout, inaccessible
   controls, and configuration that bypasses typed validation.
4. Write the local-component review from SADD section 11.
5. Keep the Roci worktree untouched. If a component is worth moving later,
   write a short separate proposal instead of starting the port here.

### Deliverable

A fully tested Portico rebuild, visual evidence, and a plain decision list for
future Roci work.

### Checks

- `task roci:format`
- `task roci:lint`
- `task roci:build:strict`
- `task roci:test`
- `task roci:visual`
- `task roci:publish:win-x64`
- `task roci:publish:linux-x64` when the host/toolchain supports it
- `git diff --check`

### Exit

All required checks pass, every known P1/P2 issue is fixed, and the packet has
evidence for the page-by-page comparison and the local-component decision.
