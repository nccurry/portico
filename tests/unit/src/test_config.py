"""Tests for the complete, single-file application configuration."""

import tomllib
from pathlib import Path

import pytest

from src.config import _FILTER_SET_KEYS, _SECTION_KEYS, _TRANSACTION_SET_KEYS, ConfigError, Settings, load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG = PROJECT_ROOT / "config.toml"
DEMO_CONFIG = PROJECT_ROOT / "portico-demo.toml"


def _copy_config(tmp_path: Path, *, name: str = "config.toml") -> Path:
    path = tmp_path / name
    path.write_text(CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _load(path: Path) -> Settings:
    return load_settings(config_path=path, environ={}, project_root=PROJECT_ROOT)


def test_config_is_generic_complete_and_not_a_demo() -> None:
    settings = _load(CONFIG)

    assert settings.data.source == "remote"
    assert settings.data.directory is None
    assert not settings.is_demo
    assert settings.lookback.lookback_months == (3, 6, 12, 24)
    assert settings.thresholds.expense == 3000
    assert settings.income_savings.default_view == "regular"
    assert [transaction_set.key for transaction_set in settings.transaction_sets] == ["all"]
    assert settings.filter_set("spending").options == ("all",)
    assert settings.filter_set("year_over_year").default == "all"
    assert settings.subscriptions.known_categories == ()
    assert settings.financial_independence.included_groups == ()
    assert settings.merchants.aliases == ()


def test_config_shows_every_supported_static_setting() -> None:
    document = tomllib.loads(CONFIG.read_text(encoding="utf-8"))

    for section_name, supported_keys in _SECTION_KEYS.items():
        assert set(document[section_name]) == supported_keys
    assert set(document["transaction_sets"]["all"]) == _TRANSACTION_SET_KEYS
    for filter_set in document["filter_sets"].values():
        assert set(filter_set) == _FILTER_SET_KEYS


def test_demo_config_is_complete_local_data_and_is_detected_by_name() -> None:
    settings = _load(DEMO_CONFIG)

    assert settings.is_demo
    assert settings.data.source == "local"
    assert settings.data.directory == PROJECT_ROOT / "demo" / "data"
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
    assert settings.filter_set("spending").default == "discretionary"
    assert settings.filter_set("year_over_year").default == "utilities"


def test_demo_banner_requires_the_exact_demo_filename(tmp_path: Path) -> None:
    renamed = tmp_path / "demo.toml"
    renamed.write_text(DEMO_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")

    assert not _load(renamed).is_demo


def test_selected_configuration_is_not_merged_with_another_file(tmp_path: Path) -> None:
    partial = tmp_path / "partial.toml"
    partial.write_text("[thresholds]\nexpense = 1250\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"Configuration section \[data\] must be a table"):
        _load(partial)


def test_local_directory_resolves_relative_to_its_complete_config(tmp_path: Path) -> None:
    config_directory = tmp_path / "settings"
    config_directory.mkdir()
    config = _copy_config(config_directory)
    _replace(config, 'source = "remote"', 'source = "local"')
    _replace(config, 'directory = ""', 'directory = "../exports"')

    settings = _load(config)

    assert settings.data.directory == tmp_path / "exports"


def test_portico_config_path_selects_one_complete_configuration(tmp_path: Path) -> None:
    config = _copy_config(tmp_path)
    _replace(config, "expense = 3000", "expense = 1250")

    settings = load_settings(
        environ={"PORTICO_CONFIG_PATH": str(config)},
        project_root=PROJECT_ROOT,
    )

    assert settings.thresholds.expense == 1250


def test_relative_portico_config_path_resolves_from_the_project_root() -> None:
    settings = load_settings(
        environ={"PORTICO_CONFIG_PATH": "portico-demo.toml"},
        project_root=PROJECT_ROOT,
    )

    assert settings.is_demo
    assert settings.data.directory == PROJECT_ROOT / "demo" / "data"


def test_missing_portico_config_path_is_an_error() -> None:
    with pytest.raises(ConfigError, match="PORTICO_CONFIG_PATH does not exist"):
        load_settings(environ={"PORTICO_CONFIG_PATH": "missing.toml"}, project_root=PROJECT_ROOT)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('source = "remote"', 'source = "demo"', "source must be one of"),
        ('source = "remote"', 'source = "local"', "data.directory is required"),
        ('directory = ""', 'directory = "exports"', "only used when data.source = 'local'"),
        ("expense = 3000", 'expense = "high"', "expense must be an integer"),
        ("expense = 3000", "expense = 999", "expense must be between 1000 and 100000"),
        ("lookback_months = [3, 6, 12, 24]", "lookback_months = [12, 3]", "must be in ascending order"),
        ("default_lookback_months = 12", "default_lookback_months = 5", "must be included"),
        ("minimum_confidence = 80", "minimum_confidence = 69", "must be between 70 and 100"),
        ('debt_baseline_date = ""', 'debt_baseline_date = "not-a-date"', "must be an ISO"),
    ],
)
def test_invalid_values_are_rejected(tmp_path: Path, old: str, new: str, message: str) -> None:
    config = _copy_config(tmp_path)
    _replace(config, old, new)

    with pytest.raises(ConfigError, match=message):
        _load(config)


def test_unknown_keys_are_rejected(tmp_path: Path) -> None:
    config = _copy_config(tmp_path)
    _replace(config, "expense = 3000", "expense = 3000\nexpnese = 1250")

    with pytest.raises(ConfigError, match=r"Unknown key.*expnese"):
        _load(config)


def test_unknown_transaction_set_references_are_rejected(tmp_path: Path) -> None:
    config = _copy_config(tmp_path)
    _replace(
        config,
        "# Keys of transaction sets to add.\nincludes = []",
        '# Keys of transaction sets to add.\nincludes = ["missing"]',
    )

    with pytest.raises(ConfigError, match="references unknown set"):
        _load(config)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("merchants = []", "merchants = []\nmerchant_like = []", r"Unknown key.*merchant_like"),
        ("includes = []", 'includes = ["all"]', "references contain a cycle"),
        ('default = "all"', 'default = "missing"', "default must be one"),
    ],
)
def test_dynamic_transaction_set_validation_is_retained(
    tmp_path: Path,
    old: str,
    new: str,
    message: str,
) -> None:
    config = _copy_config(tmp_path)
    _replace(config, old, new)

    with pytest.raises(ConfigError, match=message):
        _load(config)


def test_retired_reference_date_setting_is_rejected(tmp_path: Path) -> None:
    config = _copy_config(tmp_path)
    _replace(
        config,
        'directory = ""',
        'directory = ""\nreference_date = "2026-01-01T00:00:00+00:00"',
    )

    with pytest.raises(ConfigError, match=r"Unknown key.*reference_date"):
        _load(config)


def test_invalid_or_unreadable_complete_config_is_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.toml"
    invalid.write_text("[thresholds\nexpense = 1250", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"Invalid TOML in invalid\.toml"):
        _load(invalid)
    with pytest.raises(ConfigError, match="Could not read configuration file"):
        _load(tmp_path)
