# Session Notes - November 8, 2025

## Summary
Built a comprehensive Tiller Streamlit financial dashboard with year-over-year comparisons, savings rate tracking, and optimized performance through caching.

---

## Initial Setup & Bug Fixes

### PyCharm Configuration
- **Issue:** System Python trying to run venv's streamlit.exe
- **Fix:** Configure PyCharm to use `.venv\Scripts\python.exe` as interpreter
- **Run config:** Module: `streamlit`, Parameters: `run Home.py`

### Data Loading Issues
1. **Spreadsheet URLs:** Changed from environment variables to Streamlit secrets (`secrets.toml`)
2. **Connection names:** Updated to match class names (`transactions_spreadsheet`, `balance_history_spreadsheet`)
3. **Removed redundant URL parameters:** Connections already know URLs from secrets

### Type Hint Errors
- **Problem:** `Optional[datetime]` used `datetime` module instead of class
- **Fix:** Changed to `Optional[datetime.datetime]` in 5 locations

### Date Parsing Issues
1. **Mixed formats:** Added `format='mixed'` to `pd.to_datetime()` calls
2. **Mixed timezones:** Added `utc=True` to handle timezone offsets
3. **Groupby errors:** Added `numeric_only=True` to prevent summing datetime columns

---

## Performance Optimizations

### Caching Implementation
```python
@st.cache_resource(ttl=300)  # For class instances
def load_transactions_data():
    return TransactionsSpreadsheet()

@st.cache_resource(ttl=300)
def load_balance_history_data():
    return BalanceHistorySpreadsheet()
```

**Impact:**
- First load: 5-10 seconds (Google Sheets download)
- Subsequent loads: <1 second (cached)
- Data shared across all pages

### Sparkline Optimizations
- **Problem:** 570+ dataframe scans per page load (nested loops)
- **Fix 1:** Sample weekly instead of every snapshot date (52 points vs 300+)
- **Fix 2:** Created cached helper functions:
  - `calculate_net_worth_sparkline()`
  - `calculate_group_sparkline()`

**Result:** Home page loads much faster after first visit

---

## Pages Created

### 1. Home Page (Enhanced)
**Features:**
- Total net worth metric
- Net worth sparkline (last 12 months, gold line)
- Account groups in 3-column grid
- Each group shows:
  - Balance metric
  - Sparkline (green for assets, red for liabilities)
  - Expandable account details table
- Proper Asset/Liability calculation using Class field

### 2. Year over Year (Consolidated)
**Merged:** Bills, Food, Discretionary into one page with tabs
**Features:**
- Bills tab: 6 bill categories
- Food tab: Groceries, Restaurants/Bars
- Discretionary tab: Shopping, Travel, Entertainment (by group)
- Year-over-year line charts (current year green, previous years gray)
- Trims leading/trailing zeros, keeps middle gaps
- Pivoted data tables
- Expandable transaction details

**Helper module:** `src/page_helpers.py` with reusable functions

### 3. Savings Rate (Merged with Income vs Expense)
**Page title:** "Income, Expenses & Savings"

**Metrics (5 columns):**
- Latest Month %
- Avg Savings Rate %
- Avg $ Saved/Month
- Saved (Latest)
- vs Last Month

**Two Charts (Stacked Vertically):**
1. **Savings Rate %** (top)
   - Green line (actual rate)
   - Light gray line (0% break-even)
   - Gold dashed line (configurable target %)
   
2. **Income vs Expenses $** (bottom)
   - Green bars (income)
   - Red bars (expenses)
   - Gold line (net cash flow)
   - No legend (colors self-explanatory)

**Filters:**
- Exclude Groups: Transfer, Travel (default)
- Exclude Categories: Tax Return Payment, Given Gift, Christmas, 401k (default)
- Filter Large Expenses: Checkbox + $3,000 threshold on All Categories
- Savings Rate Target: Configurable (default 20%)

**Tables:**
- Monthly Savings Data (summary)
- Large Transactions (>$500, adjustable slider)
- All Included Transactions (full list)

