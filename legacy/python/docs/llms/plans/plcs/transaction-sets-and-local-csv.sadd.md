# Transaction sets and spreadsheet sources — design

## Design decisions

### Use transaction sets, not another list registry

The application needs one reusable financial-policy boundary. A separate
registry of Group lists, Category lists, and account lists would add indirection
without removing the real duplication. A transaction set is the named list:
it may contain selectors from several real spreadsheet fields and may compose other
sets.

Direct selectors are a union. This preserves the current spending-view rule and
keeps the model simple:

```toml
[transaction_sets.all]
label = "All spending"

[transaction_sets.utilities]
label = "Utilities"
categories = ["Electric", "Natural Gas", "Internet", "Mobile Phone", "Water & Sewer", "Trash"]

[transaction_sets.non_discretionary]
label = "Non-discretionary"
groups = ["Bills", "Donations", "Health", "Housing", "Insurance", "Maintenance", "Travel"]
categories = ["Automobile Fuel", "Given Gift", "Groceries", "Tax Return Payment"]
transactions_like = ["TAX AGENCY", "CHECK", "MORTGAGE", "VACATION RENTAL"]

[transaction_sets.discretionary]
label = "Discretionary"
includes = ["all"]
excludes = ["non_discretionary"]

[filter_sets.spending]
options = ["all", "discretionary"]
default = "discretionary"

[filter_sets.year_over_year]
options = ["all", "utilities", "discretionary"]
default = "utilities"
```

Each configuration uses the exact values from its selected spreadsheet. The
demo configuration uses the committed synthetic workbook values.
`utilities` is intentionally just a category selector in the example: the
Categories sheet already owns each category's Group and no fuzzy Group/category
intersection is required.

Within one selector, values are alternatives. A transaction belongs to a set
when it matches any direct selector or any referenced `includes` set; matches
from every referenced `excludes` set are removed last. An empty set is useful
for `all` and means every expense row handed to the resolver. This scope does
not add arbitrary `and`, `or`, or regular-expression expressions. A future need
for a true intersection should be expressed by an exact Category rather than a
new query language unless a concrete report requires more.

## Configuration shape

`src/config.py` will replace `SpendingViewSettings`, `SpendingSettings`, and
`YearOverYearSettings` with these frozen settings:

- `TransactionSetSettings`: key, label, direct selectors, included keys, and
  excluded keys.
- `FilterSetSettings`: key, ordered option keys, and default key.
- `TransactionSetSettings` lookup and `FilterSetSettings` lookup methods on the
  root settings object or a small dedicated settings container.
- `DataSettings`: `source` and an optional local directory.
- `Settings.is_demo`: derived only when the selected file is named
  `portico-demo.toml`.

The parser will accept dynamic `[transaction_sets.<key>]` and
`[filter_sets.<key>]` tables. It will reject unknown properties, duplicate
keys/labels/selector entries, invalid identifiers, unknown set references,
invalid filter-set options/defaults, and cycles in the include/exclude graph.
It will remove `[spending]`, `[year_over_year]`, and the subscription regex
property after all consumers have migrated.

Groups, Categories, and Accounts are selected by exact source values. Merchants
are selected after applying `normalize_merchant_name` and the configured alias
map. `transactions_like` calls the current literal, case-insensitive
description matcher. Neither field is named a generic "term" or interpreted as
a regex.

`known_category_terms` should become an exact `known_categories` list while
this configuration surface is being cleaned up. This keeps subscription
categorization data-backed for the same reason as utility membership.

## Runtime flow

```text
Spreadsheet rows
  -> scrubbed Transactions dataframe
  -> selected TransactionSetSettings + merchant aliases
  -> recursive transaction-set mask
  -> page-local adjustment overlay
  -> spending ledger (Included, Exclusion_Reason, Net_Spend)
  -> report aggregation, chart, merchant table, and transaction details
```

Create a small `src/transaction_sets.py` module rather than embedding recursive
logic in Streamlit pages. It will contain pure functions that:

1. Build direct masks for exact Groups, Categories, Accounts, normalized
   Merchants, and `transactions_like` descriptions.
2. Resolve referenced sets with a per-call cache.
3. Return an inclusion mask and enough membership detail for the ledger to
   explain exclusions without changing a report total.

`src/analysis/spending.py` remains the owner of its expense ledger. It will call
the resolver before it applies the existing user-adjustable controls. This makes
the selected configured set the common baseline and makes page-local filters a
narrowing overlay. The ledger is still the single input to spending totals,
merchant tables, and details.

Extend the shared typed filter shape only for fields the resolver genuinely
needs, including exact Accounts and normalized Merchants. Do not create a
generic untyped filter dictionary. Existing income, budget, and FI controls
retain their current independent policy unless they explicitly opt into a
configured transaction set later.

## Report migration

### Spending by Category and Spending by Merchant

- Replace the current `[spending.views]` selector with the configured
  `filter_sets.spending` options.
- Change `render_spending_filters` to receive the selected transaction set and
  preserve the page-local reset/modified-state contract using its stable set
  key.
- Apply the same selected set to current and comparison ledgers, every summary,
  drill-down, and excluded-row badge.
- Pass the one configured alias map to both merchant paths. The merchant table
  must group on the normalized `Merchant` value, while the Transactions tab
  continues to display `Full Description` verbatim.

### Year over Year

- Replace the static Utility/Discretionary presets with
  `filter_sets.year_over_year` choices. Keep single-category and single-group
  exploration as explicit non-preset modes.
