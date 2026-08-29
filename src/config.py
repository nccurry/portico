"""Load validated application settings from tracked and local TOML files."""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.constants import FI_SPENDING_LOOKBACK_OPTIONS


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULTS_PATH = PROJECT_ROOT / "config" / "defaults.toml"
LOCAL_PATH = PROJECT_ROOT / "config" / "local.toml"


class ConfigError(ValueError):
    """A user-facing application configuration error."""


@dataclass(frozen=True)
class DataSettings:
    """Data source and demo-file settings."""

    mode: str
    demo_directory: Path

    @property
    def is_demo(self) -> bool:
        """Return whether the app uses synthetic demo data."""
        return self.mode == "demo"


@dataclass(frozen=True)
class ThresholdSettings:
    """Transaction and duplicate-detection thresholds."""

    expense: int
    income: int
    duplicate_minimum: float
    duplicate_days: int


@dataclass(frozen=True)
class IncomeSavingsSettings:
    """Defaults for income and savings reports."""

    target_rate: int
    exclude_categories: tuple[str, ...]
    exclude_groups: tuple[str, ...]


@dataclass(frozen=True)
class SpendingSettings:
    """Defaults for discretionary-spending reports."""

    exclude_categories: tuple[str, ...]
    exclude_groups: tuple[str, ...]


@dataclass(frozen=True)
class SubscriptionSettings:
    """Defaults for subscription views and detection."""

    default_exclude_categories: tuple[str, ...]
    detection_excluded_categories: tuple[str, ...]
    detection_excluded_pattern: str


@dataclass(frozen=True)
class FinancialIndependenceSettings:
    """Defaults for financial-independence scenarios."""

    expected_return_rate: float
    withdrawal_rate: float
    spending_lookback_months: int
    projection_years: int
    included_account_patterns: tuple[str, ...]
    included_groups: tuple[str, ...]


@dataclass(frozen=True)
class MerchantSettings:
    """Local merchant-description aliases."""

    aliases: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class Settings:
    """Validated application settings."""

    data: DataSettings
    thresholds: ThresholdSettings
    income_savings: IncomeSavingsSettings
    spending: SpendingSettings
    subscriptions: SubscriptionSettings
    financial_independence: FinancialIndependenceSettings
    merchants: MerchantSettings


_SECTION_KEYS = {
    "data": {"mode", "demo_directory"},
    "thresholds": {"expense", "income", "duplicate_minimum", "duplicate_days"},
    "income_savings": {"target_rate", "exclude_categories", "exclude_groups"},
    "spending": {"exclude_categories", "exclude_groups"},
    "subscriptions": {
        "default_exclude_categories",
        "detection_excluded_categories",
        "detection_excluded_pattern",
    },
    "financial_independence": {
        "expected_return_rate",
        "withdrawal_rate",
        "spending_lookback_months",
        "projection_years",
        "included_account_patterns",
        "included_groups",
    },
    "merchants": {"aliases"},
}


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as file:
            return tomllib.load(file)
    except FileNotFoundError as error:
        raise ConfigError(f"Configuration file does not exist: {path.name}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"Invalid TOML in {path.name}: {error}") from error
    except OSError as error:
        raise ConfigError(f"Could not read configuration file: {path.name}") from error


def _merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            merged[key] = _merge(current, value)
        else:
            merged[key] = value
    return merged


def _validate_keys(document: Mapping[str, Any]) -> None:
    unknown_sections = set(document) - set(_SECTION_KEYS)
    if unknown_sections:
        names = ", ".join(sorted(unknown_sections))
        raise ConfigError(f"Unknown configuration section(s): {names}")

    for section_name, allowed_keys in _SECTION_KEYS.items():
        section = document.get(section_name)
        if not isinstance(section, Mapping):
            raise ConfigError(f"Configuration section [{section_name}] must be a table")
        unknown_keys = set(section) - allowed_keys
        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            raise ConfigError(f"Unknown key(s) in [{section_name}]: {names}")

    aliases = document["merchants"].get("aliases")
    if not isinstance(aliases, Mapping):
        raise ConfigError("Configuration section [merchants.aliases] must be a table")


def _integer(section: Mapping[str, Any], key: str, minimum: int, maximum: int) -> int:
    value = section.get(key)
    if type(value) is not int:
        raise ConfigError(f"{key} must be an integer")
    if not minimum <= value <= maximum:
        raise ConfigError(f"{key} must be between {minimum} and {maximum}")
    return value


def _number(section: Mapping[str, Any], key: str, minimum: float, maximum: float) -> float:
    value = section.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"{key} must be a number")
    result = float(value)
    if not minimum <= result <= maximum:
        raise ConfigError(f"{key} must be between {minimum:g} and {maximum:g}")
    return result


