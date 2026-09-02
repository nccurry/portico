from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.config import ConfigError, load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULTS = PROJECT_ROOT / "config" / "defaults.toml"


def test_defaults_match_the_public_application_profile(tmp_path: Path) -> None:
    settings = load_settings(defaults_path=DEFAULTS, local_path=tmp_path / "missing.toml", environ={})

    assert settings.data.mode == "google_sheets"
    assert settings.data.demo_reference_date == datetime(1995, 4, 20, tzinfo=UTC)
    assert settings.reporting.lookback_months == (3, 6, 12, 24)
    assert settings.reporting.default_lookback_months == 12
    assert settings.thresholds.expense == 3000
    assert settings.income_savings.default_view == "regular"
    assert settings.spending.default_view == "discretionary"
    assert [view.key for view in settings.spending.views] == ["all", "discretionary"]
    assert settings.spending.view("discretionary").exclude_transactions_like == ()
    assert settings.subscriptions.known_category_terms == ("subscription",)
    assert settings.subscriptions.minimum_confidence == 80
    assert settings.subscriptions.stale_after_days == 45
    assert settings.year_over_year.utility_group_terms == ("bill", "housing")
    assert "electric" in settings.year_over_year.utility_category_terms
    assert settings.budget.history_months == 12
    assert settings.data_health.stale_account_days == 7
    assert settings.data_health.duplicate_require_same_account
    assert not settings.data_health.duplicate_require_same_category
    assert settings.data_health.duplicate_require_same_description
    assert settings.weekly_summary.average_weeks == 8
    assert settings.weekly_summary.rolling_weeks == 4
    assert settings.weekly_summary.top_merchant_count == 3
    assert settings.income_savings.target_rate == 20
    assert settings.financial_independence.included_groups == (
        "Savings",
        "Investments",
        "Retirement",
    )
    assert settings.financial_independence.target_amount == 5_000_000
    assert settings.financial_safety.emergency_fund_target_months == 6
    assert settings.financial_safety.emergency_fund_included_groups == ("Savings",)
    assert settings.financial_safety.emergency_fund_exclude_groups == ("Travel", "Donations")
    assert settings.financial_safety.debt_included_groups == ("Credit Cards", "Home Loan", "Auto Loan")
    assert settings.financial_safety.debt_baseline_date is None


def test_local_file_and_environment_override_defaults(tmp_path: Path) -> None:
    local = tmp_path / "local.toml"
    local.write_text("[thresholds]\nexpense = 1250\n", encoding="utf-8")

    settings = load_settings(
        defaults_path=DEFAULTS,
        local_path=local,
        environ={"PORTICO_DATA_SOURCE": "demo"},
        project_root=PROJECT_ROOT,
    )

    assert settings.data.is_demo
    assert settings.thresholds.expense == 1250


