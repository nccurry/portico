using System.Globalization;
using Portico.App.Ui;
using Portico.App.Ui.Components;
using Portico.Dashboard;
using Portico.Finance;
using Roci.Core;
using Roci.Input;
using Roci.Ui;
using Roci.Ui.Widgets;

namespace Portico.App.Ui.Pages;

/// <summary>Builds the source-shaped Spending by category page from configured controls and reports.</summary>
internal sealed class PorticoSpendingPageRenderer
{
    private static readonly string[] RequiredWidgets =
    [
        "summary",
        "trend",
        "ranking",
        "overview",
        "detail-summary",
        "detail-history",
        "detail-categories",
        "detail-merchants",
        "detail-transactions",
        "excluded"
    ];

    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;
    private readonly Dictionary<string, PorticoMultiSelectState<string>> _multiSelectStates = new(StringComparer.Ordinal);
    private string _includedTermDraft = string.Empty;
    private string _excludedTermDraft = string.Empty;

    /// <summary>Creates the renderer around the dashboard session that owns spending report state.</summary>
    public PorticoSpendingPageRenderer(DashboardSession session, Action requestRebuild)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
    }

    /// <summary>Gets whether a page has the complete source-shaped Spending grammar.</summary>
    public bool CanRender(DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(page);
        return page.Id == DashboardPageId.Spending
            && RequiredWidgets.All(id => page.Widgets.Any(widget => string.Equals(widget.Id, id, StringComparison.Ordinal)))
            && HasControls(page,
                "lookback",
                "spending_view",
                "comparison",
                "adjust_view",
                "reset_adjustments",
                "exclude_groups",
                "exclude_categories",
                "include_transaction_names",
                "exclude_transaction_names",
                "exclude_large_expenses",
                "expense_limit",
                "breakdown",
                "detail_month");
    }

    /// <summary>Builds the source title and data-date caption.</summary>
    public void BuildHeader(UiBuilder ui, DashboardPageDefinition page, DashboardPageReport report)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);

        DashboardWidgetReport summary = ReportFor(report, "spending.summary");
        ui.PageHeader();
        ui.Text(page.PageHeading ?? page.Title, "PageTitle")
            .SetTextStyle(PorticoSkin.PageTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        string caption = summary.DateGuide is DateOnly date
            ? $"Spending through {date.ToString("MMMM d, yyyy", CultureInfo.InvariantCulture)}"
            : "Spending by category";
        ui.Text(caption, "SpendingPageCaption")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.EndPageHeader();
    }

    /// <summary>Builds controls, report sections, retained selected detail, and excluded rows.</summary>
    public void Build(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, float> buildExpandedWidget,
        Func<string?, string> display)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);
        ArgumentNullException.ThrowIfNull(buildExpandedWidget);
        ArgumentNullException.ThrowIfNull(display);

        BuildControls(ui, page);
        if (HasCurrentIncludedRows(report))
            BuildSummary(ui, report, display);
        BuildWhereMoneyWent(ui, page, report, buildExpandedWidget, display);
        if (HasCurrentIncludedRows(report))
            BuildSelectedDetail(ui, page, report, buildExpandedWidget, display);
        BuildExcludedRows(ui, report, display);
    }

    /// <summary>Returns a local multi-select state for interaction tests.</summary>
    public PorticoMultiSelectState<string>? MultiSelectState(string controlId)
        => _multiSelectStates.GetValueOrDefault(controlId);

    private void BuildControls(UiBuilder ui, DashboardPageDefinition page)
    {
        // The source page keeps its filters on the page background. The shared
        // control bar is intentionally panel-shaped for older pages, so this
        // page owns its source-shaped wrapping row.
        ui.HStack(PorticoSkin.CompactGap, "SpendingControlBar")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.End);
        BuildSegmentedControl(ui, page, "lookback", "SpendingTimeFrame", LookbackLabel);
        BuildDropdownControl(ui, page, "spending_view", "SpendingView", SpendingViewLabel);
        BuildSegmentedControl(ui, page, "comparison", "SpendingComparison", ComparisonLabel);
        BuildAdjustControl(ui, page);
        ui.End();
    }

    private void BuildSegmentedControl(
        UiBuilder ui,
        DashboardPageDefinition page,
        string controlId,
        string name,
        Func<string, string> display)
    {
        DashboardControlDefinition control = Control(page, controlId);
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Spending, controlId);
        string selected = _session.ControlValue(DashboardPageId.Spending, controlId);
        int selectedIndex = IndexOf(options, selected);

        BeginSourceControlGroup(ui, controlId, controlId == "lookback" ? 232f : PorticoSkin.ControlMinimumWidth);
        ui.Text(control.Label, $"Control:Spending:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.SegmentedControl($"Control:Spending:{name}")
            .SetFlexGrow(1f)
            .SetFlexShrink(1f);
        foreach (string option in options)
            ui.Segment(display(option));
        ui.SetSelectedSegment(selectedIndex)
            .SetOnSegmentChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Spending, controlId, options[index]);
                _requestRebuild();
            })
        .EndSegmentedControl();
        ui.End();
    }

    private void BuildDropdownControl(
        UiBuilder ui,
        DashboardPageDefinition page,
        string controlId,
        string name,
        Func<string, string> display)
    {
        DashboardControlDefinition control = Control(page, controlId);
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Spending, controlId);
        string selected = _session.ControlValue(DashboardPageId.Spending, controlId);

        BeginSourceControlGroup(ui, controlId, PorticoSkin.ControlMinimumWidth);
        ui.Text(control.Label, $"Control:Spending:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.Dropdown($"Control:Spending:{name}")
            .SetFlexGrow(1f)
            .Text(display(selected), $"Control:Spending:{name}:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in options)
            ui.Option(display(option));
        ui.SetSelectedOption(IndexOf(options, selected))
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Spending, controlId, options[index]);
                _requestRebuild();
            })
        .EndDropdown();
        ui.End();
    }

    private static void BeginSourceControlGroup(UiBuilder ui, string controlId, float minimumWidth)
    {
        ui.VStack(PorticoSkin.FilterGap, $"Control:Spending:{controlId}:Group")
            .SetFlexBasis(minimumWidth)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Stretch);
    }

    private void BuildAdjustControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "adjust_view");
        bool modified = _session.Filters.SpendingAdjustments?.IsModified == true;
        string label = modified ? $"{control.Label} · modified" : control.Label;
        PopoverState? popover = null;

        ui.HStack(PorticoSkin.FilterGap, "Control:Spending:adjust_view:Group")
            .SetFlexBasis(320f)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Center);
        ui.Button("Control:Spending:AdjustView")
            .SetFlexBasis(320f)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetPadding(PorticoSkin.CompactActionHorizontalPadding, PorticoSkin.CompactActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(modified ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle)
            .SetCommandSurface(pointer: true, focus: true);
        ui.Text(label, "Control:Spending:AdjustView:Text")
            .SetTextStyle(PorticoSkin.ActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.SetPopover(
                content => BuildAdjustPopover(content, page, () => popover),
                PopoverOpenMode.Manual)
            .Configure(node =>
            {
                popover = node.GetStateOrDefault<PopoverState>()
                    ?? throw new InvalidOperationException("Spending Adjust view needs a popover state.");
                popover.OnOpened = () => _session.SetSpendingAdjustViewOpen(true);
                popover.OnClosed = () => _session.SetSpendingAdjustViewOpen(false);
                UiBuilder.SetPopoverOpen(popover, _session.Presentation.Spending.AdjustViewOpen);
            })
            .SetOnCommand(_ =>
            {
                PopoverState current = popover
                    ?? throw new InvalidOperationException("Spending Adjust view needs a popover state.");
                bool open = !_session.Presentation.Spending.AdjustViewOpen;
                _session.SetSpendingAdjustViewOpen(open);
                UiBuilder.SetPopoverOpen(current, open);
                _requestRebuild();
                return true;
            }, (int)InputCommands.ClickLeft, (int)InputCommands.Accept);
        ui.EndButton();
        ui.End();
    }

    private void BuildAdjustPopover(UiBuilder ui, DashboardPageDefinition page, Func<PopoverState?> popover)
    {
        ui.VStack(PorticoSkin.SectionGap, "SpendingAdjustPopover")
            .SetWidth(400f)
            .SetMaxHeight(520f)
            .SetScrollable(vertical: true, horizontal: false)
            .SetPadding(PorticoSkin.ControlBarPadding)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.HStack(PorticoSkin.CompactGap, "SpendingAdjustPopover:Header")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text("Adjust view", "SpendingAdjustPopover:Title")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        AddActionButton(
            ui,
            "Control:Spending:ResetAdjustments",
            Control(page, "reset_adjustments").Label,
            () =>
            {
                _session.InvokeControlAction(DashboardPageId.Spending, "reset_adjustments");
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle,
            compact: true);
        ui.End();

        BuildAdjustmentMultiSelect(ui, page, "exclude_groups");
        BuildAdjustmentMultiSelect(ui, page, "exclude_categories");
        BuildTextTerms(ui, page, "include_transaction_names", () => _includedTermDraft, value => _includedTermDraft = value);
        BuildTextTerms(ui, page, "exclude_transaction_names", () => _excludedTermDraft, value => _excludedTermDraft = value);
        BuildLargeExpenseControl(ui, page);

        AddActionButton(
            ui,
            "Control:Spending:CloseAdjustments",
            "Close",
            () =>
            {
                _session.SetSpendingAdjustViewOpen(false);
                if (popover() is { } current)
                    UiBuilder.SetPopoverOpen(current, false);
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
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Spending, controlId);
        PorticoMultiSelectItem<string>[] items = options
            .Select(value => new PorticoMultiSelectItem<string>(value, value, value))
            .ToArray();

        ui.VStack(PorticoSkin.FilterGap, $"SpendingAdjustment:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"SpendingAdjustment:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.MultiSelect(
            $"Control:Spending:{controlId}",
            control.Label,
            items,
            _session.ControlValues(DashboardPageId.Spending, controlId),
            state,
            values => _session.SetControlValues(DashboardPageId.Spending, controlId, values),
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
        IReadOnlySet<string> values = _session.ControlValues(DashboardPageId.Spending, controlId);
        ui.VStack(PorticoSkin.FilterGap, $"SpendingTerms:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"SpendingTerms:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        ui.HStack(PorticoSkin.FilterGap, $"SpendingTerms:{controlId}:Input")
            .SetCrossAlign(CrossAlignment.Center);
        string currentDraft = getDraft();
        ui.TextInput($"Control:Spending:{controlId}:Input", "Type text")
            .SetFlexGrow(1f)
            .Configure(node =>
            {
                TextInputState state = node.GetStateOrDefault<TextInputState>()
                    ?? throw new InvalidOperationException("Spending term input needs a text state.");
                state.Text = currentDraft;
            })
            .SetOnTextChanged(setDraft)
        .End();
        AddActionButton(
            ui,
            $"Control:Spending:{controlId}:Add",
            "Add",
            () =>
            {
                string next = getDraft();
                if (string.IsNullOrWhiteSpace(next))
                    return;
                _session.SetControlValues(DashboardPageId.Spending, controlId, values.Append(next));
                setDraft(string.Empty);
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle,
            compact: true);
        ui.End();

        if (values.Count > 0)
        {
            ui.HStack(PorticoSkin.FilterGap, $"SpendingTerms:{controlId}:Values")
                .SetFlexWrap()
                .SetCrossGap(PorticoSkin.FilterGap)
                .SetCrossAlign(CrossAlignment.Center);
            foreach (string value in values.OrderBy(value => value, StringComparer.Ordinal))
            {
                string captured = value;
                AddActionButton(
                    ui,
                    $"Control:Spending:{controlId}:Remove:{captured}",
                    $"Remove {captured}",
                    () =>
                    {
                        _session.SetControlValues(DashboardPageId.Spending, controlId, values.Where(value => !string.Equals(value, captured, StringComparison.Ordinal)));
                        _requestRebuild();
                    },
                    PorticoSkin.QuietActionStyle,
                    compact: true);
            }
            ui.End();
        }
        ui.End();
    }

    private void BuildLargeExpenseControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition toggle = Control(page, "exclude_large_expenses");
        bool selected = bool.Parse(_session.ControlValue(DashboardPageId.Spending, "exclude_large_expenses"));
        ui.VStack(PorticoSkin.FilterGap, "SpendingLargeExpense")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.ToggleButton("Control:Spending:exclude_large_expenses", selected, next =>
        {
            _session.SetControlToggle(DashboardPageId.Spending, "exclude_large_expenses", next);
            _requestRebuild();
        })
            .SetFlexGrow(1f);
        ui.Text(toggle.Label, "Control:Spending:exclude_large_expenses:Label")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        ui.EndButton();

        if (selected)
        {
            DashboardControlDefinition limit = Control(page, "expense_limit");
            decimal value = decimal.Parse(_session.ControlValue(DashboardPageId.Spending, "expense_limit"), CultureInfo.InvariantCulture);
            ui.HStack(PorticoSkin.FilterGap, "SpendingExpenseLimit")
                .SetCrossAlign(CrossAlignment.Center);
            ui.Text(limit.Label, "Control:Spending:expense_limit:Label")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
            ui.NumberInput(
                    "Control:Spending:expense_limit",
                    (double)limit.Minimum!.Value,
                    (double)limit.Maximum!.Value,
                    (double)value,
                    (double)limit.Step!.Value)
                .SetFlexGrow(1f)
                .SetOnNumberValueChanged(next =>
                {
                    _session.SetControlNumber(DashboardPageId.Spending, "expense_limit", (decimal)next);
                    _requestRebuild();
                })
            .EndNumberInput();
            ui.End();
        }
        ui.End();
    }

    private void BuildSummary(UiBuilder ui, DashboardPageReport report, Func<string?, string> display)
    {
        DashboardWidgetReport summary = ReportFor(report, "spending.summary");
        ui.HStack(PorticoSkin.CompactGap, "SpendingMetricDeck")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in summary.Metrics.Take(3))
        {
            ui.MetricCard($"SpendingMetric:{metric.Label}")
                .SetStyle(PorticoSkin.RaisedPanelStyle)
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, "Spending")
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"Spending:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();

        ReportMetric? excluded = summary.Metrics.Skip(3).FirstOrDefault(metric => metric.Label == "Excluded");
        if (excluded is { Value: > 0m })
        {
            ui.HStack(PorticoSkin.CompactGap, "SpendingExclusionBadgeRow")
                .SetFlexGrow(0f)
                .SetFlexShrink(0f)
                .SetMinSize(0f, 32f)
                .SetMargin(0f, 0f, 0f, PorticoSkin.CompactGap)
                .SetCrossAlign(CrossAlignment.Center);
            ui.Panel("SpendingExclusionBadge")
                .SetPadding(PorticoSkin.StatusPadding)
                .SetCornerRadius(PorticoSkin.SmallCornerRadius)
                .SetStyle(PorticoSkin.MutedPanelStyle);
            ui.Text($"{display(excluded.Display)} excluded · {display(excluded.Detail)}", "SpendingExclusionBadge:Text")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
            ui.End();
            ui.End();
        }
    }

    private void BuildWhereMoneyWent(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, float> buildExpandedWidget,
        Func<string?, string> display)
    {
        DashboardWidgetReport overview = ReportFor(report, "spending.overview");
        ui.SectionPanel(
            "Section:where_money_went",
            "Where the money went",
            "Compare the spending trend with the ranked breakdown.");
        BuildBreakdownControl(ui, page);

        if (!HasCurrentIncludedRows(report))
        {
            ui.EmptyPanel(
                "No spending is included in this view.",
                "Adjust the filters to continue.",
                "SpendingNoIncludedRows");
            ui.EndSectionPanel();
            return;
        }

        if (overview.Rows.Count == 0)
        {
            ui.EmptyPanel("No spending to show", overview.EmptyMessage ?? "No spending matches these controls.", "SpendingNoResults");
            ui.EndSectionPanel();
            return;
        }

        ui.HStack(PorticoSkin.SectionGap, "SpendingChartSplit")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.SectionGap)
            .SetCrossAlign(CrossAlignment.Start);
        BuildWidget(page, report, "trend", buildExpandedWidget, 1.45f, "Monthly trend · top 5");
        int rankedCount = ReportFor(report, "spending.ranking").Series.Sum(series => series.Points.Count);
        string entityLabel = _session.Filters.SpendingBreakdown == SpendingBreakdown.Group ? "groups" : "categories";
        BuildWidget(
            page,
            report,
            "ranking",
            buildExpandedWidget,
            1f,
            $"Top {display(rankedCount.ToString(CultureInfo.InvariantCulture))} {entityLabel} by spending");
        ui.End();
        BuildOverviewRows(ui, overview, display);
        ui.EndSectionPanel();
    }

    private void BuildBreakdownControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "breakdown");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Spending, "breakdown");
        string selected = _session.ControlValue(DashboardPageId.Spending, "breakdown");
        ui.VStack(PorticoSkin.FilterGap, "SpendingBreakdownControl")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, "SpendingBreakdownControl:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.SegmentedControl("Control:Spending:Breakdown")
            .SetFlexGrow(1f);
        foreach (string option in options)
            ui.Segment(TitleCase(option));
        ui.SetSelectedSegment(IndexOf(options, selected))
            .SetOnSegmentChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Spending, "breakdown", options[index]);
                _requestRebuild();
            })
        .EndSegmentedControl();
        ui.End();
    }

    private void BuildOverviewRows(UiBuilder ui, DashboardWidgetReport overview, Func<string?, string> display)
    {
        string? selected = _session.Presentation.Spending.SelectedEntity(_session.Filters.SpendingBreakdown);
        ui.VStack(PorticoSkin.TableGap, "SpendingOverview")
            .SetMaxHeight(360f)
            .SetScrollable(vertical: true, horizontal: true)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.HStack(PorticoSkin.TableRowGap, "SpendingOverview:Header")
            .SetPadding(PorticoSkin.TableRowHorizontalPadding, PorticoSkin.TableRowVerticalPadding)
            .SetCornerRadius(PorticoSkin.TableCornerRadius)
            .SetCrossAlign(CrossAlignment.Center)
            .SetStyle(PorticoSkin.MutedPanelStyle);
        foreach (string column in overview.Columns)
        {
            ui.Text(column, $"SpendingOverview:Header:{column}")
                .SetFlexBasis(column == "Monthly trend" ? 132f : 112f)
                .SetFlexGrow(0f)
                .SetFlexShrink(0f)
                .SetTextStyle(PorticoSkin.NavigationGroupLabelText)
                .SetFontStyle(FontStyle.Bold)
            .End();
        }
        ui.End();

        for (int index = 0; index < Math.Min(overview.Rows.Count, 12); index++)
        {
            ReportTableRow row = overview.Rows[index];
            string entity = row.Values[0];
            bool isSelected = string.Equals(entity, selected, StringComparison.Ordinal)
                || (selected is null && index == 0);
            ui.Button($"SpendingOverviewRow:{entity}")
                .SetPadding(PorticoSkin.TableRowHorizontalPadding, PorticoSkin.TableRowVerticalPadding)
                .SetCornerRadius(PorticoSkin.TableCornerRadius)
                .SetStyle(isSelected ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle)
                .SetCommandSurface(pointer: true, focus: true)
                .SetOnCommand(
                    _ =>
                    {
                        _session.SetSpendingSelectedEntity(_session.Filters.SpendingBreakdown, entity);
                        _requestRebuild();
                        return true;
                    },
                    (int)InputCommands.ClickLeft,
                    (int)InputCommands.Accept);
            ui.HStack(PorticoSkin.TableRowGap, $"SpendingOverviewRow:{entity}:Content")
                .SetFlexGrow(1f)
                .SetCrossAlign(CrossAlignment.Center);
            for (int valueIndex = 0; valueIndex < row.Values.Count; valueIndex++)
            {
                string value = row.Values[valueIndex];
                string column = overview.Columns[valueIndex];
                if (column == "Monthly trend")
                {
                    ReportSeries? series = overview.Series.FirstOrDefault(item => string.Equals(item.Label, entity, StringComparison.Ordinal));
                    if (series is not null)
                    {
                        ui.Sparkline($"SpendingOverviewSparkline:{entity}")
                            .Values(series.Points.Select(point => (double)point.Y))
                            .Filled()
                            .Stroke(PorticoSkin.Accent)
                            .SetFlexBasis(132f)
                            .SetFlexGrow(0f)
                            .SetFlexShrink(0f)
                        .EndChart();
                        continue;
                    }
                }

                ui.Text(display(value), $"SpendingOverviewRow:{entity}:{value}")
                    .SetFlexBasis(112f)
                    .SetFlexGrow(0f)
                    .SetFlexShrink(0f)
                    .SetTextStyle(PorticoSkin.HelperText)
                .End();
            }
            ui.End();
            ui.EndButton();
        }
        ui.End();
    }

    private void BuildSelectedDetail(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, float> buildExpandedWidget,
        Func<string?, string> display)
    {
        DashboardWidgetReport overview = ReportFor(report, "spending.overview");
        if (overview.Rows.Count == 0)
            return;

        ReportTableRow selectedRow = SelectedRow(overview);
        string entity = DetailTitle(selectedRow);
        IReadOnlyList<string> tabs = _session.Filters.SpendingBreakdown == SpendingBreakdown.Group
            ? ["Categories", "Merchants", "Transactions"]
            : ["Merchants", "Transactions"];
        string selectedTab = tabs.Contains(_session.Presentation.Spending.DetailTab, StringComparer.Ordinal)
            ? _session.Presentation.Spending.DetailTab
            : tabs[0];

        ui.SectionPanel(
            "Section:selected_detail",
            entity,
            "Choose a month, then inspect the selected spending detail.");
        BuildDetailMetricDeck(ui, ReportFor(report, "spending.detail_summary"), display);
        BuildWidget(page, report, "detail-history", buildExpandedWidget, 1f);
        BuildDetailMonthControl(ui, page);
        BuildDetailTabs(ui, tabs, selectedTab);
        DashboardWidgetReport detail = selectedTab switch
        {
            "Categories" => ReportFor(report, "spending.detail_categories"),
            "Merchants" => ReportFor(report, "spending.detail_merchants"),
            "Transactions" => ReportFor(report, "spending.detail_transactions"),
            _ => throw new InvalidOperationException($"Unsupported Spending detail tab '{selectedTab}'.")
        };
        if (detail.Rows.Count == 0)
            ui.EmptyPanel(selectedTab, detail.EmptyMessage ?? "No detail matches this selection.", $"SpendingDetailEmpty:{selectedTab}");
        else
            PorticoTableRenderer.Build(ui, $"spending-detail:{selectedTab}", detail.Columns, detail.Rows, display);
        ui.EndSectionPanel();
    }

    private void BuildDetailMonthControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "detail_month");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Spending, "detail_month");
        string selected = _session.ControlValue(DashboardPageId.Spending, "detail_month");
        if (!options.Contains(selected, StringComparer.Ordinal))
            selected = "all";

        ui.HStack(PorticoSkin.FilterGap, "SpendingDetailMonthControl")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(control.Label, "SpendingDetailMonthControl:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.Dropdown("Control:Spending:DetailMonth")
            .SetFlexGrow(1f)
            .Text(DetailMonthLabel(selected), "Control:Spending:DetailMonth:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in options)
            ui.Option(DetailMonthLabel(option));
        ui.SetSelectedOption(IndexOf(options, selected))
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Spending, "detail_month", options[index]);
                _requestRebuild();
            })
        .EndDropdown();
        ui.End();
    }

    private static void BuildDetailMetricDeck(UiBuilder ui, DashboardWidgetReport summary, Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.CompactGap, "SpendingDetailMetricDeck")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in summary.Metrics)
        {
            ui.MetricCard($"SpendingDetailMetric:{metric.Label}")
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, "SpendingDetail")
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"SpendingDetail:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();
    }

    private void BuildDetailTabs(UiBuilder ui, IReadOnlyList<string> tabs, string selected)
    {
        ui.SegmentedControl("SpendingDetailTabs")
            .SetFlexGrow(1f);
        foreach (string tab in tabs)
            ui.Segment(tab);
        ui.SetSelectedSegment(IndexOf(tabs, selected))
            .SetOnSegmentChanged((index, _) =>
            {
                _session.SetSpendingDetailTab(tabs[index]);
                _requestRebuild();
            })
        .EndSegmentedControl();
    }

    private void BuildExcludedRows(UiBuilder ui, DashboardPageReport report, Func<string?, string> display)
    {
        DashboardWidgetReport excluded = ReportFor(report, "spending.excluded");
        if (excluded.Rows.Count == 0)
            return;

        bool expanded = _session.Presentation.Spending.ExcludedRowsExpanded;
        ui.Collapsible($"Excluded from this view ({excluded.Rows.Count})", expanded)
            .SetOnCollapsibleToggled(next =>
            {
                _session.SetSpendingExcludedRowsExpanded(next);
                _requestRebuild();
            });
        PorticoTableRenderer.Build(ui, "spending-excluded", excluded.Columns, excluded.Rows, display);
        ui.EndCollapsible();
    }

    private static void BuildWidget(
        DashboardPageDefinition page,
        DashboardPageReport report,
        string widgetId,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, float> buildExpandedWidget,
        float grow,
        string? title = null)
    {
        DashboardWidgetDefinition widget = page.Widgets.Single(candidate => candidate.Id == widgetId);
        if (title is not null)
            widget = widget with { Title = title };
        buildExpandedWidget(widget, ReportFor(report, widget.Report), grow);
    }

    private static DashboardWidgetReport ReportFor(DashboardPageReport report, string id)
        => report.Widgets.TryGetValue(id, out DashboardWidgetReport? value)
            ? value
            : throw new InvalidOperationException($"Spending report '{id}' is missing.");

    private static bool HasCurrentIncludedRows(DashboardPageReport report)
        => ReportFor(report, "spending.summary").Metrics
            .FirstOrDefault(metric => metric.Label == "Included rows")
            ?.Value > 0m;

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

        throw new InvalidOperationException($"Spending control has no selected option '{selected}'.");
    }

    private ReportTableRow SelectedRow(DashboardWidgetReport overview)
    {
        string? selected = _session.Presentation.Spending.SelectedEntity(_session.Filters.SpendingBreakdown);
        return overview.Rows.FirstOrDefault(row => string.Equals(row.Values[0], selected, StringComparison.Ordinal))
            ?? overview.Rows[0];
    }

    private string DetailTitle(ReportTableRow row)
        => _session.Filters.SpendingBreakdown == SpendingBreakdown.Category && row.Values.Count > 1
            ? $"{row.Values[0]} · {row.Values[1]}"
            : row.Values[0];

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

    private string SpendingViewLabel(string value) => _session.SpendingSetLabel(value);

    private static string ComparisonLabel(string value)
        => value == "last_year" ? "Last year" : "Previous period";

    private static string DetailMonthLabel(string value)
        => value == "all"
            ? "All months"
            : YearMonth.TryParse(value, out YearMonth month)
                ? month.Start.ToString("MMMM yyyy", CultureInfo.InvariantCulture)
                : value;

    private static string TitleCase(string value)
        => value.Length == 0 ? value : char.ToUpperInvariant(value[0]) + value[1..];

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
