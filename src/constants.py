"""Configuration constants used across the application."""

from typing import Final

# Savings and budget controls
MIN_SAVINGS_RATE: Final[int] = 0
MAX_SAVINGS_RATE: Final[int] = 100
SAVINGS_RATE_STEP: Final[int] = 5

# Financial Independence page
FI_SPENDING_LOOKBACK_OPTIONS: Final[list[int]] = [6, 12, 24, 36]

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
COLOR_INCOME: Final[str] = "#57CC57"
COLOR_EXPENSE: Final[str] = "#E07A75"
COLOR_SAVINGS: Final[str] = "#F2B84B"
COLOR_ASSET: Final[str] = "#57CC57"
COLOR_LIABILITY: Final[str] = "#E07A75"
COLOR_NET_WORTH: Final[str] = "#70A5EB"
COLOR_PLACEHOLDER: Final[str] = "#94A3B8"
COLOR_BUDGET: Final[str] = "#94A3B8"
COLOR_OVER_BUDGET: Final[str] = "#E07A75"
COLOR_UNDER_BUDGET: Final[str] = "#57CC57"
COLOR_ADDITIONAL_SPENDING: Final[str] = "#A78BFA"

# Restrained categorical palette shared by charts
COLOR_PALETTE: Final[list[str]] = [
    "#70A5EB",
    "#57CC57",
    "#F2B84B",
    "#A78BFA",
    "#E07A75",
    "#5CC8BE",
    "#94A3B8",
    "#D98CC8",
    "#D19A66",
    "#7F9EBC",
]

# Time period options
TIME_PERIODS: Final[list[str]] = [
    "This Month",
    "Last Month",
    "Last 3 Months",
    "Last 6 Months",
    "Last 12 Months",
    "Year to Date",
    "All Time",
]
