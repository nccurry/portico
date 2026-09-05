using System.Globalization;
using System.Numerics;
using Portico.App.Ui;
using Portico.Dashboard;
using Roci.Core;
using Roci.Input;
using Roci.Ui;
using Roci.Ui.Rendering;

namespace Portico.App;

/// <summary>Builds the configuration-driven Portico dashboard from typed reports.</summary>
public sealed class PorticoDashboardScene
{
    private static readonly DashboardNavigationGroup[] NavigationGroups =
    [
        DashboardNavigationGroup.Analyze,
        DashboardNavigationGroup.Plan,
        DashboardNavigationGroup.Maintain
    ];

    private readonly DashboardSession _session;
    private readonly PorticoDashboardDisplayState _displayState;
    private readonly IPorticoRefreshBoundary _refreshBoundary;
    private bool _rebuildRequired;
    private Task<PorticoRefreshResult>? _refreshTask;

    /// <summary>Creates a retained scene for the given dashboard session.</summary>
    public PorticoDashboardScene(
        Vector2 viewportSize,
        DashboardSession session,
        PorticoDashboardDisplayState? displayState = null,
        IPorticoRefreshBoundary? refreshBoundary = null)
    {
        ArgumentNullException.ThrowIfNull(session);

        _session = session;
        _displayState = displayState ?? new PorticoDashboardDisplayState();
        _refreshBoundary = refreshBoundary ?? new UnavailablePorticoRefreshBoundary();
        Stage = new UiStage(viewportSize, PorticoSkin.Create());
        Stage.ViewportChanged += _ => _rebuildRequired = true;
        Build();
    }

    /// <summary>Gets the retained Roci stage owned by this scene.</summary>
    public UiStage Stage { get; }

    /// <summary>Gets the small display state shared by the rail and visible page.</summary>
    public PorticoDashboardDisplayState DisplayState => _displayState;

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

    /// <summary>Changes the privacy presentation without changing the current report.</summary>
    public void ToggleHideValues()
    {
        _displayState.ToggleHideValues();
        _rebuildRequired = true;
    }

    /// <summary>Starts an app-owned source check when no other refresh request is pending.</summary>
    public void RequestDataRefresh()
    {
        if (!_displayState.BeginRefresh())
            return;

        try
        {
            _refreshTask = _refreshBoundary.CheckSourceAsync();
        }
        catch (Exception)
        {
            _displayState.CompleteRefresh(PorticoRefreshResult.Failed());
        }

        _rebuildRequired = true;
    }

    /// <summary>Applies pending state changes to the retained UI tree.</summary>
    public void Refresh()
    {
        CompleteRefreshIfReady();
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
        FocusBookmark? focusBookmark = FocusProcessor.CaptureBookmark(Stage.Root, static node => node.Name);
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
        if (_displayState.IsDemoData)
            BuildDemoDataBanner();
        BuildPageHeader(page);
        BuildContent(page);

        Ui.End();
        Ui.EndRootPanel();
        Stage.InvalidateLayout();
        FocusProcessor.RestoreBookmark(
            Stage.Root,
            focusBookmark,
            FindFocusableNode,
            CurrentNavigationNode);
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

        BuildRailNavigation();

        Ui.Panel("RailSpacer")
            .SetFlexGrow(1f)
        .End();
        BuildRailDisplayState();

        Ui.End();
    }

    private void BuildRailNavigation()
    {
        IReadOnlyList<DashboardPageDefinition> pages = NavigationPages();
        int selectedIndex = pages
            .Select((page, index) => (page, index))
            .FirstOrDefault(item => item.page.Id == _session.CurrentPage)
            .index;

        Ui.VStack(PorticoSkin.CompactGap, "NavigationItems")
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetSelectionGroup(
                SelectionGroupOrientation.Vertical,
                wrap: true,
                syncFocus: true,
                selectOnHover: false,
                clearSelectionOnPointerMiss: false)
            .Configure(node =>
            {
                SelectionGroupState state = node.GetStateOrDefault<SelectionGroupState>()
                    ?? throw new InvalidOperationException("Navigation items need a selection group.");
                state.SelectedIndex = selectedIndex;
            });

        foreach (DashboardPageDefinition page in pages.Where(page => NavigationGroupFor(page) == DashboardNavigationGroup.Standalone))
            BuildNavigationItem(page);

        foreach (DashboardNavigationGroup group in NavigationGroups)
        {
            DashboardPageDefinition[] groupedPages = pages
                .Where(page => NavigationGroupFor(page) == group)
                .ToArray();
            if (groupedPages.Length == 0)
                continue;

            Ui.VStack(PorticoSkin.FilterGap, $"NavigationGroup:{group}")
                .SetCrossAlign(CrossAlignment.Stretch)
                .SetStyle(PorticoSkin.NavigationGroupPanelStyle);
            Ui.Text(GroupLabel(group), $"NavigationGroupLabel:{group}")
                .SetTextStyle(PorticoSkin.NavigationGroupLabelText)
                .SetFontStyle(FontStyle.Bold)
            .End();
            foreach (DashboardPageDefinition page in groupedPages)
                BuildNavigationItem(page);
            Ui.End();
        }

        Ui.End();
    }