**Data Quality:**
- Excludes current incomplete month
- Filters from 2024-01 onwards (bad 2022-2023 data excluded)
- Excludes Transfer group (money movements)
- Excludes miscategorized categories (401k realized gains, etc.)

### 4. Top Expenses
**Features:**
- Current month vs previous month comparison
- Horizontal bar chart (top 10 categories)
- Metrics: Highest category, total expenses, biggest increase
- Full category table with $ and % change

### 5. Spending by Category
**Features:**
- Time period selector (This Month, Last 3 Months, etc.)
- Pie chart (spending distribution)
- Top 10 bar chart
- Group breakdown metrics
- Full category table with percentages

---

## Key Data Issues Discovered & Fixed

### Google Sheets Formula Fixes
**Problem:** `$D$2:D` notation doesn't work with ARRAYFORMULA

**Fixed formulas for Transactions sheet:**
```excel
={"Group";
   ARRAYFORMULA(
      IF(D2:D="", "",
         IFERROR(VLOOKUP(D2:D, Categories!$A$2:$B, 2, FALSE), "Uncategorized")
      )
   )
}
```

**Fixed formulas for Balance History sheet:**
```excel
={"Group";
   ARRAYFORMULA(
      IF(D2:D="", "",
         IFERROR(
            VLOOKUP(D2:D & " - " & E2:E & " (" & UPPER(RIGHT(F2:F, 4)) & ")", Accounts!$A$2:$C, 3, FALSE),
            ""
         )
      )
   )
}
```

Applied same fix to: Type, Hide From Reports columns

### Miscategorized Data Found
- **494 Transfer transactions** with wrong Group
- **RSU/ESPP** transactions miscategorized
- **401k realized gains** ($25k) counted as income (should be Transfer/Investment)

### Savings Rate Calculation Issues
**Problem 1:** Original logic used pivot that didn't handle Type grouping correctly  
**Problem 2:** `.abs()` applied incorrectly, breaking sign logic  
**Problem 3:** Large expense filter was also filtering income  

**Fixed logic:**
```python
# Keep original signs
df_pivot['Savings'] = df_pivot['Income'] + df_pivot['Expense']  # Expense is negative
df_pivot['Income_Display'] = df_pivot['Income'].abs()
df_pivot['Expense_Display'] = df_pivot['Expense'].abs()
df_pivot['Savings_Rate'] = (Savings / Income_Display * 100)
```

---

## Chart Alignment Solutions

### Problem
Two stacked charts (Savings Rate % and Income vs Expenses $) were misaligned due to:
- Different Y-axis label widths
- Legend on one chart but not the other

### Solution
```python
# Shared X-axis
x_axis = alt.X('Month:O', axis=alt.Axis(labelAngle=-45, title='Month'), sort=None)

# Shared Y-axis config
y_axis_config = {'labelLimit': 100, 'labelPadding': 5}

# Both charts use same settings
y=alt.Y('...', axis=alt.Axis(title='...', **y_axis_config))
```

---

## Deprecation Warnings Fixed

### Streamlit API Updates
- `use_container_width=True` → `width='stretch'`
- `GridUpdateMode.SELECTION_CHANGED` → `update_on=['selectionChanged']`

### Pandas Future Warnings
- Added `utc=True` to all `pd.to_datetime()` calls
- Added `numeric_only=True` to `.sum()` operations

---

## File Structure

### Created
- `Pages/Savings_Rate.py` (merged Income vs Expense into this)
- `Pages/Year_over_Year.py` (consolidated Bills, Food, Discretionary)
- `Pages/Top_Expenses.py`
- `Pages/Spending_by_Category.py`
- `src/page_helpers.py` (shared YoY comparison logic)

### Deleted
- `Pages/Bills.py` (merged into Year_over_Year)
- `Pages/Food.py` (merged into Year_over_Year)
- `Pages/Discretionary.py` (merged into Year_over_Year)
- `Pages/Income_vs_Expense.py` (merged into Savings_Rate)
- `Pages/Cash_Flow_Heatmap.py` (not useful)