def _string(section: Mapping[str, Any], key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string")
    return value.strip()


def _strings(section: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = section.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ConfigError(f"{key} must be an array of non-empty strings")
    result = tuple(item.strip() for item in value)
    normalized = [item.casefold() for item in result]
    if len(normalized) != len(set(normalized)):
        raise ConfigError(f"{key} must not contain duplicates")
    return result


def _demo_directory(section: Mapping[str, Any], project_root: Path) -> Path:
    configured = Path(_string(section, "demo_directory"))
    if configured.is_absolute():
        raise ConfigError("demo_directory must be relative to the repository root")
    resolved = (project_root / configured).resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError as error:
        raise ConfigError("demo_directory must stay inside the repository") from error
    return resolved


def _merchant_aliases(section: Mapping[str, Any]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    aliases = section["aliases"]
    assert isinstance(aliases, Mapping)
    normalized: list[tuple[str, tuple[str, ...]]] = []
    for merchant, fragments in aliases.items():
        if not isinstance(merchant, str) or not merchant.strip():
            raise ConfigError("Merchant alias names must be non-empty strings")
        values = _strings({"fragments": fragments}, "fragments")
        normalized.append((merchant.strip(), values))
    names = [merchant.casefold() for merchant, _ in normalized]
    if len(names) != len(set(names)):
        raise ConfigError("Merchant alias names must not contain duplicates")
    return tuple(normalized)


def _build_settings(document: Mapping[str, Any], project_root: Path) -> Settings:
    _validate_keys(document)
    data = document["data"]
    thresholds = document["thresholds"]
    income_savings = document["income_savings"]
    spending = document["spending"]
    subscriptions = document["subscriptions"]
    financial_independence = document["financial_independence"]
    merchants = document["merchants"]
    assert all(
        isinstance(section, Mapping)
        for section in (data, thresholds, income_savings, spending, subscriptions, financial_independence, merchants)
    )

    mode = _string(data, "mode")
    if mode not in {"google_sheets", "demo"}:
        raise ConfigError("data.mode must be 'google_sheets' or 'demo'")
    pattern = _string(subscriptions, "detection_excluded_pattern")
    try:
        re.compile(pattern)
    except re.error as error:
        raise ConfigError(f"detection_excluded_pattern is not a valid regular expression: {error}") from error
    spending_lookback_months = _integer(financial_independence, "spending_lookback_months", 1, 120)
    if spending_lookback_months not in FI_SPENDING_LOOKBACK_OPTIONS:
        options = ", ".join(str(value) for value in FI_SPENDING_LOOKBACK_OPTIONS)
        raise ConfigError(f"spending_lookback_months must be one of: {options}")

    return Settings(
        data=DataSettings(mode=mode, demo_directory=_demo_directory(data, project_root)),
        thresholds=ThresholdSettings(
            expense=_integer(thresholds, "expense", 1_000, 100_000),
            income=_integer(thresholds, "income", 5_000, 100_000),
            duplicate_minimum=_number(thresholds, "duplicate_minimum", 0, 1_000),
            duplicate_days=_integer(thresholds, "duplicate_days", 0, 7),
        ),
        income_savings=IncomeSavingsSettings(
            target_rate=_integer(income_savings, "target_rate", 0, 100),
            exclude_categories=_strings(income_savings, "exclude_categories"),
            exclude_groups=_strings(income_savings, "exclude_groups"),
        ),
        spending=SpendingSettings(
            exclude_categories=_strings(spending, "exclude_categories"),
            exclude_groups=_strings(spending, "exclude_groups"),
        ),
        subscriptions=SubscriptionSettings(
            default_exclude_categories=_strings(subscriptions, "default_exclude_categories"),
            detection_excluded_categories=_strings(subscriptions, "detection_excluded_categories"),
            detection_excluded_pattern=pattern,
        ),
        financial_independence=FinancialIndependenceSettings(
            expected_return_rate=_number(financial_independence, "expected_return_rate", 0, 20),
            withdrawal_rate=_number(financial_independence, "withdrawal_rate", 0.5, 10),
            spending_lookback_months=spending_lookback_months,
            projection_years=_integer(financial_independence, "projection_years", 1, 100),
            included_account_patterns=_strings(financial_independence, "included_account_patterns"),
            included_groups=_strings(financial_independence, "included_groups"),
        ),
        merchants=MerchantSettings(aliases=_merchant_aliases(merchants)),
    )


def load_settings(
    *,
    defaults_path: Path = DEFAULTS_PATH,
    local_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    project_root: Path = PROJECT_ROOT,
) -> Settings:
    """Load tracked defaults, an optional local file, and narrow environment overrides."""
    environment = os.environ if environ is None else environ
    document = _read_toml(defaults_path)

    configured_local = environment.get("PORTICO_CONFIG_PATH")
    selected_local = (
        Path(configured_local) if configured_local else local_path or project_root / "config" / "local.toml"
    )
    if selected_local.exists():
        document = _merge(document, _read_toml(selected_local))
    elif configured_local:
        raise ConfigError("PORTICO_CONFIG_PATH does not exist")

    data_mode = environment.get("PORTICO_DATA_SOURCE")
    if data_mode:
        document = _merge(document, {"data": {"mode": data_mode}})
    return _build_settings(document, project_root)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return settings for the current process."""
    return load_settings()


def clear_settings_cache() -> None:
    """Clear the process settings cache for tests and explicit reloads."""
    get_settings.cache_clear()