    private void BuildNavigationItem(DashboardPageDefinition page)
    {
        bool selected = page.Id == _session.CurrentPage;
        string label = RailLabel(page);

        Ui.Button($"NavigationItem:{page.Id}")
            .SetPadding(PorticoSkin.NavigationItemHorizontalPadding, PorticoSkin.NavigationItemVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(selected ? PorticoSkin.SelectedNavigationActionStyle : PorticoSkin.NavigationActionStyle)
            .SetSelectionGroupItem()
            .SetCommandSurface(pointer: true, focus: true, selected: true)
            .SetOnCommand(
                _ =>
                {
                    SelectPage(page.Id);
                    return true;
                },
                (int)InputCommands.ClickLeft,
                (int)InputCommands.Accept)
            .Configure(node => node.Active = selected);

        Ui.HStack(PorticoSkin.NavigationIconGap, $"NavigationContent:{page.Id}")
            .SetCrossAlign(CrossAlignment.Center)
            .SetFlexGrow(1f);
        Ui.Text(PorticoNavigationIcons.Glyph(page.Icon), $"NavigationIcon:{page.Id}")
            .SetWidth(PorticoSkin.NavigationIconWidth)
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        Ui.Text(label, $"NavigationLabel:{page.Id}")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        Ui.End();
        Ui.EndButton();
    }

    private void BuildRailDisplayState()
    {
        Ui.VStack(PorticoSkin.CompactGap, "RailGlobalState")
            .SetCrossAlign(CrossAlignment.Stretch);

        if (_displayState.IsDemoData)
        {
            Ui.Panel("RailDemoDataState")
                .SetPadding(PorticoSkin.StatusPadding)
                .SetCornerRadius(PorticoSkin.SmallCornerRadius)
                .SetStyle(PorticoSkin.LoadingPanelStyle);
            Ui.Text("Demo data", "RailDemoDataLabel")
                .SetTextStyle(PorticoSkin.HelperText.Overlay(PorticoSkin.LoadingText))
                .SetFontStyle(FontStyle.Bold)
            .End();
            Ui.End();
        }

        AddButton(
            "HideValuesAction",
            _displayState.HideValues ? "Show values" : "Hide values",
            ToggleHideValues,
            _displayState.HideValues ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle,
            compact: true);

        Ui.HStack(PorticoSkin.FilterGap, "RailLoadStatus")
            .SetCrossAlign(CrossAlignment.Center);
        Ui.Panel("RailLoadStatusIndicator")
            .SetSize(PorticoSkin.StatusIndicatorSize, PorticoSkin.StatusIndicatorSize)
            .SetCornerRadius(PorticoSkin.StatusIndicatorSize)
            .SetStyle(LoadStatusPanelStyle())
        .End();
        Ui.Text(LoadStatusLabel(), "RailLoadStatusLabel")
            .SetTextStyle(PorticoSkin.HelperText.Overlay(PorticoSkin.ToneTextStyle(LoadStatusTone())))
            .SetFontStyle(FontStyle.Bold)
        .End();
        Ui.End();
        Ui.Text(_displayState.StatusMessage, "RailLoadStatusMessage")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();

        AddButton(
            "RefreshDataAction",
            _displayState.LoadStatus == PorticoDataLoadStatus.Loading ? "Refreshing..." : "Refresh data",
            RequestDataRefresh,
            PorticoSkin.SecondaryActionStyle,
            compact: true,
            enabled: _displayState.LoadStatus != PorticoDataLoadStatus.Loading);

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

        Ui.Text(PageHeading(page), "PageTitle")
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

        if (_displayState.LoadStatus != PorticoDataLoadStatus.Loaded)
            BuildLoadStatePanel();

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

    private void BuildDemoDataBanner()
    {
        Ui.HStack(PorticoSkin.FilterGap, "DemoDataBanner")
            .SetPadding(PorticoSkin.MainPadding, PorticoSkin.DemoBannerVerticalPadding)
            .SetCrossAlign(CrossAlignment.Center)
            .SetStyle(PorticoSkin.LoadingPanelStyle);
        Ui.Text("Demo data", "DemoDataBannerTitle")
            .SetTextStyle(PorticoSkin.HelperText.Overlay(PorticoSkin.LoadingText))
            .SetFontStyle(FontStyle.Bold)
        .End();
        Ui.Text("Synthetic records are shown in this desktop session.", "DemoDataBannerMessage")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        Ui.End();
    }

    private void BuildLoadStatePanel()
    {
        Ui.HStack(PorticoSkin.FilterGap, "LoadStatePanel")
            .SetPadding(PorticoSkin.StatusPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetCrossAlign(CrossAlignment.Center)
            .SetStyle(LoadStatusPanelStyle());
        Ui.Text(LoadStatusLabel(), "LoadStateTitle")
            .SetTextStyle(PorticoSkin.HelperText.Overlay(PorticoSkin.ToneTextStyle(LoadStatusTone())))
            .SetFontStyle(FontStyle.Bold)
        .End();
        Ui.Text(_displayState.StatusMessage, "LoadStateMessage")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
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
            Ui.Text(DisplayPrivateText(metric.Display), $"MetricValue:{widgetId}:{metric.Label}")
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
        EndChartWithDetails();
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
            .XAxis(ChartAxisConfig.Category(formatter: FormatCategoryAxis))
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
        EndChartWithDetails();
    }

    private void BuildDateBarChart(DashboardWidgetDefinition widget, IReadOnlyList<ReportSeries> series)
    {
        Ui.CartesianChart($"Chart:{widget.Id}")
            .XAxis(ChartAxisConfig.Category(formatter: FormatCategoryAxis))
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
        EndChartWithDetails();
    }

    private void BuildCategoryChart(DashboardWidgetDefinition widget, IReadOnlyList<ReportSeries> series)
    {
        if (widget.Kind == DashboardWidgetKind.ComboChart)
        {
            BuildCategoryComboChart(widget, series);
            return;
        }

        Ui.CartesianChart($"Chart:{widget.Id}")
            .XAxis(ChartAxisConfig.Category(formatter: FormatCategoryAxis))
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
        EndChartWithDetails();
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
            .XAxis(ChartAxisConfig.Category(formatter: FormatCategoryAxis))
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
        EndChartWithDetails();
    }

    private void BuildNumericChart(DashboardWidgetDefinition widget, IReadOnlyList<ReportSeries> series)
    {
        if (widget.Kind == DashboardWidgetKind.ComboChart)
            throw new InvalidOperationException($"Dashboard combo chart '{widget.Id}' needs date or category report data.");

        Ui.CartesianChart($"Chart:{widget.Id}")
            .XAxis(ChartAxisConfig.Linear("Position", formatter: FormatAxisValue))
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

        EndChartWithDetails();
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
            .Select(range => new ChartTimelineRange(
                DisplayPrivateText(range.Category),
                range.Start,
                range.End,
                DisplayPrivateText(range.Label)))
            .ToArray();

        Ui.CartesianChart($"Chart:{widgetId}")
            .XAxis(ChartAxisConfig.Date("Date", formatter: FormatDateAxis))
            .YAxis(ChartAxisConfig.Category("Merchant", formatter: FormatCategoryAxis))
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

        EndChartWithDetails();
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
                DisplayPrivateText(cell.Display)))
            .ToArray();

        Ui.CartesianChart($"Chart:{widgetId}")
            .XAxis(ChartAxisConfig.Category("Spending change", formatter: FormatCategoryAxis))
            .YAxis(ChartAxisConfig.Category("Return", formatter: FormatCategoryAxis))
            .Legend(ChartLegendPlacement.Hidden)
            .HeatmapSeries("sensitivity")
                .SeriesLabel("Runway")
                .HeatmapCells(cells)
                .SeriesStyle(new ChartHeatmapStyleOverrides
                {
                    ColorScale = ChartHeatmapColorScale.Automatic(PorticoSkin.HeatmapLow, PorticoSkin.HeatmapHigh),
                    CellFillRatio = PorticoSkin.HeatmapCellFillRatio
                });
        EndChartWithDetails();
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
            Ui.Text(TrimCell(header ? value : DisplayPrivateText(value)), $"{name}:{value}")
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

    private void AddButton(
        string name,
        string label,
        Action action,
        string style,
        bool compact = false,
        bool enabled = true)
    {
        Ui.Button(name)
            .SetPadding(
                compact ? PorticoSkin.CompactActionHorizontalPadding : PorticoSkin.ActionHorizontalPadding,
                compact ? PorticoSkin.CompactActionVerticalPadding : PorticoSkin.ActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(style)
            .Enabled(enabled)
            .SetCommandSurface(pointer: true, focus: true)
            .SetOnCommand(
                _ =>
                {
                    action();
                    return true;
                },
                (int)InputCommands.ClickLeft,
                (int)InputCommands.Accept);
        Ui.Text(label, $"{name}:Text")
            .SetTextStyle(compact ? PorticoSkin.CompactActionText : PorticoSkin.ActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        Ui.EndButton();
    }

    private DashboardPageDefinition CurrentPage()
        => _session.Definition.Pages.First(page => page.Id == _session.CurrentPage);

    private void CompleteRefreshIfReady()
    {
        if (_refreshTask is not { IsCompleted: true } refreshTask)
            return;

        _refreshTask = null;
        try
        {
            _displayState.CompleteRefresh(refreshTask.GetAwaiter().GetResult());
        }
        catch (Exception)
        {
            _displayState.CompleteRefresh(PorticoRefreshResult.Failed());
        }

        _rebuildRequired = true;
    }

    private IReadOnlyList<DashboardPageDefinition> NavigationPages()
        => _session.Definition.Pages
            .Select((page, index) => (Page: page, Index: index))
            .Where(item => item.Page.Visible)
            .OrderBy(item => item.Page.NavigationOrder > 0 ? item.Page.NavigationOrder : item.Index + 1)
            .Select(item => item.Page)
            .ToArray();

    private LayoutNode? FindFocusableNode(string name)
        => Stage.Root.GetSelfAndDescendants()
            .FirstOrDefault(node => string.Equals(node.Name, name, StringComparison.Ordinal));

    private LayoutNode? CurrentNavigationNode()
        => FindFocusableNode($"NavigationItem:{_session.CurrentPage}");

    private static DashboardNavigationGroup NavigationGroupFor(DashboardPageDefinition page)
        => page.NavigationGroup != DashboardNavigationGroup.Unspecified
            ? page.NavigationGroup
            : page.Id == DashboardPageId.Home
                ? DashboardNavigationGroup.Standalone
                : DashboardNavigationGroup.Analyze;

    private static string GroupLabel(DashboardNavigationGroup group)
        => group switch
        {
            DashboardNavigationGroup.Analyze => "ANALYZE",
            DashboardNavigationGroup.Plan => "PLAN",
            DashboardNavigationGroup.Maintain => "MAINTAIN",
            _ => throw new ArgumentOutOfRangeException(nameof(group), group, "Only labeled navigation groups have a label.")
        };

    private static string RailLabel(DashboardPageDefinition page)
        => page.RailLabel ?? page.Title;

    private static string PageHeading(DashboardPageDefinition page)
        => page.PageHeading ?? page.Title;

    private string LoadStatusPanelStyle()
        => _displayState.LoadStatus switch
        {
            PorticoDataLoadStatus.Loaded => PorticoSkin.PositivePanelStyle,
            PorticoDataLoadStatus.Loading => PorticoSkin.LoadingPanelStyle,
            PorticoDataLoadStatus.Failed => PorticoSkin.NegativePanelStyle,
            PorticoDataLoadStatus.Unavailable => PorticoSkin.WarningPanelStyle,
            _ => throw new ArgumentOutOfRangeException()
        };

    private string LoadStatusTone()
        => _displayState.LoadStatus switch
        {
            PorticoDataLoadStatus.Loaded => "positive",
            PorticoDataLoadStatus.Loading => "loading",
            PorticoDataLoadStatus.Failed => "negative",
            PorticoDataLoadStatus.Unavailable => "warning",
            _ => throw new ArgumentOutOfRangeException()
        };

    private string LoadStatusLabel()
        => _displayState.LoadStatus switch
        {
            PorticoDataLoadStatus.Loaded => _displayState.IsDemoData ? "Demo data ready" : "Data ready",
            PorticoDataLoadStatus.Loading => "Refreshing data",
            PorticoDataLoadStatus.Failed => "Refresh failed",
            PorticoDataLoadStatus.Unavailable => "Refresh unavailable",
            _ => throw new ArgumentOutOfRangeException()
        };

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

    private string FormatDateAxis(DateOnly value)
        => _displayState.HideValues ? "Hidden" : value.ToString("MMM yy", CultureInfo.InvariantCulture);

    private string FormatAxisValue(double value)
    {
        if (_displayState.HideValues)
            return "Hidden";
        if (Math.Abs(value) >= 1_000_000d)
            return $"{value / 1_000_000d:0.#}m";
        if (Math.Abs(value) >= 1_000d)
            return $"{value / 1_000d:0.#}k";
        return value.ToString("0.#", CultureInfo.InvariantCulture);
    }

    private string FormatCategoryAxis(string value) => DisplayPrivateText(value);

    private string DisplayPrivateText(string? value)
        => value is null
            ? string.Empty
            : _displayState.HideValues && value.Any(char.IsDigit) ? "Hidden" : value;

    private void EndChartWithDetails()
    {
        Ui.HoverDetails();
        if (_displayState.HideValues)
            Ui.FormatChartTooltip(static _ => "Values hidden.");
        Ui.SetFlexGrow(1f).EndChart();
    }

    private static string TrimCell(string value)
        => value.Length <= 28 ? value : $"{value[..25]}...";
}
