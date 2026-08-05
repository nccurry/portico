"""Configuration constants used across the application."""

from typing import Final

# Data filtering thresholds
DEFAULT_EXPENSE_THRESHOLD: Final[int] = 3000
DEFAULT_INCOME_THRESHOLD: Final[int] = 20000
DEFAULT_LARGE_TRANSACTION_THRESHOLD: Final[int] = 500
MIN_DUPLICATE_AMOUNT: Final[float] = 10.0
DEFAULT_DUPLICATE_DAYS_THRESHOLD: Final[int] = 1

# Savings and budget targets
DEFAULT_SAVINGS_RATE_TARGET: Final[int] = 20
DEFAULT_BUDGET_GROUPS: Final[list[str]] = [
    "Shopping",
    "Food",
    "Travel",
    "Entertainment",
]
MIN_SAVINGS_RATE: Final[int] = 0
MAX_SAVINGS_RATE: Final[int] = 100
SAVINGS_RATE_STEP: Final[int] = 5

# Financial Independence page
DEFAULT_EXPECTED_RETURN_RATE: Final[float] = 7.0
DEFAULT_FI_SPENDING_LOOKBACK_MONTHS: Final[int] = 12
DEFAULT_FI_PROJECTION_YEARS: Final[int] = 30
FI_SPENDING_LOOKBACK_OPTIONS: Final[list[int]] = [6, 12, 24, 36]

# Default portfolio accounts pre-selected in the FI filter panel.
# Matched case-insensitively against Account names; also unions any account
# whose Group is "Savings".
DEFAULT_FI_INCLUDED_ACCOUNTS: Final[list[str]] = [
    "Treasury Bond",
    "HSA",
    "Individual",
    "NVIDIA",
    "Corp IRA",
    "Traditional IRA",
    "Equity Awards",
]

# Date filtering
SPARKLINE_LOOKBACK_OPTIONS: Final[dict[str, int | None]] = {
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "2Y": 730,
    "5Y": 1825,
    "All": None,
}
SPARKLINE_LOOKBACK_DEFAULT: Final[str] = "1Y"

# Display settings
TRANSACTION_TABLE_HEIGHT: Final[int] = 600
CHART_HEIGHT_STANDARD: Final[int] = 350
CHART_HEIGHT_SPARKLINE: Final[int] = 50
CHART_HEIGHT_NET_WORTH_SPARKLINE: Final[int] = 60

# Color schemes
COLOR_INCOME: Final[str] = 'lightgreen'
COLOR_EXPENSE: Final[str] = 'lightcoral'
COLOR_SAVINGS: Final[str] = 'gold'
COLOR_ASSET: Final[str] = 'lightgreen'
COLOR_LIABILITY: Final[str] = 'lightcoral'
COLOR_NET_WORTH: Final[str] = 'gold'
COLOR_PLACEHOLDER: Final[str] = 'lightgray'
COLOR_BUDGET: Final[str] = '#a0a0a0'
COLOR_OVER_BUDGET: Final[str] = '#e15759'
COLOR_UNDER_BUDGET: Final[str] = '#59a14f'
COLOR_ADDITIONAL_SPENDING: Final[str] = 'mediumpurple'

# Tableau10 color palette for category charts
COLOR_PALETTE: Final[list[str]] = [
    '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
    '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac'
]

# Default filter lists
DEFAULT_EXCLUDE_CATEGORIES: Final[list[str]] = [
    'Tax Return Payment',
    'Given Gift',
    'Christmas',
    '401k',
    'HSA',
    'Stock Purchase',
    'Investment',
    'Home Improvements',
]

# FI page treats HSA spending as real spending (medical), so don't exclude it.
DEFAULT_EXCLUDE_CATEGORIES_FI: Final[list[str]] = [
    c for c in DEFAULT_EXCLUDE_CATEGORIES if c != 'HSA'
]

DEFAULT_EXCLUDE_GROUPS_INCOME_SAVINGS: Final[list[str]] = [
    'Travel',
    'Donations',
]

# FI page also excludes Income groups by default — they never affect the
# spending average (which is Type=='Expense' only) but keeping them out
# declutters the "transactions used" expander.
DEFAULT_EXCLUDE_GROUPS_FI: Final[list[str]] = [
    'Travel',
    'Donations',
    'Income',
]

DEFAULT_EXCLUDE_GROUPS_SPENDING: Final[list[str]] = [
    'Bills',
    'Income',
    'Donations',
    'Investment',
]

DEFAULT_EXCLUDE_GROUPS_BUDGET: Final[list[str]] = [
    'Transfer',
    'Income',
    'Investment',
]

# Subscription detection — categories excluded from recurring-charge detection
SUBSCRIPTION_EXCLUDED_CATEGORIES: Final[list[str]] = [
    'Mortgage Payment',
    'Auto Loan Payment',
    'Student Loan Payment',
    'Personal Loan Payment',
    'Car Payment',
    'Rent',
    'Investment',
    'Stock Purchase',
    '401k',
    'HSA',
    'RSU',
    'ESPP',
]

SUBSCRIPTION_EXCLUDED_CATEGORY_PATTERN: Final[str] = (
    r'Mortgage|Loan|Investment|401k|HSA|RSU|ESPP'
)

# Time period options
TIME_PERIODS: Final[list[str]] = [
    "This Month",
    "Last Month",
    "Last 3 Months",
    "Last 6 Months",
    "Last 12 Months",
    "Year to Date",
    "All Time"
]
