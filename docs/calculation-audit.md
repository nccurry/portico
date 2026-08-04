# Financial calculation audit

This catalog records the formulas used by the application, their input rules,
and the tests that independently verify them. The audit uses only the committed,
anonymized fixtures under `tests/data/fixtures`; it does not read live sheets.

## Conventions

- Tiller income amounts are positive and expense amounts are negative.
- Spending is displayed as a positive magnitude after selecting expense rows.
- Transfers and hidden rows are excluded where the page filter specifies them.
- Monthly windows are inclusive. Income/Savings and FI exclude the incomplete
  current month; Budget deliberately reports and projects the selected month.
- Calculations retain full floating-point precision. Currency is rendered to
  cents or whole dollars as indicated by each metric, and rates are rendered to
  one decimal place.

## Calculation catalog

| Page/domain | Displayed calculation | Formula and data rules | Verification | Result |
|---|---|---|---|---|
| Home | Group balance | Latest `(Date, Time)` row per visible account, summed by group | Net-worth unit tests, fixture pattern tests, AppTest values | Correct |
| Home | Total net worth | Latest asset balances minus latest liability balances | Independent signed latest-balance fixture oracle and AppTest value | Correct |
| Income/Savings | Monthly income and expense | Sum signed `Amount` by `Month` and `Type` after filters | Hand-calculated unit cases and aggregation conservation tests | Correct |
| Income/Savings | Monthly savings | `Income + Expense` because expenses are negative | Per-month identity tests and AppTest values | Correct |
| Income/Savings | Monthly savings rate | `Savings / abs(Income) * 100`; zero when income is at most one cent | Boundary and outlier unit tests | Correct |
| Income/Savings | Average monthly rate | Arithmetic mean of monthly savings rates | Independent multi-month examples and AppTest values | Correct |
| Income/Savings | Overall rate | `sum(Savings) / sum(abs(Income)) * 100` | Weighted-rate examples and AppTest values | Correct |
| Income/Savings | Filtered amount | Gross excluded income plus gross excluded expenses | Independent summary example | **Fixed**: previously used `abs(net amount)`, which understated mixed excluded income and expenses |
| Spending | Category total | Absolute value of summed expense amounts by category | Raw-to-category conservation test and AppTest values | Correct |
| Spending | Category percentage | `Category spending / total spending * 100` | Percentage-sum invariant | Correct |
| Spending | Percentiles and mean | Pandas quantiles and mean of absolute expense amounts | Hand-calculated distributions and boundary cases | Correct |
| Spending | Size buckets | `<25`, `25 <= amount < 250`, and `>=250`; dollar and count shares use their respective totals | Partition/count/share invariants and AppTest values | Correct |
| Spending | Pareto share | Smallest descending transaction prefix reaching at least 80% of spending, divided by transaction count | Hand-calculated concentration and exact-boundary examples | **Fixed**: an exact 80% first transaction previously counted one additional transaction |
| Spending | Histogram buckets | Absolute amounts grouped through `$5K+`, with no upper limit | Bucket conservation and high-value regression tests | **Fixed**: values above $100,000 were previously omitted from the chart |
| Year over Year | Monthly comparison | Absolute monthly category/group totals pivoted by calendar year | Spreadsheet aggregation tests and fixture-backed table totals | Correct |
| Duplicates | Potential pairs | Equal signed amount, within day threshold, with optional account/category/normalized-description equality; self-pairs and mirrored pairs removed | Boundary, filter, and `n choose 2` tests | Correct |
| Duplicates | Total and affected months | Sum absolute amount once per flagged pair; distinct pair months | Independent summary and AppTest table/metric values | Correct |
| Subscriptions | Cadence | Average first-to-last interval classified as monthly, quarterly, annual, or irregular | Cadence boundary and detection tests | Correct |
| Subscriptions | Monthly cost | Median charge, divided by 3 for quarterly or 12 for annual cadence | Hand-calculated cadence examples | Correct |
| Subscriptions | Annual and average cost | `Monthly cost * 12`; total monthly cost divided by detected count | Independent summary identity and AppTest values | Correct |
| Subscriptions | Charge timeline | First/last matching expense date for the normalized merchant and amount band | Expense/refund regression and fixture-backed AppTest | **Fixed**: same-amount income/refund rows can no longer extend a subscription timeline |
| Merchants | Merchant statistics | Expense-only sum, mean, count, first/last date, and modal category/account by normalized merchant | Merchant unit tests and independent summary/timeline examples | Correct |
| Merchants | Headline total and average | Sum qualifying merchant totals; divide by qualifying merchant count | Independent summary example and AppTest values | Correct |
| Budget | Monthly/YTD spent | Absolute expense sums by category after selected filters; YTD spans January through selected month | Monthly/YTD unit tests and fixture patterns | Correct |
| Budget | Remaining and utilization | `Budget - Spent`; `Spent / Budget * 100`, with infinity for unbudgeted spending in detail rows | Zero-budget and exact-boundary tests | Correct |
| Budget | Projection | `Spent / days elapsed * days in month`; zero before any elapsed day | Hand-calculated month-length tests and category projection tests | Correct |
| Top Transactions | Top-N share | Stable descending absolute expenses; `sum(top N) / sum(all period expenses) * 100` | Tie, empty, date-window, and AppTest scenario tests | Correct |
| Financial Independence | Average monthly spending | Mean of positive monthly expense totals across months containing expenses in the completed-month window | Independent direct-groupby fixture oracle | Correct |
| Financial Independence | Annual return and coverage | `Portfolio * rate`; `(return + supplemental income) / total spending` | Closed-form examples and AppTest values | Correct |
| Financial Independence | Runway | Closed-form depletion time for `B(n+1)=B(n)*(1+r)-net withdrawal`, with zero/infinite boundary handling | Closed-form and recurrence tests | Correct |
| Financial Independence | Projection | Apply the yearly recurrence and clamp depleted balances to zero | Per-year invariant tests | Correct |
| Data Health | Issue counts | Counts of independently classified schema, sign, account, age, and budget issues | Data-health unit tests and AppTest values | Correct |

## Confidence gates

- Pure calculations are tested with expected values written independently of
  the production implementation.
- Cross-domain fixture tests verify conservation and algebraic identities.
- Streamlit AppTest verifies exact rendered metrics and representative changed
  inputs without accessing the network.
- Both source-only and combined CI coverage run with branch coverage enabled.

Passing tests substantially increases confidence but cannot prove correctness
for every possible future input. Any formula change must update this catalog and
add an expected-value case that would fail under the previous behavior.
