"""Streamlit AppTest smoke tests for every page.

Each page is loaded via ``AppTest.from_file`` with only the data-loading
functions mocked — the rest of the code (filters, helpers, charts) runs
for real, giving us cheap end-to-end coverage.

Requires the committed synthetic files under ``demo/data``.
"""

import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.config import clear_settings_cache
from tests.custom_types import FullDatasetFactory, SpreadsheetBundle

# Page modules are not imported directly; AppTest runs them from file.

# ---------------------------------------------------------------------------
# Shared factory
# ---------------------------------------------------------------------------

_PAGE_DIR = Path(__file__).resolve().parents[2] / "pages"
_MASKED_VALUE = "XXXXXXXX"
_SENSITIVE_TEXT = re.compile(
    r"\$\s*\d|\b\d[\d,]*(?:\.\d+)?%|\b\d[\d,]*(?:\.\d+)?\s+"
    r"(?:accounts?|days?|merchants?|rows?|transactions?|years?)\b",
    re.IGNORECASE,
)


def _metric_values(at: AppTest) -> list[tuple[str, str, str]]:
    """Return rendered metric labels, values, and deltas in page order."""
    return [(metric.label, metric.value, metric.delta) for metric in at.metric]


def _metric_labels(at: AppTest) -> list[str]:
    """Return rendered metric labels in page order."""
    return [metric.label for metric in at.metric]


def _select_three_months(at: AppTest) -> None:
    at.segmented_control(key="income_lookback").set_value("3M")


def _select_actual_income(at: AppTest) -> None:
    at.segmented_control(key="income_calculation_view").set_value("Actual")


def _edit_regular_income_without_travel(at: AppTest) -> None:
    at.multiselect(key="income_regular_exclude_expense_groups").set_value([])


def _edit_and_reset_regular_income(at: AppTest) -> None:
    at.multiselect(key="income_regular_exclude_expense_groups").set_value([])
    at.run()
    next(button for button in at.button if button.label == "Reset defaults").click()


def _select_may_income_month_from_cash_chart(at: AppTest) -> None:
    at.session_state["income_history_0"] = {
        "selection": {"cash_month_pick": [{"Month_Key": "1994-05"}]},
    }


def _select_may_income_month_from_rate_chart(at: AppTest) -> None:
    at.session_state["income_history_0"] = {
        "selection": {"rate_month_pick": [{"Month_Key": "1994-05"}]},
    }


def _select_top_ten(at: AppTest) -> None:
    at.segmented_control(key="top_transactions_focus").set_value("Largest")
    at.number_input(key="top_transactions_largest_count").set_value(10)


def _select_one_off_transactions(at: AppTest) -> None:
    at.segmented_control(key="top_transactions_focus").set_value("One-off merchants")


def _select_transfer_transactions(at: AppTest) -> None:
    at.segmented_control(key="top_transactions_type").set_value("Transfers")


def _search_market_basket_transactions(at: AppTest) -> None:
    at.text_input(key="top_transactions_search").set_value("market basket")


def _search_for_missing_transactions(at: AppTest) -> None:
    at.text_input(key="top_transactions_search").set_value("not-a-real-transaction")


def _limit_transaction_maximum(at: AppTest) -> None:
    at.number_input(key="top_transactions_maximum").set_value(1_000.0)


def _set_fi_scenario(at: AppTest) -> None:
    at.number_input(key="fi_scenario_spending").set_value(50_000.0)
    at.number_input(key="fi_scenario_income").set_value(20_000.0)
    at.number_input(key="fi_scenario_return_rate").set_value(5.0)


def _set_fi_spending_and_adjust_source(at: AppTest) -> None:
    at.number_input(key="fi_scenario_spending").set_value(50_000.0)
    at.multiselect(key="fi_exclude_groups").set_value(["Food"])


def _clear_subscription_categories(at: AppTest) -> None:
    at.multiselect[0].set_value([])


def _show_all_subscription_lifecycles(at: AppTest) -> None:
    at.segmented_control[0].set_value("All merchants")


def _select_three_month_subscription_lookback(at: AppTest) -> None:
    at.selectbox[0].set_value("Last 3 months")


def _select_three_month_home_lookback(at: AppTest) -> None:
    at.segmented_control[0].set_value("3M")


def _switch_home_to_subscriptions(at: AppTest) -> None:
    at.switch_page("pages/5_Subscriptions.py")


def _select_food_spending_group(at: AppTest) -> None:
    at.segmented_control(key="spending_breakdown").set_value("Group")
    at.run()
    overview = next(table for table in at.dataframe if str(table.key).startswith("spending_overview_"))
    row = overview.value.index[overview.value["Entity"].eq("Food")].tolist()[0]
    at.session_state[str(overview.key)] = {
        "selection": {"rows": [row], "columns": [], "cells": []},
    }


def _select_food_and_february_spending(at: AppTest) -> None:
    _select_food_spending_group(at)
    at.run()
    at.session_state["spending_history_Group_Food_0"] = {
        "selection": {"spending_month_pick": [{"Month": "1995-02"}]},
    }


def _select_food_then_three_months(at: AppTest) -> None:
    _select_food_spending_group(at)
    at.run()
    at.segmented_control(key="spending_lookback").set_value("3M")


def _select_spending_category_breakdown(at: AppTest) -> None:
    at.segmented_control(key="spending_breakdown").set_value("Category")


def _select_all_spending(at: AppTest) -> None:
    at.segmented_control(key="spending_view").set_value("All spending")


def _exclude_all_spending_groups(at: AppTest) -> None:
    groups = at.multiselect(key="spending_discretionary_exclude_groups")
    groups.set_value(groups.options)


def _select_year_over_year_group(at: AppTest) -> None:
    at.segmented_control(key="year_over_year_view").set_value("Single group")


def _select_year_over_year_discretionary(at: AppTest) -> None:
    at.segmented_control(key="year_over_year_view").set_value("Discretionary spending")


def _add_groceries_to_year_over_year_utility(at: AppTest) -> None:
    at.multiselect(key="year_over_year_utility_bills_categories").set_value(["Electric", "Groceries"])


def _select_juniper_kitchen_merchant(at: AppTest) -> None:
    overview = next(table for table in at.dataframe if str(table.key).startswith("merchant_overview_"))
    row = overview.value.index[overview.value["Merchant"].eq("JUNIPER KITCHEN DINNER")].tolist()[0]
    at.session_state[str(overview.key)] = {
        "selection": {"rows": [row], "columns": [], "cells": []},
    }


def _select_juniper_kitchen_in_february(at: AppTest) -> None:
    _select_juniper_kitchen_merchant(at)
    at.run()
    at.selectbox(key="merchant_detail_month").set_value("1995-02")


def _set_discretionary_three_month_merchant_view(at: AppTest) -> None:
    at.segmented_control(key="merchant_lookback").set_value("3M")
    at.segmented_control(key="merchant_view").set_value("Discretionary")
    at.segmented_control(key="merchant_comparison").set_value("Last year")


def _set_all_merchant_view(at: AppTest) -> None:
    at.segmented_control(key="merchant_view").set_value("All spending")


def _include_all_groups_in_discretionary_merchant_view(at: AppTest) -> None:
    at.multiselect(key="spending_discretionary_exclude_groups").set_value([])


def _select_food_budget_group(at: AppTest) -> None:
    overview = next(table for table in at.dataframe if str(table.key).startswith("budget_group_performance_"))
    row = overview.value.index[overview.value["Entity"].eq("Food")].tolist()[0]
    at.session_state[str(overview.key)] = {
        "selection": {"rows": [row], "columns": [], "cells": []},
    }


def _select_food_then_previous_budget_month(at: AppTest) -> None:
    _select_food_budget_group(at)
    at.run()
    month = at.selectbox(key="budget_month")
    month.set_value(month.options[1])


def _exclude_groceries_from_budget(at: AppTest) -> None:
    at.multiselect(key="budget_exclude_categories").set_value(["Groceries"])


def _select_passed_data_health_check(at: AppTest) -> None:
    at.selectbox(key="data_health_check").set_value("uncategorized")


