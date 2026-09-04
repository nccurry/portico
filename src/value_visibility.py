"""Shared presentation helpers for hiding data-derived values."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any, cast

import altair as alt
import pandas as pd
import streamlit as st

from src.custom_types import ColumnConfig

MASKED_VALUE = "XXXXXXXX"
MASKED_AXIS_LABEL_EXPR = f"isNumber(datum.value) ? '{MASKED_VALUE}' : datum.label"
VALUES_HIDDEN_KEY = "hide_values"
type AltairChart = (
    alt.Chart
    | alt.ConcatChart
    | alt.FacetChart
    | alt.HConcatChart
    | alt.LayerChart
    | alt.RepeatChart
    | alt.VConcatChart
)


def values_hidden() -> bool:
    """Return whether the current session is hiding data-derived values."""
    return bool(st.session_state.get(VALUES_HIDDEN_KEY, False))


def mask_value(value: str) -> str:
    """Mask a formatted value when value hiding is enabled."""
    return MASKED_VALUE if values_hidden() else value


def render_value_visibility_control() -> None:
    """Render the app-wide value visibility setting in the sidebar."""
    with st.sidebar:
        hidden = st.toggle(
            "Hide values",
            key=VALUES_HIDDEN_KEY,
            help="Hides amounts, percentages, and data-derived counts across every page.",
            persist_state="session",
            width="stretch",
        )
        if hidden:
            st.caption("Amounts, percentages, and counts are hidden.")


def mask_numeric_column_config(
    frame: pd.DataFrame,
    column_config: ColumnConfig | None = None,
    *,
    visible: set[str] | None = None,
) -> ColumnConfig:
    """Mask displayed numeric cells while preserving the underlying dataframe."""
    if not values_hidden():
        return column_config or {}

    visible_columns = visible or set()
    masked: dict[str, Any] = deepcopy(dict(column_config or {}))
    numeric_columns = {str(column) for column in frame.select_dtypes(include="number").columns}
    for column in frame.columns:
        column_name = str(column)
        if column_name in visible_columns:
            continue

        existing = masked.get(column_name)
        configured_type: dict[str, Any] | None = None
        if isinstance(existing, Mapping):
            type_config = existing.get("type_config")
            if isinstance(type_config, Mapping):
                configured_type = deepcopy(dict(type_config))

        is_configured_number = configured_type is not None and configured_type.get("type") in {"number", "progress"}
        if column_name not in numeric_columns and not is_configured_number:
            continue
        if column_name in masked and existing is None:
            continue
        if isinstance(existing, Mapping):
            configured = deepcopy(dict(existing))
            if configured_type is not None:
                if configured_type.get("type") in {"line_chart", "area_chart", "bar_chart"}:
                    continue
                configured_type["format"] = MASKED_VALUE
                configured["type_config"] = configured_type
                masked[column_name] = configured
                continue

        label = existing if isinstance(existing, str) else None
        masked[column_name] = st.column_config.NumberColumn(
            label,
            format=MASKED_VALUE,
        )

    return cast(ColumnConfig, masked)


def mask_chart_values(chart: AltairChart) -> AltairChart:
    """Mask numeric axis labels without changing chart data or interactions."""
    if not values_hidden():
        return chart

    return cast(
        AltairChart,
        chart.configure_axis(labelExpr=MASKED_AXIS_LABEL_EXPR),
    )


def value_safe_altair_chart(
    chart: AltairChart,
    **kwargs: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Render an Altair chart with quantitative labels masked when requested."""
    renderer = cast(Callable[..., Any], st.altair_chart)
    return renderer(mask_chart_values(chart), **kwargs)


def value_safe_dataframe(
    frame: pd.DataFrame,
    *,
    column_config: ColumnConfig | None = None,
    visible_numeric_columns: set[str] | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Render a dataframe with numeric display formats masked when requested."""
    return st.dataframe(
        frame,
        column_config=mask_numeric_column_config(
            frame,
            column_config,
            visible=visible_numeric_columns,
        ),
        **kwargs,
    )