### Modified
- `Home.py` - Added net worth dashboard with sparklines
- `src/spreadsheet.py` - Added helper methods, caching functions
- `requirements.txt` - Added/removed dependencies
- `README.md` - Documented Google Sheets formulas

---

## Key Design Decisions

### Data Exclusion Philosophy
**Goal:** Show "recurring lifestyle" savings rate - money you could realistically reduce to save more

**Include (things that reduce savings):**
- Regular paychecks
- Groceries, restaurants, shopping
- Bills, subscriptions
- Entertainment, hobbies
- Normal home expenses

**Exclude by default (things you save FOR):**
- Travel (you save to go on vacation)
- Gifts (you budget for giving)
- Christmas (seasonal, not recurring)
- Tax payments (planned obligation)
- Home improvements (you save for projects)
- 401k gains (portfolio growth, not spendable income)
- Transfers (money movements)

**Configurable threshold:**
- Large expenses >$3,000 filtered (catches one-time big purchases)
- Can be adjusted or disabled

### Chart Color Scheme
- **Green:** Income, assets, positive savings
- **Red/Coral:** Expenses, liabilities
- **Gold:** Net/savings, target lines
- **Gray:** Zero lines, previous years, inactive data

---

## Technical Details

### Caching Strategy
- `@st.cache_resource` - For class instances (spreadsheet objects)
- `@st.cache_data` - For DataFrames and calculations (sparklines)
- TTL: 300 seconds (5 minutes)
- Shared across all pages and users

### Date Handling
- All dates parsed with `format='mixed', utc=True`
- Month strings formatted as 'YYYY-MM'
- Comparisons use timezone-aware pd.Timestamp
- Current month excluded from incomplete data

### Data Flow
1. Load from Google Sheets (cached)
2. Scrub data (parse dates, clean amounts)
3. Apply user filters (groups, categories, thresholds)
4. Calculate metrics (monthly aggregates)
5. Display charts and tables

---

## Outstanding Issues

### Data Quality
- 494 miscategorized Transfer transactions (need Google Sheets formula update)
- Some 401k gains showing as Income (should be Investment/Transfer)
- May need to re-categorize large paychecks if they're bonuses

### Potential Future Enhancements
- Budget vs Actual tracking (would need budget data)
- Debt payoff projection
- Net worth composition over time (stacked area chart)
- Transaction anomaly detection
- Mobile-responsive layout improvements

---

## Dependencies

```
pandas
streamlit
st-gsheets-connection
altair
pyyaml
openpyxl (for analyzing local Excel files)
```

Note: Removed `streamlit-aggrid` (was unstable, replaced with native `st.dataframe`)

---

## Google Sheets Configuration

### Secrets (.streamlit/secrets.toml)
```toml
[connections.transactions]
type = "gsheets"
spreadsheet = "https://docs.google.com/spreadsheets/d/..."

[connections.balance_history]
type = "gsheets"
spreadsheet = "https://docs.google.com/spreadsheets/d/..."
```

### Required Sheets
1. **Transactions** - Transaction data with auto-populated Group/Type via VLOOKUP
2. **Balance History** - Account balances over time with auto-populated Group
3. **Categories** - Lookup table (Category → Group, Type, Hide)
4. **Accounts** - Lookup table (Account name + Institution + Last4 → Group, Hide)

---

## Lessons Learned

1. **Streamlit's native components are more stable** than third-party (AgGrid had rendering issues)
2. **Caching is critical** for Google Sheets-backed apps (10× speedup)
3. **Data quality matters more than visualizations** - Spent significant time fixing miscategorizations
4. **Simple filters are better than complex ones** - Group-based exclusions > individual category lists
5. **Side-by-side comparisons are powerful** - Savings % next to Income/Expense $ tells the full story
6. **Alignment is harder than expected** - Y-axis labels, legends, all affect chart positioning

