"""Streamlit-independent cleaning for Tiller spreadsheet data."""

from __future__ import annotations

import pandas as pd


class SpreadsheetSchemaError(ValueError):
    """Raised when an imported sheet is missing required columns."""


TRANSACTIONS_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
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
    }
)
CATEGORIES_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "Category",
        "Group",
        "Type",
        "Hide From Reports",
    }
)
BALANCE_HISTORY_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "Date",
        "Time",
        "Balance",
        "Account",
        "Account #",
        "Account ID",
        "Institution",
        "Class",
        "Month",
        "Week",
        "Date Added",
    }
)


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: frozenset[str],
    sheet_name: str,
) -> None:
    """Raise when ``df`` is missing required Tiller columns."""
    missing = sorted(required_columns - set(df.columns))
    if missing:
        joined = ", ".join(missing)
        raise SpreadsheetSchemaError(f"{sheet_name} sheet is missing required columns: {joined}")


def scrub_categories(raw_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return category metadata and long-format monthly budgets."""
    df = raw_df.copy()
    validate_required_columns(df, CATEGORIES_REQUIRED_COLUMNS, "Categories")

    metadata = df.filter(["Category", "Group", "Type", "Hide From Reports"]).copy()
    metadata = metadata.dropna(subset=["Category"])

    budget_frames: list[pd.DataFrame] = []
    for column in df.columns[4:]:
        try:
            month = pd.to_datetime(column)
        except ValueError, TypeError:
            continue
        cleaned = df[column].astype(str).str.replace(r"[$,]", "", regex=True)
        budget_frames.append(
            pd.DataFrame(
                {
                    "Category": df["Category"],
                    "Month": month.strftime("%Y-%m"),
                    "Budget": pd.to_numeric(cleaned, errors="coerce").fillna(0),
                }
            )
        )

    if not budget_frames:
        budget = pd.DataFrame(columns=["Category", "Month", "Budget", "Group", "Type"])
        return metadata, budget

    budget = pd.concat(budget_frames, ignore_index=True).dropna(subset=["Category"])
    budget = budget.merge(metadata[["Category", "Group", "Type"]], on="Category", how="left")
    return metadata, budget


def scrub_transactions(raw_df: pd.DataFrame, categories: pd.DataFrame) -> pd.DataFrame:
    """Return normalized transactions joined to category metadata."""
    df = raw_df.copy()
    validate_required_columns(df, TRANSACTIONS_REQUIRED_COLUMNS, "Transactions")

    df = df.drop("Unnamed: 0", axis=1, errors="ignore")
    df["Amount"] = df["Amount"].replace(r"[\$,]", "", regex=True).astype(float)

    for column in ["Date", "Month", "Week", "Date Added", "Categorized Date"]:
        df[column] = pd.to_datetime(df[column], format="mixed", utc=True)

    df["Month"] = df["Month"].dt.strftime("%Y-%m")
    df["Week"] = df["Week"].dt.strftime("%U")

    df = df.drop(columns=["Group", "Type", "Hide From Reports"], errors="ignore")
    df = df.merge(categories, on="Category", how="left")
    df["Group"] = df["Group"].fillna("Uncategorized")
    df["Type"] = df["Type"].fillna("")
    df["Hide From Reports"] = df["Hide From Reports"].fillna("")

    return df.filter(
        [
            "Date",
            "Category",
            "Amount",
            "Account",
            "Month",
            "Full Description",
            "Group",
            "Type",
            "Institution",
            "Account #",
        ]
    )
