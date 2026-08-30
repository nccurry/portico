import datetime as dt
import logging
import threading
from typing import cast
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from scripts.container_entrypoint import (
    DEFAULT_DISCORD_CRON,
    load_scheduler_settings,
    main,
    next_scheduled_time,
    run_scheduler,
)


def test_scheduler_is_disabled_by_default() -> None:
    settings = load_scheduler_settings({})

    assert settings.enabled is False
    assert settings.cron == DEFAULT_DISCORD_CRON
    assert settings.timezone.key == "Etc/UTC"


def test_disabled_scheduler_ignores_unused_schedule_settings() -> None:
    settings = load_scheduler_settings(
        {
            "PORTICO_DISCORD_ENABLED": "false",
            "PORTICO_DISCORD_CRON": "not cron",
            "TZ": "not/a-timezone",
        }
    )

    assert settings.enabled is False


def test_enabled_scheduler_loads_cron_and_timezone() -> None:
    settings = load_scheduler_settings(
        {
            "PORTICO_DISCORD_ENABLED": "true",
            "PORTICO_DISCORD_CRON": "30 8 * * 1",
            "TZ": "America/Chicago",
        }
    )

    assert settings.enabled is True
    assert settings.cron == "30 8 * * 1"
    assert settings.timezone.key == "America/Chicago"


@pytest.mark.parametrize("value", ["", "1", "yes", "enabled"])
def test_enabled_setting_requires_true_or_false(value: str) -> None:
    with pytest.raises(ValueError, match="must be true or false"):
        load_scheduler_settings({"PORTICO_DISCORD_ENABLED": value})


@pytest.mark.parametrize("cron", ["", "0 9 * *", "0 9 * * * *", "invalid cron value here"])
def test_enabled_scheduler_rejects_invalid_cron(cron: str) -> None:
    with pytest.raises(ValueError, match="five-field cron"):
        load_scheduler_settings({"PORTICO_DISCORD_ENABLED": "true", "PORTICO_DISCORD_CRON": cron})


def test_enabled_scheduler_rejects_invalid_timezone() -> None:
    with pytest.raises(ValueError, match="IANA timezone"):
        load_scheduler_settings({"PORTICO_DISCORD_ENABLED": "true", "TZ": "not/a-timezone"})


def test_next_scheduled_time_uses_configured_timezone() -> None:
    timezone = ZoneInfo("America/Chicago")
    settings = load_scheduler_settings(
        {
            "PORTICO_DISCORD_ENABLED": "true",
            "PORTICO_DISCORD_CRON": "0 9 * * 0",
            "TZ": timezone.key,
        }
    )
    saturday = dt.datetime(2026, 8, 29, 10, 0, tzinfo=timezone)

    assert next_scheduled_time(settings, saturday) == dt.datetime(2026, 8, 30, 9, 0, tzinfo=timezone)


def test_next_scheduled_time_rejects_naive_clock() -> None:
    settings = load_scheduler_settings({"PORTICO_DISCORD_ENABLED": "true"})

    with pytest.raises(ValueError, match="include a timezone"):
        next_scheduled_time(settings, dt.datetime(2026, 8, 29, 10, 0))


def test_scheduler_sends_and_stops() -> None:
    settings = load_scheduler_settings({"PORTICO_DISCORD_ENABLED": "true"})
    stop_event_mock = MagicMock(spec=threading.Event)
    stop_event_mock.is_set.side_effect = [False, True]
    stop_event_mock.wait.return_value = False
    send = MagicMock(return_value=0)

    run_scheduler(
        settings,
        cast(threading.Event, stop_event_mock),
        now=lambda: dt.datetime(2026, 8, 29, 10, 0, tzinfo=settings.timezone),
        send=send,
    )

    send.assert_called_once_with()


def test_main_reports_invalid_configuration(caplog: pytest.LogCaptureFixture) -> None:
    with (
        patch("scripts.container_entrypoint.run_container", side_effect=ValueError("bad setting")),
        caplog.at_level(logging.ERROR),
    ):
        assert main() == 2

    assert "Invalid container configuration: bad setting" in caplog.text
