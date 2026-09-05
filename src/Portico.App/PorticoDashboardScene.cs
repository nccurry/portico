using System.Globalization;
using System.Numerics;
using Portico.App.Ui;
using Portico.Dashboard;
using Roci.Core;
using Roci.Ui;
using Roci.Ui.Rendering;

namespace Portico.App;

/// <summary>Builds the configuration-driven Portico dashboard from typed reports.</summary>
public sealed class PorticoDashboardScene
{
    private readonly DashboardSession _session;
    private bool _rebuildRequired;

    /// <summary>Creates a retained scene for the given dashboard session.</summary>
    public PorticoDashboardScene(Vector2 viewportSize, DashboardSession session)
    {
        ArgumentNullException.ThrowIfNull(session);

        _session = session;
        Stage = new UiStage(viewportSize, PorticoSkin.Create());
        Stage.ViewportChanged += _ => _rebuildRequired = true;
        Build();
    }

    /// <summary>Gets the retained Roci stage owned by this scene.</summary>
    public UiStage Stage { get; }

    /// <summary>Selects a configured page for the main content area.</summary>
    public void SelectPage(DashboardPageId pageId)
    {
        _session.SelectPage(pageId);
        _rebuildRequired = true;
    }

    /// <summary>Applies a configured filter value to the report session.</summary>
    public void SetFilter(string source, string value)
    {
        _session.SetFilter(source, value);
        _rebuildRequired = true;
    }

    /// <summary>Applies pending state changes to the retained UI tree.</summary>
    public void Refresh()
    {
        if (_rebuildRequired)
            Build();
    }

    /// <summary>Advances the scene and applies a requested page or filter rebuild.</summary>
    public void Update(
        ref UiInput input,
        ITextMeasurer textMeasurer,
        UiRenderScaleOptions renderScaleOptions,
        float effectiveUiScale)
    {
        Refresh();

        Stage.Update(textMeasurer, ref input, renderScaleOptions, effectiveUiScale);
    }

    private UiBuilder Ui => Stage.Ui;

    private void Build()
    {
        _rebuildRequired = false;
        Stage.Root.ClearChildren();

        Ui.RootPanel()
            .SetSize(Stage.ViewportSize.X, Stage.ViewportSize.Y)
            .SetBackgroundColor(PorticoSkin.Window)
            .SetPadding(PorticoSkin.ShellPadding)
            .Configure(node =>
            {
                var flex = FlexContainer.Horizontal(PorticoSkin.ShellGap);
                flex.CrossAlignment = CrossAlignment.Stretch;
                node.FlexContainer = flex;
                node.Name = "PorticoShell";
            });

        BuildNavigationRail();

        Ui.VStack(PorticoSkin.PageGap, "MainColumn")
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.MainPanelStyle);

        DashboardPageDefinition page = CurrentPage();
        BuildPageHeader(page);
        BuildContent(page);

