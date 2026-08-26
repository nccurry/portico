from pathlib import Path

import pytest

from src.config import ConfigError, load_settings


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULTS = PROJECT_ROOT / "config" / "defaults.toml"


def test_defaults_match_the_public_application_profile(tmp_path: Path) -> None:
    settings = load_settings(defaults_path=DEFAULTS, local_path=tmp_path / "missing.toml", environ={})

    assert settings.data.mode == "google_sheets"
    assert settings.thresholds.expense == 3000
    assert settings.income_savings.target_rate == 20
    assert settings.financial_independence.included_groups == (
        "Savings",
        "Investments",
        "Retirement",
    )


def test_local_file_and_environment_override_defaults(tmp_path: Path) -> None:
    local = tmp_path / "local.toml"
    local.write_text("[thresholds]\nexpense = 1250\n", encoding="utf-8")

    settings = load_settings(
        defaults_path=DEFAULTS,
        local_path=local,
        environ={"TILLER_DATA_SOURCE": "demo"},
        project_root=PROJECT_ROOT,
    )

    assert settings.data.is_demo
    assert settings.thresholds.expense == 1250


def test_unknown_local_key_is_rejected(tmp_path: Path) -> None:
    local = tmp_path / "local.toml"
    local.write_text("[thresholds]\nexpnese = 1250\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"Unknown key.*expnese"):
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
    with pytest.raises(ConfigError, match="TILLER_CONFIG_PATH does not exist"):
        load_settings(
            defaults_path=DEFAULTS,
            environ={"TILLER_CONFIG_PATH": "missing-local.toml"},
            project_root=PROJECT_ROOT,
        )
