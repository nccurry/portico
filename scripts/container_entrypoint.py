"""Run Streamlit and the optional Discord scheduler in one container."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import datetime as dt
import logging
import os
import signal
import subprocess
import threading
from types import FrameType
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from src.discord_notifier import main as run_discord_notifier


DEFAULT_DISCORD_CRON = "0 9 * * 0"
DEFAULT_TIMEZONE = "Etc/UTC"
STREAMLIT_COMMAND = (
    "streamlit",
    "run",
    "Home.py",
    "--server.address=0.0.0.0",
    "--server.port=8501",
    "--server.headless=true",
    "--server.runOnSave=false",
    "--client.showErrorDetails=false",
    "--browser.gatherUsageStats=false",
)

LOGGER = logging.getLogger("portico.container")


@dataclass(frozen=True)
class SchedulerSettings:
    """Validated settings for the optional Discord scheduler."""

    enabled: bool
    cron: str
    timezone: ZoneInfo


def load_scheduler_settings(environment: Mapping[str, str] = os.environ) -> SchedulerSettings:
    """Load the scheduler settings from environment variables."""
    enabled_value = environment.get("PORTICO_DISCORD_ENABLED", "false").strip().lower()
    if enabled_value not in {"true", "false"}:
        raise ValueError("PORTICO_DISCORD_ENABLED must be true or false.")

    cron_expression = environment.get("PORTICO_DISCORD_CRON", DEFAULT_DISCORD_CRON).strip()
    timezone_name = environment.get("TZ", DEFAULT_TIMEZONE).strip()
    if enabled_value == "false":
        return SchedulerSettings(enabled=False, cron=cron_expression, timezone=ZoneInfo(DEFAULT_TIMEZONE))

    if len(cron_expression.split()) != 5 or not croniter.is_valid(cron_expression):
        raise ValueError("PORTICO_DISCORD_CRON must be a valid five-field cron expression.")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("TZ must be a valid IANA timezone name.") from error
    return SchedulerSettings(enabled=True, cron=cron_expression, timezone=timezone)


def next_scheduled_time(settings: SchedulerSettings, now: dt.datetime) -> dt.datetime:
    """Return the next scheduled run after an aware datetime."""
    if now.tzinfo is None:
        raise ValueError("The scheduler clock must include a timezone.")
    next_run = croniter(settings.cron, now).get_next(dt.datetime)
    if not isinstance(next_run, dt.datetime):
        raise TypeError("croniter returned an invalid datetime.")
    return next_run


def run_scheduler(
    settings: SchedulerSettings,
    stop_event: threading.Event,
    *,
    now: Callable[[], dt.datetime],
    send: Callable[[], int],
) -> None:
    """Send the Discord summary on schedule until the container stops."""
    while not stop_event.is_set():
        current_time = now()
        run_at = next_scheduled_time(settings, current_time)
        LOGGER.info("Next Discord summary: %s", run_at.isoformat())
        if stop_event.wait(max(0.0, (run_at - current_time).total_seconds())):
            return

        exit_code = send()
        if exit_code != 0:
            LOGGER.error("The scheduled Discord summary failed with exit code %d.", exit_code)


def send_discord_summary() -> int:
    """Send the current weekly summary through the existing notifier command."""
    return run_discord_notifier(("send", "--output=json"))


def run_container(environment: Mapping[str, str] = os.environ) -> int:
    """Run Streamlit and start the scheduler when it is enabled."""
    settings = load_scheduler_settings(environment)
    stop_event = threading.Event()
    process = subprocess.Popen(STREAMLIT_COMMAND)

    def stop_process(signum: int, _frame: FrameType | None) -> None:
        stop_event.set()
        if process.poll() is None:
            process.send_signal(signum)

    signal.signal(signal.SIGTERM, stop_process)
    signal.signal(signal.SIGINT, stop_process)

    scheduler: threading.Thread | None = None
    if settings.enabled:
        LOGGER.info("Discord summaries enabled with schedule %s in %s.", settings.cron, settings.timezone.key)
        scheduler = threading.Thread(
            target=run_scheduler,
            kwargs={
                "settings": settings,
                "stop_event": stop_event,
                "now": lambda: dt.datetime.now(settings.timezone),
                "send": send_discord_summary,
            },
            name="discord-scheduler",
            daemon=True,
        )
        scheduler.start()
    else:
        LOGGER.info("Discord summaries disabled.")

    try:
        return process.wait()
    finally:
        stop_event.set()
        if scheduler is not None:
            scheduler.join(timeout=5)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the container entry point."""
    if argv:
        raise ValueError("The container entry point does not accept arguments.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        return run_container()
    except ValueError as error:
        LOGGER.error("Invalid container configuration: %s", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
