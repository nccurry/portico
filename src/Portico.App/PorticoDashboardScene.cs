using System.Globalization;
using System.Numerics;
using Portico.Dashboard;
using Roci.Core;
using Roci.Ui;
using Roci.Ui.Rendering;

namespace Portico.App;

/// <summary>Builds the configuration-driven Portico dashboard from typed reports.</summary>
public sealed class PorticoDashboardScene
{
    private static readonly Color Canvas = new(244, 243, 238);
    private static readonly Color Surface = new(255, 255, 253);
    private static readonly Color SurfaceMuted = new(235, 238, 235);
    private static readonly Color Ink = new(31, 45, 56);
    private static readonly Color Muted = new(94, 105, 107);
    private static readonly Color Border = new(207, 214, 210);
    private static readonly Color Teal = new(32, 118, 111);
    private static readonly Color Clay = new(181, 77, 64);
    private static readonly Color Copper = new(181, 132, 51);
    private static readonly Color DrawerScrim = new(31, 45, 56, 96);
    private static readonly Color[] SeriesColors = [Teal, Copper, Clay, new Color(72, 107, 173), new Color(126, 88, 156)];

    private readonly DashboardSession _session;
    private bool _drawerOpen;
    private bool _rebuildRequired;

    /// <summary>Creates a retained scene for the given dashboard session.</summary>
    public PorticoDashboardScene(Vector2 viewportSize, DashboardSession session)
    {
        ArgumentNullException.ThrowIfNull(session);

        _session = session;
        Stage = new UiStage(viewportSize, UiSkin.Light());
        Stage.ViewportChanged += _ => _rebuildRequired = true;
        Build();
    }

    /// <summary>Gets the retained Roci stage owned by this scene.</summary>
    public UiStage Stage { get; }

    /// <summary>Gets whether the left page drawer is currently shown.</summary>
    public bool IsDrawerOpen => _drawerOpen;

    /// <summary>Opens or closes the left page drawer.</summary>
    public void ToggleDrawer()
    {
        _drawerOpen = !_drawerOpen;
        _rebuildRequired = true;
    }

    /// <summary>Closes the left page drawer without changing the page or filters.</summary>
    public void DismissDrawer()
    {
        if (!_drawerOpen)
            return;

        _drawerOpen = false;
        _rebuildRequired = true;
    }

    /// <summary>Selects a configured page and closes the drawer.</summary>
    public void SelectPage(DashboardPageId pageId)
    {
        _session.SelectPage(pageId);
        _drawerOpen = false;
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
            .SetBackgroundColor(Canvas)
            .SetPadding(16f)
            .Configure(node =>
            {
                var flex = FlexContainer.Vertical(12f);
                flex.CrossAlignment = CrossAlignment.Stretch;
                node.FlexContainer = flex;
                node.Name = "PorticoRoot";
            });

        DashboardPageDefinition page = CurrentPage();
        BuildHeader(page);
        BuildPageHeader(page);
        BuildContent(page);
        if (_drawerOpen)
            BuildDrawer();

        Ui.EndRootPanel();
        Stage.InvalidateLayout();
    }

    private void BuildHeader(DashboardPageDefinition page)
    {
        Ui.HStack(10f, "TopBar")
            .SetCrossAlign(CrossAlignment.Center)
            .SetPadding(12f, 8f)
            .SetBackgroundColor(Surface)
            .SetBorderColor(Border)
            .SetBorderWidth(1f)
            .SetCornerRadius(10f);

        AddButton("OpenMenu", "Menu", ToggleDrawer, Teal, Surface);

        Ui.VStack(1f, "AppName")
            .SetFlexGrow(1f);
        Ui.Text(_session.Definition.AppTitle, "AppTitle")
            .SetFontSize(18)
            .SetFontStyle(FontStyle.Bold)
            .SetTextColor(Ink)
        .End();
        Ui.Text(page.Title, "CurrentPageLabel")
            .SetFontSize(11)
            .SetTextColor(Muted)
        .End();
        Ui.End();

        Ui.Text("Local session", "SessionStatus")
            .SetFontSize(11)
            .SetTextColor(Muted)
            .SetAlignSelf(CrossAlignment.Center)
        .End();

        Ui.End();
    }

