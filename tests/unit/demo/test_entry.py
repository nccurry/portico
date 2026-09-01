import pandas as pd

from demo.pages.entry import format_currency, load_demo_data, period_start


def test_load_demo_data_prepares_grouped_synthetic_records() -> None:
    balances, transactions = load_demo_data()

    assert {"Balance", "Date", "Group"}.issubset(balances.columns)
    assert {"Amount", "Date", "Group"}.issubset(transactions.columns)
    assert "Savings" in balances["Group"].unique()
    assert "Food" in transactions["Group"].unique()


def test_period_start_and_currency_formatting() -> None:
    dates = pd.Series(pd.to_datetime(["2026-01-01", "2026-06-01"], utc=True))

    assert period_start(dates, 3) == pd.Timestamp("2026-03-01", tz="UTC")
    assert period_start(dates, None) == pd.Timestamp("2026-01-01", tz="UTC")
    assert format_currency(-1234.5) == "-$1,234"
