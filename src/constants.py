"""Configuration constants used across the application."""

# Data filtering thresholds
DEFAULT_EXPENSE_THRESHOLD = 3000
DEFAULT_INCOME_THRESHOLD = 20000
DEFAULT_LARGE_TRANSACTION_THRESHOLD = 500
MIN_DUPLICATE_AMOUNT = 10.0
DEFAULT_DUPLICATE_DAYS_THRESHOLD = 1

# Savings and budget targets
DEFAULT_SAVINGS_RATE_TARGET = 20
MIN_SAVINGS_RATE = 0
MAX_SAVINGS_RATE = 100
SAVINGS_RATE_STEP = 5

# Date filtering
SPARKLINE_HISTORY_DAYS = 365
SPARKLINE_SAMPLE_FREQUENCY = 'W'  # Weekly

# Display settings
TRANSACTION_TABLE_HEIGHT = 600
DEFAULT_PAGE_SIZE = 100
CHART_HEIGHT_STANDARD = 350
CHART_HEIGHT_SPARKLINE = 50
CHART_HEIGHT_NET_WORTH_SPARKLINE = 60

# Color schemes
COLOR_INCOME = 'lightgreen'
COLOR_EXPENSE = 'lightcoral'
COLOR_SAVINGS = 'gold'
COLOR_ASSET = 'lightgreen'
COLOR_LIABILITY = 'lightcoral'
COLOR_NET_WORTH = 'gold'
COLOR_PLACEHOLDER = 'lightgray'
COLOR_BUDGET = '#a0a0a0'
COLOR_OVER_BUDGET = '#e15759'
COLOR_UNDER_BUDGET = '#59a14f'

# Tableau10 color palette for category charts
COLOR_PALETTE = [
    '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
    '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac'
]

# Default filter lists
DEFAULT_EXCLUDE_CATEGORIES = [
    'Tax Return Payment',
    'Given Gift',
    'Christmas',
    '401k',
    'HSA',
    'Stock Purchase',
    'Investment',
    'Home Improvements',
]

DEFAULT_EXCLUDE_GROUPS_INCOME_SAVINGS = [
    'Travel',
    'Donations',
]

DEFAULT_EXCLUDE_GROUPS_SPENDING = [
    'Bills',
    'Income',
    'Donations',
    'Investment',
]

DEFAULT_EXCLUDE_GROUPS_BUDGET = [
    'Transfer',
    'Income',
    'Investment',
]

# Time period options
TIME_PERIODS = [
    "This Month",
    "Last Month",
    "Last 3 Months",
    "Last 6 Months",
    "Last 12 Months",
    "Year to Date",
    "All Time"
]