def test_household_report_defaults_can_be_overridden(tmp_path: Path) -> None:
    local = tmp_path / "local.toml"
    local.write_text(
        """
[reporting]
lookback_months = [1, 3, 18]
default_lookback_months = 3
[spending]
default_view = "all"
[spending.views.discretionary]
exclude_transactions_like = ["IRS", "CHECK"]
[budget]
history_months = 18
[data_health]
stale_account_days = 30
[financial_safety]
emergency_fund_target_months = 4
debt_baseline_date = 2024-01-15
[subscriptions]
minimum_confidence = 90
[weekly_summary]
average_weeks = 12
rolling_weeks = 6
top_merchant_count = 5
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(defaults_path=DEFAULTS, local_path=local, environ={}, project_root=PROJECT_ROOT)

    assert settings.reporting.lookback_months == (1, 3, 18)
    assert settings.reporting.default_lookback_months == 3
    assert settings.spending.default_view == "all"
    assert settings.spending.view("discretionary").exclude_transactions_like == ("IRS", "CHECK")
    assert settings.budget.history_months == 18
    assert settings.data_health.stale_account_days == 30
    assert settings.financial_safety.emergency_fund_target_months == 4
    assert settings.financial_safety.debt_baseline_date == datetime(2024, 1, 15).date()
    assert settings.subscriptions.minimum_confidence == 90
    assert settings.weekly_summary.average_weeks == 12
    assert settings.weekly_summary.rolling_weeks == 6
    assert settings.weekly_summary.top_merchant_count == 5


def test_spending_views_support_configured_labels_and_filters(tmp_path: Path) -> None:
    local = tmp_path / "local.toml"
    local.write_text(
        """
[spending]
default_view = "routine"
[spending.views.routine]
label = "Routine purchases"
include_groups = ["Food", "Shopping"]
include_transactions_like = ["Coffee"]
exclude_transactions_like = ["Gift card"]
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(defaults_path=DEFAULTS, local_path=local, environ={}, project_root=PROJECT_ROOT)

    assert settings.spending.default_view == "routine"
    assert settings.spending.view("routine").label == "Routine purchases"
    assert settings.spending.view("routine").include_groups == ("Food", "Shopping")
    assert settings.spending.view("routine").include_transactions_like == ("Coffee",)
    assert settings.spending.view("routine").exclude_transactions_like == ("Gift card",)


def test_unknown_local_key_is_rejected(tmp_path: Path) -> None:
    local = tmp_path / "local.toml"
    local.write_text("[thresholds]\nexpnese = 1250\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"Unknown key.*expnese"):
        load_settings(defaults_path=DEFAULTS, local_path=local, environ={}, project_root=PROJECT_ROOT)


def test_unknown_spending_view_key_is_rejected(tmp_path: Path) -> None:
    local = tmp_path / "local.toml"
    local.write_text(
        '[spending.views.discretionary]\nexclude_merchants_like = ["IRS"]\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match=r"Unknown key.*exclude_merchants_like"):
        load_settings(defaults_path=DEFAULTS, local_path=local, environ={}, project_root=PROJECT_ROOT)


def test_invalid_toml_is_rejected(tmp_path: Path) -> None:
    local = tmp_path / "local.toml"
    local.write_text("[thresholds\nexpense = 1250", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"Invalid TOML in local\.toml"):
        load_settings(defaults_path=DEFAULTS, local_path=local, environ={}, project_root=PROJECT_ROOT)


def test_unreadable_local_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Could not read configuration file"):
        load_settings(defaults_path=DEFAULTS, local_path=tmp_path, environ={}, project_root=PROJECT_ROOT)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ('[thresholds]\nexpense = "high"\n', "expense must be an integer"),
        ("[thresholds]\nexpense = 999\n", "expense must be between 1000 and 100000"),
        ("[thresholds]\nincome = 100001\n", "income must be between 5000 and 100000"),
        ("[thresholds]\nduplicate_minimum = 1001\n", "duplicate_minimum must be between 0 and 1000"),
        ("[thresholds]\nduplicate_days = 8\n", "duplicate_days must be between 0 and 7"),
        ("[income_savings]\ntarget_rate = 101\n", "target_rate must be between 0 and 100"),
        (
            "[financial_independence]\nexpected_return_rate = -1\n",
            "expected_return_rate must be between 0 and 20",
        ),
        (
            "[financial_independence]\nwithdrawal_rate = 10.5\n",
            "withdrawal_rate must be between 0.5 and 10",
        ),
        (
            "[financial_independence]\ntarget_amount = 0\n",
            r"target_amount must be between 1 and 1e\+08",
        ),
        (
            "[reporting]\nlookback_months = [12, 3]\n",
            "lookback_months must be in ascending order",
        ),
        (
            "[reporting]\ndefault_lookback_months = 5\n",
            "default_lookback_months must be included in lookback_months",
        ),
        (
            '[spending]\ndefault_view = "sometimes"\n',
            "default_view must name a configured spending view",
        ),
        (
            "[subscriptions]\nminimum_confidence = 69\n",
            "minimum_confidence must be between 70 and 100",
        ),
        (
            "[budget]\nhistory_months = 0\n",
            "history_months must be between 1 and 120",
        ),
        (
            "[financial_safety]\nemergency_fund_target_months = 0\n",
            "emergency_fund_target_months must be between 1 and 24",
        ),
        (
            '[financial_safety]\ndebt_baseline_date = "not-a-date"\n',
            "debt_baseline_date must be an ISO 8601 date or an empty string",
        ),
        (
            "[weekly_summary]\nrolling_weeks = 53\n",
            "rolling_weeks must be between 1 and 52",
        ),
        (
            "[data_health]\nduplicate_require_same_account = 1\n",
            "duplicate_require_same_account must be true or false",
        ),
        (
            '[data]\ndemo_reference_date = "not-a-date"\n',
            "demo_reference_date must be an ISO 8601 date and time",
        ),
        (
            '[data]\ndemo_reference_date = "1995-04-20T00:00:00"\n',
            "demo_reference_date must include a timezone",
        ),
    ],
)
def test_invalid_values_are_rejected(tmp_path: Path, document: str, message: str) -> None:
    local = tmp_path / "local.toml"
    local.write_text(document, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_settings(defaults_path=DEFAULTS, local_path=local, environ={}, project_root=PROJECT_ROOT)


def test_demo_directory_cannot_escape_repository(tmp_path: Path) -> None:
    local = tmp_path / "local.toml"
    local.write_text('[data]\ndemo_directory = "../private"\n', encoding="utf-8")

    with pytest.raises(ConfigError, match="must stay inside"):
        load_settings(defaults_path=DEFAULTS, local_path=local, environ={}, project_root=PROJECT_ROOT)


def test_explicit_missing_local_file_is_an_error() -> None:
    with pytest.raises(ConfigError, match="PORTICO_CONFIG_PATH does not exist"):
        load_settings(
            defaults_path=DEFAULTS,
            environ={"PORTICO_CONFIG_PATH": "missing-local.toml"},
            project_root=PROJECT_ROOT,
        )


def test_relative_config_path_resolves_from_project_root(tmp_path: Path) -> None:
    config_directory = tmp_path / "config"
    config_directory.mkdir()
    (config_directory / "household.toml").write_text("[thresholds]\nexpense = 1500\n", encoding="utf-8")

    settings = load_settings(
        defaults_path=DEFAULTS,
        environ={"PORTICO_CONFIG_PATH": "config/household.toml"},
        project_root=tmp_path,
    )

    assert settings.thresholds.expense == 1500
