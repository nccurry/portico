"""Streamlit test isolation and date-freezing fixtures."""

from collections.abc import Callable, Generator
from datetime import tzinfo
from typing import overload
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@overload
def _passthrough_decorator[**P, R](
    func: Callable[P, R],
    /,
) -> Callable[P, R]: ...


@overload
def _passthrough_decorator[**P, R](
    **kwargs: object,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def _passthrough_decorator(*args: object, **kwargs: object) -> object:
    """Return the function unchanged whether used directly or with options."""
    if args and callable(args[0]):
        return args[0]
    return lambda func: func


# 1. disable_streamlit  (autouse)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def disable_streamlit() -> Generator[None]:
    """Neuter Streamlit decorators and helpers so tests never touch a running app."""
    with (
        patch("streamlit.cache_data", side_effect=_passthrough_decorator),
        patch("streamlit.cache_resource", side_effect=_passthrough_decorator),
        patch("streamlit.stop", MagicMock()),
    ):
        yield


# freezegun integration -- pin time for tests marked @pytest.mark.uses_real_dates
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def frozen_time(
    request: pytest.FixtureRequest,
    reference_date: pd.Timestamp,
) -> Generator[None]:
    """Freeze time to the synthetic fixture date for marked tests.

    Patches both ``datetime.datetime.now`` (via freezegun) and
    ``pandas.Timestamp.now`` directly. freezegun alone cannot freeze
    ``pd.Timestamp.now()`` because pandas reads the wall clock at the C
    level and bypasses Python-side ``time.time``/``datetime`` patches.

    tz_offset=0 keeps freezegun's faked datetime aligned with UTC so it does
    not collide with tz-aware Timestamps in fixtures.
    """
    if request.node.get_closest_marker("uses_real_dates") is None:
        yield
        return

    from freezegun import freeze_time

    iso = reference_date.isoformat()
    frozen_utc = reference_date if reference_date.tz is not None else reference_date.tz_localize("UTC")

    def _frozen_now(
        cls: type[pd.Timestamp],
        tz: str | tzinfo | None = None,
    ) -> pd.Timestamp:
        """Return the configured reference date in the requested tz (or naive)."""
        if tz is None:
            return frozen_utc.tz_convert("UTC").tz_localize(None)
        return frozen_utc.tz_convert(tz)

    with patch.object(pd.Timestamp, "now", classmethod(_frozen_now)), freeze_time(iso, tz_offset=0):
        yield
