"""Regenerate the committed synthetic data used by the demo and tests."""

from __future__ import annotations

import csv
from datetime import date, timedelta
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
CATEGORIES = (
    ("Salary", "Income", "Income", "", 0),
    ("Groceries", "Food", "Expense", "", 500),
    ("Restaurants", "Food", "Expense", "", 250),
    ("Electric", "Bills", "Expense", "", 150),
    ("Rent", "Housing", "Expense", "", 1600),
    ("Streaming Subscription", "Entertainment", "Expense", "", 50),
    ("Cloud Subscription", "Software", "Expense", "", 40),
    ("Shopping", "Shopping", "Expense", "", 3000),
    ("Travel", "Travel", "Expense", "", 1000),
    ("Transfer", "Transfer", "Transfer", "Hide", 0),
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
    """Format a date like the Tiller CSV export."""
    return value.strftime("%m/%d/%Y")


def _format_amount(value: float) -> str:
    """Format a money value like the Tiller CSV export."""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _transaction_row(
    when: date,
    category: str,
    amount: float,
    account: str,
    description: str,
) -> dict[str, str]:
    """Build one raw transaction row."""
    account_number, institution = (
        ("xxxx1001", "Aurora Bank") if account == "Checking-B" else ("xxxx2002", "Harbor Card")
    )
    month = when.replace(day=1)
    week = when - timedelta(days=when.weekday())
    formatted_date = _format_date(when)
    return {
        "Date": formatted_date,
        "Category": category,
        "Amount": _format_amount(amount),
        "Account": account,
        "Month": _format_date(month),
        "Week": _format_date(week),
        "Full Description": description,
        "Institution": institution,
        "Account #": account_number,
        "Date Added": formatted_date,
        "Categorized Date": formatted_date,
    }


def _monthly_transaction_rows(month: date, month_index: int) -> list[dict[str, str]]:
    """Build the regular income and spending for one month."""
    salary = 4_200 + month_index * 23
    groceries = -(310 + month.month * 9 + month_index % 6 * 7)
    restaurants = -(105 + month.month * 6 + month_index % 5 * 9)
    electric = -(100 + (40 if month.month in {1, 2, 7, 8} else 15) + month_index % 4 * 4)
    rent = -(1_200 + month_index * 12)
    transfer = -(350 + month_index % 4 * 25)
    return [
        _transaction_row(month.replace(day=15), "Salary", salary, "Checking-B", "payroll deposit monthly"),
        _transaction_row(month.replace(day=16), "Groceries", groceries, "Checking-B", "market basket staples"),
        _transaction_row(month.replace(day=17), "Restaurants", restaurants, "Credit-H", "corner cafe dinner"),
        _transaction_row(month.replace(day=18), "Electric", electric, "Checking-B", "utility power bill"),
        _transaction_row(month.replace(day=19), "Rent", rent, "Checking-B", "apartment rent payment"),
        _transaction_row(month.replace(day=20), "Transfer", transfer, "Checking-B", "transfer to savings"),
    ]


def _special_transaction_rows() -> list[dict[str, str]]:
    """Build fixed rows used by page and integration tests."""
    rows: list[dict[str, str]] = []
    for when, amount, description in (
        (date(1995, 2, 7), -45.99, "duplicate pair seed 1"),
        (date(1994, 12, 12), -125.50, "duplicate pair seed 2"),
        (date(1994, 10, 5), -78.00, "duplicate pair seed 3"),
    ):
        rows.extend(
            [
                _transaction_row(when, "Restaurants", amount, "Checking-B", description),
                _transaction_row(when, "Restaurants", amount, "Checking-B", description),
            ]
        )

    for number, month in enumerate(_month_starts()[-6:], start=1):
        rows.append(
            _transaction_row(
                month.replace(day=17),
                "Streaming Subscription",
                -15.99,
                "Credit-H",
                f"verum streamus {number:05d}",
            )
        )
    for number, month in enumerate(_month_starts()[-5:], start=1):
        rows.append(
            _transaction_row(
                month.replace(day=17),
                "Cloud Subscription",
                -9.99,
                "Credit-H",
                f"nimbus cloudus {number:05d}",
            )
        )

    rows.extend(
        [
            _transaction_row(date(1995, 3, 16), "Shopping", -2_500, "Credit-H", "magnum boxus 99000"),
            _transaction_row(date(1995, 3, 9), "Shopping", -2_500, "Credit-H", "magnum boxus 99001"),
            _transaction_row(date(1994, 3, 17), "Groceries", -87.65, "Checking-B", "cross year staple"),
            _transaction_row(date(1995, 3, 17), "Groceries", -87.65, "Checking-B", "cross year staple"),
            _transaction_row(date(1995, 4, 17), "Groceries", -300, "Checking-B", "budget burn over"),
            _transaction_row(date(1995, 4, 17), "Restaurants", -50, "Checking-B", "budget burn under"),
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
    for index, row in enumerate(rows):
        row["Unnamed: 0"] = str(index)
    _write_csv(DATA_DIRECTORY / "transactions.csv", TRANSACTION_COLUMNS, rows)


def _balance_rows() -> list[dict[str, str]]:
    """Build monthly balances for every account in the synthetic workbook."""
    accounts = (
        ("Checking-B", "xxxx1001", "acct000000000000AB01", "Aurora Bank", "Depository", "Asset", 2_500, 100),
        ("Credit-H", "xxxx2002", "acct000000000000CD02", "Harbor Card", "Credit", "Liability", 2_900, -35),
        ("HSA", "xxxx3003", "acct000000000000EF03", "Fidelity", "Depository", "Asset", 8_000, 200),
        (
            "Individual Brokerage",
            "xxxx4004",
            "acct000000000000GH04",
            "Vanguard",
            "Investment",
            "Asset",
            50_000,
            1_300,
        ),
        ("Corp IRA", "xxxx5005", "acct000000000000IJ05", "Fidelity", "Investment", "Asset", 120_000, 3_000),
        ("Mortgage", "xxxx6006", "acct000000000000KL06", "Aurora Bank", "Loan", "Liability", 235_000, -1_000),
        ("ZeroSum-A", "xxxx0001", "acct000000000000ZS01", "Aurora Bank", "Depository", "Asset", 0, 0),
    )
    rows: list[dict[str, str]] = []
    for month_index, month in enumerate(_month_starts()):
        when = month.replace(day=20)
        week = when - timedelta(days=when.weekday())
        for account, number, account_id, institution, account_type, account_class, opening, change in accounts:
            rows.append(
                {
                    "Date": _format_date(when),
                    "Time": f"{when.isoformat()} 08:00:00",
                    "Account": account,
                    "Account #": number,
                    "Account ID": account_id,
                    "Balance ID": f"bal-{account.casefold().replace(' ', '-')}-{month_index:03d}",
                    "Institution": institution,
                    "Balance": _format_amount(opening + change * month_index),
                    "Month": _format_date(month),
                    "Week": _format_date(week),
                    "Type": account_type,
                    "Class": account_class,
                    "Account Status": "Active",
                    "Date Added": "05/01/1992",
                }
            )
    for index, row in enumerate(rows):
        row["Unnamed: 0"] = str(index)
    return rows


def _write_balances() -> None:
    """Write the synthetic balance-history export."""
    _write_csv(DATA_DIRECTORY / "balance_history.csv", BALANCE_COLUMNS, _balance_rows())


def _write_categories() -> None:
    """Write budgets for the full synthetic date range."""
    month_columns = [f"{year}-{month:02d}-01" for year in range(1992, 1996) for month in range(1, 13)]
    columns = ("Category", "Group", "Type", "Hide From Reports", *month_columns)
    rows: list[dict[str, str | int]] = []
    for category, group, transaction_type, hidden, monthly_budget in CATEGORIES:
        row: dict[str, str | int] = {
            "Category": category,
            "Group": group,
            "Type": transaction_type,
            "Hide From Reports": hidden,
        }
        row.update(dict.fromkeys(month_columns, monthly_budget))
        if category == "Groceries":
            row["1995-04-01"] = 100
        if category == "Restaurants":
            row["1995-04-01"] = 1_000
        rows.append(row)
    _write_csv(DATA_DIRECTORY / "categories.csv", columns, rows)


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]] | list[dict[str, str | int]]) -> None:
    """Write one compact CSV file with stable newlines."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Regenerate all date-based demo exports."""
    _write_transactions()
    _write_balances()
    _write_categories()
    print("Regenerated demo data for May 1992 through April 1995")


if __name__ == "__main__":
    main()
