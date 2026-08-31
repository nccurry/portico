"""Compare one spending group or category across calendar years."""

import calendar
from typing import cast

import altair as alt
import pandas as pd
import streamlit as st

from src.analysis.year_over_year import (
    build_year_over_year_history,
    build_year_totals,
    spending_entities,
    spending_preset_categories,
    summarize_year_over_year,
)
from src.constants import COLOR_NET_WORTH
from src.custom_types import YearOverYearSummary
from src.page_helpers import render_data_refresh_controls
from src.reporting_periods import latest_data_timestamp, rolling_month_window
from src.spreadsheet import TransactionsSpreadsheet, load_transactions_data
from src.value_visibility import mask_value, value_safe_altair_chart, value_safe_dataframe


MONTHS = list(calendar.month_abbr[1:])
PRIOR_YEAR_COLORS = ["#CBD5E1", "#94A3B8", "#64748B", "#475569", "#334155"]
VIEW_OPTIONS = [
    "Utility bills",
    "Discretionary spending",
    "Single category",
    "Single group",
]
MAX_DEFAULT_PRESET_CATEGORIES = 8


def _preferred_entity(entities: list[str], dimension: str) -> str:
    if not entities:
        return ""
    if dimension == "Group" and "Bills" in entities:
        return "Bills"
    priorities = [
        "electric",
        "electricity",
        "utilities",
        "water",
        "natural gas",
        "internet",
        "phone",
    ]
    for priority in priorities:
        match = next(
            (entity for entity in entities if priority in entity.lower()),
            None,
        )
        if match is not None:
            return match
    return entities[0]


def _format_currency(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return "Not available"
    sign = "+" if signed and value > 0 else "-" if value < 0 else ""
    return mask_value(f"{sign}${abs(value):,.0f}")


def _format_percent(value: float | None) -> str | None:
    if value is None:
        return None
    sign = "+" if value > 0 else ""
    return mask_value(f"{sign}{value:.1f}%")


def _year_colors(years: list[int]) -> tuple[list[str], list[str]]:
    ordered = [str(year) for year in sorted(years, reverse=True)]
    colors = [COLOR_NET_WORTH]
    colors.extend(PRIOR_YEAR_COLORS[min(index, len(PRIOR_YEAR_COLORS) - 1)] for index in range(len(ordered) - 1))
    return ordered, colors


def _create_year_chart(
    history: pd.DataFrame,
    *,
    height: int,
) -> alt.LayerChart:
    years = sorted(history["Year"].astype(int).unique().tolist())
    year_domain, year_colors = _year_colors(years)
    color = alt.Color(
        "Year_Label:N",
        title=None,
        scale=alt.Scale(domain=year_domain, range=year_colors),
        legend=alt.Legend(
            orient="top",
            direction="horizontal",
            symbolType="stroke",
        ),
    )
    base = alt.Chart(history).encode(
        x=alt.X(
            "Month_Label:N",
            title=None,
            sort=MONTHS,
            axis=alt.Axis(labelAngle=0),
        ),
        y=alt.Y(
            "Spending:Q",
            title="Monthly spending ($)",
            axis=alt.Axis(format="$~s"),
            scale=alt.Scale(zero=True),
        ),
        color=color,
        order=alt.Order("Year:Q", sort="ascending"),
        tooltip=[
            alt.Tooltip("Year_Label:N", title="Year"),
            alt.Tooltip("Month_Label:N", title="Month"),
            alt.Tooltip("Spending:Q", title="Spending", format="$,.2f"),
        ],
    )
    lines = base.mark_line().encode(
        strokeWidth=alt.condition(
            "datum.Is_Current",
            alt.value(4),
            alt.value(2),
        ),
        opacity=alt.condition(
            "datum.Is_Current",
            alt.value(1),
            alt.value(0.82),
        ),
    )
    points = base.mark_point(filled=True).encode(
        size=alt.condition(
            "datum.Is_Current",
            alt.value(75),
            alt.value(38),
        ),
    )
    zero = alt.Chart(pd.DataFrame({"Spending": [0.0]})).mark_rule(color="#64748B", opacity=0.45).encode(y="Spending:Q")
    return cast(
        alt.LayerChart,
        alt.layer(zero, lines, points).properties(height=height),
    )


def _render_metrics(summary: YearOverYearSummary, *, border: bool) -> None:
    current_year = summary["current_year"]
    previous_year = summary["previous_year"]
    month_name = calendar.month_name[summary["through_month"]]
    with st.container(horizontal=True):
        st.metric(
            f"{current_year} through {month_name}",
            _format_currency(summary["current_total"]),
            border=border,
        )
        st.metric(
            (f"{previous_year} through {month_name}" if previous_year is not None else "Previous year"),
            _format_currency(summary["previous_total"]),
            border=border,
        )
        st.metric(
            "Change",
            _format_currency(summary["change"], signed=True),
            _format_percent(summary["change_pct"]),
            delta_color="inverse",
            border=border,
        )


def _render_details(
    transactions: pd.DataFrame,
    history: pd.DataFrame,
    *,
    dimension: str,
    entity: str,
    through_month: int,
) -> None:
    with st.expander("Details", icon=":material/receipt_long:"):
        totals = build_year_totals(history, through_month=through_month)
        value_safe_dataframe(
            totals,
            width="stretch",
            hide_index=True,
            column_config={
                "Year": st.column_config.NumberColumn("Year", format="%d"),
                "Spending_Through_Month": st.column_config.NumberColumn(
                    f"Spending through {calendar.month_name[through_month]}",
                    format="$%.2f",
                ),
                "Change": st.column_config.NumberColumn(
                    "Change from prior year",
                    format="$%+.2f",
                ),
                "Change_Pct": st.column_config.NumberColumn(
                    "Change %",
                    format="%+.1f%%",
                ),
            },
            visible_numeric_columns={"Year"},
        )

        expenses = transactions[
            transactions["Type"].eq("Expense") & transactions[dimension].astype(str).eq(entity)
        ].copy()
        expenses["Spending"] = -pd.to_numeric(
            expenses["Amount"],
            errors="coerce",
        )
        columns = [
            "Date",
            "Full Description",
            "Group",
            "Category",
            "Account",
            "Spending",
        ]
        display = expenses.sort_values("Date", ascending=False)[
            [column for column in columns if column in expenses]
        ].rename(columns={"Full Description": "Description"})
        value_safe_dataframe(
            display,
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn("Date", format="MMM DD, YYYY"),
                "Description": st.column_config.TextColumn(
                    "Description",
                    width="large",
                    pinned=True,
                ),
                "Spending": st.column_config.NumberColumn(
                    "Spending",
                    format="$%.2f",
                ),
            },
        )


