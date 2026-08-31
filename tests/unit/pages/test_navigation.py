"""Tests for the application navigation contract."""

from Home import ANALYZE_PAGE_SPECS


def test_analyze_pages_keep_spending_views_together() -> None:
    """Keep exact sidebar labels and the requested spending-page order."""
    assert [title for _, title, _ in ANALYZE_PAGE_SPECS] == [
        "Income and savings",
        "Spending by merchant",
        "Spending by category",
        "Year over year",
        "Subscriptions",
        "Transactions",
    ]
