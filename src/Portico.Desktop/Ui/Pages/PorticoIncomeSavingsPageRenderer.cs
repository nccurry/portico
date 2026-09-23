using System.Globalization;
using Portico.Desktop.Ui;
using Portico.Desktop.Ui.Components;
using Portico.Finance;
using Roci.Core;
using Roci.Input;
using Roci.Ui;
using Roci.Ui.Charts;
using Roci.Ui.Widgets;

namespace Portico.Desktop.Ui.Pages;

/// <summary>Builds the Income and savings page from report data and configured controls.</summary>
internal sealed class PorticoIncomeSavingsPageRenderer
{
    private static readonly string[] RequiredWidgets =
    [
        "summary",
        "cash-flow",
        "savings-rate",
        "detail",
        "included-categories",
        "included-transactions",
        "excluded-transactions",
        "monthly-totals"
    ];

    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;
    private readonly Dictionary<string, PorticoMultiSelectState<string>> _multiSelectStates = new(StringComparer.Ordinal);
    private string _includedTermDraft = string.Empty;
    private string _excludedTermDraft = string.Empty;

    /// <summary>Creates a renderer around the dashboard session that owns Income and savings state.</summary>
    public PorticoIncomeSavingsPageRenderer(DashboardSession session, Action requestRebuild)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
    }

    /// <summary>Checks whether the Income and savings page defines every required widget and control.</summary>
    public bool CanRender(DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(page);
        return page.Id == DashboardPageId.IncomeSavings
            && RequiredWidgets.All(id => page.Widgets.Any(widget => string.Equals(widget.Id, id, StringComparison.Ordinal)))
            && HasControls(
                page,
                "lookback",
                "calculation",
                "adjust_calculation",
                "reset_adjustments",
                "exclude_income_categories",
                "exclude_expense_groups",
                "exclude_expense_categories",
                "include_transaction_names",
                "exclude_transaction_names",
                "exclude_large_income",
                "income_limit",
                "exclude_large_expenses",
                "expense_limit",
                "savings_rate_target",
                "detail_month",
                "detail_tab");
    }

    /// <summary>Builds the source title and selected calculation caption.</summary>
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
        ui.Text(
                _session.Filters.RegularIncome ? "Regular calculation" : "Actual calculation",
                "IncomeSavingsPageCaption")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.EndPageHeader();
    }

    /// <summary>Builds source controls, summary cards, charts, selected month detail, and monthly totals.</summary>
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

        IncomeSavingsPageView view = report.IncomeSavingsView
            ?? throw new InvalidOperationException("Income and savings report needs a page view.");
        BuildControls(ui, page);
        BuildSummary(ui, view, display);
        if (!view.HasLedgerRows)
        {
            ui.EmptyPanel(
                "No included income or expense transactions",
                view.EmptyMessage ?? "No categorized income or expense transactions are available.",
                "IncomeSavingsEmpty");
            return;
        }

        BuildMonthlyCashFlow(ui, page, report, view, display);
        BuildMonthDetail(ui, page, report, view, display);
        BuildMonthlyTotals(ui, report, view, display);
    }

    /// <summary>Returns local multi-select state for interaction tests.</summary>
    public PorticoMultiSelectState<string>? MultiSelectState(string controlId)
        => _multiSelectStates.GetValueOrDefault(controlId);

    private void BuildControls(UiBuilder ui, DashboardPageDefinition page)
    {
        ui.HStack(PorticoSkin.CompactGap, "IncomeSavingsControlBar")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.End);
        BuildSegmentedControl(ui, page, "lookback", "TimeFrame", LookbackLabel, 232f);
        BuildSegmentedControl(ui, page, "calculation", "Calculation", CalculationLabel, PorticoSkin.ControlMinimumWidth);
        BuildAdjustControl(ui, page);
        ui.End();
    }

    private void BuildSegmentedControl(
        UiBuilder ui,
        DashboardPageDefinition page,
        string controlId,
        string name,
        Func<string, string> display,
        float minimumWidth)
    {
        DashboardControlDefinition control = Control(page, controlId);
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.IncomeSavings, controlId);
        string selected = _session.ControlValue(DashboardPageId.IncomeSavings, controlId);

        ui.VStack(PorticoSkin.FilterGap, $"Control:IncomeSavings:{controlId}:Group")
            .SetFlexBasis(minimumWidth)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"Control:IncomeSavings:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.SegmentedControl($"Control:IncomeSavings:{name}")
            .SetFlexGrow(1f)
            .SetFlexShrink(1f);
        foreach (string option in options)
            ui.Segment(display(option));
        ui.SetSelectedSegment(IndexOf(options, selected))
            .SetOnSegmentChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.IncomeSavings, controlId, options[index]);
                _requestRebuild();
            })
        .EndSegmentedControl();
        ui.End();
    }

    private void BuildAdjustControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "adjust_calculation");
        IncomeSavingsAdjustments current = _session.Presentation.IncomeSavingsAdjustments(_session.Filters.RegularIncome);
        bool modified = current.IsModifiedFrom(_session.IncomeSavingsDefaultAdjustments(_session.Filters.RegularIncome));
        string label = modified ? $"{control.Label} · modified" : control.Label;
        PopoverState? popover = null;

        ui.HStack(PorticoSkin.FilterGap, "Control:IncomeSavings:adjust_calculation:Group")
            .SetWidth(UiLength.Auto)
            .SetMaxWidth(220f)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Center);
        ui.Button("Control:IncomeSavings:AdjustCalculation")
            .SetWidth(UiLength.Auto)
            .SetMaxWidth(220f)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetPadding(PorticoSkin.CompactActionHorizontalPadding, PorticoSkin.CompactActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(modified ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle)
            .SetCommandSurface(pointer: true, focus: true);
        ui.Text(label, "Control:IncomeSavings:AdjustCalculation:Text")
            .SetTextStyle(PorticoSkin.ActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.SetPopover(
                content => BuildAdjustPopover(content, page, () => popover),
                PopoverOpenMode.Manual)
            .Configure(node =>
            {
                popover = node.GetStateOrDefault<PopoverState>()
                    ?? throw new InvalidOperationException("Income Adjust calculation needs a popover state.");
                popover.OnOpened = () => _session.Presentation.SetIncomeAdjustCalculationOpen(true);
                popover.OnClosed = () => _session.Presentation.SetIncomeAdjustCalculationOpen(false);
                UiBuilder.SetPopoverOpen(popover, _session.Presentation.IncomeSavings.AdjustCalculationOpen);
            })
            .SetOnCommand(_ =>
            {
                PopoverState state = popover
                    ?? throw new InvalidOperationException("Income Adjust calculation needs a popover state.");
                bool open = !_session.Presentation.IncomeSavings.AdjustCalculationOpen;
                _session.Presentation.SetIncomeAdjustCalculationOpen(open);
                UiBuilder.SetPopoverOpen(state, open);
                _requestRebuild();
                return true;
            }, (int)InputCommands.ClickLeft, (int)InputCommands.Accept);
        ui.EndButton();
        ui.End();
    }

    private void BuildAdjustPopover(UiBuilder ui, DashboardPageDefinition page, Func<PopoverState?> popover)
    {
        ui.VStack(PorticoSkin.SectionGap, "IncomeSavingsAdjustPopover")
            .SetWidth(420f)
            .SetMaxHeight(560f)
            .SetScrollable(vertical: true, horizontal: false)
            .SetPadding(PorticoSkin.ControlBarPadding)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.HStack(PorticoSkin.CompactGap, "IncomeSavingsAdjustPopover:Header")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text("Adjust calculation", "IncomeSavingsAdjustPopover:Title")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        AddActionButton(
            ui,
            "Control:IncomeSavings:ResetAdjustments",
            Control(page, "reset_adjustments").Label,
            () =>
            {
                _session.InvokeControlAction(DashboardPageId.IncomeSavings, "reset_adjustments");
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle,
            compact: true);
        ui.End();

        BuildAdjustmentMultiSelect(ui, page, "exclude_income_categories");
        BuildAdjustmentMultiSelect(ui, page, "exclude_expense_groups");
        BuildAdjustmentMultiSelect(ui, page, "exclude_expense_categories");
        BuildTextTerms(ui, page, "include_transaction_names", () => _includedTermDraft, value => _includedTermDraft = value);
        BuildTextTerms(ui, page, "exclude_transaction_names", () => _excludedTermDraft, value => _excludedTermDraft = value);
        BuildLimitControl(ui, page, "exclude_large_income", "income_limit");
        BuildLimitControl(ui, page, "exclude_large_expenses", "expense_limit");
        BuildTargetRateControl(ui, page);

        AddActionButton(
            ui,
            "Control:IncomeSavings:CloseAdjustments",
            "Close",
            () =>
            {
                _session.Presentation.SetIncomeAdjustCalculationOpen(false);
                if (popover() is { } state)
                    UiBuilder.SetPopoverOpen(state, false);
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle,
            compact: true);
        ui.End();
    }

    private void BuildAdjustmentMultiSelect(UiBuilder ui, DashboardPageDefinition page, string controlId)
    {
        DashboardControlDefinition control = Control(page, controlId);
        PorticoMultiSelectState<string> state = _multiSelectStates.GetValueOrDefault(controlId)
            ?? new PorticoMultiSelectState<string>(comparer: StringComparer.Ordinal);
        _multiSelectStates[controlId] = state;
        PorticoMultiSelectItem<string>[] items = _session.ControlOptions(DashboardPageId.IncomeSavings, controlId)
            .Select(value => new PorticoMultiSelectItem<string>(value, value, value))
            .ToArray();

        ui.VStack(PorticoSkin.FilterGap, $"IncomeSavingsAdjustment:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"IncomeSavingsAdjustment:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.MultiSelect(
            $"Control:IncomeSavings:{controlId}",
            control.Label,
            items,
            _session.ControlValues(DashboardPageId.IncomeSavings, controlId),
            state,
            values => _session.SetControlValues(DashboardPageId.IncomeSavings, controlId, values),
            _requestRebuild);
        ui.End();
    }

    private void BuildTextTerms(
        UiBuilder ui,
        DashboardPageDefinition page,
        string controlId,
        Func<string> getDraft,
        Action<string> setDraft)
    {
        DashboardControlDefinition control = Control(page, controlId);
        IReadOnlySet<string> values = _session.ControlValues(DashboardPageId.IncomeSavings, controlId);
        ui.VStack(PorticoSkin.FilterGap, $"IncomeSavingsTerms:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"IncomeSavingsTerms:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        ui.HStack(PorticoSkin.FilterGap, $"IncomeSavingsTerms:{controlId}:Input")
            .SetCrossAlign(CrossAlignment.Center);
        string draft = getDraft();
        ui.TextInput($"Control:IncomeSavings:{controlId}:Input", "Type text")
            .SetFlexGrow(1f)
            .Configure(node =>
            {
                TextInputState state = node.GetStateOrDefault<TextInputState>()
                    ?? throw new InvalidOperationException("Income term input needs a text state.");
                state.Text = draft;
            })
            .SetOnTextChanged(setDraft)
        .End();
        AddActionButton(
            ui,
            $"Control:IncomeSavings:{controlId}:Add",
            "Add",
            () =>
            {
                string next = getDraft();
                if (string.IsNullOrWhiteSpace(next))
                    return;
                _session.SetControlValues(DashboardPageId.IncomeSavings, controlId, values.Append(next));
                setDraft(string.Empty);
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle,
            compact: true);
        ui.End();

        if (values.Count > 0)
        {
            ui.HStack(PorticoSkin.FilterGap, $"IncomeSavingsTerms:{controlId}:Values")
                .SetFlexWrap()
                .SetCrossGap(PorticoSkin.FilterGap)
                .SetCrossAlign(CrossAlignment.Center);
            foreach (string value in values.OrderBy(value => value, StringComparer.Ordinal))
            {
                string captured = value;
                AddActionButton(
                    ui,
                    $"Control:IncomeSavings:{controlId}:Remove:{captured}",
                    $"Remove {captured}",
                    () =>
                    {
                        _session.SetControlValues(
                            DashboardPageId.IncomeSavings,
                            controlId,
                            values.Where(value => !string.Equals(value, captured, StringComparison.Ordinal)));
                        _requestRebuild();
                    },
                    PorticoSkin.QuietActionStyle,
                    compact: true);
            }
            ui.End();
        }
        ui.End();
    }

    private void BuildLimitControl(UiBuilder ui, DashboardPageDefinition page, string toggleId, string limitId)
    {
        DashboardControlDefinition toggle = Control(page, toggleId);
        bool selected = bool.Parse(_session.ControlValue(DashboardPageId.IncomeSavings, toggleId));
        ui.VStack(PorticoSkin.FilterGap, $"IncomeSavingsLimit:{toggleId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.ToggleButton($"Control:IncomeSavings:{toggleId}", selected, next =>
        {
            _session.SetControlToggle(DashboardPageId.IncomeSavings, toggleId, next);
            _requestRebuild();
        })
            .SetFlexGrow(1f);
        ui.Text(toggle.Label, $"Control:IncomeSavings:{toggleId}:Label")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        ui.EndButton();

        if (selected)
        {
            DashboardControlDefinition limit = Control(page, limitId);
            decimal value = decimal.Parse(_session.ControlValue(DashboardPageId.IncomeSavings, limitId), CultureInfo.InvariantCulture);
            ui.HStack(PorticoSkin.FilterGap, $"IncomeSavingsLimit:{limitId}")
                .SetCrossAlign(CrossAlignment.Center);
            ui.Text(limit.Label, $"Control:IncomeSavings:{limitId}:Label")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
            ui.NumberInput(
                    $"Control:IncomeSavings:{limitId}",
                    (double)limit.Minimum!.Value,
                    (double)limit.Maximum!.Value,
                    (double)value,
                    (double)limit.Step!.Value)
                .SetFlexGrow(1f)
                .SetOnNumberValueChanged(next =>
                {
                    _session.SetControlNumber(DashboardPageId.IncomeSavings, limitId, (decimal)next);
                    _requestRebuild();
                })
            .EndNumberInput();
            ui.End();
        }
        ui.End();
    }

    private void BuildTargetRateControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "savings_rate_target");
        decimal value = decimal.Parse(_session.ControlValue(DashboardPageId.IncomeSavings, "savings_rate_target"), CultureInfo.InvariantCulture);
        ui.HStack(PorticoSkin.FilterGap, "IncomeSavingsTargetRate")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(control.Label, "Control:IncomeSavings:savings_rate_target:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.NumberInput(
                "Control:IncomeSavings:savings_rate_target",
                (double)control.Minimum!.Value,
                (double)control.Maximum!.Value,
                (double)value,
                (double)control.Step!.Value)
            .SetFlexGrow(1f)
            .SetOnNumberValueChanged(next =>
            {
                _session.SetControlNumber(DashboardPageId.IncomeSavings, "savings_rate_target", (decimal)next);
                _requestRebuild();
            })
        .EndNumberInput();
        ui.End();
    }

    private static void BuildSummary(UiBuilder ui, IncomeSavingsPageView view, Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.CompactGap, "IncomeSavingsMetricDeck")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in view.SummaryMetrics)
        {
            ui.MetricCard($"IncomeSavingsMetric:{metric.Label}")
                .SetStyle(PorticoSkin.RaisedPanelStyle)
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, "IncomeSavings")
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"IncomeSavings:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();
    }

    private static void BuildMonthlyCashFlow(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        IncomeSavingsPageView view,
        Func<string?, string> display)
    {
        DashboardWidgetDefinition cashFlow = Widget(page, "cash-flow");
        DashboardWidgetDefinition savingsRate = Widget(page, "savings-rate");
        bool mostlyPositive = view.PositiveSurplusMonths >= view.MonthCount / 2f;
        string positiveMonthTone = mostlyPositive ? "positive" : "warning";
        ui.SectionPanel(
            "Section:monthly_cash_flow",
            cashFlow.Title,
            actions: header =>
            {
                header.Panel("IncomeSavingsPositiveMonthsBadge")
                    .SetFlexBasis(190f)
                    .SetFlexGrow(0f)
                    .SetFlexShrink(0f)
                    .SetPadding(PorticoSkin.StatusPadding)
                    .SetCornerRadius(PorticoSkin.SmallCornerRadius)
                    .SetStyle(mostlyPositive ? PorticoSkin.PositivePanelStyle : PorticoSkin.WarningPanelStyle);
                header.Text(
                        display($"{view.PositiveSurplusMonths} of {view.MonthCount} positive months"),
                        "IncomeSavingsPositiveMonthsBadge:Text")
                    .SetTextStyle(PorticoSkin.ToneTextStyle(positiveMonthTone))
                .End();
                header.End();
            });
        if (view.ExcludedCount > 0)
        {
            ui.Panel("IncomeSavingsExclusionBadge")
                .SetPadding(PorticoSkin.StatusPadding)
                .SetCornerRadius(PorticoSkin.SmallCornerRadius)
                .SetStyle(PorticoSkin.MutedPanelStyle);
            ui.Text(
                    display($"{view.ExcludedCount} excluded · {view.ExcludedIncome.ToString("C0", CultureInfo.GetCultureInfo("en-US"))} income · {view.ExcludedSpending.ToString("C0", CultureInfo.GetCultureInfo("en-US"))} spending"),
                    "IncomeSavingsExclusionBadge:Text")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
            ui.End();
        }
        if (!view.HasIncludedRows)
        {
            ui.EmptyPanel(
                "All transactions are excluded",
                view.EmptyMessage ?? "Adjust the calculation to include transactions.",
                "IncomeSavingsCashFlowEmpty");
            ui.EndSectionPanel();
            return;
        }
        BuildCashFlowChart(ui, ReportFor(report, cashFlow.Report), cashFlow, display);
        BuildSavingsRateChart(ui, ReportFor(report, savingsRate.Report), savingsRate, display);
        ui.EndSectionPanel();
    }

    private static void BuildCashFlowChart(
        UiBuilder ui,
        DashboardWidgetReport report,
        DashboardWidgetDefinition widget,
        Func<string?, string> display)
    {
        ui.CartesianChart("Chart:cash-flow")
            .XAxis(ChartAxisConfig.Category(formatter: value => display(value)))
            .YAxis(ChartAxisConfig.Linear(widget.YAxisTitle ?? "Monthly cash flow ($)", formatter: value => display(CompactCurrency(value))))
            .Legend(ChartLegendPlacement.Bottom)
            .SetHeight(300f)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f);

        for (int index = 0; index < report.Series.Count; index++)
        {
            ReportSeries series = report.Series[index];
            ChartCategoryValue[] points = CategoryPoints(series);
            if (series.Id is "income" or "spending")
            {
                ui.BarSeries(series.Id)
                    .SeriesLabel(series.Label)
                    .Bars(points)
                    .BarFill(PorticoSkin.SeriesColor(index));
            }
            else
            {
                ui.LineSeries(series.Id)
                    .SeriesLabel(series.Label)
                    .CategoryPoints(points)
                    .Stroke(PorticoSkin.SeriesColor(index), PorticoSkin.ChartStrokeWidth)
                    .Markers(ChartMarkerShape.Circle, PorticoSkin.ChartMarkerSize);
            }
        }

        if (ContainsBothSigns(report.Series))
            ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(PorticoSkin.Border).BelowSeries();
        ui.SetFlexGrow(1f).EndChart();
    }

    private static void BuildSavingsRateChart(
        UiBuilder ui,
        DashboardWidgetReport report,
        DashboardWidgetDefinition widget,
        Func<string?, string> display)
    {
        ui.CartesianChart("Chart:savings-rate")
            .XAxis(ChartAxisConfig.Category(formatter: value => display(value)))
            .YAxis(ChartAxisConfig.Linear(widget.YAxisTitle ?? "Savings rate (%)", formatter: value => display($"{value:0}%")))
            .Legend(ChartLegendPlacement.Bottom)
            .SetHeight(150f)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f);

        for (int index = 0; index < report.Series.Count; index++)
        {
            ReportSeries series = report.Series[index];
            var line = ui.LineSeries(series.Id)
                .SeriesLabel(series.Label)
                .CategoryPoints(CategoryPoints(series))
                .Stroke(PorticoSkin.SeriesColor(index), PorticoSkin.ChartStrokeWidth);
            if (index == 0)
                line.Markers(ChartMarkerShape.Circle, PorticoSkin.ChartMarkerSize);
            else
                line.NoMarkers();
        }

        ui.ReferenceLine(ChartAxis.Y, 0d).Stroke(PorticoSkin.Border).BelowSeries();
        ui.SetFlexGrow(1f).EndChart();
    }

    private static ChartCategoryValue[] CategoryPoints(ReportSeries series)
        => series.Points
            .Select(point => new ChartCategoryValue(
                point.Date?.ToString("MMM yyyy", CultureInfo.InvariantCulture)
                    ?? point.Category
                    ?? string.Empty,
                (double)point.Y))
            .ToArray();

    private static string CompactCurrency(double value)
        => Math.Abs(value) >= 1_000_000d
            ? $"${value / 1_000_000d:0.#}m"
            : Math.Abs(value) >= 1_000d
                ? $"${value / 1_000d:0.#}k"
                : $"${value:0}";

    private static bool ContainsBothSigns(IReadOnlyList<ReportSeries> series)
        => series.SelectMany(item => item.Points).Any(point => point.Y < 0m)
            && series.SelectMany(item => item.Points).Any(point => point.Y > 0m);

    private void BuildMonthDetail(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        IncomeSavingsPageView view,
        Func<string?, string> display)
    {
        ui.SectionPanel(
            "Section:month_detail",
            "Month detail",
            string.IsNullOrEmpty(view.DetailMonth) ? null : DetailMonthLabel(view.DetailMonth));
        BuildDetailMonthControl(ui, page, view);
        BuildDetailMetrics(ui, view.DetailMetrics, display);
        BuildDetailTabs(ui, view);

        bool included = string.Equals(_session.Presentation.IncomeSavings.DetailTab, "Included", StringComparison.Ordinal);
        if (included)
        {
            DashboardWidgetReport categories = ReportFor(report, "income.included_categories");
            DashboardWidgetReport transactions = ReportFor(report, "income.included_transactions");
            if (categories.Rows.Count > 0)
            {
                ui.SectionHeading("IncomeSavingsIncludedCategories", "By category");
                PorticoTableRenderer.Build(ui, "income-included-categories", categories.Columns, categories.Rows, display);
            }
            ui.SectionHeading("IncomeSavingsIncludedTransactions", "Transactions");
            if (transactions.Rows.Count == 0)
                ui.EmptyPanel("Included", transactions.EmptyMessage ?? "No included transactions for this month.", "IncomeSavingsIncludedEmpty");
            else
                PorticoTableRenderer.Build(ui, "income-included-transactions", transactions.Columns, transactions.Rows, display);
        }
        else
        {
            DashboardWidgetReport excluded = ReportFor(report, "income.excluded_transactions");
            ui.SectionHeading("IncomeSavingsExcludedTransactions", "Excluded transactions");
            if (excluded.Rows.Count == 0)
                ui.EmptyPanel("Excluded", excluded.EmptyMessage ?? "No excluded transactions for this month.", "IncomeSavingsExcludedEmpty");
            else
                PorticoTableRenderer.Build(ui, "income-excluded-transactions", excluded.Columns, excluded.Rows, display);
        }
        ui.EndSectionPanel();
    }

    private void BuildDetailMonthControl(UiBuilder ui, DashboardPageDefinition page, IncomeSavingsPageView view)
    {
        DashboardControlDefinition control = Control(page, "detail_month");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.IncomeSavings, "detail_month");
        string selected = options.Contains(view.DetailMonth, StringComparer.Ordinal)
            ? view.DetailMonth
            : options.FirstOrDefault() ?? string.Empty;
        if (string.IsNullOrEmpty(selected))
            return;

        ui.HStack(PorticoSkin.FilterGap, "IncomeSavingsDetailMonthControl")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(control.Label, "IncomeSavingsDetailMonthControl:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.Dropdown("Control:IncomeSavings:DetailMonth")
            .SetFlexGrow(1f)
            .Text(DetailMonthLabel(selected), "Control:IncomeSavings:DetailMonth:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in options)
            ui.Option(DetailMonthLabel(option));
        ui.SetSelectedOption(IndexOf(options, selected))
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.IncomeSavings, "detail_month", options[index]);
                _requestRebuild();
            })
        .EndDropdown();
        ui.End();
    }

    private static void BuildDetailMetrics(UiBuilder ui, IReadOnlyList<ReportMetric> metrics, Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.CompactGap, "IncomeSavingsDetailMetricDeck")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in metrics)
        {
            ui.MetricCard($"IncomeSavingsDetailMetric:{metric.Label}")
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, "IncomeSavingsDetail")
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"IncomeSavingsDetail:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();
    }

    private void BuildDetailTabs(UiBuilder ui, IncomeSavingsPageView view)
    {
        string selected = _session.Presentation.IncomeSavings.DetailTab is "Included" or "Excluded"
            ? _session.Presentation.IncomeSavings.DetailTab
            : "Included";
        IReadOnlyList<string> tabs = [
            $"Included ({view.IncludedTransactions.Count})",
            $"Excluded ({view.ExcludedTransactions.Count})"
        ];
        int selectedIndex = selected == "Included" ? 0 : 1;

        ui.SegmentedControl("IncomeSavingsDetailTabs")
            .SetFlexGrow(1f);
        foreach (string tab in tabs)
            ui.Segment(tab);
        ui.SetSelectedSegment(selectedIndex)
            .SetOnSegmentChanged((index, _) =>
            {
                _session.Presentation.SetIncomeDetailTab(index == 0 ? "Included" : "Excluded");
                _requestRebuild();
            })
        .EndSegmentedControl();
    }

    private void BuildMonthlyTotals(
        UiBuilder ui,
        DashboardPageReport report,
        IncomeSavingsPageView view,
        Func<string?, string> display)
    {
        DashboardWidgetReport totals = ReportFor(report, "income.monthly_totals");
        bool expanded = _session.Presentation.IncomeSavings.MonthlyTotalsExpanded;
        ui.Collapsible("Monthly totals", expanded)
            .SetOnCollapsibleToggled(next =>
            {
                _session.Presentation.SetIncomeMonthlyTotalsExpanded(next);
                _requestRebuild();
            });
        if (totals.Rows.Count == 0)
            ui.EmptyPanel("Monthly totals", totals.EmptyMessage ?? view.EmptyMessage ?? "No monthly totals are available.", "IncomeSavingsTotalsEmpty");
        else
            PorticoTableRenderer.Build(ui, "income-monthly-totals", totals.Columns, totals.Rows, display);
        ui.EndCollapsible();
    }

    private static DashboardWidgetDefinition Widget(DashboardPageDefinition page, string id)
        => page.Widgets.Single(widget => string.Equals(widget.Id, id, StringComparison.Ordinal));

    private static DashboardWidgetReport ReportFor(DashboardPageReport report, string id)
        => report.Widgets.TryGetValue(id, out DashboardWidgetReport? value)
            ? value
            : throw new InvalidOperationException($"Income and savings report '{id}' is missing.");

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

        throw new InvalidOperationException($"Income and savings control has no selected option '{selected}'.");
    }

    private static string LookbackLabel(string value)
        => int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int months)
            ? months switch
            {
                3 => "3M",
                6 => "6M",
                12 => "1Y",
                24 => "2Y",
                _ => $"{months}M"
            }
            : value;

    private static string CalculationLabel(string value)
        => string.Equals(value, "regular", StringComparison.Ordinal) ? "Regular" : "Actual";

    private static string DetailMonthLabel(string value)
        => YearMonth.TryParse(value, out YearMonth month)
            ? month.Start.ToString("MMMM yyyy", CultureInfo.InvariantCulture)
            : value;

    private static void AddActionButton(
        UiBuilder ui,
        string name,
        string label,
        Action action,
        string style,
        bool compact)
    {
        ui.Button(name)
            .SetPadding(
                compact ? PorticoSkin.CompactActionHorizontalPadding : PorticoSkin.ActionHorizontalPadding,
                compact ? PorticoSkin.CompactActionVerticalPadding : PorticoSkin.ActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(style)
            .SetCommandSurface(pointer: true, focus: true)
            .SetOnCommand(
                _ =>
                {
                    action();
                    return true;
                },
                (int)InputCommands.ClickLeft,
                (int)InputCommands.Accept);
        ui.Text(label, $"{name}:Text")
            .SetTextStyle(compact ? PorticoSkin.CompactActionText : PorticoSkin.ActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.EndButton();
    }
}
