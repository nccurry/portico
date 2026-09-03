"""Tests for the strict, composable application configuration."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.config import ConfigError, load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULTS = PROJECT_ROOT / "config" / "defaults.toml"
DEMO_PROFILE = PROJECT_ROOT / "config" / "demo.toml"
HOUSEHOLD_EXAMPLE = PROJECT_ROOT / "config" / "household.example.toml"


def test_defaults_are_generic_and_data_agnostic() -> None:
    settings = load_settings(defaults_path=DEFAULTS, environ={})

    assert settings.data.source == "google_sheets"
    assert settings.data.directory is None
    assert settings.data.reference_date is None
    assert not settings.data.show_demo_banner
    assert settings.reporting.lookback_months == (3, 6, 12, 24)
    assert settings.thresholds.expense == 3000
    assert settings.income_savings.default_view == "regular"
    assert [transaction_set.key for transaction_set in settings.transaction_sets] == ["all"]
    assert settings.filter_set("spending").options == ("all",)
    assert settings.filter_set("spending").default == "all"
    assert settings.filter_set("year_over_year").options == ("all",)
    assert settings.filter_set("year_over_year").default == "all"
    assert settings.subscriptions.known_categories == ()
    assert settings.subscriptions.default_exclude_categories == ()
    assert settings.subscriptions.detection_excluded_categories == ()
    assert settings.subscriptions.minimum_confidence == 80
    assert settings.subscriptions.stale_after_days == 45
    assert settings.budget.history_months == 12
    assert settings.data_health.stale_account_days == 7
    assert settings.weekly_summary.top_merchant_count == 3
    assert settings.financial_independence.target_amount == 1_000_000
    assert settings.financial_independence.included_groups == ()
    assert settings.financial_safety.emergency_fund_included_groups == ()
    assert settings.financial_safety.debt_included_groups == ()
    assert settings.merchants.aliases == ()


def test_demo_profile_is_an_explicit_local_csv_configuration() -> None:
    settings = load_settings(
        defaults_path=DEFAULTS,
        override_path=DEMO_PROFILE,
        environ={},
        project_root=PROJECT_ROOT,
    )

    assert settings.data.source == "local_csv"
    assert settings.data.directory == PROJECT_ROOT / "demo" / "data"
    assert settings.data.reference_date == datetime(1995, 4, 20, tzinfo=UTC)
    assert settings.data.show_demo_banner
    assert settings.income_savings.exclude_groups == ("Travel", "Donations")
    assert [transaction_set.key for transaction_set in settings.transaction_sets] == [
        "all",
        "utilities",
        "non_discretionary",
        "discretionary",
    ]
    assert settings.transaction_set("utilities").categories == (
        "Electric",
        "Natural Gas",
        "Internet",
        "Mobile Phone",
        "Water & Sewer",
        "Trash",
    )
    assert settings.subscriptions.known_categories == (
        "Streaming Subscription",
        "Cloud Subscription",
        "Music Subscription",
        "News Subscription",
        "Fitness Subscription",
        "Meal Kit Subscription",
    )
    assert settings.filter_set("spending").options == ("all", "discretionary")
    assert settings.filter_set("spending").default == "discretionary"
    assert settings.filter_set("year_over_year").options == ("all", "utilities", "discretionary")
    assert settings.filter_set("year_over_year").default == "utilities"
    assert settings.financial_independence.included_groups == ("Savings", "Investments", "Retirement")
    assert settings.financial_safety.debt_included_groups == ("Credit Cards", "Liabilities")


def test_household_example_is_a_valid_explicit_profile() -> None:
    settings = load_settings(
        defaults_path=DEFAULTS,
        override_path=HOUSEHOLD_EXAMPLE,
        environ={},
        project_root=PROJECT_ROOT,
    )

    assert settings.data.source == "google_sheets"
    assert settings.transaction_set("utilities").categories == (
        "Electricity",
        "Natural gas",
        "Internet",
        "Mobile phone",
        "Water",
    )
    assert settings.filter_set("spending").default == "discretionary"
    assert settings.financial_independence.target_amount == 2_000_000
    assert settings.merchants.aliases == (("Example market", ("EXAMPLE MARKET #123", "EXAMPLE MKT")),)


def test_household_profile_stays_out_of_public_build_contexts() -> None:
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "config/household.toml" in gitignore
    assert "config/household.toml" in dockerignore
    assert "config/household.example.toml" in dockerfile
    assert "config/household.toml" not in dockerfile


def test_local_file_is_not_loaded_implicitly(tmp_path: Path) -> None:
    config_directory = tmp_path / "config"
    config_directory.mkdir()
    (config_directory / "local.toml").write_text("[thresholds]\nexpense = 1250\n", encoding="utf-8")

    settings = load_settings(defaults_path=DEFAULTS, environ={}, project_root=tmp_path)

    assert settings.thresholds.expense == 3000


def test_explicit_override_can_change_report_and_transaction_set_defaults(tmp_path: Path) -> None:
    override = tmp_path / "override.toml"
    override.write_text(
        """