        Ui.End();
        Ui.EndRootPanel();
        Stage.InvalidateLayout();
    }

    private void BuildNavigationRail()
    {
        Ui.VStack(PorticoSkin.SectionGap, "NavigationRail")
            .SetWidth(PorticoSkin.NavigationRailWidth)
            .SetFlexBasis(PorticoSkin.NavigationRailWidth)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetPadding(PorticoSkin.RailPadding)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RailPanelStyle);

        Ui.Text(_session.Definition.AppTitle, "RailAppTitle")
            .SetTextStyle(PorticoSkin.RailTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        Ui.Text("Personal finance dashboard", "RailSubtitle")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();

        Ui.Panel("RailDivider")
            .SetHeight(PorticoSkin.DividerHeight)
            .SetBackgroundColor(PorticoSkin.Border)
        .End();
        Ui.Text("NAVIGATION", "RailPlaceholderLabel")
            .SetTextStyle(PorticoSkin.NavigationGroupLabelText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        Ui.Text("Page navigation is added in Phase 2.", "RailPlaceholder")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        Ui.Panel("RailSpacer")
            .SetFlexGrow(1f)
        .End();
        Ui.Text("Local demo data", "RailStatus")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();

        Ui.End();
    }

    private void BuildPageHeader(DashboardPageDefinition page)
    {
        Ui.VStack(PorticoSkin.CompactGap, "PageHeader")
            .SetPadding(PorticoSkin.MainPadding, PorticoSkin.HeaderTopPadding, PorticoSkin.MainPadding, PorticoSkin.ShellPadding)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.HeaderPanelStyle);

        Ui.VStack(PorticoSkin.HeadingGap, "PageHeading");

        Ui.Text(page.Title, "PageTitle")
            .SetTextStyle(PorticoSkin.PageTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        Ui.Text(page.Description, "PageDescription")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        Ui.End();

        if (page.Filters.Count > 0)
        {
            Ui.HStack(PorticoSkin.CompactGap, "FilterGroups")
                .SetFlexWrap()
                .SetCrossGap(PorticoSkin.CompactGap)
                .SetCrossAlign(CrossAlignment.Center);
            foreach (DashboardFilterDefinition filter in page.Filters)
                BuildFilter(filter);
            Ui.End();
        }

        Ui.End();
    }

    private void BuildFilter(DashboardFilterDefinition filter)
    {
        Ui.HStack(PorticoSkin.FilterGap, $"Filter:{filter.Id}")
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Center);

        Ui.Text(filter.Label, $"FilterLabel:{filter.Id}")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetAlignSelf(CrossAlignment.Center)
        .End();

        string selected = CurrentFilterValue(filter.Source);
        foreach (string option in filter.Options)
        {
            string capturedOption = option;
            bool isSelected = string.Equals(selected, capturedOption, StringComparison.Ordinal);
            AddButton(
                $"Filter:{filter.Id}:{capturedOption}",
                DisplayFilterValue(capturedOption),
                () =>
                {
                    SetFilter(filter.Source, capturedOption);
                },
                isSelected ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle,
                compact: true);
        }

        Ui.End();
    }

    private void BuildContent(DashboardPageDefinition page)
    {
        Ui.VStack(PorticoSkin.SectionGap, "PageBody")
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetScrollable(vertical: true, horizontal: false)
            .SetPadding(PorticoSkin.MainPadding, PorticoSkin.ShellPadding, PorticoSkin.MainPadding, PorticoSkin.MainPadding);

        DashboardPageReport report = _session.Report.Page(page.Id);
        for (int index = 0; index < page.Widgets.Count;)
        {
            DashboardWidgetDefinition widget = page.Widgets[index];
            if (widget.Span == 2)
            {
                BuildWidget(widget, report.Widgets[widget.Report]);
                index++;
                continue;
            }

            Ui.HStack(PorticoSkin.SectionGap, $"WidgetRow:{index}")
                .SetFlexWrap()
                .SetCrossGap(PorticoSkin.SectionGap)
                .SetCrossAlign(CrossAlignment.Start);
            BuildWidget(widget, report.Widgets[widget.Report], expand: true);
            index++;
            if (index < page.Widgets.Count && page.Widgets[index].Span == 1)
            {
                DashboardWidgetDefinition next = page.Widgets[index];
                BuildWidget(next, report.Widgets[next.Report], expand: true);
                index++;
            }
            else
            {
                Ui.Panel($"WidgetRowSpacer:{index}")
                    .SetFlexGrow(1f)
                .End();
            }
            Ui.End();
        }

        Ui.End();
    }

    private void BuildWidget(DashboardWidgetDefinition widget, DashboardWidgetReport report, bool expand = false)
    {
        Ui.VStack(PorticoSkin.CompactGap, $"Widget:{widget.Id}")
            .SetHeight(WidgetHeight(widget.Kind))
            .SetFlexGrow(expand ? 1f : 0f)
            .SetFlexShrink(expand ? 1f : 0f)
            .SetPadding(PorticoSkin.WidgetPadding)
            .SetCornerRadius(PorticoSkin.CardCornerRadius)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        if (expand)
            Ui.SetFlexBasis(PorticoSkin.WidgetMinimumWidth);

        Ui.Text(widget.Title, $"WidgetTitle:{widget.Id}")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        if (!string.IsNullOrWhiteSpace(widget.Description))
        {
            Ui.Text(widget.Description, $"WidgetDescription:{widget.Id}")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
        }

        if (report.Metrics.Count > 0)
            BuildMetrics(widget.Id, report.Metrics);

        if (report.Series.Count == 0
            && report.Rows.Count == 0
            && report.Metrics.Count == 0
            && report.TimelineRanges.Count == 0
            && report.HeatmapCells.Count == 0)
        {
            BuildEmpty(report.EmptyMessage);
        }
        else
        {
            switch (widget.Kind)
            {
                case DashboardWidgetKind.Metric:
                    break;
                case DashboardWidgetKind.Table:
                    BuildTable(widget.Id, report);
                    break;
                case DashboardWidgetKind.Timeline:
                    BuildTimeline(widget.Id, report);
                    break;
                case DashboardWidgetKind.Heatmap:
                    BuildHeatmap(widget.Id, report);
                    break;
                case DashboardWidgetKind.Sparkline:
                    BuildSparkline(widget.Id, report);
                    break;
                default:
                    BuildChart(widget, report);
                    break;
            }
        }

        Ui.End();
    }

    private void BuildMetrics(string widgetId, IReadOnlyList<ReportMetric> metrics)
    {
        Ui.HStack(PorticoSkin.CompactGap, $"Metrics:{widgetId}")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetFlexGrow(1f);

        foreach (ReportMetric metric in metrics)
        {
            Ui.VStack(PorticoSkin.MetricGap, $"Metric:{widgetId}:{metric.Label}")
                .SetFlexBasis(PorticoSkin.MetricMinimumWidth)
                .SetFlexGrow(1f)
                .SetFlexShrink(1f)
                .SetPadding(PorticoSkin.MetricPadding)
                .SetCornerRadius(PorticoSkin.SmallCornerRadius)
                .SetStyle(PorticoSkin.MutedPanelStyle);
            Ui.Text(metric.Label, $"MetricLabel:{widgetId}:{metric.Label}")
                .SetTextStyle(PorticoSkin.MetricLabelText)
            .End();
            Ui.Text(metric.Display, $"MetricValue:{widgetId}:{metric.Label}")
                .SetTextStyle(PorticoSkin.MetricToneTextStyle(metric.Tone))
                .SetFontStyle(FontStyle.Bold)
            .End();
            Ui.End();
        }

        Ui.End();
    }

    private void BuildChart(DashboardWidgetDefinition widget, DashboardWidgetReport report)
    {
        if (report.Series.Count == 0)
        {
            BuildEmpty(report.EmptyMessage);
            return;
        }

        if (report.Series.All(series => series.Points.All(point => point.Date is not null)))
        {
            BuildDateChart(widget, report.Series);
            return;
        }

        if (report.Series.All(series => series.Points.All(point => !string.IsNullOrWhiteSpace(point.Category))))
        {
            BuildCategoryChart(widget, report.Series);
            return;
        }

        BuildNumericChart(widget, report.Series);
    }

    private void BuildDateChart(DashboardWidgetDefinition widget, IReadOnlyList<ReportSeries> series)
    {
        if (widget.Kind == DashboardWidgetKind.ComboChart)
        {
            BuildDateComboChart(widget, series);
            return;
        }

        if (widget.Kind == DashboardWidgetKind.BarChart)
        {
            BuildDateBarChart(widget, series);
            return;
        }

        Ui.CartesianChart($"Chart:{widget.Id}")
            .XAxis(ChartAxisConfig.Date("Date", formatter: FormatDateAxis))
            .YAxis(ChartAxisConfig.Linear("Value", formatter: FormatAxisValue))
            .Legend(series.Count > 1 ? ChartLegendPlacement.Bottom : ChartLegendPlacement.Hidden);

        for (int index = 0; index < series.Count; index++)
        {
            ReportSeries item = series[index];
            ChartDatePoint[] points = item.Points
                .Select(point => new ChartDatePoint(point.Date!.Value, (double)point.Y))
                .ToArray();
            Color color = PorticoSkin.SeriesColor(index);

            if (widget.Kind == DashboardWidgetKind.AreaChart && index == 0)
            {
                Ui.AreaSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .DatePoints(points)
                    .Stroke(color, PorticoSkin.ChartStrokeWidth)
                    .AreaFill(color)
                    .AreaOpacity(PorticoSkin.AreaFillOpacity);
            }
            else if (widget.Kind == DashboardWidgetKind.ScatterChart)
            {
                Ui.ScatterSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .DatePoints(points)
                    .MarkerColor(color)
                    .Markers(ChartMarkerShape.Circle, PorticoSkin.ChartMarkerSize);
            }
            else
            {
                Ui.LineSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .DatePoints(points)
                    .Stroke(color, PorticoSkin.ChartStrokeWidth)
                    .NoMarkers();
            }
        }

        if (ContainsBothSigns(series))
            Ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(PorticoSkin.Border).BelowSeries();
        Ui.HoverDetails().SetFlexGrow(1f).EndChart();
    }

    private void BuildDateComboChart(DashboardWidgetDefinition widget, IReadOnlyList<ReportSeries> series)
    {
        var values = series
            .Select(item => (Item: item, Values: item.Points
                .Select(point => new ChartCategoryValue(
                    point.Date!.Value.ToString("MMM yyyy", CultureInfo.InvariantCulture),
                    (double)point.Y))
                .ToArray()))
            .ToArray();
        IReadOnlySet<string> barSeries = ValidateComboSeries(widget, values.Select(item => (item.Item.Id, (IReadOnlyList<ChartCategoryValue>)item.Values)));

        Ui.CartesianChart($"Chart:{widget.Id}")
            .XAxis(ChartAxisConfig.Category())
            .YAxis(ChartAxisConfig.Linear("Value", formatter: FormatAxisValue))
            .Legend(ChartLegendPlacement.Bottom);

        for (int index = 0; index < values.Length; index++)
        {
            (ReportSeries item, ChartCategoryValue[] points) = values[index];
            Color color = PorticoSkin.SeriesColor(index);
            if (barSeries.Contains(item.Id))
            {
                Ui.BarSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .Bars(points)
                    .BarFill(color);
            }
            else
            {
                Ui.LineSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .CategoryPoints(points)
                    .Stroke(color, PorticoSkin.ChartStrokeWidth)
                    .NoMarkers();
            }
        }

        if (ContainsBothSigns(series))
            Ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(PorticoSkin.Border).BelowSeries();
        Ui.HoverDetails().SetFlexGrow(1f).EndChart();
    }

    private void BuildDateBarChart(DashboardWidgetDefinition widget, IReadOnlyList<ReportSeries> series)
    {
        Ui.CartesianChart($"Chart:{widget.Id}")
            .XAxis(ChartAxisConfig.Category())
            .YAxis(ChartAxisConfig.Linear("Value", formatter: FormatAxisValue))
            .Legend(series.Count > 1 ? ChartLegendPlacement.Bottom : ChartLegendPlacement.Hidden);

        for (int index = 0; index < series.Count; index++)
        {
            ReportSeries item = series[index];
            ChartCategoryValue[] points = item.Points
                .Select(point => new ChartCategoryValue(
                    point.Date!.Value.ToString("MMM yyyy", CultureInfo.InvariantCulture),
                    (double)point.Y))
                .ToArray();
            Ui.BarSeries(item.Id)
                .SeriesLabel(item.Label)
                .Bars(points)
                .BarFill(PorticoSkin.SeriesColor(index));
        }

        if (ContainsBothSigns(series))
            Ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(PorticoSkin.Border).BelowSeries();
        Ui.HoverDetails().SetFlexGrow(1f).EndChart();
    }

    private void BuildCategoryChart(DashboardWidgetDefinition widget, IReadOnlyList<ReportSeries> series)
    {
        if (widget.Kind == DashboardWidgetKind.ComboChart)
        {
            BuildCategoryComboChart(widget, series);
            return;
        }

        Ui.CartesianChart($"Chart:{widget.Id}")
            .XAxis(ChartAxisConfig.Category())
            .YAxis(ChartAxisConfig.Linear("Value", formatter: FormatAxisValue))
            .Legend(series.Count > 1 ? ChartLegendPlacement.Bottom : ChartLegendPlacement.Hidden);

        for (int index = 0; index < series.Count; index++)
        {
            ReportSeries item = series[index];
            ChartCategoryValue[] points = item.Points
                .Select(point => new ChartCategoryValue(point.Category!, (double)point.Y))
                .ToArray();
            Color color = PorticoSkin.SeriesColor(index);

            if (widget.Kind == DashboardWidgetKind.BarChart)
            {
                Ui.BarSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .Bars(points)
                    .BarFill(color);
            }
            else
            {
                Ui.LineSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .CategoryPoints(points)
                    .Stroke(color, PorticoSkin.ChartStrokeWidth)
                    .NoMarkers();
            }
        }

        if (ContainsBothSigns(series))
            Ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(PorticoSkin.Border).BelowSeries();
        Ui.HoverDetails().SetFlexGrow(1f).EndChart();
    }

    private void BuildCategoryComboChart(DashboardWidgetDefinition widget, IReadOnlyList<ReportSeries> series)
    {
        var values = series
            .Select(item => (Item: item, Values: item.Points
                .Select(point => new ChartCategoryValue(point.Category!, (double)point.Y))
                .ToArray()))
            .ToArray();
        IReadOnlySet<string> barSeries = ValidateComboSeries(widget, values.Select(item => (item.Item.Id, (IReadOnlyList<ChartCategoryValue>)item.Values)));

        Ui.CartesianChart($"Chart:{widget.Id}")
            .XAxis(ChartAxisConfig.Category())
            .YAxis(ChartAxisConfig.Linear("Value", formatter: FormatAxisValue))
            .Legend(ChartLegendPlacement.Bottom);

        for (int index = 0; index < values.Length; index++)
        {
            (ReportSeries item, ChartCategoryValue[] points) = values[index];
            Color color = PorticoSkin.SeriesColor(index);
            if (barSeries.Contains(item.Id))
            {
                Ui.BarSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .Bars(points)
                    .BarFill(color);
            }
            else
            {
                Ui.LineSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .CategoryPoints(points)
                    .Stroke(color, PorticoSkin.ChartStrokeWidth)
                    .NoMarkers();
            }
        }

        if (ContainsBothSigns(series))
            Ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(PorticoSkin.Border).BelowSeries();
        Ui.HoverDetails().SetFlexGrow(1f).EndChart();
    }

    private void BuildNumericChart(DashboardWidgetDefinition widget, IReadOnlyList<ReportSeries> series)
    {
        if (widget.Kind == DashboardWidgetKind.ComboChart)
            throw new InvalidOperationException($"Dashboard combo chart '{widget.Id}' needs date or category report data.");

        Ui.CartesianChart($"Chart:{widget.Id}")
            .XAxis(ChartAxisConfig.Linear("Position"))
            .YAxis(ChartAxisConfig.Linear("Value", formatter: FormatAxisValue))
            .Legend(series.Count > 1 ? ChartLegendPlacement.Bottom : ChartLegendPlacement.Hidden);

        for (int index = 0; index < series.Count; index++)
        {
            ReportSeries item = series[index];
            ChartPoint[] points = item.Points
                .Select(point => new ChartPoint((double)point.X, (double)point.Y))
                .ToArray();
            Color color = PorticoSkin.SeriesColor(index);
            if (widget.Kind == DashboardWidgetKind.ScatterChart)
            {
                Ui.ScatterSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .Points(points)
                    .MarkerColor(color)
                    .Markers(ChartMarkerShape.Circle, PorticoSkin.ChartMarkerSize);
            }
            else
            {
                Ui.LineSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .Points(points)
                    .Stroke(color, PorticoSkin.ChartStrokeWidth)
                    .NoMarkers();
            }
        }

        Ui.HoverDetails().SetFlexGrow(1f).EndChart();
    }

    private void BuildSparkline(string widgetId, DashboardWidgetReport report)
    {
        foreach (ReportSeries series in report.Series.Take(4))
        {
            Ui.HStack(PorticoSkin.SparklineGap, $"SparklineRow:{widgetId}:{series.Id}")
                .SetCrossAlign(CrossAlignment.Center)
                .SetFlexGrow(1f);
            Ui.Text(series.Label, $"SparklineLabel:{widgetId}:{series.Id}")
                .SetWidth(PorticoSkin.SparklineLabelWidth)
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
            Ui.Sparkline($"Sparkline:{widgetId}:{series.Id}")
                .Values(series.Points.Select(point => (double)point.Y))
                .Filled()
                .Stroke(PorticoSkin.Accent)
                .SetFlexGrow(1f)
            .EndChart();
            Ui.End();
        }
    }

    private void BuildTable(string widgetId, DashboardWidgetReport report)
    {
        if (report.Rows.Count == 0)
        {
            BuildEmpty(report.EmptyMessage);
            return;
        }

        Ui.VStack(PorticoSkin.TableGap, $"Table:{widgetId}")
            .SetFlexGrow(1f)
            .SetScrollable(vertical: true, horizontal: false);
        BuildTableRow($"TableHeader:{widgetId}", report.Columns, true, null);
        for (int index = 0; index < Math.Min(report.Rows.Count, 30); index++)
        {
            ReportTableRow row = report.Rows[index];
            BuildTableRow($"TableRow:{widgetId}:{index}", row.Values, false, row.Tone);
        }
        Ui.End();
    }

    private void BuildTimeline(string widgetId, DashboardWidgetReport report)
    {
        if (report.TimelineRanges.Count == 0)
        {
            BuildEmpty(report.EmptyMessage);
            return;
        }

        ChartTimelineRange[] ranges = report.TimelineRanges
            .Select(range => new ChartTimelineRange(range.Category, range.Start, range.End, range.Label))
            .ToArray();

        Ui.CartesianChart($"Chart:{widgetId}")
            .XAxis(ChartAxisConfig.Date("Date", formatter: FormatDateAxis))
            .YAxis(ChartAxisConfig.Category("Merchant"))
            .Legend(ChartLegendPlacement.Hidden)
            .TimelineSeries("ranges")
                .SeriesLabel("Subscription history")
                .TimelineRanges(ranges)
                .SeriesStyle(new ChartTimelineStyleOverrides
                {
                    FillColor = PorticoSkin.Accent,
                    FillOpacity = PorticoSkin.TimelineFillOpacity,
                    BandFillRatio = PorticoSkin.TimelineBandFillRatio
                });

        if (report.DateGuide is DateOnly dateGuide)
            Ui.ReferenceLine(dateGuide).Stroke(PorticoSkin.Warning).GuideLabel("As of");

        Ui.HoverDetails().SetFlexGrow(1f).EndChart();
    }

    private void BuildHeatmap(string widgetId, DashboardWidgetReport report)
    {
        if (report.HeatmapCells.Count == 0)
        {
            BuildEmpty(report.EmptyMessage);
            return;
        }

        ChartHeatmapCell[] cells = report.HeatmapCells
            .Select(cell => new ChartHeatmapCell(
                cell.XCategory,
                cell.YCategory,
                (double)cell.Value,
                cell.Display))
            .ToArray();

        Ui.CartesianChart($"Chart:{widgetId}")
            .XAxis(ChartAxisConfig.Category("Spending change"))
            .YAxis(ChartAxisConfig.Category("Return"))
            .Legend(ChartLegendPlacement.Hidden)
            .HeatmapSeries("sensitivity")
                .SeriesLabel("Runway")
                .HeatmapCells(cells)
                .SeriesStyle(new ChartHeatmapStyleOverrides
                {
                    ColorScale = ChartHeatmapColorScale.Automatic(PorticoSkin.HeatmapLow, PorticoSkin.HeatmapHigh),
                    CellFillRatio = PorticoSkin.HeatmapCellFillRatio
                });
        Ui.HoverDetails().SetFlexGrow(1f).EndChart();
    }

    private void BuildTableRow(string name, IReadOnlyList<string> values, bool header, string? tone)
    {
        Ui.HStack(PorticoSkin.TableRowGap, name)
            .SetPadding(PorticoSkin.TableRowHorizontalPadding, PorticoSkin.TableRowVerticalPadding)
            .SetCornerRadius(PorticoSkin.TableCornerRadius)
            .SetCrossAlign(CrossAlignment.Center)
            .SetStyle(header ? PorticoSkin.MutedPanelStyle : PorticoSkin.TablePanelStyle);
        foreach (string value in values)
        {
            Ui.Text(TrimCell(value), $"{name}:{value}")
                .SetFlexGrow(1f)
                .SetTextStyle(header
                    ? PorticoSkin.NavigationGroupLabelText
                    : PorticoSkin.HelperText.Overlay(PorticoSkin.ToneTextStyle(tone)))
                .SetFontStyle(header ? FontStyle.Bold : FontStyle.Regular)
            .End();
        }
        Ui.End();
    }

    private void BuildEmpty(string? message)
    {
        Ui.Text(message ?? "No data is available for this selection.", "EmptyState")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.HelperText)
            .CenterSelf()
        .End();
    }

    private void AddButton(string name, string label, Action action, string style, bool compact = false)
    {
        Ui.Button(name)
            .SetPadding(
                compact ? PorticoSkin.CompactActionHorizontalPadding : PorticoSkin.ActionHorizontalPadding,
                compact ? PorticoSkin.CompactActionVerticalPadding : PorticoSkin.ActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(style)
            .SetClickable(_ =>
            {
                action();
                return true;
            });
        Ui.Text(label, $"{name}:Text")
            .SetTextStyle(compact ? PorticoSkin.CompactActionText : PorticoSkin.ActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        Ui.EndButton();
    }

    private DashboardPageDefinition CurrentPage()
        => _session.Definition.Pages.First(page => page.Id == _session.CurrentPage);

    private string CurrentFilterValue(string source)
        => source switch
        {
            "lookback" => _session.Filters.LookbackMonths.ToString(CultureInfo.InvariantCulture),
            "spending" => _session.Filters.SpendingSet,
            "year_over_year" => _session.Filters.YearOverYearSet,
            "income_view" => _session.Filters.RegularIncome ? "regular" : "actual",
            _ => string.Empty
        };

    private static float WidgetHeight(DashboardWidgetKind kind)
        => kind switch
        {
            DashboardWidgetKind.Metric => PorticoSkin.MetricWidgetHeight,
            DashboardWidgetKind.Table => PorticoSkin.TableWidgetHeight,
            DashboardWidgetKind.Timeline => PorticoSkin.TableWidgetHeight,
            DashboardWidgetKind.Heatmap => PorticoSkin.TableWidgetHeight,
            DashboardWidgetKind.Sparkline => PorticoSkin.SparklineWidgetHeight,
            _ => PorticoSkin.ChartWidgetHeight
        };

    private static bool ContainsBothSigns(IReadOnlyList<ReportSeries> series)
        => series.SelectMany(item => item.Points).Any(point => point.Y < 0m)
            && series.SelectMany(item => item.Points).Any(point => point.Y > 0m);

    private static IReadOnlySet<string> ValidateComboSeries(
        DashboardWidgetDefinition widget,
        IEnumerable<(string Id, IReadOnlyList<ChartCategoryValue> Values)> series)
    {
        string[] configured = widget.BarSeries?.ToArray()
            ?? throw new InvalidOperationException($"Dashboard combo chart '{widget.Id}' needs bar_series.");
        var barSeries = new HashSet<string>(configured, StringComparer.Ordinal);
        (string Id, IReadOnlyList<ChartCategoryValue> Values)[] values = series.ToArray();
        if (barSeries.Any(id => !values.Any(item => string.Equals(item.Id, id, StringComparison.Ordinal))))
            throw new InvalidOperationException($"Dashboard combo chart '{widget.Id}' refers to an unknown report series.");

        string[]? categories = null;
        foreach ((_, IReadOnlyList<ChartCategoryValue> points) in values)
        {
            string[] current = points.Select(point => point.Category).ToArray();
            if (categories is null)
            {
                categories = current;
                continue;
            }

            if (!categories.SequenceEqual(current, StringComparer.Ordinal))
                throw new InvalidOperationException($"Dashboard combo chart '{widget.Id}' needs every series to use the same categories.");
        }

        return barSeries;
    }

    private static string DisplayFilterValue(string value)
        => value switch
        {
            "regular" => "Regular income",
            "actual" => "All income",
            _ when int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int months) => $"{months} mo",
            _ => value.Replace('_', ' ')
        };

    private static string FormatDateAxis(DateOnly value)
        => value.ToString("MMM yy", CultureInfo.InvariantCulture);

    private static string FormatAxisValue(double value)
    {
        if (Math.Abs(value) >= 1_000_000d)
            return $"{value / 1_000_000d:0.#}m";
        if (Math.Abs(value) >= 1_000d)
            return $"{value / 1_000d:0.#}k";
        return value.ToString("0.#", CultureInfo.InvariantCulture);
    }

    private static string TrimCell(string value)
        => value.Length <= 28 ? value : $"{value[..25]}...";
}
