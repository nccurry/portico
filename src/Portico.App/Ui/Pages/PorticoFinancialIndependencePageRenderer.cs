using System.Globalization;

using Portico.App.Ui;
using Portico.App.Ui.Components;
using Portico.Dashboard;
using Roci.Core;
using Roci.Input;
using Roci.Ui;
using Roci.Ui.Widgets;

namespace Portico.App.Ui.Pages;

/// <summary>Builds the source-shaped Financial Independence scenario page from typed reports.</summary>
internal sealed class PorticoFinancialIndependencePageRenderer
{
    private static readonly string[] RequiredWidgets =
    ["summary", "projection", "funding", "sensitivity", "source-accounts", "source-spending", "source-transactions"];

    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;
    private readonly Dictionary<string, PorticoMultiSelectState<string>> _multiSelectStates = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _termDrafts = new(StringComparer.Ordinal);

    /// <summary>Creates the Financial Independence renderer around the dashboard session.</summary>
    public PorticoFinancialIndependencePageRenderer(DashboardSession session, Action requestRebuild)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
    }

    /// <summary>Gets whether a page declares the complete source-shaped FI grammar.</summary>
    public bool CanRender(DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(page);
        return page.Id == DashboardPageId.FinancialIndependence
            && RequiredWidgets.All(id => page.Widgets.Any(widget => string.Equals(widget.Id, id, StringComparison.Ordinal)))
            && HasControls(
                page,
                "assets",
                "spending",
                "income",
                "return_rate",
                "withdrawal_rate",
                "years",
                "reset_scenario",
                "adjust_source_data",
                "include_accounts",
                "spending_lookback",
                "exclude_groups",
                "exclude_categories",
                "include_transaction_names",
                "exclude_transaction_names",
                "exclude_large_expenses",
                "expense_limit",
                "source_details",
                "source_tab");
    }

    /// <summary>Builds the source page title and source-data caption.</summary>
    public void BuildHeader(UiBuilder ui, DashboardPageDefinition page, DashboardPageReport report)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);

        FinancialIndependencePageView view = View(report);
        ui.PageHeader();
        ui.Text(page.PageHeading ?? page.Title, "PageTitle")
            .SetTextStyle(PorticoSkin.PageTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.Text(view.LatestDataCaption ?? "Portfolio funding, projection, and runway sensitivity", "FinancialIndependencePageCaption")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.EndPageHeader();
    }

    /// <summary>Builds source controls, the editable scenario, charts, and source-details tabs.</summary>
    public void Build(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool> buildWidget,
        Func<string?, string> display)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);
        ArgumentNullException.ThrowIfNull(buildWidget);
        ArgumentNullException.ThrowIfNull(display);

        FinancialIndependencePageView view = View(report);
        BuildSourceControl(ui, page);
        if (view.EmptyMessage is not null)
        {
            ui.EmptyPanel("Financial Independence needs source data", view.EmptyMessage, "FinancialIndependenceEmpty");
            return;
        }

        BuildScenario(ui, page);
        BuildMetricDeck(ui, ReportFor(report, "fi.summary"), display);
        ui.SectionPanel("Section:fi_projection", "Portfolio runway projection", "See the selected annual scenario through the requested projection horizon.");
        buildWidget(Widget(page, "projection"), ReportFor(report, "fi.projection"), false);
        ui.EndSectionPanel();

        ui.HStack(PorticoSkin.SectionGap, "FinancialIndependenceFundingSplit")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.SectionGap)
            .SetCrossAlign(CrossAlignment.Start);
        buildWidget(Widget(page, "funding"), ReportFor(report, "fi.funding"), true);
        buildWidget(Widget(page, "sensitivity"), ReportFor(report, "fi.sensitivity"), true);
        ui.End();
        BuildSourceDetails(ui, page, report, display);
    }

    /// <summary>Returns retained multi-select state for focused interaction tests.</summary>
    public PorticoMultiSelectState<string>? MultiSelectState(string controlId)
        => _multiSelectStates.GetValueOrDefault(controlId);

    private void BuildSourceControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "adjust_source_data");
        bool open = _session.Presentation.FinancialIndependence.AdjustSourceDataOpen;
        PopoverState? popover = null;
        ui.HStack(PorticoSkin.CompactGap, "FinancialIndependenceControlBar")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Button("Control:FinancialIndependence:AdjustSourceData")
            .SetPadding(PorticoSkin.CompactActionHorizontalPadding, PorticoSkin.CompactActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(open ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle)
            .SetCommandSurface(pointer: true, focus: true);
        ui.Text(control.Label, "Control:FinancialIndependence:AdjustSourceData:Text")
            .SetTextStyle(PorticoSkin.ActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.SetPopover(content => BuildSourcePopover(content, page, () => popover), PopoverOpenMode.Manual)
            .Configure(node =>
            {
                popover = node.GetStateOrDefault<PopoverState>()
                    ?? throw new InvalidOperationException("Financial Independence source controls need a popover state.");
                popover.OnOpened = () => _session.SetFinancialIndependenceAdjustSourceDataOpen(true);
                popover.OnClosed = () => _session.SetFinancialIndependenceAdjustSourceDataOpen(false);
                UiBuilder.SetPopoverOpen(popover, open);
            })
            .SetOnCommand(
                _ =>
                {
                    bool next = !_session.Presentation.FinancialIndependence.AdjustSourceDataOpen;
                    _session.SetFinancialIndependenceAdjustSourceDataOpen(next);
                    UiBuilder.SetPopoverOpen(popover!, next);
                    _requestRebuild();
                    return true;
                },
                (int)InputCommands.ClickLeft,
                (int)InputCommands.Accept);
        ui.EndButton();
        ui.End();
    }

    private void BuildSourcePopover(UiBuilder ui, DashboardPageDefinition page, Func<PopoverState?> popover)
    {
        ui.VStack(PorticoSkin.SectionGap, "FinancialIndependenceSourcePopover")
            .SetWidth(520f)
            .SetMaxHeight(620f)
            .SetScrollable(vertical: true, horizontal: false)
            .SetPadding(PorticoSkin.ControlBarPadding)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.HStack(PorticoSkin.CompactGap, "FinancialIndependenceSourcePopover:Header")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text("Adjust source data", "FinancialIndependenceSourcePopover:Title")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        AddActionButton(
            ui,
            "Control:FinancialIndependence:CloseSourceData",
            "Close",
            () =>
            {
                _session.SetFinancialIndependenceAdjustSourceDataOpen(false);
                if (popover() is { } state)
                    UiBuilder.SetPopoverOpen(state, false);
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle);
        ui.End();

        ui.HStack(PorticoSkin.SectionGap, "FinancialIndependenceSourcePopover:Columns")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.SectionGap)
            .SetCrossAlign(CrossAlignment.Start);
        ui.VStack(PorticoSkin.SectionGap, "FinancialIndependenceSourcePopover:Portfolio")
            .SetFlexBasis(220f)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text("Portfolio", "FinancialIndependenceSourcePopover:PortfolioTitle")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        BuildMultiSelect(ui, page, "include_accounts");
        BuildDropdown(ui, page, "spending_lookback", "Spending history", value => $"Last {value} months");
        ui.End();

        ui.VStack(PorticoSkin.SectionGap, "FinancialIndependenceSourcePopover:Spending")
            .SetFlexBasis(220f)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text("Spending baseline", "FinancialIndependenceSourcePopover:SpendingTitle")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        BuildMultiSelect(ui, page, "exclude_groups");
        BuildMultiSelect(ui, page, "exclude_categories");
        BuildTextTerms(ui, page, "include_transaction_names");
        BuildTextTerms(ui, page, "exclude_transaction_names");
        BuildLargeExpenseControl(ui, page);
        ui.End();
        ui.End();
        ui.End();
    }

    private void BuildScenario(UiBuilder ui, DashboardPageDefinition page)
    {
        ui.SectionPanel("Section:fi_scenario", "Scenario", "Edit annual assumptions without changing the source data.");
        DashboardControlDefinition reset = Control(page, "reset_scenario");
        AddActionButton(
            ui,
            "Control:FinancialIndependence:ResetScenario",
            reset.Label,
            () =>
            {
                _session.InvokeControlAction(DashboardPageId.FinancialIndependence, reset.Id);
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle);
        BuildScenarioRow(ui, page, ["assets", "spending", "income"]);
        BuildScenarioRow(ui, page, ["return_rate", "withdrawal_rate", "years"]);
        ui.EndSectionPanel();
    }

    private void BuildScenarioRow(UiBuilder ui, DashboardPageDefinition page, IReadOnlyList<string> controls)
    {
        ui.HStack(PorticoSkin.SectionGap, $"FinancialIndependenceScenarioRow:{controls[0]}")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.SectionGap)
            .SetCrossAlign(CrossAlignment.End);
        foreach (string id in controls)
            BuildNumberInput(ui, page, id, $"Scenario:{id}");
        ui.End();
    }

    private void BuildNumberInput(UiBuilder ui, DashboardPageDefinition page, string controlId, string scope)
    {
        DashboardControlDefinition control = Control(page, controlId);
        decimal value = decimal.Parse(_session.ControlValue(DashboardPageId.FinancialIndependence, control.Id), CultureInfo.InvariantCulture);
        ui.VStack(PorticoSkin.FilterGap, $"FinancialIndependence{scope}")
            .SetFlexBasis(220f)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"FinancialIndependence{scope}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        ui.NumberInput(
                $"Control:FinancialIndependence:{controlId}",
                (double)control.Minimum!.Value,
                (double)control.Maximum!.Value,
                (double)value,
                (double)control.Step!.Value)
            .SetFlexGrow(1f)
            .SetOnNumberValueChanged(next =>
            {
                _session.SetControlNumber(DashboardPageId.FinancialIndependence, control.Id, (decimal)next);
                _requestRebuild();
            })
        .EndNumberInput();
        ui.End();
    }

    private void BuildMultiSelect(UiBuilder ui, DashboardPageDefinition page, string controlId)
    {
        DashboardControlDefinition control = Control(page, controlId);
        PorticoMultiSelectState<string> state = _multiSelectStates.GetValueOrDefault(controlId)
            ?? new PorticoMultiSelectState<string>(comparer: StringComparer.Ordinal);
        _multiSelectStates[controlId] = state;
        PorticoMultiSelectItem<string>[] items = _session.ControlOptions(DashboardPageId.FinancialIndependence, control.Id)
            .Select(value => new PorticoMultiSelectItem<string>(value, value, value))
            .ToArray();
        ui.VStack(PorticoSkin.FilterGap, $"FinancialIndependenceSource:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"FinancialIndependenceSource:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        ui.MultiSelect(
            $"Control:FinancialIndependence:{controlId}",
            control.Label,
            items,
            _session.ControlValues(DashboardPageId.FinancialIndependence, control.Id),
            state,
            values => _session.SetControlValues(DashboardPageId.FinancialIndependence, control.Id, values),
            _requestRebuild);
        ui.End();
    }

    private void BuildDropdown(
        UiBuilder ui,
        DashboardPageDefinition page,
        string controlId,
        string name,
        Func<string, string> display)
    {
        DashboardControlDefinition control = Control(page, controlId);
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.FinancialIndependence, control.Id);
        string selected = _session.ControlValue(DashboardPageId.FinancialIndependence, control.Id);
        ui.VStack(PorticoSkin.FilterGap, $"FinancialIndependenceSource:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"FinancialIndependenceSource:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.Dropdown($"Control:FinancialIndependence:{name}")
            .SetFlexGrow(1f)
            .Text(display(selected), $"Control:FinancialIndependence:{name}:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in options)
            ui.Option(display(option));
        ui.SetSelectedOption(IndexOf(options, selected))
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.FinancialIndependence, control.Id, options[index]);
                _requestRebuild();
            })
        .EndDropdown();
        ui.End();
    }

    private void BuildTextTerms(UiBuilder ui, DashboardPageDefinition page, string controlId)
    {
        DashboardControlDefinition control = Control(page, controlId);
        IReadOnlySet<string> values = _session.ControlValues(DashboardPageId.FinancialIndependence, control.Id);
        string draft = _termDrafts.GetValueOrDefault(controlId) ?? string.Empty;
        ui.VStack(PorticoSkin.FilterGap, $"FinancialIndependenceTerms:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"FinancialIndependenceTerms:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        ui.HStack(PorticoSkin.FilterGap, $"FinancialIndependenceTerms:{controlId}:Input")
            .SetCrossAlign(CrossAlignment.Center);
        ui.TextInput($"Control:FinancialIndependence:{controlId}:Input", "Type text")
            .SetFlexGrow(1f)
            .Configure(node =>
            {
                TextInputState state = node.GetStateOrDefault<TextInputState>()
                    ?? throw new InvalidOperationException("Financial Independence term input needs a text state.");
                state.Text = draft;
            })
            .SetOnTextChanged(value => _termDrafts[controlId] = value)
        .End();
        AddActionButton(
            ui,
            $"Control:FinancialIndependence:{controlId}:Add",
            "Add",
            () =>
            {
                string next = _termDrafts.GetValueOrDefault(controlId) ?? string.Empty;
                if (string.IsNullOrWhiteSpace(next))
                    return;
                _session.SetControlValues(DashboardPageId.FinancialIndependence, control.Id, values.Append(next));
                _termDrafts[controlId] = string.Empty;
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle);
        ui.End();
        if (values.Count > 0)
        {
            ui.HStack(PorticoSkin.FilterGap, $"FinancialIndependenceTerms:{controlId}:Values")
                .SetFlexWrap()
                .SetCrossGap(PorticoSkin.FilterGap)
                .SetCrossAlign(CrossAlignment.Center);
            foreach (string value in values.OrderBy(value => value, StringComparer.Ordinal))
            {
                string captured = value;
                AddActionButton(
                    ui,
                    $"Control:FinancialIndependence:{controlId}:Remove:{captured}",
                    $"Remove {captured}",
                    () =>
                    {
                        _session.SetControlValues(
                            DashboardPageId.FinancialIndependence,
                            control.Id,
                            values.Where(value => !string.Equals(value, captured, StringComparison.Ordinal)));
                        _requestRebuild();
                    },
                    PorticoSkin.QuietActionStyle);
            }
            ui.End();
        }
        ui.End();
    }

    private void BuildLargeExpenseControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition toggle = Control(page, "exclude_large_expenses");
        bool selected = bool.Parse(_session.ControlValue(DashboardPageId.FinancialIndependence, toggle.Id));
        ui.VStack(PorticoSkin.FilterGap, "FinancialIndependenceSource:LargeExpense")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.ToggleButton("Control:FinancialIndependence:exclude_large_expenses", selected, next =>
        {
            _session.SetControlToggle(DashboardPageId.FinancialIndependence, toggle.Id, next);
            _requestRebuild();
        })
            .SetFlexGrow(1f);
        ui.Text(toggle.Label, "FinancialIndependenceSource:LargeExpense:Label")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        ui.EndButton();

        if (selected)
            BuildNumberInput(ui, page, "expense_limit", "Source:expense_limit");
        ui.End();
    }

    private static void BuildMetricDeck(UiBuilder ui, DashboardWidgetReport summary, Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.CompactGap, "FinancialIndependenceMetricDeck")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in summary.Metrics)
        {
            ui.MetricCard($"FinancialIndependenceMetric:{metric.Label}")
                .SetStyle(PorticoSkin.RaisedPanelStyle)
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, "FinancialIndependence")
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"FinancialIndependence:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();
    }

    private void BuildSourceDetails(UiBuilder ui, DashboardPageDefinition page, DashboardPageReport report, Func<string?, string> display)
    {
        DashboardControlDefinition collapsible = Control(page, "source_details");
        DashboardControlDefinition tabControl = Control(page, "source_tab");
        bool expanded = _session.Presentation.FinancialIndependence.SourceDetailsOpen;
        string selected = _session.Presentation.FinancialIndependence.SourceDetailsTab;
        IReadOnlyList<string> tabs = _session.ControlOptions(DashboardPageId.FinancialIndependence, tabControl.Id);
        if (!tabs.Contains(selected, StringComparer.Ordinal))
            selected = tabs.FirstOrDefault() ?? "Accounts";

        ui.Collapsible(collapsible.Label, expanded)
            .SetOnCollapsibleToggled(next =>
            {
                _session.SetFinancialIndependenceSourceDetailsOpen(next);
                _requestRebuild();
            });
        ui.TabPanel("FinancialIndependenceSourceDetailsTabs")
            .AsWidget(out WidgetRef<TabPanelState> tabPanel)
            .SetFlexGrow(1f)
            .SetOnTabChanged(index =>
            {
                _session.SetControlValue(DashboardPageId.FinancialIndependence, tabControl.Id, tabs[index]);
                _requestRebuild();
            });
        foreach (string tab in tabs)
        {
            ui.Tab(tab);
            DashboardWidgetReport source = tab switch
            {
                "Accounts" => ReportFor(report, "fi.source_accounts"),
                "Spending" => ReportFor(report, "fi.source_spending"),
                "Transactions" => ReportFor(report, "fi.source_transactions"),
                _ => throw new InvalidOperationException($"Unsupported Financial Independence source tab '{tab}'.")
            };
            if (tab == "Spending")
            {
                ui.VStack(PorticoSkin.CompactGap, "FinancialIndependenceSourceSpending")
                    .SetMinSize(0f, 280f)
                    .SetPadding(PorticoSkin.WidgetPadding)
                    .SetCornerRadius(PorticoSkin.CardCornerRadius)
                    .SetStyle(PorticoSkin.RaisedPanelStyle);
                ui.Text("Spending history", "FinancialIndependenceSourceSpending:Title")
                    .SetTextStyle(PorticoSkin.SectionTitleText)
                    .SetFontStyle(FontStyle.Bold)
                .End();
                if (source.Series.Count == 0)
                    ui.EmptyPanel("No source spending", source.EmptyMessage ?? "No spending source data is available.", "FinancialIndependenceSourceSpendingEmpty");
                else
                    PorticoTableRenderer.Build(ui, "fi-source-spending", ["Month", "Spending"], source.Series[0].Points.Select(point => new ReportTableRow([
                        point.Date?.ToString("MMM yyyy", CultureInfo.InvariantCulture) ?? "",
                        point.Y.ToString("C0", CultureInfo.CurrentCulture)
                    ])).ToArray(), display);
                ui.End();
            }
            else if (source.Rows.Count == 0)
            {
                ui.EmptyPanel("No source data", source.EmptyMessage ?? "No source data is available.", $"FinancialIndependenceSourceEmpty:{tab}");
            }
            else
            {
                PorticoTableRenderer.Build(ui, $"fi-source-{tab.ToLowerInvariant()}", source.Columns, source.Rows, display, maximumRows: 100);
            }
            ui.EndTab();
        }
        tabPanel.SetActiveTab(IndexOf(tabs, selected));
        ui.EndTabPanel();
        ui.EndCollapsible();
    }

    private static FinancialIndependencePageView View(DashboardPageReport report)
        => report.FinancialIndependenceView ?? throw new InvalidOperationException("Financial Independence view is missing.");

    private static DashboardWidgetReport ReportFor(DashboardPageReport report, string id)
        => report.Widgets.TryGetValue(id, out DashboardWidgetReport? widget)
            ? widget
            : throw new InvalidOperationException($"Financial Independence report '{id}' is missing.");

    private static DashboardWidgetDefinition Widget(DashboardPageDefinition page, string id)
        => page.Widgets.Single(widget => string.Equals(widget.Id, id, StringComparison.Ordinal));

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

        return 0;
    }

    private static void AddActionButton(UiBuilder ui, string name, string label, Action action, string style)
    {
        ui.Button(name)
            .SetPadding(PorticoSkin.CompactActionHorizontalPadding, PorticoSkin.CompactActionVerticalPadding)
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
            .SetTextStyle(PorticoSkin.CompactActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.EndButton();
    }
}