[reporting]
lookback_months = [1, 3, 18]
default_lookback_months = 3
[transaction_sets.routine]
label = "Routine purchases"
groups = ["Food", "Shopping"]
transactions_like = ["Coffee"]
[filter_sets.spending]
options = ["all", "routine"]
default = "routine"
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

    settings = load_settings(defaults_path=DEFAULTS, override_path=override, environ={}, project_root=PROJECT_ROOT)

    assert settings.reporting.lookback_months == (1, 3, 18)
    assert settings.reporting.default_lookback_months == 3
    assert settings.transaction_set("routine").groups == ("Food", "Shopping")
    assert settings.transaction_set("routine").transactions_like == ("Coffee",)
    assert settings.filter_set("spending").default == "routine"
    assert settings.budget.history_months == 18
    assert settings.data_health.stale_account_days == 30
    assert settings.financial_safety.emergency_fund_target_months == 4
    assert settings.financial_safety.debt_baseline_date == datetime(2024, 1, 15).date()
    assert settings.subscriptions.minimum_confidence == 90
    assert settings.weekly_summary.average_weeks == 12
    assert settings.weekly_summary.rolling_weeks == 6
    assert settings.weekly_summary.top_merchant_count == 5


def test_local_csv_relative_directory_resolves_from_the_overlay(tmp_path: Path) -> None:
    config_directory = tmp_path / "config"
    config_directory.mkdir()
    expected_directory = tmp_path / "exports"
    override = config_directory / "local.toml"
    override.write_text(
        '[data]\nsource = "local_csv"\ndirectory = "../exports"\nreference_date = "2024-01-01T00:00:00+00:00"\n',
        encoding="utf-8",
    )

    settings = load_settings(defaults_path=DEFAULTS, override_path=override, environ={}, project_root=PROJECT_ROOT)

    assert settings.data.directory == expected_directory
    assert settings.data.reference_date == datetime(2024, 1, 1, tzinfo=UTC)


def test_legacy_data_source_environment_variable_is_ignored() -> None:
    settings = load_settings(
        defaults_path=DEFAULTS,
        environ={"PORTICO_DATA_SOURCE": "local_csv"},
        project_root=PROJECT_ROOT,
    )

    assert settings.data.source == "google_sheets"


