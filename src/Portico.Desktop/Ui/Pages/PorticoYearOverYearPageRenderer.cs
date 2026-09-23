using System.Globalization;
using Portico.Desktop.Ui;
using Portico.Desktop.Ui.Components;
using Roci.Core;
using Roci.Input;
using Roci.Ui;
using Roci.Ui.Charts;
using Roci.Ui.Widgets;

namespace Portico.Desktop.Ui.Pages;

/// <summary>Builds the Year over year comparison page from report data and configured controls.</summary>
internal sealed class PorticoYearOverYearPageRenderer
{
    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;
    private readonly PorticoMultiSelectState<string> _presetCategoryState = new(comparer: StringComparer.Ordinal);

    /// <summary>Creates a renderer around the dashboard session that owns Year over year state.</summary>
    public PorticoYearOverYearPageRenderer(DashboardSession session, Action requestRebuild)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
    }

    /// <summary>Checks whether the Year over year page defines every required widget and control.</summary>
    public bool CanRender(DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(page);
        return page.Id == DashboardPageId.YearOverYear
            && page.Widgets.Any(widget => string.Equals(widget.Id, "comparison", StringComparison.Ordinal))
            && page.Widgets.Any(widget => string.Equals(widget.Id, "year-totals", StringComparison.Ordinal))
            && HasControls(page, "view", "preset_categories", "single_category", "single_group");
    }

    /// <summary>Builds the source title and latest-data caption.</summary>
    public void BuildHeader(UiBuilder ui, DashboardPageDefinition page, DashboardPageReport report)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);

        ui.PageHeader();
        ui.Text(page.PageHeading ?? page.Title, "PageTitle")
            .SetTextStyle(PorticoSkin.PageTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        if (report.YearOverYearView?.LatestDataCaption is { Length: > 0 } caption)
        {
            ui.Text(caption, "YearOverYearLatestData")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
        }
        else
        {
            ui.Text(page.Description, "YearOverYearPageCaption")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
        }
        ui.EndPageHeader();
    }

    /// <summary>Builds source view controls, comparison cards, charts, and expandable card details.</summary>
    public void Build(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        Func<string?, string> display)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);
        ArgumentNullException.ThrowIfNull(display);

        YearOverYearPageView view = report.YearOverYearView
            ?? throw new InvalidOperationException("Year over year report needs a page view.");
        BuildControls(ui, page);
        if (view.Comparisons.Count == 0)
        {
            ui.EmptyPanel(
                "No comparison to show",
                view.EmptyMessage ?? "Choose an expense view to compare.",
                "YearOverYearEmpty");
            return;
        }

        bool compact = _session.Presentation.YearOverYear.ViewMode == YearOverYearViewMode.Preset;
        foreach (YearOverYearComparisonView comparison in view.Comparisons)
            BuildComparison(ui, comparison, compact, display);
    }

    /// <summary>Returns local Year over year multi-select state for focused interaction tests.</summary>
    public PorticoMultiSelectState<string>? MultiSelectState(string controlId)
        => string.Equals(controlId, "preset_categories", StringComparison.Ordinal)
            ? _presetCategoryState
            : null;

    private void BuildControls(UiBuilder ui, DashboardPageDefinition page)
    {
        ui.HStack(PorticoSkin.CompactGap, "YearOverYearControlBar")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.End);
        BuildViewControl(ui, page);
        switch (_session.Presentation.YearOverYear.ViewMode)
        {
            case YearOverYearViewMode.Preset:
                BuildPresetCategoryPicker(ui, page);
                break;
            case YearOverYearViewMode.SingleCategory:
                BuildEntityPicker(ui, page, "single_category", "SingleCategory");
                break;
            case YearOverYearViewMode.SingleGroup:
                BuildEntityPicker(ui, page, "single_group", "SingleGroup");
                break;
            default:
                throw new ArgumentOutOfRangeException();
        }
        ui.End();
    }

    private void BuildViewControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "view");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.YearOverYear, "view");
        string selected = _session.ControlValue(DashboardPageId.YearOverYear, "view");
        ui.VStack(PorticoSkin.FilterGap, "Control:YearOverYear:view:Group")
            .SetFlexBasis(440f)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, "Control:YearOverYear:view:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.SegmentedControl("Control:YearOverYear:View")
            .SetFlexGrow(1f);
        foreach (string option in options)
            ui.Segment(ViewLabel(option));
        ui.SetSelectedSegment(IndexOf(options, selected))
            .SetOnSegmentChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.YearOverYear, "view", options[index]);
                _requestRebuild();
            })
        .EndSegmentedControl();
        ui.End();
    }

    private void BuildPresetCategoryPicker(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "preset_categories");
        PorticoMultiSelectItem<string>[] items = _session.ControlOptions(DashboardPageId.YearOverYear, "preset_categories")
            .Select(value => new PorticoMultiSelectItem<string>(value, value, value))
            .ToArray();
        ui.VStack(PorticoSkin.FilterGap, "Control:YearOverYear:preset_categories:Group")
            .SetFlexBasis(300f)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, "Control:YearOverYear:preset_categories:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.MultiSelect(
            "Control:YearOverYear:PresetCategories",
            control.Label,
            items,
            _session.ControlValues(DashboardPageId.YearOverYear, "preset_categories"),
            _presetCategoryState,
            values => _session.SetControlValues(DashboardPageId.YearOverYear, "preset_categories", values),
            _requestRebuild);
        ui.End();
    }

    private void BuildEntityPicker(UiBuilder ui, DashboardPageDefinition page, string controlId, string name)
    {
        DashboardControlDefinition control = Control(page, controlId);
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.YearOverYear, controlId);
        ui.VStack(PorticoSkin.FilterGap, $"Control:YearOverYear:{controlId}:Group")
            .SetFlexBasis(300f)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"Control:YearOverYear:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        if (options.Count == 0)
        {
            ui.Text("No choices available", $"Control:YearOverYear:{controlId}:Empty")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
            ui.End();
            return;
        }

        string selected = _session.ControlValue(DashboardPageId.YearOverYear, controlId);
        if (!options.Contains(selected, StringComparer.Ordinal))
            selected = options[0];
        ui.Dropdown($"Control:YearOverYear:{name}")
            .SetFlexGrow(1f)
            .Text(selected, $"Control:YearOverYear:{name}:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in options)
            ui.Option(option);
        ui.SetSelectedOption(IndexOf(options, selected))
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.YearOverYear, controlId, options[index]);
                _requestRebuild();
            })
        .EndDropdown();
        ui.End();
    }

    private void BuildComparison(
        UiBuilder ui,
        YearOverYearComparisonView comparison,
        bool compact,
        Func<string?, string> display)
    {
        string entity = comparison.Entity;
        ui.VStack(PorticoSkin.SectionGap, $"YearOverYearComparison:{entity}")
            .SetPadding(PorticoSkin.SectionPadding)
            .SetCornerRadius(PorticoSkin.CardCornerRadius)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.Text(display(entity), $"YearOverYearComparison:{entity}:Title")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.Text($"Through {comparison.ThroughMonthLabel}", $"YearOverYearComparison:{entity}:Caption")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        BuildMetricDeck(ui, entity, comparison.Metrics, display);
        BuildChart(ui, entity, comparison.Series, compact);
        BuildDetails(ui, entity, comparison, display);
        ui.End();
    }

    private static void BuildMetricDeck(
        UiBuilder ui,
        string entity,
        IReadOnlyList<ReportMetric> metrics,
        Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.CompactGap, $"YearOverYearMetrics:{entity}")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in metrics)
        {
            ui.MetricCard($"YearOverYearMetric:{entity}:{metric.Label}")
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, "YearOverYear")
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"YearOverYear:{entity}:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();
    }

    private static void BuildChart(
        UiBuilder ui,
        string entity,
        IReadOnlyList<ReportSeries> series,
        bool compact)
    {
        ui.CartesianChart($"YearOverYearChart:{entity}")
            .XAxis(ChartAxisConfig.Date(
                domain: ChartDateDomain.Fixed(new DateOnly(2000, 1, 1), new DateOnly(2000, 12, 31)),
                formatter: MonthLabel))
            .YAxis(ChartAxisConfig.Linear("Monthly spending ($)"))
            .Legend(series.Count > 1 ? ChartLegendPlacement.Top : ChartLegendPlacement.Hidden)
            .SetHeight(compact ? 280f : 470f)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f);
        for (int index = 0; index < series.Count; index++)
        {
            ReportSeries item = series[index];
            ChartDatePoint[] points = item.Points
                .Select(point => new ChartDatePoint(
                    new DateOnly(
                        2000,
                        point.Date?.Month ?? throw new InvalidOperationException("Year-over-year history needs calendar months."),
                        1),
                    (double)point.Y))
                .ToArray();
            ui.LineSeries(item.Id)
                .SeriesLabel(item.Label)
                .DatePoints(points)
                .Stroke(YearColor(index), index == 0 ? 4f : PorticoSkin.ChartStrokeWidth)
                .Markers(ChartMarkerShape.Circle, index == 0 ? PorticoSkin.ChartMarkerSize : 3f);
        }
        ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(PorticoSkin.Border).BelowSeries();
        ui.SetFlexGrow(1f).EndChart();
    }

    private void BuildDetails(
        UiBuilder ui,
        string entity,
        YearOverYearComparisonView comparison,
        Func<string?, string> display)
    {
        bool expanded = _session.Presentation.YearOverYear.ExpandedDetails.Contains(entity);
        ui.Collapsible("Details", expanded)
            .SetOnCollapsibleToggled(next =>
            {
                _session.SetYearOverYearDetailsExpanded(entity, next);
                _requestRebuild();
            });
        PorticoTableRenderer.Build(ui, $"year-over-year-totals:{entity}", comparison.TotalColumns, comparison.TotalRows, display);
        PorticoTableRenderer.Build(ui, $"year-over-year-transactions:{entity}", comparison.TransactionColumns, comparison.TransactionRows, display);
        ui.EndCollapsible();
    }

    private static string MonthLabel(DateOnly date)
        => date.ToString("MMM", CultureInfo.InvariantCulture);

    private static Color YearColor(int index)
        => index switch
        {
            0 => PorticoSkin.Accent,
            1 => new Color(203, 213, 225),
            2 => new Color(148, 163, 184),
            3 => new Color(100, 116, 139),
            4 => new Color(71, 85, 105),
            _ => new Color(51, 65, 85)
        };

    private string ViewLabel(string value)
        => value switch
        {
            "single_category" => "Single category",
            "single_group" => "Single group",
            _ => _session.YearOverYearSetLabel(value)
        };

    private static DashboardControlDefinition Control(DashboardPageDefinition page, string id)
        => page.Controls.Single(control => string.Equals(control.Id, id, StringComparison.Ordinal));

    private static bool HasControls(DashboardPageDefinition page, params string[] ids)
        => ids.All(id => page.Controls.Any(control => string.Equals(control.Id, id, StringComparison.Ordinal)));

    private static int IndexOf(IReadOnlyList<string> values, string selected)
    {
        for (int index = 0; index < values.Count; index++)
        {
            if (string.Equals(values[index], selected, StringComparison.Ordinal))
                return index;
        }

        throw new InvalidOperationException($"Year over year control has no selected option '{selected}'.");
    }
}
