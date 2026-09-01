"""Run the interactive Portico browser demo."""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src.analysis.home import build_account_inventory, build_net_worth_history

DATA_DIRECTORY = Path(__file__).parents[1] / "data"
LOOKBACK_MONTHS = {
    "6 months": 6,
    "12 months": 12,
    "All data": None,
}


@st.cache_data(show_spinner=False)
def load_demo_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and prepare the committed synthetic records."""
    balances = pd.read_csv(DATA_DIRECTORY / "balance_history.csv")
    balances["Balance"] = pd.to_numeric(
        balances["Balance"].str.replace(r"[$,]", "", regex=True),
        errors="coerce",
    )
    balances["Date"] = pd.to_datetime(balances["Date"], format="%m/%d/%Y", utc=True)
    balances["Time"] = pd.to_datetime(balances["Time"], format="%m/%d/%Y %H:%M:%S", utc=True)

    accounts = pd.read_csv(DATA_DIRECTORY / "accounts.csv")
    account_number = balances["Account #"].fillna("").astype(str)
    account_suffix = balances["Account ID"].fillna("").astype(str).str[-4:].str.upper()
    balances["_account_key"] = (
        balances["Account"].astype(str) + " - " + account_number + " (" + account_suffix + ")"
    ).str.lower()
    accounts["_account_key"] = accounts["Account"].astype(str).str.lower()
    balances = balances.merge(accounts[["_account_key", "Group", "Hide"]], on="_account_key", how="left")
    balances = balances[balances["Hide"].fillna("") != "Hide"].copy()
    balances["Group"] = balances["Group"].fillna("Uncategorized")

    transactions = pd.read_csv(DATA_DIRECTORY / "transactions.csv")
    transactions["Date"] = pd.to_datetime(transactions["Date"], format="%m/%d/%Y", utc=True)
    transactions["Amount"] = pd.to_numeric(
        transactions["Amount"].str.replace(r"[$,]", "", regex=True),
        errors="coerce",
    )
    categories = pd.read_csv(DATA_DIRECTORY / "categories.csv")
    transactions = transactions.merge(categories[["Category", "Group"]], on="Category", how="left")
    transactions["Group"] = transactions["Group"].fillna("Uncategorized")
    return balances, transactions


def period_start(dates: pd.Series, months: int | None) -> pd.Timestamp:
    """Return the first date for the selected reporting period."""
    first = pd.Timestamp(dates.min())
    if months is None:
        return first
    return max(first, pd.Timestamp(dates.max()) - pd.DateOffset(months=months))


def format_currency(value: float) -> str:
    """Format a money value for a metric or table."""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def render_net_worth(balances: pd.DataFrame, months: int | None) -> None:
    """Show the balance history and current account summary."""
    start = period_start(balances["Date"], months)
    end = pd.Timestamp(balances["Date"].max())
    history = build_net_worth_history(balances, start, end)
    current = history.iloc[-1]
    opening = history.iloc[0]

    st.title("Accounts and net worth")
    st.caption("Synthetic data only. This demo runs entirely in your browser.")
    net_worth, assets, debt = st.columns(3)
    net_worth.metric(
        "Net worth",
        format_currency(float(current["Net_Worth"])),
        format_currency(float(current["Net_Worth"] - opening["Net_Worth"])),
    )
    assets.metric(
        "Assets",
        format_currency(float(current["Assets"])),
        format_currency(float(current["Assets"] - opening["Assets"])),
    )
    debt.metric(
        "Liabilities",
        format_currency(abs(float(current["Liabilities"]))),
        format_currency(abs(float(current["Liabilities"])) - abs(float(opening["Liabilities"]))),
    )

    chart = (
        alt.Chart(history)
        .transform_fold(["Assets", "Liabilities", "Net_Worth"], as_=["Type", "Value"])
        .mark_line()
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Value:Q", axis=alt.Axis(format="$,.0f"), title=None),
            color=alt.Color("Type:N", title=None),
            tooltip=[alt.Tooltip("Date:T", format="%b %d, %Y"), alt.Tooltip("Value:Q", format="$,.0f")],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, use_container_width=True)

    accounts = build_account_inventory(balances, start, end)
    account_table = accounts[["Group", "Account", "Institution", "Balance", "Period_Change"]].copy()
    account_table["Balance"] = account_table["Balance"].map(format_currency)
    account_table["Period_Change"] = account_table["Period_Change"].map(format_currency)
    with st.expander("Account details"):
        st.dataframe(account_table, use_container_width=True, hide_index=True)


def render_spending(transactions: pd.DataFrame, months: int | None) -> None:
    """Show a category breakdown that responds to the group selector."""
    start = period_start(transactions["Date"], months)
    spending = transactions[(transactions["Date"] >= start) & (transactions["Amount"] < 0)].copy()
    spending = spending[spending["Group"] != "Transfer"]
    groups = ["All spending", *sorted(spending["Group"].unique())]
    selected_group = st.selectbox("Spending group", groups)
    if selected_group != "All spending":
        spending = spending[spending["Group"] == selected_group]

    summary = (
        spending.assign(Spend=spending["Amount"].abs())
        .groupby("Category", as_index=False)
        .agg({"Spend": "sum"})
        .sort_values("Spend", ascending=False)
    )
    st.subheader("Spending by category")
    chart = (
        alt.Chart(summary.head(8))
        .mark_bar()
        .encode(
            x=alt.X("Spend:Q", axis=alt.Axis(format="$,.0f"), title=None),
            y=alt.Y("Category:N", sort="-x", title=None),
            tooltip=[alt.Tooltip("Category:N"), alt.Tooltip("Spend:Q", format="$,.0f")],
        )
        .properties(height=280)
    )
    st.altair_chart(chart, use_container_width=True)
    summary["Spend"] = summary["Spend"].map(format_currency)
    st.dataframe(summary, use_container_width=True, hide_index=True)


def main() -> None:
    """Run the browser-safe sample of Portico's core reporting."""
    st.set_page_config(page_title="Portico demo", page_icon=":material/account_balance:", layout="wide")
    balances, transactions = load_demo_data()
    with st.sidebar:
        st.header("Demo controls")
        lookback = st.selectbox("Time frame", list(LOOKBACK_MONTHS))
        st.caption("Change the time frame and spending group to explore the sample data.")
        st.markdown("[View source on GitHub](https://github.com/nccurry/portico)")
    months = LOOKBACK_MONTHS[lookback]
    render_net_worth(balances, months)
    render_spending(transactions, months)


if __name__ == "__main__":
    main()