def test_unknown_override_key_is_rejected(tmp_path: Path) -> None:
    override = tmp_path / "override.toml"
    override.write_text("[thresholds]\nexpnese = 1250\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"Unknown key.*expnese"):
        load_settings(defaults_path=DEFAULTS, override_path=override, environ={}, project_root=PROJECT_ROOT)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ('[transaction_sets.discretionary]\nmerchant_like = ["IRS"]\n', "Unknown key.*merchant_like"),
        ('[filter_sets.spending]\nitems = ["all"]\n', "Unknown key.*items"),
        ('[transaction_sets.Mixed]\nlabel = "Mixed"\n', "Transaction set keys must use lowercase"),
        ('[transaction_sets.new]\nlabel = "All spending"\n', "Transaction set labels must not contain duplicates"),
        ('[transaction_sets.new]\nlabel = "New"\nincludes = ["missing"]\n', "references unknown set"),
        ('[transaction_sets.all]\nincludes = ["all"]\n', "references contain a cycle"),
        ('[filter_sets.spending]\noptions = ["all"]\ndefault = "discretionary"\n', "default must be one"),
        ('[data]\nsource = "demo"\n', "source must be one of"),
        ('[data]\nsource = "local_csv"\n', "data.directory is required"),
        ('[data]\nreference_date = "2024-01-01T00:00:00+00:00"\n', "require data.source"),
        (
            '[data]\nsource = "local_csv"\ndirectory = "data"\nreference_date = "not-a-date"\n',
            "reference_date must be an ISO 8601",
        ),
    ],
)
def test_transaction_set_and_local_source_validation(tmp_path: Path, document: str, message: str) -> None:
    override = tmp_path / "override.toml"
    override.write_text(document, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_settings(defaults_path=DEFAULTS, override_path=override, environ={}, project_root=PROJECT_ROOT)


def test_invalid_toml_is_rejected(tmp_path: Path) -> None:
    override = tmp_path / "override.toml"
    override.write_text("[thresholds\nexpense = 1250", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"Invalid TOML in override\.toml"):
        load_settings(defaults_path=DEFAULTS, override_path=override, environ={}, project_root=PROJECT_ROOT)


def test_unreadable_override_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Could not read configuration file"):
        load_settings(defaults_path=DEFAULTS, override_path=tmp_path, environ={}, project_root=PROJECT_ROOT)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ('[thresholds]\nexpense = "high"\n', "expense must be an integer"),
        ("[thresholds]\nexpense = 999\n", "expense must be between 1000 and 100000"),
        ("[thresholds]\nincome = 100001\n", "income must be between 5000 and 100000"),
        ("[thresholds]\nduplicate_minimum = 1001\n", "duplicate_minimum must be between 0 and 1000"),
        ("[thresholds]\nduplicate_days = 8\n", "duplicate_days must be between 0 and 7"),
        ("[income_savings]\ntarget_rate = 101\n", "target_rate must be between 0 and 100"),
        ("[financial_independence]\nexpected_return_rate = -1\n", "expected_return_rate must be between 0 and 20"),
        ("[financial_independence]\nwithdrawal_rate = 10.5\n", "withdrawal_rate must be between 0.5 and 10"),
        ("[financial_independence]\ntarget_amount = 0\n", r"target_amount must be between 1 and 1e\+08"),
        ("[reporting]\nlookback_months = [12, 3]\n", "lookback_months must be in ascending order"),
        ("[reporting]\ndefault_lookback_months = 5\n", "default_lookback_months must be included"),
        ("[subscriptions]\nminimum_confidence = 69\n", "minimum_confidence must be between 70 and 100"),
        ("[budget]\nhistory_months = 0\n", "history_months must be between 1 and 120"),
        (
            "[financial_safety]\nemergency_fund_target_months = 0\n",
            "emergency_fund_target_months must be between 1 and 24",
        ),
        ('[financial_safety]\ndebt_baseline_date = "not-a-date"\n', "debt_baseline_date must be an ISO"),
        ("[weekly_summary]\nrolling_weeks = 53\n", "rolling_weeks must be between 1 and 52"),
        ("[data_health]\nduplicate_require_same_account = 1\n", "duplicate_require_same_account must be true or false"),
    ],
)
def test_existing_numeric_and_policy_validation_is_retained(tmp_path: Path, document: str, message: str) -> None:
    override = tmp_path / "override.toml"
    override.write_text(document, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_settings(defaults_path=DEFAULTS, override_path=override, environ={}, project_root=PROJECT_ROOT)


def test_missing_config_override_path_is_an_error() -> None:
    with pytest.raises(ConfigError, match="PORTICO_CONFIG_PATH does not exist"):
        load_settings(
            defaults_path=DEFAULTS,
            environ={"PORTICO_CONFIG_PATH": "missing-override.toml"},
            project_root=PROJECT_ROOT,
        )


def test_relative_config_path_resolves_from_project_root(tmp_path: Path) -> None:
    config_directory = tmp_path / "config"
    config_directory.mkdir()
    (config_directory / "override.toml").write_text("[thresholds]\nexpense = 1500\n", encoding="utf-8")

    settings = load_settings(
        defaults_path=DEFAULTS,
        environ={"PORTICO_CONFIG_PATH": "config/override.toml"},
        project_root=tmp_path,
    )

    assert settings.thresholds.expense == 1500