- Resolve the selected set before deriving eligible categories, so Utilities,
  Discretionary, and All each use exactly the same calculation pipeline.
- Remove `utility_bill_categories` and `discretionary_categories` special-case
  matching. Derive the ordered category picker from the filtered rows instead.
- Use the selected set for history, totals, and details, not only the initial
  category choice.

### Other merchant consumers

Move alias-map construction out of the page-helper boundary or expose a small
pure helper so all merchant grouping functions can receive it. Propagate it to
subscription inventory/candidates/history/detail lookup as well as the existing
Spending and Top Transactions paths. This prevents a canonical merchant from
splitting differently by report.

## Subscription detection

`detection_excluded_categories` remains an array of exact Categories-sheet
values. Delete `detection_excluded_pattern`, its regex compilation, and the
`str.contains(..., regex=True)` branch. The demo profile supplies synthetic
category names where needed.

## Spreadsheet sources and demo configuration

Use a discriminated source configuration in the one complete normal file:

```toml
[data]
source = "remote"
directory = ""
```

The separate complete demo configuration uses local files:

```toml
[data]
source = "local"
directory = "demo/data"
```

The local directory is valid only for `local`. Resolve a relative directory
against the TOML file that defines it; accept an absolute path for a deliberate
container bind mount. A source reads `categories.csv`, `accounts.csv`,
`transactions.csv`, and `balance_history.csv` using the same spreadsheet
classes and scrubbers as the remote connection. Reports use the latest date in
the loaded data, which keeps both local and remote sources on the same rule.

`config.toml` is the normal configuration and users edit or mount it directly.
`portico-demo.toml` is a complete file for synthetic data. Demo entry points
explicitly set `PORTICO_CONFIG_PATH` to it. Remove `PORTICO_DATA_SOURCE` from
code, Task, Docker commands, smoke tests, and documentation. Do not merge
configuration files. When needed, mount a local data directory separately from
the single `config.toml` file.

The Docker image and browser-demo archive must include `portico-demo.toml`. The
browser entrypoint selects it before loading the normal application. The demo
banner is inferred from that exact file name, so ordinary local CSV users do not
see a synthetic-data warning.

## Cash-flow chart alignment

`create_cash_flow_history_chart` will add one month-start temporal column and
use it for every bar, line, point selection, selected-month rule, and x axis.
The visible axis uses a month/year formatter; the upper panel hides that same
axis. The vconcat retains a shared x scale and aligned bounds. This avoids two
ordinal label scales with independently sized panels, which caused upper marks
to visually drift from the lower labels.

## File-level delivery plan

1. `config.toml`, `portico-demo.toml`, and `src/config.py`
   - Migrate source and policy schema; add typed parsing and graph validation.
2. New `src/transaction_sets.py`, `src/custom_types.py`,
   `src/transaction_filters.py`, `src/analysis/spending.py`, and `src/filters.py`
   - Add pure resolution and wire it into typed ledgers and adjustable controls.
3. `pages/2_Spending_by_Category.py`, `pages/3_Year_over_Year.py`, and
   `pages/6_Merchant_Analysis.py`
   - Adopt configured filter sets and remove the utility special case.
4. `src/analysis/subscriptions.py`, `pages/5_Subscriptions.py`,
   `src/analysis/merchants.py`, and `src/page_helpers.py`
   - Remove regex matching and use one merchant alias path.
5. `src/spreadsheet.py`, `src/reporting_periods.py`, `scripts/doctor.py`,
   `Taskfile.yml`, `Dockerfile`, `scripts/smoke_container.py`,
   `demo/pages/entry.py`, and `scripts/build_pages_demo.py`
   - Implement local CSV/profile selection and package it.
6. `pages/1_Income_and_Savings.py`
   - Use one temporal month scale for the two chart panels.
7. `README.md`, `.env.example`, `docs/architecture.md`, demo-data guidance, and
   affected unit/integration/AppTest files
   - Document the surface and lock behavior with regressions.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Normal and synthetic names differ. | Keep full normal and demo configurations; test both. |
| A composed set changes a total silently. | Test row identities and reconciled totals for `all`, `utilities`, and `discretionary`. |
| Alias logic diverges again. | Require all grouping call sites to accept the same alias map and add cross-report fixtures. |
| A local CSV snapshot has an old date. | Use the latest date in the loaded data for every source. |
| Configuration becomes a query language. | Limit it to direct union selectors plus named include/exclude composition. |

## Deferred work

- A user-editable Categories-sheet report-tag column.
- Regex or fuzzy matching beyond explicit literal transaction descriptions.
- Arbitrary boolean predicates or source plugins.
- Adding configured transaction-set menus to reports that do not currently have
  a spending-view concept.

## Requirements traceability

| Requirements | Design section | Test coverage |
| --- | --- | --- |
| TS-1 through TS-4 | Configuration shape; Runtime flow | Config and transaction-set unit tests |
| TS-5 through TS-7 | Runtime flow; Report migration | Ledger, integration, and Streamlit AppTests |
| SUB-1 | Subscription detection | Subscription-analysis unit tests |
| MER-1 | Report migration; Other merchant consumers | Cross-report merchant alias tests |
| DATA-1 through DATA-3 | Local CSV source and demo profile | Source, doctor, archive, and container tests |
| CHART-1 | Cash-flow chart alignment | Chart-spec regression test |
