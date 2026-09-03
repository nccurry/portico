"""Regenerate the committed synthetic data used by the demo and tests."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRECTORY = PROJECT_ROOT / "demo" / "data"
FIRST_MONTH = date(1992, 5, 1)
LAST_MONTH = date(1995, 4, 1)

TRANSACTION_COLUMNS = (
    "Unnamed: 0",
    "Date",
    "Category",
    "Amount",
    "Account",
    "Month",
    "Week",
    "Full Description",
    "Institution",
    "Account #",
    "Date Added",
    "Categorized Date",
)
BALANCE_COLUMNS = (
    "Unnamed: 0",
    "Date",
    "Time",
    "Account",
    "Account #",
    "Account ID",
    "Balance ID",
    "Institution",
    "Balance",
    "Month",
    "Week",
    "Type",
    "Class",
    "Account Status",
    "Date Added",
)
ACCOUNT_COLUMNS = ("Account", "Class Override", "Group", "Hide")


@dataclass(frozen=True)
class DemoAccount:
    """Describe one account in the synthetic dataset."""

    name: str
    number: str
    account_id: str
    institution: str
    account_type: str
    account_class: str
    group: str
    opening_balance: int
    monthly_change: int
    swings: tuple[int, ...]


@dataclass(frozen=True)
class DemoCategory:
    """Describe one synthetic category and its monthly budget."""

    name: str
    group: str
    transaction_type: str
    hidden: str
    monthly_budget: int
    annual_change: int = 0
    monthly_swings: tuple[int, ...] = ()


@dataclass(frozen=True)
class DemoSubscription:
    """Describe one recurring synthetic subscription."""

    category: str
    description: str
    amount: float
    start: date
    end: date
    day: int
    account: str


ACCOUNTS = (
    DemoAccount(
        "Main Checking",
        "xxxx1001",
        "demo-account-MC01",
        "Aurora Bank",
        "Depository",
        "Asset",
        "Savings",
        3_800,
        45,
        (-420, 260, -180, 340, -280, 410, -130, 180),
    ),
    DemoAccount(
        "Emergency Savings",
        "xxxx1002",
        "demo-account-ES02",
        "Aurora Bank",
        "Depository",
        "Asset",
        "Savings",
        8_600,
        260,
        (-1_200, 740, -520, 980, -760, 430, 1_050, -280),
    ),
    DemoAccount(
        "Travel Fund",
        "xxxx1003",
        "demo-account-TF03",
        "Aurora Bank",
        "Depository",
        "Asset",
        "Savings",
        2_700,
        75,
        (-950, 680, -540, 320, -780, 840, -260, 470),
    ),
    DemoAccount(
        "Everyday Card",
        "xxxx2001",
        "demo-account-EC04",
        "Harbor Card",
        "Credit",
        "Liability",
        "Credit Cards",
        1_150,
        0,
        (420, -180, 690, -230, 310, -480, 530, -120),
    ),
    DemoAccount(
        "Travel Rewards Card",
        "xxxx2002",
        "demo-account-TR05",
        "Harbor Card",
        "Credit",
        "Liability",
        "Credit Cards",
        760,
        0,
        (210, 480, -130, 720, -240, 310, 560, -190),
    ),
    DemoAccount(
        "Brokerage Account",
        "xxxx3001",
        "demo-account-BA06",
        "Northstar Investments",
        "Investment",
        "Asset",
        "Investments",
        64_000,
        760,
        (-3_600, 2_200, -1_500, 3_800, -2_700, 1_100, 4_100, -800, 2_600),
    ),
    DemoAccount(
        "Health Savings Account",
        "xxxx3002",
        "demo-account-HS07",
        "Northstar Investments",
        "Depository",
        "Asset",
        "Investments",
        6_800,
        175,
        (-540, 280, -160, 460, -320, 240, 590),
    ),
    DemoAccount(
        "Education Fund",
        "xxxx3003",
        "demo-account-EF08",
        "Northstar Investments",
        "Investment",
        "Asset",
        "Investments",
        13_500,
        230,
        (-1_050, 640, -390, 900, -760, 480, 1_130, -260),
    ),
    DemoAccount(
        "Workplace 401(k)",
        "xxxx4001",
        "demo-account-WK09",
        "Northstar Investments",
        "Investment",
        "Asset",
        "Retirement",
        96_000,
        1_450,
        (-4_800, 2_100, -2_900, 5_300, -3_700, 1_600, 4_700, -1_200),
    ),
    DemoAccount(
        "Roth IRA",
        "xxxx4002",
        "demo-account-RI10",
        "Northstar Investments",
        "Investment",
        "Asset",
        "Retirement",
        22_500,
        320,
        (-1_150, 620, -740, 1_260, -890, 430, 1_480),
    ),
    DemoAccount(
        "Home Loan",
        "xxxx5001",
        "demo-account-HL11",
        "Aurora Bank",
        "Loan",
        "Liability",
        "Liabilities",
        170_000,
        -625,
        (120, -70, 85, -110, 60, -40),
    ),
    DemoAccount(
        "Auto Loan",
        "xxxx5002",
        "demo-account-AL12",
        "Aurora Bank",
        "Loan",
        "Liability",
        "Liabilities",
        11_800,
        -235,
        (260, -180, 120, -240, 80, -100),
    ),
)
ACCOUNT_BY_NAME = {account.name: account for account in ACCOUNTS}

CATEGORIES = (
    DemoCategory("Salary", "Income", "Income", "", 0),
    DemoCategory("Interest", "Income", "Income", "", 0),
    DemoCategory("Rent", "Housing", "Expense", "", 1_260, 70),
    DemoCategory(
        "Electric",
        "Bills",
        "Expense",
        "",
        125,
        5,
        (45, 30, 10, -5, -15, -20, -15, 5, 15, 10, 25, 40),
    ),
    DemoCategory(
        "Natural Gas",
        "Bills",
        "Expense",
        "",
        70,
        3,
        (55, 45, 20, 0, -20, -30, -35, -30, -15, 0, 25, 50),
    ),
    DemoCategory("Internet", "Bills", "Expense", "", 42, 2),
    DemoCategory("Mobile Phone", "Bills", "Expense", "", 62, 2),
    DemoCategory(
        "Water & Sewer",
        "Bills",
        "Expense",
        "",
        48,
        2,
        (8, 5, 0, -3, -5, -5, -3, 0, 4, 6, 8, 10),
    ),
    DemoCategory("Trash", "Bills", "Expense", "", 25, 1),
    DemoCategory(
        "Groceries",
        "Food",
        "Expense",
        "",
        540,
        20,
        (25, 20, 10, 0, -10, -5, 5, 15, 25, 30, 45, 70),
    ),
    DemoCategory(
        "Restaurants",
        "Food",
        "Expense",
        "",
        290,
        15,
        (-30, -20, -10, 0, 15, 25, 35, 45, 25, 20, 40, 70),
    ),
    DemoCategory(
        "Coffee",
        "Food",
        "Expense",
        "",
        95,
        4,
        (-10, -5, 0, 5, 8, 10, 12, 8, 5, 0, 5, 15),
    ),
    DemoCategory(
        "Automobile Fuel",
        "Transportation",
        "Expense",
        "",
        165,
        8,
        (10, 5, 0, -10, -15, -10, 5, 15, 20, 15, 5, 0),
    ),
    DemoCategory("Auto Insurance", "Insurance", "Expense", "", 95, 4),
    DemoCategory(
        "Shopping",
        "Shopping",
        "Expense",
        "",
        320,
        15,
        (-100, -60, -40, 10, 35, 50, 70, 40, 20, 10, 80, 160),
    ),
    DemoCategory("Home Supplies", "Maintenance", "Expense", "", 110, 6),
    DemoCategory("Medical", "Health", "Expense", "", 85, 5),
    DemoCategory("Pet Care", "Household", "Expense", "", 65, 3),
    DemoCategory(
        "Travel",
        "Travel",
        "Expense",
        "",
        260,
        12,
        (-200, -180, -120, 20, 80, 130, 200, 180, 100, 30, -80, 220),
    ),
    DemoCategory(
        "Given Gift",
        "Donations",
        "Expense",
        "",
        50,
        2,
        (-40, -40, -30, -20, -10, -10, 0, 0, 10, 20, 50, 180),
    ),
    DemoCategory("Charitable Giving", "Donations", "Expense", "", 55, 3),
    DemoCategory("Streaming Subscription", "Entertainment", "Expense", "", 16),
    DemoCategory("Cloud Subscription", "Software", "Expense", "", 8),
    DemoCategory("Music Subscription", "Entertainment", "Expense", "", 11),
    DemoCategory("News Subscription", "Entertainment", "Expense", "", 10),
    DemoCategory("Fitness Subscription", "Health", "Expense", "", 35),
    DemoCategory("Meal Kit Subscription", "Food", "Expense", "", 75),
    DemoCategory("Transfer", "Transfer", "Transfer", "Hide", 0),
)

SUBSCRIPTIONS = (
    DemoSubscription(
        "Streaming Subscription",
        "Flicker Stream Membership",
        12.99,
        FIRST_MONTH,
        LAST_MONTH,
        23,
        "Everyday Card",
    ),
    DemoSubscription(
        "Cloud Subscription",
        "CloudBox Storage Plan",
        6.99,
        FIRST_MONTH,
        LAST_MONTH,
        24,
        "Everyday Card",
    ),
    DemoSubscription(
        "Music Subscription",
        "Soundwave Music Plan",
        9.99,
        FIRST_MONTH,
        LAST_MONTH,
        25,
        "Everyday Card",
    ),
    DemoSubscription(
        "News Subscription",
        "Morning Gazette Digital",
        8.50,
        date(1992, 5, 1),
        date(1993, 10, 1),
        26,
        "Everyday Card",
    ),
    DemoSubscription(
        "Fitness Subscription",
        "Fit Club Membership",
        32.00,
        date(1993, 5, 1),
        date(1994, 8, 1),
        27,
        "Everyday Card",
    ),
    DemoSubscription(
        "Fitness Subscription",
        "Fit Club Membership",
        36.00,
        date(1995, 1, 1),
        LAST_MONTH,
        27,
        "Everyday Card",
    ),
    DemoSubscription(
        "Meal Kit Subscription",
        "Pantry Box Delivery",
        68.00,
        date(1994, 1, 1),
        date(1994, 8, 1),
        22,
        "Travel Rewards Card",
    ),
)


def _month_starts() -> list[date]:
    """Return every synthetic data month in chronological order."""
    months: list[date] = []
    month = FIRST_MONTH
    while month <= LAST_MONTH:
        months.append(month)
        month = date(month.year + 1, 1, 1) if month.month == 12 else date(month.year, month.month + 1, 1)
    return months


def _format_date(value: date) -> str:
    """Format a date like the spreadsheet CSV export."""
    return value.strftime("%m/%d/%Y")


def _format_amount(value: float) -> str:
    """Format a money value like the spreadsheet CSV export."""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _monthly_amount(
    base: float,
    month: date,
    month_index: int,
    swings: tuple[int, ...],
    *,
    annual_change: float = 0,
) -> float:
    """Return one stable but non-repeating amount for a calendar month."""
    swing = swings[month_index % len(swings)] if swings else 0
    years_since_start = month.year - FIRST_MONTH.year
    return round(base + annual_change * years_since_start + swing, 2)


def _transaction_row(
    when: date,
    category: str,
    amount: float,
    account_name: str,
    description: str,
) -> dict[str, str]:
    """Build one raw transaction row."""
    account = ACCOUNT_BY_NAME[account_name]
    month = when.replace(day=1)
    week = when - timedelta(days=when.weekday())
    formatted_date = _format_date(when)
    return {
        "Date": formatted_date,
        "Category": category,
        "Amount": _format_amount(amount),
        "Account": account.name,
        "Month": _format_date(month),
        "Week": _format_date(week),
        "Full Description": description,
        "Institution": account.institution,
        "Account #": account.number,
        "Date Added": formatted_date,
        "Categorized Date": formatted_date,
    }


def _monthly_transaction_rows(month: date, month_index: int) -> list[dict[str, str]]:
    """Build varied income and spending for one month."""

    def amount(base: float, swings: tuple[int, ...], annual_change: float = 0) -> float:
        """Return a varied monthly amount for this row set."""
        return _monthly_amount(
            base,
            month,
            month_index,
            swings,
            annual_change=annual_change,
        )

    rows = [
        _transaction_row(
            month.replace(day=1),
            "Rent",
            -amount(1_240, (0, 10, -5, 20, 5, -10, 15), 70),
            "Main Checking",
            "Maple Street Rent",
        ),
        _transaction_row(
            month.replace(day=2),
            "Salary",
            amount(2_080, (25, -30, 40, -15, 10, 35, -20), 95),
            "Main Checking",
            "Cedar Works Payroll",
        ),
        _transaction_row(
            month.replace(day=3),
            "Salary",
            amount(2_115, (-20, 35, -15, 30, 0, -25, 45), 95),
            "Main Checking",
            "Cedar Works Payroll",
        ),
        _transaction_row(
            month.replace(day=4),
            "Interest",
            amount(12, (0, 2, 1, 3, 2), 3),
            "Emergency Savings",
            "Aurora Savings Interest",
        ),
        _transaction_row(
            month.replace(day=5),
            "Electric",
            -amount(105, (45, 35, 12, -5, -18, -22, -15, 8, 20, 16, 30, 48), 6),
            "Main Checking",
            "City Electric Service",
        ),
        _transaction_row(
            month.replace(day=6),
            "Natural Gas",
            -amount(48, (65, 52, 25, 2, -14, -24, -30, -22, -8, 5, 30, 60), 4),
            "Main Checking",
            "Harbor Gas Service",
        ),
        _transaction_row(
            month.replace(day=7),
            "Internet",
            -amount(38, (0, 1, 0, 2, 1), 2),
            "Main Checking",
            "Civic Fiber Internet",
        ),
        _transaction_row(
            month.replace(day=8),
            "Mobile Phone",
            -amount(56, (2, 0, 3, 1, -1), 2),
            "Everyday Card",
            "Northline Mobile Phone",
        ),
        _transaction_row(
            month.replace(day=9),
            "Water & Sewer",
            -amount(42, (10, 7, 2, -2, -5, -7, -4, 0, 5, 7, 9, 12), 2),
            "Main Checking",
            "City Water Sewer",
        ),
        _transaction_row(
            month.replace(day=10),
            "Trash",
            -amount(22, (0, 1, 0, 1), 1),
            "Main Checking",
            "Neighborhood Trash Service",
        ),
        _transaction_row(
            month.replace(day=11),
            "Groceries",
            -amount(245, (35, -20, 10, 45, -10, 25, -5, 40, 15), 12),
            "Main Checking",
            "Market Basket Staples",
        ),
        _transaction_row(
            month.replace(day=12),
            "Groceries",
            -amount(220, (-15, 30, 5, -20, 40, 10, 25, -5), 12),
            "Everyday Card",
            "Greenway Market Groceries",
        ),
        _transaction_row(
            month.replace(day=13),
            "Coffee",
            -amount(24, (8, -5, 4, 10, -2, 6), 3),
            "Everyday Card",
            "Northstar Coffee Roasters",
        ),
        _transaction_row(
            month.replace(day=14),
            "Restaurants",
            -amount(62, (20, -15, 8, 32, -8, 14, 25), 10),
            "Everyday Card",
            "Juniper Kitchen Dinner",
        ),
        _transaction_row(
            month.replace(day=15),
            "Restaurants",
            -amount(78, (-20, 25, 5, -12, 36, 10, 18), 10),
            "Everyday Card",
            "Riverstone Diner Lunch",
        ),
        _transaction_row(
            month.replace(day=16),
            "Automobile Fuel",
            -amount(48, (12, -5, 8, 15, -10, 5), 5),
            "Everyday Card",
            "Highway Fuel Station",
        ),
        _transaction_row(
            month.replace(day=17),
            "Automobile Fuel",
            -amount(51, (-8, 14, 4, -12, 10, 18), 5),
            "Everyday Card",
            "Westside Fuel Station",
        ),
        _transaction_row(
            month.replace(day=18),
            "Shopping",
            -amount(105, (-45, 20, 80, -30, 55, 10, -20, 110), 14),
            "Travel Rewards Card",
            "Willow Goods Market",
        ),
        _transaction_row(
            month.replace(day=19),
            "Charitable Giving",
            -amount(45, (0, 10, 5, -5), 3),
            "Main Checking",
            "River Aid Donation",
        ),
        _transaction_row(
            month.replace(day=20),
            "Transfer",
            -amount(420, (80, -40, 120, -90, 40), 20),
            "Main Checking",
            "Transfer Emergency Savings",
        ),
        _transaction_row(
            month.replace(day=20),
            "Transfer",
            amount(420, (80, -40, 120, -90, 40), 20),
            "Emergency Savings",
            "Transfer Emergency Savings",
        ),
    ]

    if month_index % 2 == 0:
        rows.append(
            _transaction_row(
                month.replace(day=21),
                "Home Supplies",
                -amount(72, (30, -20, 50, -10, 15), 7),
                "Travel Rewards Card",
                "Harbor Home Supplies",
            )
        )
    if month_index % 3 == 1:
        rows.append(
            _transaction_row(
                month.replace(day=21),
                "Medical",
                -amount(58, (25, -12, 40, 5), 5),
                "Everyday Card",
                "Pine Medical Clinic",
            )
        )
    if month_index % 4 == 0:
        rows.append(
            _transaction_row(
                month.replace(day=21),
                "Pet Care",
                -amount(48, (15, -8, 22, 5), 4),
                "Everyday Card",
                "Elm Pet Market",
            )
        )
    if month.month in {3, 6, 9, 12}:
        rows.append(
            _transaction_row(
                month.replace(day=21),
                "Auto Insurance",
                -amount(265, (10, -5, 15, 0), 10),
                "Main Checking",
                "Harbor Auto Insurance",
            )
        )
    if month_index % 3 == 2:
        rows.append(
            _transaction_row(
                month.replace(day=22),
                "Travel",
                -amount(180, (140, -60, 310, 40, -90), 20),
                "Travel Rewards Card",
                "Lakeview Travel Booking",
            )
        )
    if month.month == 12:
        rows.append(
            _transaction_row(
                month.replace(day=22),
                "Given Gift",
                -amount(180, (30, -20, 45), 12),
                "Travel Rewards Card",
                "Willow Gifts Holiday",
            )
        )

    for subscription in SUBSCRIPTIONS:
        if subscription.start <= month <= subscription.end:
            rows.append(
                _transaction_row(
                    month.replace(day=subscription.day),
                    subscription.category,
                    -subscription.amount,
                    subscription.account,
                    subscription.description,
                )
            )
    return rows


def _special_transaction_rows() -> list[dict[str, str]]:
    """Build a few fixed rows for data-health and tie handling."""
    rows: list[dict[str, str]] = []
    for when, category, account, amount, description in (
        (date(1995, 2, 7), "Restaurants", "Everyday Card", -45.99, "Juniper Kitchen Receipt"),
        (date(1994, 12, 12), "Home Supplies", "Travel Rewards Card", -125.50, "Harbor Home Receipt"),
        (date(1994, 10, 5), "Coffee", "Everyday Card", -78.00, "Northstar Coffee Receipt"),
    ):
        rows.extend(
            [
                _transaction_row(when, category, amount, account, description),
                _transaction_row(when, category, amount, account, description),
            ]
        )

    rows.extend(
        [
            _transaction_row(
                date(1995, 3, 9),
                "Shopping",
                -1_250,
                "Travel Rewards Card",
                "Harbor Home Appliance",
            ),
            _transaction_row(
                date(1995, 3, 16),
                "Shopping",
                -1_250,
                "Travel Rewards Card",
                "Willow Furniture Desk",
            ),
            _transaction_row(
                date(1994, 3, 17),
                "Groceries",
                -87.65,
                "Main Checking",
                "Market Basket Pantry",
            ),
            _transaction_row(
                date(1995, 3, 17),
                "Groceries",
                -94.25,
                "Main Checking",
                "Market Basket Pantry",
            ),
        ]
    )
    return rows


def _write_transactions() -> None:
    """Write the synthetic transactions export."""
    rows = [
        row
        for month_index, month in enumerate(_month_starts())
        for row in _monthly_transaction_rows(month, month_index)
    ]
    rows.extend(_special_transaction_rows())
    rows.sort(
        key=lambda row: (
            datetime.strptime(row["Date"], "%m/%d/%Y"),
            row["Full Description"],
            row["Amount"],
        )
    )
    for index, row in enumerate(rows):
        row["Unnamed: 0"] = str(index)
    _write_csv(DATA_DIRECTORY / "transactions.csv", TRANSACTION_COLUMNS, rows)


def _account_key(account: DemoAccount) -> str:
    """Return the composite account key used by the Accounts table."""
    return f"{account.name} - {account.number} ({account.account_id[-4:].upper()})"


def _balance_rows() -> list[dict[str, str]]:
    """Build monthly balances with varied trends."""
    rows: list[dict[str, str]] = []
    for month_index, month in enumerate(_month_starts()):
        when = month.replace(day=20)
        week = when - timedelta(days=when.weekday())
        for account in ACCOUNTS:
            swing = account.swings[month_index % len(account.swings)] if account.swings else 0
            balance = max(0, account.opening_balance + account.monthly_change * month_index + swing)
            rows.append(
                {
                    "Date": _format_date(when),
                    "Time": f"{when.isoformat()} 08:00:00",
                    "Account": account.name,
                    "Account #": account.number,
                    "Account ID": account.account_id,
                    "Balance ID": f"bal-{account.account_id.casefold()}-{month_index:03d}",
                    "Institution": account.institution,
                    "Balance": _format_amount(balance),
                    "Month": _format_date(month),
                    "Week": _format_date(week),
                    "Type": account.account_type,
                    "Class": account.account_class,
                    "Account Status": "Active",
                    "Date Added": _format_date(FIRST_MONTH),
                }
            )
    for index, row in enumerate(rows):
        row["Unnamed: 0"] = str(index)
    return rows


def _write_balances() -> None:
    """Write the synthetic balance-history export."""
    _write_csv(DATA_DIRECTORY / "balance_history.csv", BALANCE_COLUMNS, _balance_rows())


def _write_accounts() -> None:
    """Write account groups for the synthetic balance-history export."""
    rows = [
        {
            "Account": _account_key(account),
            "Class Override": "",
            "Group": account.group,
            "Hide": "",
        }
        for account in ACCOUNTS
    ]
    _write_csv(DATA_DIRECTORY / "accounts.csv", ACCOUNT_COLUMNS, rows)


def _budget_for(category: DemoCategory, month: date) -> int:
    """Return a realistic budget for one category and month."""
    if category.transaction_type != "Expense":
        return 0
    years_since_start = month.year - FIRST_MONTH.year
    swing = category.monthly_swings[month.month - 1] if category.monthly_swings else 0
    return max(0, category.monthly_budget + category.annual_change * years_since_start + swing)


def _write_categories() -> None:
    """Write budgets for the full synthetic date range."""
    months = [date(year, month, 1) for year in range(1992, 1996) for month in range(1, 13)]
    month_columns = [month.isoformat() for month in months]
    columns = ("Category", "Group", "Type", "Hide From Reports", *month_columns)
    rows: list[dict[str, str | int]] = []
    for category in CATEGORIES:
        row: dict[str, str | int] = {
            "Category": category.name,
            "Group": category.group,
            "Type": category.transaction_type,
            "Hide From Reports": category.hidden,
        }
        row.update({month.isoformat(): _budget_for(category, month) for month in months})
        rows.append(row)
    _write_csv(DATA_DIRECTORY / "categories.csv", columns, rows)


def _write_csv(
    path: Path,
    columns: tuple[str, ...],
    rows: list[dict[str, str]] | list[dict[str, str | int]],
) -> None:
    """Write one compact CSV file with stable newlines."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Regenerate all synthetic demo exports."""
    _write_transactions()
    _write_balances()
    _write_accounts()
    _write_categories()
    print("Regenerated varied demo data for May 1992 through April 1995")


if __name__ == "__main__":
    main()
