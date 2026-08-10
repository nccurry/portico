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

# Dark financial-dashboard palette
COLOR_INCOME: Final[str] = '#57CC57'
COLOR_EXPENSE: Final[str] = '#E07A75'
COLOR_SAVINGS: Final[str] = '#F2B84B'
COLOR_ASSET: Final[str] = '#57CC57'
COLOR_LIABILITY: Final[str] = '#E07A75'
COLOR_NET_WORTH: Final[str] = '#70A5EB'
COLOR_PLACEHOLDER: Final[str] = '#94A3B8'
COLOR_BUDGET: Final[str] = '#94A3B8'
COLOR_OVER_BUDGET: Final[str] = '#E07A75'
COLOR_UNDER_BUDGET: Final[str] = '#57CC57'
COLOR_ADDITIONAL_SPENDING: Final[str] = '#A78BFA'

# Restrained categorical palette shared by charts
COLOR_PALETTE: Final[list[str]] = [
    '#70A5EB', '#57CC57', '#F2B84B', '#A78BFA', '#E07A75',
    '#5CC8BE', '#94A3B8', '#D98CC8', '#D19A66', '#7F9EBC'
]

# Default filter lists
DEFAULT_EXCLUDE_CATEGORIES_INCOME_SAVINGS: Final[list[str]] = [
    'Tax Return Refund',
    'Investment',
    'Credit Card Rewards',
    'RSU',
    'ESPP',
    'Bonus',
    'Received Gift',
    'Tax Return Payment',
    'Christmas',
    'Home Repairs',
    'Automobile Repairs',
    'Home Improvements',
    'Misc Maintainence',
]

DEFAULT_EXCLUDE_GROUPS_INCOME_SAVINGS: Final[list[str]] = [
    'Travel',
    'Donations',
]

# Categories hidden from the discretionary spending view by default.
DEFAULT_EXCLUDE_CATEGORIES_SPENDING: Final[list[str]] = ['Christmas']

DEFAULT_EXCLUDE_GROUPS_SPENDING: Final[list[str]] = [
    'Bills',
    'Income',
    'Donations',
    'Maintenance',
    'Travel',
]

DEFAULT_EXCLUDE_CATEGORIES_SUBSCRIPTIONS: Final[list[str]] = [
    'Automobile Fuel',
    'Fee',
    'Medical Bill',
    'Video Games',
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