def _hide_values(at: AppTest) -> None:
    controls = [toggle for toggle in at.toggle if toggle.key == "hide_values"]
    if controls:
        controls[0].set_value(True)
    else:
        at.session_state["hide_values"] = True


def _make_app(
    page_file: str,
    make_full_dataset: FullDatasetFactory,
    patches: list[str],
    interact: Callable[[AppTest], None] | None = None,
) -> AppTest:
    """Build an ``AppTest`` for *page_file* with the given loader patches."""
    txns, bal, cats, accts = make_full_dataset()

    lookup: dict[str, object] = {
        "src.spreadsheet.load_transactions_data": txns,
        "src.spreadsheet.load_balance_history_data": bal,
        "src.spreadsheet.load_categories_data": cats,
        "src.spreadsheet.load_accounts_data": accts,
    }

    # Stack the patches — each target → the corresponding spreadsheet object
    ctx = [patch(target, return_value=lookup[target]) for target in patches]
    for c in ctx:
        c.start()

    try:
        at = AppTest.from_file(_PAGE_DIR / page_file, default_timeout=30)
        at.run()
        if interact is not None:
            interact(at)
            at.run()
    finally:
        for c in ctx:
            c.stop()

    return at


def _make_home_app_from_balance(balances: object) -> AppTest:
    """Run Home with an explicitly supplied balance spreadsheet."""
    with patch("src.spreadsheet.load_balance_history_data", return_value=balances):
        return AppTest.from_file(_PAGE_DIR / "../Home.py", default_timeout=30).run()


def _dataset_with_one_off_travel(
    make_full_dataset: FullDatasetFactory,
) -> SpreadsheetBundle:
    """Add a recent travel expense so calculation presets differ visibly."""
    bundle = make_full_dataset()
    transactions = bundle[0]
    travel = transactions.scrubbed_df.loc[transactions.scrubbed_df["Category"].eq("Shopping")].iloc[[0]].copy()
    travel["Category"] = "Travel"
    travel["Group"] = "Travel"
    travel["Amount"] = -1_200.0
    travel["Full Description"] = "one-off travel"
    latest = pd.to_datetime(transactions.scrubbed_df["Date"], utc=True).max()
    travel["Date"] = latest
    travel["Month"] = latest.strftime("%Y-%m")
    transactions.scrubbed_df = pd.concat(
        [transactions.scrubbed_df, travel],
        ignore_index=True,
    )
    return bundle


def _dataset_with_non_discretionary_expenses(
    make_full_dataset: FullDatasetFactory,
) -> SpreadsheetBundle:
    """Add large gift and tax expenses inside an otherwise discretionary group."""
    bundle = make_full_dataset()
    transactions = bundle[0]
    rows = transactions.scrubbed_df.loc[transactions.scrubbed_df["Category"].eq("Shopping")].iloc[[0, 1]].copy()
    rows["Category"] = ["Given Gift", "Tax Return Payment"]
    rows["Amount"] = [-8_000.0, -7_000.0]
    rows["Full Description"] = ["gift test merchant", "tax test merchant"]
    latest = pd.to_datetime(transactions.scrubbed_df["Date"], utc=True).max()
    rows["Date"] = latest
    rows["Month"] = latest.strftime("%Y-%m")
    transactions.scrubbed_df = pd.concat(
        [transactions.scrubbed_df, rows],
        ignore_index=True,
    )
    return bundle


def _table_with_columns(at: AppTest, columns: set[str]) -> pd.DataFrame:
    """Return the rendered dataframe containing all requested columns."""
    return next(table.value for table in at.dataframe if columns.issubset(table.value.columns))


def _chart_params(spec: object) -> list[Mapping[str, object]]:
    """Collect selection parameters from any level of a Vega-Lite spec."""
    if isinstance(spec, Mapping):
        params = [param for param in spec.get("params", []) if isinstance(param, Mapping)]
        return params + [param for child in spec.values() for param in _chart_params(child)]
    if isinstance(spec, list):
        return [param for child in spec for param in _chart_params(child)]
    return []


def _assert_chart_values_hidden(spec: Mapping[str, object]) -> None:
    """Assert that rendered charts mask numeric axis labels."""
    config = spec.get("config")
    assert isinstance(config, Mapping)
    axis = config.get("axis")
    assert isinstance(axis, Mapping)
    assert axis.get("labelExpr") == ("isNumber(datum.value) ? 'XXXXXXXX' : datum.label")


def _chart_marks(spec: object) -> list[object]:
    """Collect marks from every layer in a rendered Vega-Lite spec."""
    if isinstance(spec, Mapping):
        marks = [spec["mark"]] if "mark" in spec else []
        return marks + [mark for child in spec.values() for mark in _chart_marks(child)]
    if isinstance(spec, list):
        return [mark for child in spec for mark in _chart_marks(child)]
    return []


# ---------------------------------------------------------------------------
# Smoke tests — every page boots without error
# ---------------------------------------------------------------------------