def _render_comparison(
    transactions: pd.DataFrame,
    *,
    dimension: str,
    entity: str,
    through_month: int,
    compact: bool,
) -> None:
    history = build_year_over_year_history(
        transactions,
        dimension=dimension,
        entity=entity,
    )
    if history.empty:
        return
    summary = summarize_year_over_year(
        history,
        through_month=through_month,
    )
    with st.container(border=True):
        st.subheader(entity)
        _render_metrics(summary, border=False)
        value_safe_altair_chart(
            _create_year_chart(history, height=280 if compact else 470),
            width="stretch",
        )
        _render_details(
            transactions,
            history,
            dimension=dimension,
            entity=entity,
            through_month=through_month,
        )


def _preset_selection(
    transactions: pd.DataFrame,
    *,
    view: str,
) -> list[str]:
    available = spending_entities(transactions, "Category")
    defaults = spending_preset_categories(transactions, view)[:MAX_DEFAULT_PRESET_CATEGORIES]
    key = f"year_over_year_{view.lower().replace(' ', '_')}_categories"
    st.session_state.setdefault(key, defaults)
    with st.popover(
        "Choose categories",
        icon=":material/tune:",
        width="stretch",
    ):
        selected = st.multiselect(
            "Categories",
            available,
            key=key,
            persist_state="page",
        )
    return [category for category in selected if category in available]


def configure_page(transactions_spreadsheet: TransactionsSpreadsheet) -> None:
    """Render curated or single-entity year-over-year comparisons."""
    st.title("Year over year")
    transactions = transactions_spreadsheet.scrubbed_df.copy()
    expenses = transactions[transactions["Type"].eq("Expense")]
    if expenses.empty:
        st.info("No expense transactions are available.")
        return

    _, current_through = rolling_month_window(1)
    cutoff = pd.Period(current_through, freq="M")
    analysis_transactions = transactions[transactions["Month"].astype(str) <= current_through].copy()
    latest = latest_data_timestamp(transactions)
    if latest is not None:
        st.caption(f"Latest data {latest.strftime('%b %d, %Y')} · includes {cutoff.strftime('%b %Y')} to date")

    controls = st.columns([3, 2], vertical_alignment="bottom")
    with controls[0]:
        view = st.segmented_control(
            "View",
            VIEW_OPTIONS,
            default="Utility bills",
            key="year_over_year_view",
            persist_state="page",
        )
    if view in {"Utility bills", "Discretionary spending"}:
        with controls[1]:
            selected_entities = _preset_selection(
                analysis_transactions,
                view=str(view),
            )
        if not selected_entities:
            st.info("Choose at least one category to compare.")
            return
        for entity in selected_entities:
            _render_comparison(
                analysis_transactions,
                dimension="Category",
                entity=entity,
                through_month=cutoff.month,
                compact=True,
            )
        return

    dimension = "Category" if view == "Single category" else "Group"
    entities = spending_entities(analysis_transactions, dimension)
    if not entities:
        st.info(f"No expense {dimension.lower()} data is available.")
        return
    preferred = _preferred_entity(entities, dimension)
    with controls[1]:
        entity = st.selectbox(
            dimension,
            entities,
            index=entities.index(preferred),
            key=f"year_over_year_{dimension.lower()}",
            persist_state="page",
        )
    _render_comparison(
        analysis_transactions,
        dimension=dimension,
        entity=str(entity),
        through_month=cutoff.month,
        compact=False,
    )


def main() -> None:
    """Streamlit entry point for the Year over Year page."""
    st.set_page_config(layout="wide")
    render_data_refresh_controls()
    configure_page(load_transactions_data())


if __name__ == "__main__":
    main()