    private void BuildPageHeader(DashboardPageDefinition page)
    {
        Ui.VStack(8f, "PageHeading")
            .SetPadding(4f, 0f);

        Ui.Text(page.Title, "PageTitle")
            .SetFontSize(28)
            .SetFontStyle(FontStyle.Bold)
            .SetTextColor(Ink)
        .End();
        Ui.Text(page.Description, "PageDescription")
            .SetFontSize(13)
            .SetTextColor(Muted)
        .End();

        if (page.Filters.Count > 0)
        {
            Ui.HStack(8f, "FilterGroups")
                .SetCrossAlign(CrossAlignment.Center);
            foreach (DashboardFilterDefinition filter in page.Filters)
                BuildFilter(filter);
            Ui.End();
        }

        Ui.End();
    }

    private void BuildFilter(DashboardFilterDefinition filter)
    {
        Ui.HStack(5f, $"Filter:{filter.Id}")
            .SetCrossAlign(CrossAlignment.Center);

        Ui.Text(filter.Label, $"FilterLabel:{filter.Id}")
            .SetFontSize(11)
            .SetTextColor(Muted)
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
                isSelected ? Teal : SurfaceMuted,
                isSelected ? Surface : Ink,
                compact: true);
        }

        Ui.End();
    }

    private void BuildContent(DashboardPageDefinition page)
    {
        Ui.VStack(12f, "PageContent")
            .SetFlexGrow(1f)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetScrollable(vertical: true, horizontal: false)
            .SetPadding(2f, 2f, 12f, 8f);

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

            Ui.HStack(12f, $"WidgetRow:{index}")
                .SetCrossAlign(CrossAlignment.Stretch);
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
        Ui.VStack(8f, $"Widget:{widget.Id}")
            .SetHeight(WidgetHeight(widget.Kind))
            .SetFlexGrow(expand ? 1f : 0f)
            .SetPadding(14f)
            .SetBackgroundColor(Surface)
            .SetBorderColor(Border)
            .SetBorderWidth(1f)
            .SetCornerRadius(10f)
            .SetCrossAlign(CrossAlignment.Stretch);

        Ui.Text(widget.Title, $"WidgetTitle:{widget.Id}")
            .SetFontSize(16)
            .SetFontStyle(FontStyle.Bold)
            .SetTextColor(Ink)
        .End();
        if (!string.IsNullOrWhiteSpace(widget.Description))
        {
            Ui.Text(widget.Description, $"WidgetDescription:{widget.Id}")
                .SetFontSize(11)
                .SetTextColor(Muted)
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
        Ui.HStack(10f, $"Metrics:{widgetId}")
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetFlexGrow(1f);

        foreach (ReportMetric metric in metrics)
        {
            Ui.VStack(3f, $"Metric:{widgetId}:{metric.Label}")
                .SetFlexGrow(1f)
                .SetPadding(10f)
                .SetBackgroundColor(SurfaceMuted)
                .SetCornerRadius(6f);
            Ui.Text(metric.Label, $"MetricLabel:{widgetId}:{metric.Label}")
                .SetFontSize(11)
                .SetTextColor(Muted)
            .End();
            Ui.Text(metric.Display, $"MetricValue:{widgetId}:{metric.Label}")
                .SetFontSize(20)
                .SetFontStyle(FontStyle.Bold)
                .SetTextColor(ToneColor(metric.Tone))
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
            Color color = SeriesColors[index % SeriesColors.Length];

            if (widget.Kind == DashboardWidgetKind.AreaChart && index == 0)
            {
                Ui.AreaSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .DatePoints(points)
                    .Stroke(color, 2f)
                    .AreaFill(color)
                    .AreaOpacity(0.18f);
            }
            else if (widget.Kind == DashboardWidgetKind.ScatterChart)
            {
                Ui.ScatterSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .DatePoints(points)
                    .MarkerColor(color)
                    .Markers(ChartMarkerShape.Circle, 5f);
            }
            else
            {
                Ui.LineSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .DatePoints(points)
                    .Stroke(color, 2f)
                    .NoMarkers();
            }
        }

        if (ContainsBothSigns(series))
            Ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(Border).BelowSeries();
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
            Color color = SeriesColors[index % SeriesColors.Length];
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
                    .Stroke(color, 2f)
                    .NoMarkers();
            }
        }

        if (ContainsBothSigns(series))
            Ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(Border).BelowSeries();
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
                .BarFill(SeriesColors[index % SeriesColors.Length]);
        }

        if (ContainsBothSigns(series))
            Ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(Border).BelowSeries();
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
            Color color = SeriesColors[index % SeriesColors.Length];

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
                    .Stroke(color, 2f)
                    .NoMarkers();
            }
        }

        if (ContainsBothSigns(series))
            Ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(Border).BelowSeries();
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
            Color color = SeriesColors[index % SeriesColors.Length];
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
                    .Stroke(color, 2f)
                    .NoMarkers();
            }
        }

        if (ContainsBothSigns(series))
            Ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(Border).BelowSeries();
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
            Color color = SeriesColors[index % SeriesColors.Length];
            if (widget.Kind == DashboardWidgetKind.ScatterChart)
            {
                Ui.ScatterSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .Points(points)
                    .MarkerColor(color)
                    .Markers(ChartMarkerShape.Circle, 5f);
            }
            else
            {
                Ui.LineSeries(item.Id)
                    .SeriesLabel(item.Label)
                    .Points(points)
                    .Stroke(color, 2f)
                    .NoMarkers();
            }
        }

        Ui.HoverDetails().SetFlexGrow(1f).EndChart();
    }

    private void BuildSparkline(string widgetId, DashboardWidgetReport report)
    {
        foreach (ReportSeries series in report.Series.Take(4))
        {
            Ui.HStack(8f, $"SparklineRow:{widgetId}:{series.Id}")
                .SetCrossAlign(CrossAlignment.Center)
                .SetFlexGrow(1f);
            Ui.Text(series.Label, $"SparklineLabel:{widgetId}:{series.Id}")
                .SetWidth(120f)
                .SetFontSize(11)
                .SetTextColor(Muted)
            .End();
            Ui.Sparkline($"Sparkline:{widgetId}:{series.Id}")
                .Values(series.Points.Select(point => (double)point.Y))
                .Filled()
                .Stroke(Teal)
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

        Ui.VStack(3f, $"Table:{widgetId}")
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
                    FillColor = Teal,
                    FillOpacity = 0.72f,
                    BandFillRatio = 0.62f
                });

        if (report.DateGuide is DateOnly dateGuide)
            Ui.ReferenceLine(dateGuide).Stroke(Copper).GuideLabel("As of");

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
                    ColorScale = ChartHeatmapColorScale.Automatic(Clay, Teal),
                    CellFillRatio = 0.92f
                });
        Ui.HoverDetails().SetFlexGrow(1f).EndChart();
    }

    private void BuildTableRow(string name, IReadOnlyList<string> values, bool header, string? tone)
    {
        Ui.HStack(6f, name)
            .SetPadding(7f, 5f)
            .SetBackgroundColor(header ? SurfaceMuted : Surface)
            .SetCornerRadius(4f)
            .SetCrossAlign(CrossAlignment.Center);
        foreach (string value in values)
        {
            Ui.Text(TrimCell(value), $"{name}:{value}")
                .SetFlexGrow(1f)
                .SetFontSize(header ? 11 : 12)
                .SetFontStyle(header ? FontStyle.Bold : FontStyle.Regular)
                .SetTextColor(header ? Muted : ToneColor(tone))
            .End();
        }
        Ui.End();
    }

    private void BuildEmpty(string? message)
    {
        Ui.Text(message ?? "No data is available for this selection.", "EmptyState")
            .SetFlexGrow(1f)
            .SetFontSize(13)
            .SetTextColor(Muted)
            .CenterSelf()
        .End();
    }

    private void BuildDrawer()
    {
        Ui.AnchorOverlay("PorticoDrawerOverlay", UiStackLayer.Modal)
            .SetFillViewport()
            .SetBlocksLower()
            .Configure(node =>
            {
                var flex = FlexContainer.Horizontal(0f);
                flex.CrossAlignment = CrossAlignment.Stretch;
                node.FlexContainer = flex;
            });

        Ui.VStack(8f, "DrawerPanel")
            .SetWidth(Math.Min(320f, Stage.ViewportSize.X * 0.78f))
            .SetPadding(16f)
            .SetBackgroundColor(Surface)
            .SetBorderColor(Border)
            .SetBorderWidth(1f)
            .SetCrossAlign(CrossAlignment.Stretch);
        Ui.Text(_session.Definition.AppTitle, "DrawerTitle")
            .SetFontSize(20)
            .SetFontStyle(FontStyle.Bold)
            .SetTextColor(Ink)
        .End();
        Ui.Text("Pages", "DrawerCaption")
            .SetFontSize(11)
            .SetTextColor(Muted)
        .End();
        Ui.MenuList("DrawerPages")
            .SetFlexGrow(1f)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetCancelAction(DismissDrawer);
        foreach (DashboardPageDefinition page in _session.Definition.Pages.Where(item => item.Visible))
        {
            DashboardPageDefinition capturedPage = page;
            bool isCurrentPage = capturedPage.Id == _session.CurrentPage;
            Ui.MenuItem(
                capturedPage.Title,
                () =>
                {
                    SelectPage(capturedPage.Id);
                },
                content =>
                {
                    content.HStack(8f, $"DrawerPageContent:{capturedPage.Id}")
                        .SetCrossAlign(CrossAlignment.Center)
                        .SetFlexGrow(1f);
                    content.Text(capturedPage.Title, $"DrawerPageTitle:{capturedPage.Id}")
                        .SetFlexGrow(1f)
                    .End();
                    if (isCurrentPage)
                    {
                        content.Text("Current", $"DrawerCurrentPage:{capturedPage.Id}")
                            .SetFontSize(10)
                            .SetFontStyle(FontStyle.Bold)
                            .SetTextColor(Teal)
                        .End();
                    }
                    content.End();
                },
                name: $"DrawerPage:{capturedPage.Id}");
        }
        Ui.EndMenuList();
        AddButton("CloseDrawer", "Close menu", DismissDrawer, SurfaceMuted, Ink);
        Ui.End();

        Ui.Panel("DrawerScrim")
            .SetFlexGrow(1f)
            .SetBackgroundColor(DrawerScrim)
            .SetBlocksLower()
            .SetClickable(_ =>
            {
                DismissDrawer();
                return true;
            })
        .End();
        Ui.End();
    }

    private void AddButton(string name, string label, Action action, Color background, Color foreground, bool compact = false)
    {
        Ui.Button(name)
            .SetPadding(compact ? 8f : 12f, compact ? 4f : 7f)
            .SetBackgroundColor(background)
            .SetCornerRadius(6f)
            .SetClickable(_ =>
            {
                action();
                return true;
            });
        Ui.Text(label, $"{name}:Text")
            .SetFontSize(compact ? 11 : 12)
            .SetFontStyle(FontStyle.Bold)
            .SetTextColor(foreground)
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
            DashboardWidgetKind.Metric => 155f,
            DashboardWidgetKind.Table => 310f,
            DashboardWidgetKind.Timeline => 310f,
            DashboardWidgetKind.Heatmap => 310f,
            DashboardWidgetKind.Sparkline => 200f,
            _ => 290f
        };

    private static Color ToneColor(string? tone)
        => tone switch
        {
            "positive" => Teal,
            "negative" => Clay,
            _ => Ink
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