@pytest.mark.uses_real_dates
class TestValuePrivacyMode:
    @pytest.mark.parametrize(
        ("page_file", "patches"),
        [
            ("../Home.py", ["src.spreadsheet.load_balance_history_data"]),
            ("1_Income_and_Savings.py", ["src.spreadsheet.load_transactions_data"]),
            ("2_Spending_by_Category.py", ["src.spreadsheet.load_transactions_data"]),
            ("3_Year_over_Year.py", ["src.spreadsheet.load_transactions_data"]),
            ("5_Subscriptions.py", ["src.spreadsheet.load_transactions_data"]),
            ("6_Merchant_Analysis.py", ["src.spreadsheet.load_transactions_data"]),
            (
                "7_Budget.py",
                [
                    "src.spreadsheet.load_transactions_data",
                    "src.spreadsheet.load_categories_data",
                ],
            ),
            ("8_Top_Transactions.py", ["src.spreadsheet.load_transactions_data"]),
            (
                "9_Financial_Independence.py",
                [
                    "src.spreadsheet.load_transactions_data",
                    "src.spreadsheet.load_balance_history_data",
                ],
            ),
            (
                "10_Data_Health.py",
                [
                    "src.spreadsheet.load_transactions_data",
                    "src.spreadsheet.load_balance_history_data",
                ],
            ),
        ],
    )
    def test_hides_rendered_values_on_every_page(
        self,
        page_file: str,
        patches: list[str],
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(page_file, make_full_dataset, patches, _hide_values)

        assert not at.exception
        for metric in at.metric:
            assert not _SENSITIVE_TEXT.search(f"{metric.value} {metric.delta}")
        for element_type in (
            "badge",
            "caption",
            "error",
            "info",
            "markdown",
            "success",
            "warning",
        ):
            for element in at.get(element_type):
                value = str(getattr(element, "value", ""))
                assert not _SENSITIVE_TEXT.search(value), (page_file, value)
        for expander in at.get("expander"):
            label = str(getattr(expander, "label", ""))
            assert not _SENSITIVE_TEXT.search(label), (page_file, label)
        for table in at.dataframe:
            configs = json.loads(table.proto.columns)
            for column in table.value.select_dtypes(include="number").columns:
                config = configs.get(str(column), {})
                type_config = config.get("type_config", {})
                if type_config.get("type") in {
                    "area_chart",
                    "bar_chart",
                    "line_chart",
                }:
                    continue
                if str(column) == "Year":
                    continue
                assert type_config.get("format") == _MASKED_VALUE, (
                    page_file,
                    str(column),
                )
        for chart in at.get("vega_lite_chart"):
            spec = json.loads(chart.proto.spec)
            assert _chart_marks(spec), page_file
            _assert_chart_values_hidden(spec)
            assert chart.proto.datasets, page_file

        if page_file == "../Home.py":
            assert at.toggle(key="hide_values").value is True
        if page_file == "9_Financial_Independence.py":
            runway = next(metric for metric in at.metric if metric.label == "Runway")
            assert runway.delta == f"Until portfolio reaches {_MASKED_VALUE}"


@pytest.mark.uses_real_dates
class TestHomeSmoke:
    def test_runs_without_exception(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "../Home.py",
            make_full_dataset,
            ["src.spreadsheet.load_balance_history_data"],
        )
        assert not at.exception
        assert at.title[0].value == "Accounts and net worth"
        assert {caption.value for caption in at.caption} == {
            "Latest balance update Apr 20, 1995",
            "Loaded 1995-04-20 00:00 UTC",
        }
        assert at.segmented_control[0].key == "home_balance_lookback"
        assert at.segmented_control[0].label == "Time frame"
        assert at.segmented_control[0].value == "1Y"
        assert at.segmented_control[0].options == ["3M", "6M", "1Y", "2Y", "5Y", "All"]
        assert _metric_labels(at)[:3] == ["Net worth", "Assets", "Liabilities"]
        assert all(metric.value.startswith("$") for metric in at.metric[:3])
        assert all(not metric.proto.chart_data for metric in at.metric[:3])
        assert [heading.value for heading in at.subheader] == [
            "Net worth history",
            "Account groups",
        ]
        charts = at.get("vega_lite_chart")
        assert len(charts) == 1
        assert all(field in charts[0].proto.spec for field in ["Assets", "Liabilities", "Net_Worth"])
        assert '"point"' not in charts[0].proto.spec
        metric_labels = [metric.label for metric in at.metric]
        assert "Accounts" not in metric_labels
        assert "Net-worth impact" not in metric_labels
        group_names = {
            "Retirement",
            "Liabilities",
            "Investments",
            "Savings",
            "Credit Cards",
        }
        group_metrics = [metric for metric in at.metric[3:] if metric.label in group_names]
        assert {metric.label for metric in group_metrics} == group_names
        assert all(metric.proto.chart_data for metric in group_metrics)
        assert len(at.metric) == 8
        assert len(at.dataframe) == len(group_names)
        assert all(table.key != "home_balance_groups" for table in at.dataframe)
        assert all(
            list(table.value.columns) == ["Account", "Institution", "Balance", "Change", "Last_Updated"]
            for table in at.dataframe
        )
        assert all(
            forbidden not in table.value.columns
            for table in at.dataframe
            for forbidden in ["Type", "Class", "Net_Contribution"]
        )

    def test_group_cards_summarize_accounts(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "../Home.py",
            make_full_dataset,
            ["src.spreadsheet.load_balance_history_data"],
        )

        assert not at.exception
        metric_values = _metric_values(at)
        assert "Investments" in [label for label, _, _ in metric_values]
        assert all(label not in {"Health Savings Account", "Brokerage Account"} for label, _, _ in metric_values)
        investment_details = next(
            table.value for table in at.dataframe if "Brokerage Account" in set(table.value["Account"])
        )
        assert set(investment_details["Account"]) == {
            "Brokerage Account",
            "Education Fund",
            "Health Savings Account",
        }
        assert investment_details["Balance"].sum() > 0
        assert investment_details["Change"].abs().sum() > 0
        investment_changes = investment_details.set_index("Account")["Change"]
        assert investment_changes.abs().gt(0).all()
        assert set(investment_details["Institution"]) == {"Northstar Investments"}

    def test_lookback_control_reruns_group_cards(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "../Home.py",
            make_full_dataset,
            ["src.spreadsheet.load_balance_history_data"],
            _select_three_month_home_lookback,
        )

        assert not at.exception
        assert at.segmented_control[0].value == "3M"
        assert at.metric[0].delta.endswith("over 3M")
        assert len(at.get("vega_lite_chart")) == 1
        assert "Investments" in _metric_labels(at)

    def test_navigation_switches_to_registered_page(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "../Home.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_balance_history_data",
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_categories_data",
            ],
            _switch_home_to_subscriptions,
        )

        assert not at.exception
        assert [heading.value for heading in at.subheader] == [
            "Active subscriptions",
            "Subscription history",
            "Potential subscriptions",
            "Inactive subscriptions",
        ]

    def test_empty_data_shows_getting_started_state(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        _, balances, _, _ = make_full_dataset()
        balances.scrubbed_df = balances.scrubbed_df.iloc[0:0].copy()
        at = _make_home_app_from_balance(balances)

        assert not at.exception
        assert at.info[0].value.startswith("No balance history is available yet")
        assert at.segmented_control[0].key == "home_balance_lookback"
        assert at.segmented_control[0].value == "1Y"
        assert not at.metric
        assert not at.get("vega_lite_chart")
        assert not at.dataframe


@pytest.mark.uses_real_dates
class TestHouseholdConfiguration:
    def test_household_config_changes_dashboard_defaults(
        self,
        make_full_dataset: FullDatasetFactory,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local_config = tmp_path / "local.toml"
        local_config.write_text(
            """
[reporting]
lookback_months = [1, 3, 18]
default_lookback_months = 3
[income_savings]
default_view = "actual"
[spending]
default_view = "all"
""".strip(),
            encoding="utf-8",
        )
        monkeypatch.setenv("PORTICO_CONFIG_PATH", str(local_config))
        clear_settings_cache()

        income = _make_app(
            "1_Income_and_Savings.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
        )
        spending = _make_app(
            "2_Spending_by_Category.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
        )

        income_lookback = income.segmented_control(key="income_lookback")
        assert (income_lookback.value, income_lookback.options) == ("3M", ["1M", "3M", "18M"])
        assert income.segmented_control(key="income_calculation_view").value == "Actual"
        assert spending.segmented_control(key="spending_lookback").value == "3M"
        assert spending.segmented_control(key="spending_view").value == "All spending"


@pytest.mark.uses_real_dates
class TestIncomeAndSavingsSmoke:
    def test_regular_view_renders_calculation_and_drilldown(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "1_Income_and_Savings.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
            ],
        )
        assert not at.exception
        assert at.title[0].value == "Income and savings"

        lookback = at.segmented_control(key="income_lookback")
        assert lookback.label == "Time frame"
        assert lookback.value == "1Y"
        assert lookback.options == ["3M", "6M", "1Y", "2Y"]

        calculation = at.segmented_control(key="income_calculation_view")
        assert calculation.label == "Calculation"
        assert calculation.value == "Regular"
        assert calculation.options == ["Regular", "Actual"]

        assert len(at.get("popover")) == 1
        assert len(at.multiselect) == 3
        assert len(at.toggle) == 2
        expense_groups = at.multiselect(key="income_regular_exclude_expense_groups")
        assert not expense_groups.disabled
        assert not at.toggle(key="income_regular_filter_large_income").value
        assert not at.toggle(key="income_regular_filter_large_expenses").value
        assert any(button.label == "Reset defaults" for button in at.button)
        assert at.number_input(key="income_savings_target_rate").value == 20

        assert _metric_labels(at)[:4] == [
            "Avg monthly income",
            "Avg monthly spending",
            "Avg monthly surplus",
            "Savings rate",
        ]

        charts = at.get("vega_lite_chart")
        assert len(charts) == 1
        assert list(charts[0].proto.selection_mode) == [
            "cash_month_pick",
            "rate_month_pick",
        ]
        spec = json.loads(charts[0].proto.spec)
        assert len(spec["vconcat"]) == 2
        month_axis = spec["vconcat"][1]["layer"][0]["encoding"]["x"]["axis"]
        month_ticks = month_axis["values"]
        assert len(month_ticks) == len(set(month_ticks)) == 12
        assert all(str(value).endswith("-01") for value in month_ticks)
        month_picks = {
            str(param.get("name")): param
            for param in _chart_params(spec)
            if param.get("name") in {"cash_month_pick", "rate_month_pick"}
        }
        assert set(month_picks) == {"cash_month_pick", "rate_month_pick"}
        for month_pick in month_picks.values():
            month_select = month_pick["select"]
            assert isinstance(month_select, Mapping)
            assert month_select["fields"] == ["Month_Key"]
            selection_views = month_pick["views"]
            assert isinstance(selection_views, list)
            assert len(selection_views) == 1
        assert all(
            field in charts[0].proto.spec
            for field in [
                "Income",
                "Series",
                "Amount",
                "Cash_Flow_Surplus",
                "Savings_Rate",
            ]
        )

        month_detail = at.selectbox(key="income_detail_month")
        assert month_detail.label == "Month detail"
        assert month_detail.value == "1995-04"
        assert [tab.label.split(" (")[0] for tab in at.tabs] == ["Included", "Excluded"]
        included = _table_with_columns(at, {"Description", "Amount", "Category"})
        assert not included.empty
        assert "Exclusion reason" not in included.columns
        monthly = _table_with_columns(at, {"Month", "Savings_Rate"})
        assert len(monthly) == 12

    @pytest.mark.parametrize(
        "select_chart",
        [
            _select_may_income_month_from_cash_chart,
            _select_may_income_month_from_rate_chart,
        ],
        ids=["cash-flow", "savings-rate"],
    )
    def test_chart_selection_drives_month_detail(
        self,
        make_full_dataset: FullDatasetFactory,
        select_chart: Callable[[AppTest], None],
    ) -> None:
        at = _make_app(
            "1_Income_and_Savings.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            select_chart,
        )

        assert not at.exception
        assert at.selectbox(key="income_detail_month").value == "1994-05"
        assert _metric_labels(at)[4:] == ["Income", "Spending", "Net cash flow", "Savings rate"]
        assert [tab.label.split(" (")[0] for tab in at.tabs] == ["Included", "Excluded"]
        included = _table_with_columns(at, {"Description", "Amount", "Category"})
        assert not included.empty

    def test_three_month_selection_updates_metrics(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "1_Income_and_Savings.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_three_months,
        )
        assert not at.exception
        assert at.segmented_control(key="income_lookback").value == "3M"
        assert _metric_labels(at)[:4] == [
            "Avg monthly income",
            "Avg monthly spending",
            "Avg monthly surplus",
            "Savings rate",
        ]
        monthly = _table_with_columns(at, {"Month", "Savings_Rate"})
        assert len(monthly) == 3

    def test_actual_view_includes_one_off_travel(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = _dataset_with_one_off_travel(make_full_dataset)
        at = _make_app(
            "1_Income_and_Savings.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
            _select_actual_income,
        )

        assert not at.exception
        assert at.segmented_control(key="income_calculation_view").value == "Actual"
        assert len(at.multiselect) == 3
        assert len(at.toggle) == 2
        assert at.multiselect(key="income_actual_exclude_income_categories").value == []
        assert at.multiselect(key="income_actual_exclude_expense_groups").value == []
        assert at.multiselect(key="income_actual_exclude_expense_categories").value == []
        assert _metric_labels(at)[:4] == [
            "Avg monthly income",
            "Avg monthly spending",
            "Avg monthly surplus",
            "Savings rate",
        ]
        assert [tab.label.split(" (")[0] for tab in at.tabs] == ["Included", "Excluded"]
        included = _table_with_columns(at, {"Description", "Amount", "Category"})
        assert "one-off travel" in included["Description"].values

    def test_regular_view_can_reinclude_excluded_travel_directly(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = _dataset_with_one_off_travel(make_full_dataset)
        at = _make_app(
            "1_Income_and_Savings.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
            _edit_regular_income_without_travel,
        )

        assert not at.exception
        assert at.segmented_control(key="income_calculation_view").value == "Regular"
        expense_groups = at.multiselect(key="income_regular_exclude_expense_groups")
        assert not expense_groups.disabled
        assert expense_groups.value == []
        assert _metric_labels(at)[:4] == [
            "Avg monthly income",
            "Avg monthly spending",
            "Avg monthly surplus",
            "Savings rate",
        ]
        assert [tab.label.split(" (")[0] for tab in at.tabs] == ["Included", "Excluded"]
        included = _table_with_columns(at, {"Description", "Amount", "Category"})
        assert included["Amount"].abs().is_monotonic_decreasing

    def test_regular_view_reset_restores_defaults(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = _dataset_with_one_off_travel(make_full_dataset)
        at = _make_app(
            "1_Income_and_Savings.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
            _edit_and_reset_regular_income,
        )

        assert not at.exception
        assert at.multiselect(key="income_regular_exclude_expense_groups").value == ["Travel", "Donations"]
        assert _metric_labels(at)[:4] == [
            "Avg monthly income",
            "Avg monthly spending",
            "Avg monthly surplus",
            "Savings rate",
        ]
        assert [tab.label.split(" (")[0] for tab in at.tabs] == ["Included", "Excluded"]

    def test_empty_data_shows_empty_state(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = make_full_dataset()
        transactions = bundle[0]
        transactions.scrubbed_df = transactions.scrubbed_df.iloc[0:0].copy()
        at = _make_app(
            "1_Income_and_Savings.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
        )

        assert not at.exception
        assert [message.value for message in at.info] == [
            "No categorized income or expense transactions fall in this period.",
        ]
        assert not at.metric
        assert not at.get("vega_lite_chart")
        assert not at.dataframe

    def test_all_excluded_period_keeps_auditable_detail(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = _dataset_with_one_off_travel(make_full_dataset)
        transactions = bundle[0]
        travel = transactions.scrubbed_df.loc[transactions.scrubbed_df["Full Description"].eq("one-off travel")]
        anchor = (
            transactions.scrubbed_df.loc[transactions.scrubbed_df["Type"].eq("Transfer")].sort_values("Date").iloc[[-1]]
        )
        transactions.scrubbed_df = pd.concat([travel, anchor], ignore_index=True)
        at = _make_app(
            "1_Income_and_Savings.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
        )

        assert not at.exception
        assert _metric_values(at)[:4] == [
            ("Avg monthly income", "$0", ""),
            ("Avg monthly spending", "$0", ""),
            ("Avg monthly surplus", "$0", ""),
            ("Savings rate", "—", ""),
        ]
        assert not at.get("vega_lite_chart")
        assert "All transactions in this period are excluded from this calculation." in {
            message.value for message in at.info
        }
        assert [tab.label for tab in at.tabs] == [
            "Included (0)",
            "Excluded (1)",
        ]
        excluded = _table_with_columns(at, {"Description", "Exclusion reason"})
        assert excluded["Description"].tolist() == ["one-off travel"]
        assert excluded["Exclusion reason"].tolist() == ["Excluded group: Travel"]


@pytest.mark.uses_real_dates
class TestSpendingByCategorySmoke:
    def test_time_frame_cannot_be_cleared(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "2_Spending_by_Category.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
        )

        assert not at.exception
        assert all(control.proto.required for control in at.segmented_control)

    def test_default_overview_and_detail(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "2_Spending_by_Category.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
            ],
        )
        assert not at.exception
        assert at.title[0].value == "Spending by category"
        toolbar_weights = [column.weight for column in at.columns[:4]]
        assert toolbar_weights == pytest.approx([value / 7.05 for value in (1.6, 1.6, 1.6, 2.25)])
        assert [(control.label, control.value, control.options) for control in at.segmented_control] == [
            ("Time frame", "1Y", ["3M", "6M", "1Y", "2Y"]),
            ("View", "Discretionary", ["All spending", "Discretionary"]),
            (
                "Compare with",
                "Previous period",
                ["Previous period", "Last year"],
            ),
            ("Breakdown", "Category", ["Group", "Category"]),
        ]
        assert _metric_labels(at) == [
            "Total spending",
            "Average monthly",
            "Change vs previous 12 months",
            "Spending",
            "Average monthly",
            "Share of view",
            "Change vs previous 12 months",
        ]
        charts = at.get("vega_lite_chart")
        assert len(charts) == 3
        trend_spec = json.loads(charts[0].proto.spec)
        ranking_spec = json.loads(charts[1].proto.spec)
        assert trend_spec["mark"]["type"] == "line"
        assert trend_spec["encoding"]["color"]["field"] == "Entity"
        assert ranking_spec["mark"]["type"] == "bar"
        assert ranking_spec["encoding"]["color"]["field"] == "Entity"
        top_labels = [label.value for label in at.markdown if "top" in label.value.lower()]
        assert top_labels[0] == "**Monthly trend · top 5**"
        assert top_labels[1].endswith("categories by spending**")
        assert [tab.label for tab in at.tabs] == [
            "Merchants",
            "Transactions",
        ]
        overview = next(table.value for table in at.dataframe if str(table.key).startswith("spending_overview_"))
        assert "Rent" not in set(overview["Entity"])
        assert "Electric" not in set(overview["Entity"])
        assert "Groceries" not in set(overview["Entity"])
        assert {"Restaurants", "Coffee", "Shopping"}.issubset(set(overview["Entity"]))
        assert overview["Spending"].sum() > 0

    def test_group_selection_drives_composition_and_transactions(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "2_Spending_by_Category.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_food_spending_group,
        )

        assert not at.exception
        assert at.session_state["spending_selected_group"] == "Food"
        assert "Food" in [subheader.value for subheader in at.subheader]
        assert _metric_labels(at)[3:] == [
            "Spending",
            "Average monthly",
            "Share of view",
            "Change vs previous 12 months",
        ]
        categories = at.dataframe[1].value
        assert {"Restaurants", "Coffee"}.issubset(set(categories["Entity"]))
        assert "Groceries" not in set(categories["Entity"])
        transactions = _table_with_columns(at, {"Description", "Spending", "Category"})
        assert transactions["Spending"].abs().is_monotonic_decreasing

    def test_chart_selection_scopes_all_detail_tabs_to_one_month(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "2_Spending_by_Category.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_food_and_february_spending,
        )

        assert not at.exception
        assert at.selectbox(key="spending_detail_month").value == "1995-02"
        categories = at.dataframe[1].value
        assert {"Restaurants", "Coffee"}.issubset(set(categories["Entity"]))
        transactions = _table_with_columns(at, {"Description", "Spending", "Category"})
        assert not transactions.empty
        assert pd.to_datetime(transactions["Date"]).dt.strftime("%Y-%m").eq("1995-02").all()

    def test_selected_entity_persists_by_identity_when_timeframe_changes(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "2_Spending_by_Category.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_food_then_three_months,
        )

        assert not at.exception
        assert at.segmented_control(key="spending_lookback").value == "3M"
        assert at.session_state["spending_selected_group"] == "Food"
        assert "Food" in [subheader.value for subheader in at.subheader]

    def test_category_breakdown_keeps_group_context(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "2_Spending_by_Category.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_spending_category_breakdown,
        )

        assert not at.exception
        assert at.segmented_control(key="spending_breakdown").value == "Category"
        overview = next(table.value for table in at.dataframe if str(table.key).startswith("spending_overview_"))
        assert {"Entity", "Group", "Spending", "Monthly_Trend"}.issubset(overview.columns)
        assert {"Coffee", "Restaurants"}.issubset(set(overview["Entity"]))
        assert set(overview.loc[overview["Entity"].isin(["Coffee", "Restaurants"]), "Group"]) == {"Food"}
        assert [tab.label for tab in at.tabs] == ["Merchants", "Transactions"]

    def test_all_excluded_view_stays_auditable(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "2_Spending_by_Category.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _exclude_all_spending_groups,
        )

        assert not at.exception
        assert not at.get("vega_lite_chart")
        assert "No spending is included in this view. Adjust the filters to continue." in {
            message.value for message in at.info
        }
        excluded = _table_with_columns(at, {"Description", "Exclusion reason"})
        assert len(excluded) > 0
        assert excluded["Exclusion reason"].str.startswith("Excluded group:").all()

    def test_discretionary_view_excludes_gifts_and_tax_payments(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = _dataset_with_non_discretionary_expenses(make_full_dataset)
        default_at = _make_app(
            "2_Spending_by_Category.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
        )

        assert not default_at.exception
        assert _metric_labels(default_at)[0] == "Total spending"
        overview = next(
            table.value for table in default_at.dataframe if str(table.key).startswith("spending_overview_")
        )
        assert not {"Given Gift", "Tax Return Payment"} & set(overview["Entity"])
        excluded = _table_with_columns(
            default_at,
            {"Description", "Exclusion reason"},
        ).set_index("Description")
        assert excluded.loc["gift test merchant", "Exclusion reason"] == ("Excluded category: Given Gift")
        assert excluded.loc["tax test merchant", "Exclusion reason"] == ("Excluded category: Tax Return Payment")

        all_at = _make_app(
            "2_Spending_by_Category.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
            _select_all_spending,
        )
        assert not all_at.exception
        all_overview = next(
            table.value for table in all_at.dataframe if str(table.key).startswith("spending_overview_")
        )
        assert {"Given Gift", "Tax Return Payment"} <= set(all_overview["Entity"])
        assert _metric_labels(all_at)[0] == "Total spending"
        assert all_at.metric[0].value != default_at.metric[0].value


@pytest.mark.uses_real_dates
class TestYearOverYearSmoke:
    def test_defaults_to_utility_bill_comparisons(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "3_Year_over_Year.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
            ],
        )
        assert not at.exception
        assert at.title[0].value == "Year over year"
        view = at.segmented_control(key="year_over_year_view")
        assert view.value == "Utility bills"
        assert view.options == [
            "Utility bills",
            "Discretionary spending",
            "Single category",
            "Single group",
        ]
        categories = at.multiselect(key="year_over_year_utility_bills_categories")
        assert {
            "Electric",
            "Natural Gas",
            "Internet",
            "Mobile Phone",
            "Rent",
            "Water & Sewer",
        }.issubset(set(categories.value))
        assert "Groceries" in categories.options
        assert not at.selectbox
        assert not at.tabs
        assert len(at.metric) == len(categories.value) * 3
        for index in range(0, len(at.metric), 3):
            assert _metric_labels(at)[index : index + 3] == [
                "1995 through April",
                "1994 through April",
                "Change",
            ]

        charts = at.get("vega_lite_chart")
        assert len(charts) == len(categories.value)
        spec = json.loads(charts[0].proto.spec)
        assert len(spec["layer"]) == 3
        line_encoding = spec["layer"][1]["encoding"]
        assert line_encoding["color"]["field"] == "Year_Label"
        assert line_encoding["color"]["scale"]["range"][0] == "#70A5EB"
        assert line_encoding["strokeWidth"]["condition"]["test"] == ("datum.Is_Current")
        assert len(at.dataframe) == len(categories.value) * 2
        totals_tables = [
            table.value for table in at.dataframe if {"Year", "Spending_Through_Month"}.issubset(table.value.columns)
        ]
        assert all(totals["Year"].is_monotonic_decreasing for totals in totals_tables)
        transaction_tables = [
            table.value
            for table in at.dataframe
            if {"Date", "Description", "Category", "Spending"}.issubset(table.value.columns)
        ]
        assert {
            category for transactions in transaction_tables for category in transactions["Category"].unique()
        } == set(categories.value)

    def test_discretionary_view_stacks_relevant_categories(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "3_Year_over_Year.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_year_over_year_discretionary,
        )

        assert not at.exception
        selected = at.multiselect(key="year_over_year_discretionary_spending_categories").value
        assert {"Coffee", "Restaurants", "Shopping"}.issubset(set(selected))
        assert "Rent" not in selected
        assert "Groceries" not in selected
        assert [subheader.value for subheader in at.subheader] == selected
        assert len(at.get("vega_lite_chart")) == len(selected)
        assert len(at.metric) == len(selected) * 3

    def test_discretionary_defaults_omit_gifts_and_tax_payments(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = _dataset_with_non_discretionary_expenses(make_full_dataset)
        at = _make_app(
            "3_Year_over_Year.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
            _select_year_over_year_discretionary,
        )

        assert not at.exception
        categories = at.multiselect(key="year_over_year_discretionary_spending_categories")
        assert {"Given Gift", "Tax Return Payment"} <= set(categories.options)
        assert not {"Given Gift", "Tax Return Payment"} & set(categories.value)

    def test_preset_can_include_any_other_category(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "3_Year_over_Year.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _add_groceries_to_year_over_year_utility,
        )

        assert not at.exception
        assert [subheader.value for subheader in at.subheader] == [
            "Electric",
            "Groceries",
        ]
        assert len(at.get("vega_lite_chart")) == 2

    def test_group_view_defaults_to_bills(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "3_Year_over_Year.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_year_over_year_group,
        )

        assert not at.exception
        assert at.segmented_control(key="year_over_year_view").value == "Single group"
        assert at.selectbox(key="year_over_year_group").value == "Bills"
        transactions = _table_with_columns(
            at,
            {"Date", "Description", "Group", "Spending"},
        )
        assert set(transactions["Group"]) == {"Bills"}

    def test_empty_expense_data_has_clear_state(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = make_full_dataset()
        transactions = bundle[0]
        transactions.scrubbed_df = transactions.scrubbed_df[~transactions.scrubbed_df["Type"].eq("Expense")].copy()
        at = _make_app(
            "3_Year_over_Year.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
        )

        assert not at.exception
        assert [message.value for message in at.info] == ["No expense transactions are available."]
        assert not at.metric
        assert not at.get("vega_lite_chart")


@pytest.mark.uses_real_dates
class TestSubscriptionsSmoke:
    def test_runs_without_exception(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "5_Subscriptions.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
            ],
        )
        assert not at.exception
        assert "Subscription categories come from Tiller." in at.caption[0].value
        assert "Activity stays Active until the full cadence-based inactivity window passes" in at.caption[0].value
        assert [widget.label for widget in at.multiselect] == [
            "Tiller subscription categories",
            "Additional discovery exclusions",
        ]
        assert {
            "Cloud Subscription",
            "Fitness Subscription",
            "Meal Kit Subscription",
            "Music Subscription",
            "News Subscription",
            "Streaming Subscription",
        }.issubset(set(at.multiselect[0].value))
        assert [widget.label for widget in at.selectbox] == ["Lookback"]
        assert at.selectbox[0].value == "Last 12 months"
        assert at.selectbox[0].key == "subscription_history_lookback"
        assert at.selectbox[0].options == [
            "Last 3 months",
            "Last 6 months",
            "Last 12 months",
            "Last 24 months",
            "All history",
        ]
        assert [widget.label for widget in at.segmented_control] == ["Timeline scope"]
        assert at.segmented_control[0].value == "Active and recent"
        assert at.segmented_control[0].key == "subscription_timeline_scope"
        assert at.segmented_control[0].options == ["Active and recent", "All merchants"]
        history_caption = next(caption.value for caption in at.caption if caption.value.startswith("Lookback affects"))
        assert (
            "Lookback affects these charts only; status, cadence, forecasts, and discovery use all available "
            "transactions." in history_caption
        )
        assert "Active and recent includes active merchants" in history_caption
        assert [heading.value for heading in at.subheader] == [
            "Active subscriptions",
            "Subscription history",
            "Potential subscriptions",
            "Inactive subscriptions",
        ]
        assert [label.value for label in at.markdown] == [
            "**Subscription lifecycles**",
            "**Actual spend and 3-month average**",
            "**Active subscription merchants**",
        ]
        charts = at.get("vega_lite_chart")
        assert len(charts) == 3
        assert "Episode_Start" in charts[0].proto.spec
        assert "Needs review" not in charts[0].proto.spec
        assert "Actual_Spend" in charts[1].proto.spec
        assert "Active_Merchants" in charts[2].proto.spec
        assert at.dataframe[0].key == "active_subscriptions"
        assert {
            "CLOUDBOX STORAGE PLAN",
            "FIT CLUB MEMBERSHIP",
            "FLICKER STREAM MEMBERSHIP",
            "SOUNDWAVE MUSIC PLAN",
        }.issubset(set(at.dataframe[0].value["Merchant"]))
        assert at.dataframe[1].key == "subscription_candidates"
        assert "Evidence" in at.dataframe[1].value
        assert _metric_labels(at) == [
            "Active subscriptions",
            "Estimated monthly run rate",
            "Spent in the last 12 months",
            "12-month change",
        ]
        assert at.metric[0].value == "4"

    def test_all_merchants_timeline_scope_keeps_lifecycle_chart(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "5_Subscriptions.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _show_all_subscription_lifecycles,
        )
        assert not at.exception
        assert at.selectbox[0].value == "Last 12 months"
        assert at.segmented_control[0].value == "All merchants"
        charts = at.get("vega_lite_chart")
        assert len(charts) == 3
        assert "Episode_Start" in charts[0].proto.spec

    def test_lookback_does_not_change_full_history_metrics(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "5_Subscriptions.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_three_month_subscription_lookback,
        )
        assert not at.exception
        assert at.selectbox[0].value == "Last 3 months"
        assert _metric_labels(at) == [
            "Active subscriptions",
            "Estimated monthly run rate",
            "Spent in the last 12 months",
            "12-month change",
        ]
        assert at.metric[0].value == "4"
        charts = at.get("vega_lite_chart")
        assert len(charts) == 3

    def test_clearing_subscription_categories_updates_metrics(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "5_Subscriptions.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _clear_subscription_categories,
        )
        assert not at.exception
        assert _metric_values(at) == [
            ("Active subscriptions", "0", ""),
            ("Estimated monthly run rate", "$0.00", ""),
            ("Spent in the last 12 months", "$0.00", ""),
            ("12-month change", "Not available", ""),
        ]
        assert [message.value for message in at.info] == [
            "No active subscriptions are present in the selected Tiller categories.",
            "Select at least one Tiller subscription category to see spending history.",
        ]
        assert not at.selectbox
        assert not at.segmented_control
        assert not at.get("vega_lite_chart")
        assert at.dataframe[0].key == "subscription_candidates"


@pytest.mark.uses_real_dates
class TestMerchantAnalysisSmoke:
    def test_default_overview_and_detail(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "6_Merchant_Analysis.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
            ],
        )
        assert not at.exception
        assert at.title[0].value == "Spending by merchant"
        toolbar_weights = [column.weight for column in at.columns[:4]]
        assert toolbar_weights == pytest.approx([value / 7.05 for value in (1.6, 1.6, 1.6, 2.25)])
        assert all(control.proto.required for control in at.segmented_control)
        assert _metric_labels(at) == [
            "Total spending",
            "Average monthly",
            "Merchants",
            "At repeat merchants",
            "Spending",
            "Change vs previous 12 months",
            "Transactions",
            "Average purchase",
        ]
        assert at.segmented_control(key="merchant_lookback").value == "1Y"
        assert at.segmented_control(key="merchant_view").value == "Discretionary"
        assert at.segmented_control(key="merchant_comparison").value == "Previous period"
        overview = next(table.value for table in at.dataframe if str(table.key).startswith("merchant_overview_"))
        assert not overview["Merchant"].str.contains("RENT", case=False).any()
        assert "JUNIPER KITCHEN DINNER" in set(overview["Merchant"])
        assert {
            "Merchant",
            "Spending",
            "Share",
            "Change",
            "Transactions",
            "Monthly_Trend",
        }.issubset(overview.columns)
        assert [tab.label for tab in at.tabs] == [
            "Breakdown",
            "Descriptions",
            "Transactions",
        ]
        assert at.selectbox(key="merchant_detail_month").value == "All months"

        charts = at.get("vega_lite_chart")
        assert len(charts) == 2
        ranking_spec = json.loads(charts[0].proto.spec)
        history_spec = json.loads(charts[1].proto.spec)
        assert ranking_spec["mark"]["type"] == "bar"
        assert ranking_spec["encoding"]["y"]["field"] == "Merchant"
        assert "params" not in ranking_spec
        assert len(history_spec["layer"]) == 2
        assert {layer["mark"]["type"] for layer in history_spec["layer"]} == {
            "bar",
            "line",
        }
        assert "params" not in history_spec

    def test_selecting_merchant_updates_detail_and_transactions(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "6_Merchant_Analysis.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_juniper_kitchen_merchant,
        )

        assert not at.exception
        assert at.session_state["merchant_selected_name"] == "JUNIPER KITCHEN DINNER"
        assert any(subheader.value == "JUNIPER KITCHEN DINNER" for subheader in at.subheader)
        transactions = next(
            table.value
            for table in at.dataframe
            if {"Date", "Description", "Category", "Group", "Account", "Spending"} <= set(table.value.columns)
        )
        assert not transactions.empty
        assert transactions["Description"].str.contains("JUNIPER KITCHEN", case=False).all()

    def test_detail_month_scopes_transactions(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "6_Merchant_Analysis.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_juniper_kitchen_in_february,
        )

        assert not at.exception
        assert at.selectbox(key="merchant_detail_month").value == "1995-02"
        transactions = next(
            table.value
            for table in at.dataframe
            if {"Date", "Description", "Category", "Group", "Account", "Spending"} <= set(table.value.columns)
        )
        assert not transactions.empty
        assert set(pd.to_datetime(transactions["Date"]).dt.strftime("%Y-%m")) == {"1995-02"}

    def test_discretionary_and_comparison_controls_rebuild_inventory(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "6_Merchant_Analysis.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _set_discretionary_three_month_merchant_view,
        )

        assert not at.exception
        assert at.segmented_control(key="merchant_lookback").value == "3M"
        assert at.segmented_control(key="merchant_view").value == "Discretionary"
        assert at.segmented_control(key="merchant_comparison").value == "Last year"
        assert "Bills" in at.multiselect(key="spending_discretionary_exclude_groups").value
        overview = next(table.value for table in at.dataframe if str(table.key).startswith("merchant_overview_"))
        assert not overview.empty
        assert "JUNIPER KITCHEN DINNER" in overview["Merchant"].values

    def test_all_spending_view_restores_excluded_merchants(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "6_Merchant_Analysis.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _set_all_merchant_view,
        )

        assert not at.exception
        assert at.segmented_control(key="merchant_view").value == "All spending"
        assert _metric_labels(at)[:4] == [
            "Total spending",
            "Average monthly",
            "Merchants",
            "At repeat merchants",
        ]

    def test_discretionary_filters_are_editable_in_place(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "6_Merchant_Analysis.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _include_all_groups_in_discretionary_merchant_view,
        )

        assert not at.exception
        assert at.segmented_control(key="merchant_view").value == "Discretionary"
        assert at.multiselect(key="spending_discretionary_exclude_groups").value == []
        overview = next(table.value for table in at.dataframe if str(table.key).startswith("merchant_overview_"))
        assert "CITY ELECTRIC SERVICE" in overview["Merchant"].values

    def test_discretionary_view_excludes_gift_and_tax_merchants(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = _dataset_with_non_discretionary_expenses(make_full_dataset)
        default_at = _make_app(
            "6_Merchant_Analysis.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
        )

        assert not default_at.exception
        assert _metric_labels(default_at)[0] == "Total spending"
        overview = next(
            table.value for table in default_at.dataframe if str(table.key).startswith("merchant_overview_")
        )
        assert not {"GIFT TEST MERCHANT", "TAX TEST MERCHANT"} & set(overview["Merchant"])

        all_at = _make_app(
            "6_Merchant_Analysis.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
            _set_all_merchant_view,
        )
        assert not all_at.exception
        all_overview = next(
            table.value for table in all_at.dataframe if str(table.key).startswith("merchant_overview_")
        )
        assert {"GIFT TEST MERCHANT", "TAX TEST MERCHANT"} <= set(all_overview["Merchant"])
        assert _metric_labels(all_at)[0] == "Total spending"
        assert all_at.metric[0].value != default_at.metric[0].value


@pytest.mark.uses_real_dates
class TestBudgetSmoke:
    def test_runs_without_exception(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "7_Budget.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_categories_data",
            ],
        )
        assert not at.exception
        assert _metric_labels(at) == [
            "Spending",
            "Remaining",
            "Budget used",
            "Outside the plan",
            "Spent",
            "Budget",
            "Typical month",
            "Outside the plan",
            "YTD spending",
            "YTD budget",
            "YTD remaining",
            "YTD used",
        ]
        assert at.title[0].value == "Budget"
        assert at.selectbox(key="budget_month").value == "1995-04"
        assert len(at.get("popover")) == 1
        assert at.multiselect(key="budget_exclude_groups").value == []
        assert at.multiselect(key="budget_exclude_categories").value == []
        assert len(at.get("vega_lite_chart")) == 3

        overview = next(table for table in at.dataframe if str(table.key).startswith("budget_group_performance_"))
        assert list(overview.value.columns) == [
            "Entity",
            "Status",
            "Budget",
            "Spent",
            "Remaining",
            "Pct_Used",
            "Vs_Typical",
            "Outside_Plan",
            "Success_Rate",
            "Trend",
        ]
        assert {"Bills", "Food", "Housing", "Shopping"}.issubset(set(overview.value["Entity"]))

        pulse_spec = json.loads(at.get("vega_lite_chart")[0].proto.spec)
        assert [layer["mark"]["type"] for layer in pulse_spec["layer"]] == [
            "bar",
            "tick",
            "point",
        ]
        assert pulse_spec["layer"][2]["encoding"]["x"]["field"] == "Typical_Spend"

    def test_adjustments_change_the_budget_scope(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "7_Budget.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_categories_data",
            ],
            _exclude_groceries_from_budget,
        )

        assert not at.exception
        assert at.multiselect(key="budget_exclude_categories").value == ["Groceries"]
        assert at.metric[0].label == "Spending"

    def test_group_selection_survives_month_change(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "7_Budget.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_categories_data",
            ],
            _select_food_then_previous_budget_month,
        )

        assert not at.exception
        assert at.session_state["budget_selected_group"] == "Food"
        assert any(subheader.value == "Food" for subheader in at.subheader)
        assert [metric.label for metric in at.metric[4:8]] == [
            "Spent",
            "Budget",
            "Typical month",
            "Outside the plan",
        ]
        transactions = _table_with_columns(
            at,
            {"Date", "Category", "Description", "Account", "Net spend"},
        )
        assert set(transactions["Category"]) <= {
            "Coffee",
            "Groceries",
            "Meal Kit Subscription",
            "Restaurants",
        }

    def test_empty_transaction_data_has_clear_state(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = make_full_dataset()
        bundle[0].scrubbed_df = bundle[0].scrubbed_df.iloc[0:0].copy()
        at = _make_app(
            "7_Budget.py",
            lambda: bundle,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_categories_data",
            ],
        )

        assert not at.exception
        assert [message.value for message in at.info] == ["No transaction data is available."]
        assert not at.metric


@pytest.mark.uses_real_dates
class TestTopTransactionsSmoke:
    def test_runs_without_exception(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "8_Top_Transactions.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
            ],
        )
        assert not at.exception
        assert at.title[0].value == "Transactions"
        assert [(control.label, control.value, control.options) for control in at.segmented_control] == [
            ("Time frame", "1Y", ["3M", "6M", "1Y", "2Y", "All"]),
            ("Type", "All", ["All", "Expenses", "Income", "Transfers"]),
            (
                "Focus",
                "All transactions",
                [
                    "All transactions",
                    "Largest",
                    "One-off merchants",
                    "Unusual amounts",
                    "Refunds / reversals",
                ],
            ),
            (
                "Summarize by",
                "Group",
                ["Group", "Category", "Merchant", "Account", "Type"],
            ),
        ]
        assert _metric_labels(at) == ["Transactions", "Money out", "Money in", "Net amount"]
        assert len(at.get("popover")) == 1
        assert [widget.value for widget in at.multiselect] == [[], [], []]
        assert at.number_input(key="top_transactions_minimum").value == 0.0
        assert at.number_input(key="top_transactions_maximum").value is None
        assert at.number_input(key="top_transactions_largest_count").value == 25
        assert len(at.get("download_button")) == 1

        charts = at.get("vega_lite_chart")
        assert len(charts) == 2
        timeline_spec = json.loads(charts[0].proto.spec)
        breakdown_spec = json.loads(charts[1].proto.spec)
        assert {layer["mark"]["type"] for layer in timeline_spec["layer"]} == {
            "rule",
            "circle",
        }
        assert "params" not in timeline_spec
        assert breakdown_spec["mark"]["type"] == "bar"
        assert breakdown_spec["encoding"]["y"]["field"] == "Entity"

        transactions = _table_with_columns(
            at,
            {"Date", "Description", "Amount", "Merchant", "Flags"},
        )
        assert len(transactions) == int(at.metric[0].value.replace(",", ""))
        assert transactions["Amount"].abs().is_monotonic_decreasing

    def test_top_ten_selection_updates_metrics(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "8_Top_Transactions.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_top_ten,
        )
        assert not at.exception
        assert at.segmented_control(key="top_transactions_focus").value == "Largest"
        assert _metric_labels(at) == ["Transactions", "Money out", "Money in", "Net amount"]
        assert at.metric[0].value == "10"

    def test_one_off_focus_returns_only_single_occurrence_merchants(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "8_Top_Transactions.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_one_off_transactions,
        )

        assert not at.exception
        transactions = _table_with_columns(at, {"Occurrences", "Flags"})
        assert not transactions.empty
        assert transactions["Occurrences"].eq(1).all()
        assert transactions["Flags"].str.contains("One-off").all()

    def test_type_and_search_filters_scope_every_result(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        transfers = _make_app(
            "8_Top_Transactions.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _select_transfer_transactions,
        )
        assert not transfers.exception
        transfer_rows = _table_with_columns(transfers, {"Type", "Amount"})
        assert set(transfer_rows["Type"]) == {"Transfer"}

        searched = _make_app(
            "8_Top_Transactions.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _search_market_basket_transactions,
        )
        assert not searched.exception
        searched_rows = _table_with_columns(
            searched,
            {"Description", "Merchant", "Amount"},
        )
        assert (
            searched_rows["Description"]
            .str.contains(
                "market basket",
                case=False,
            )
            .all()
        )

    def test_empty_search_has_clear_state(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "8_Top_Transactions.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _search_for_missing_transactions,
        )

        assert not at.exception
        assert [message.value for message in at.info] == ["No transactions match this view."]
        assert not at.metric
        assert not at.get("vega_lite_chart")
        assert not at.dataframe

    def test_maximum_amount_limits_every_result(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "8_Top_Transactions.py",
            make_full_dataset,
            ["src.spreadsheet.load_transactions_data"],
            _limit_transaction_maximum,
        )

        assert not at.exception
        transactions = _table_with_columns(at, {"Amount"})
        assert transactions["Amount"].abs().max() <= 1_000.0
        timeline_spec = json.loads(at.get("vega_lite_chart")[0].proto.spec)
        assert timeline_spec["layer"][1]["encoding"]["y"]["field"] == "Amount"

    def test_empty_transaction_data_has_clear_state(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = make_full_dataset()
        bundle[0].scrubbed_df = bundle[0].scrubbed_df.iloc[0:0].copy()
        at = _make_app(
            "8_Top_Transactions.py",
            lambda: bundle,
            ["src.spreadsheet.load_transactions_data"],
        )

        assert not at.exception
        assert [message.value for message in at.info] == ["No transactions are available."]
        assert not at.segmented_control
        assert not at.metric
        assert not at.dataframe


@pytest.mark.uses_real_dates
class TestFinancialIndependenceSmoke:
    def test_runs_without_exception(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "9_Financial_Independence.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_balance_history_data",
            ],
        )
        assert not at.exception
        assert _metric_labels(at) == ["Runway", "Annual gap", "Net portfolio spending", "FI target"]
        assert at.title[0].value == "Financial independence"
        assert len(at.get("popover")) == 1
        assert at.multiselect(key="fi_include_accounts").value
        assert at.selectbox(key="fi_spending_lookback").value == 12
        scenario_values = {
            widget.label: widget.value for widget in at.number_input if str(widget.key).startswith("fi_scenario_")
        }
        investable_assets = scenario_values["Investable assets"]
        annual_spending = scenario_values["Annual spending"]
        assert isinstance(investable_assets, int | float)
        assert isinstance(annual_spending, int | float)
        assert investable_assets > 0
        assert annual_spending > 0
        assert scenario_values["Annual earned income"] == 0.0
        assert scenario_values["Expected real return (%)"] == 7.0
        assert scenario_values["Withdrawal rate (%)"] == 4.0
        assert scenario_values["Projection horizon"] == 50
        charts = at.get("vega_lite_chart")
        assert len(charts) == 4
        projection = json.loads(charts[0].proto.spec)
        sensitivity = json.loads(charts[2].proto.spec)
        assert {layer["mark"]["type"] for layer in projection["layer"]} == {
            "area",
            "line",
            "point",
            "rule",
        }
        assert sensitivity["layer"][0]["mark"]["type"] == "rect"
        assert sensitivity["layer"][1]["mark"]["type"] == "text"

    def test_return_rate_scenario_updates_fi_metrics(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "9_Financial_Independence.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_balance_history_data",
            ],
            _set_fi_scenario,
        )
        assert not at.exception
        assert _metric_labels(at) == ["Runway", "Annual gap", "Net portfolio spending", "FI target"]
        assert at.number_input(key="fi_scenario_spending").value == 50_000.0
        assert at.number_input(key="fi_scenario_income").value == 20_000.0
        assert at.number_input(key="fi_scenario_return_rate").value == 5.0

    def test_custom_scenario_survives_source_filter_changes(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "9_Financial_Independence.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_balance_history_data",
            ],
            _set_fi_spending_and_adjust_source,
        )

        assert not at.exception
        assert at.multiselect(key="fi_exclude_groups").value == ["Food"]
        assert at.number_input(key="fi_scenario_spending").value == 50_000.0

    def test_empty_source_data_has_clear_state(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = make_full_dataset()
        bundle[0].scrubbed_df = bundle[0].scrubbed_df.iloc[0:0].copy()
        at = _make_app(
            "9_Financial_Independence.py",
            lambda: bundle,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_balance_history_data",
            ],
        )

        assert not at.exception
        assert [message.value for message in at.info] == [
            "Transaction and balance history are required for this analysis."
        ]
        assert not at.metric


@pytest.mark.uses_real_dates
class TestDataHealthSmoke:
    def test_runs_without_exception(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        at = _make_app(
            "10_Data_Health.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_balance_history_data",
            ],
        )
        assert not at.exception
        assert at.title[0].value == "Data health"
        assert _metric_labels(at) == [
            "Needs attention",
            "Review items",
            "Transactions through",
            "Balances through",
        ]
        assert at.metric[1].value == "3"
        assert at.metric[2].delta == "986 rows · Updated today"
        assert at.metric[3].delta == "12 accounts · Updated today"
        assert at.selectbox(key="data_health_check").value == "duplicates"
        queue = at.dataframe[0].value
        assert queue[["Check", "Status", "Findings"]].to_dict("records") == [
            {"Check": "Missing classifications", "Status": "Passed", "Findings": 0},
            {"Check": "Missing transaction details", "Status": "Passed", "Findings": 0},
            {"Check": "Account mapping gaps", "Status": "Passed", "Findings": 0},
            {"Check": "Stale balance accounts", "Status": "Passed", "Findings": 0},
            {"Check": "Potential duplicate transactions", "Status": "Review", "Findings": 3},
            {"Check": "Refunds and income reversals", "Status": "Passed", "Findings": 0},
        ]
        assert len(at.dataframe[1].value) == 3
        assert at.dataframe[2].value["Total_Amount"].sum() == pytest.approx(249.49)
        assert at.slider(key="data_health_stale_days").value == 7
        assert at.number_input(key="data_health_duplicate_days").value == 1
        assert at.number_input(key="data_health_duplicate_minimum").value == 10.0

        passed = _make_app(
            "10_Data_Health.py",
            make_full_dataset,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_balance_history_data",
            ],
            _select_passed_data_health_check,
        )
        assert not passed.exception
        assert any("No findings for this check" in success.value for success in passed.success)

    def test_empty_source_data_has_clear_state(
        self,
        make_full_dataset: FullDatasetFactory,
    ) -> None:
        bundle = make_full_dataset()
        bundle[0].scrubbed_df = bundle[0].scrubbed_df.iloc[0:0].copy()
        bundle[1].scrubbed_df = bundle[1].scrubbed_df.iloc[0:0].copy()
        at = _make_app(
            "10_Data_Health.py",
            lambda: bundle,
            [
                "src.spreadsheet.load_transactions_data",
                "src.spreadsheet.load_balance_history_data",
            ],
        )

        assert not at.exception
        assert [message.value for message in at.info] == ["No transaction or balance data is available."]
        assert not at.metric
