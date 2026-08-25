"""Tests for app-wide value visibility helpers."""

from typing import Any, cast

import altair as alt
import pandas as pd
import streamlit as st
from streamlit.elements.vega_charts import _convert_altair_to_vega_lite_spec

from src.value_visibility import (
    MASKED_AXIS_LABEL_EXPR,
    MASKED_VALUE,
    VALUES_HIDDEN_KEY,
    mask_chart_values,
    mask_numeric_column_config,
    mask_value,
)


def test_mask_value_follows_session_setting() -> None:
    assert mask_value("$1,234") == "$1,234"

    st.session_state[VALUES_HIDDEN_KEY] = True

    assert mask_value("$1,234") == MASKED_VALUE


def test_numeric_column_config_masks_measures_but_keeps_dimensions() -> None:
    frame = pd.DataFrame(
        {
            "Year": [2025],
            "Description": ["PAYROLL XXXXXXXX8208"],
            "Amount": [123.45],
            "Trend": [[1.0, 2.0]],
        }
    )
    config = {
        "Description": st.column_config.TextColumn("Description"),
        "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
        "Trend": st.column_config.LineChartColumn("Trend"),
    }
    st.session_state[VALUES_HIDDEN_KEY] = True

    masked = mask_numeric_column_config(frame, config, visible={"Year"})

    amount_config = cast(dict[str, Any], masked["Amount"])
    trend_config = cast(dict[str, Any], masked["Trend"])
    assert amount_config["type_config"]["format"] == MASKED_VALUE
    assert trend_config["type_config"]["type"] == "line_chart"
    assert masked["Description"] == config["Description"]
    assert "Year" not in masked


def test_numeric_column_config_masks_configured_object_columns() -> None:
    frame = pd.DataFrame({"Rate": pd.Series([1.25, None], dtype=object)})
    config = {"Rate": st.column_config.NumberColumn("Rate", format="%.1f%%")}
    st.session_state[VALUES_HIDDEN_KEY] = True

    masked = mask_numeric_column_config(frame, config)

    rate_config = cast(dict[str, Any], masked["Rate"])
    assert rate_config["type_config"]["format"] == MASKED_VALUE


def test_chart_masking_preserves_chart_and_masks_numeric_axis_labels() -> None:
    frame = pd.DataFrame({"Month": ["Jan"], "Amount": [123.45]})
    chart = (
        alt.Chart(frame)
        .mark_text()
        .encode(
            x=alt.X("Month:N"),
            y=alt.Y("Amount:Q", axis=alt.Axis(format="$,.0f")),
            text=alt.Text("Amount:Q", format="$,.0f"),
            tooltip=[alt.Tooltip("Month:N"), alt.Tooltip("Amount:Q")],
        )
    )
    st.session_state[VALUES_HIDDEN_KEY] = True

    original = chart.to_dict()
    spec = mask_chart_values(chart).to_dict()
    encoding = spec["encoding"]

    assert spec["mark"] == original["mark"]
    assert spec["data"] == original["data"]
    assert spec["config"]["axis"]["labelExpr"] == MASKED_AXIS_LABEL_EXPR
    assert encoding["text"] == original["encoding"]["text"]
    assert encoding["tooltip"] == [
        {"field": "Month", "type": "nominal"},
        {"field": "Amount", "type": "quantitative"},
    ]


def test_chart_masking_preserves_layered_chart_datasets_for_streamlit() -> None:
    frame = pd.DataFrame({"Month": ["Jan", "Feb"], "Amount": [123.45, 234.56]})
    bars = alt.Chart(frame).mark_bar().encode(x="Month:N", y="Amount:Q")
    line = alt.Chart(frame).mark_line().encode(x="Month:N", y="Amount:Q")
    chart = alt.layer(bars, line)
    st.session_state[VALUES_HIDDEN_KEY] = True

    masked = mask_chart_values(chart)
    spec = _convert_altair_to_vega_lite_spec(masked)

    assert len(spec["layer"]) == 2
    assert spec["datasets"]
    assert spec["config"]["axis"]["labelExpr"] == MASKED_AXIS_LABEL_EXPR
