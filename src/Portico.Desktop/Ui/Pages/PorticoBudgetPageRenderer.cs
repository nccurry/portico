using Portico.Desktop.Ui;
using Portico.Desktop.Ui.Components;
using Roci.Core;
using Roci.Ui;

namespace Portico.Desktop.Ui.Pages;

/// <summary>Builds the Budget page from report data and configured controls.</summary>
internal sealed class PorticoBudgetPageRenderer
{
    private static readonly string[] RequiredWidgets =
    [
        "summary", "pace", "comparison", "performance", "group-summary", "history",
        "categories", "category-table", "transactions", "ytd-summary", "ytd-table"
    ];

    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;
    private readonly PorticoSpendingAdjustmentsControl _adjustments;
    private readonly PorticoMultiSelectState<string> _groupsState = new(comparer: StringComparer.Ordinal);

    /// <summary>Creates the Budget renderer around the dashboard session.</summary>
    public PorticoBudgetPageRenderer(DashboardSession session, Action requestRebuild)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
        _adjustments = new PorticoSpendingAdjustmentsControl(_session, _requestRebuild, DashboardPageId.Budget);
    }

    /// <summary>Checks whether the Budget page defines every required widget and control.</summary>
    public bool CanRender(DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(page);
        return page.Id == DashboardPageId.Budget
            && RequiredWidgets.All(id => page.Widgets.Any(widget => string.Equals(widget.Id, id, StringComparison.Ordinal)))
            && HasControls(
                page,
                "month",
                "groups",
                "adjust_view",
                "reset_adjustments",
                "exclude_groups",
                "exclude_categories",
                "include_transaction_names",
                "exclude_transaction_names",
                "exclude_large_expenses",
                "expense_limit",
                "transaction_category",
                "year_to_date");
    }

    /// <summary>Builds the page title and latest-spending caption.</summary>
    public void BuildHeader(UiBuilder ui, DashboardPageDefinition page, DashboardPageReport report)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);

        BudgetPageView view = View(report);
        ui.PageHeader();
        ui.Text(page.PageHeading ?? page.Title, "PageTitle")
            .SetTextStyle(PorticoSkin.PageTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.Text(view.LatestDataCaption ?? "Budget allocations and actual spending", "BudgetPageCaption")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.EndPageHeader();
    }

    /// <summary>Builds Budget controls, metrics, plan comparison, group detail, and year-to-date detail.</summary>
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

        BudgetPageView view = View(report);
        BuildControls(ui, page);
        if (view.EmptyMessage is not null)
        {
            ui.EmptyPanel("No budget data", view.EmptyMessage, "BudgetEmpty");
            return;
        }

        BuildMetricDeck(ui, ReportFor(report, "budget.summary"), display, "BudgetMetricDeck");
        BuildDailyPace(ui, page, report, buildExpandedWidget);
        BuildPlanComparison(ui, page, report, view, buildExpandedWidget, display);
        BuildGroupDetail(ui, page, report, view, buildExpandedWidget, display);
        BuildYearToDate(ui, page, report, display);
    }

    /// <summary>Returns a retained local multi-select state for interaction tests.</summary>
    public PorticoMultiSelectState<string>? MultiSelectState(string controlId)
        => controlId == "groups" ? _groupsState : _adjustments.MultiSelectState(controlId);

    private void BuildControls(UiBuilder ui, DashboardPageDefinition page)
    {
        ui.HStack(PorticoSkin.CompactGap, "BudgetControlBar")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.End);
        BuildMonthControl(ui, page);
        BuildGroupsControl(ui, page);
        _adjustments.Build(ui, page);
        ui.End();
    }

    private void BuildMonthControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "month");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Budget, control.Id);
        string selected = _session.ControlValue(DashboardPageId.Budget, control.Id);
        BeginControlGroup(ui, control.Id, 188f);
        ui.Text(control.Label, "Control:Budget:month:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        if (options.Count == 0)
        {
            ui.Text("No months", "Control:Budget:month:Empty")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
        }
        else
        {
            ui.Dropdown("Control:Budget:Month")
                .SetFlexGrow(1f)
                .Text(selected, "Control:Budget:Month:Value")
                .SetTextStyle(PorticoSkin.ActionText)
            .End();
            foreach (string option in options)
                ui.Option(option);
            ui.SetSelectedOption(IndexOf(options, selected))
                .SetOnSelectionChanged((index, _) =>
                {
                    _session.SetControlValue(DashboardPageId.Budget, control.Id, options[index]);
                    _requestRebuild();
                })
            .EndDropdown();
        }
        ui.End();
    }

    private void BuildGroupsControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "groups");
        PorticoMultiSelectItem<string>[] items = _session.ControlOptions(DashboardPageId.Budget, control.Id)
            .Select(value => new PorticoMultiSelectItem<string>(value, value, value))
            .ToArray();
        BeginControlGroup(ui, control.Id, 280f);
        ui.Text(control.Label, "Control:Budget:groups:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.MultiSelect(
            "Control:Budget:groups",
            control.Label,
            items,
            _session.ControlValues(DashboardPageId.Budget, control.Id),
            _groupsState,
            values => _session.SetControlValues(DashboardPageId.Budget, control.Id, values),
            _requestRebuild);
        ui.End();
    }

    private static void BeginControlGroup(UiBuilder ui, string id, float width)
    {
        ui.VStack(PorticoSkin.FilterGap, $"Control:Budget:{id}:Group")
            .SetFlexBasis(width)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Stretch);
    }

    private static void BuildMetricDeck(
        UiBuilder ui,
        DashboardWidgetReport summary,
        Func<string?, string> display,
        string name)
    {
        ui.HStack(PorticoSkin.CompactGap, name)
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in summary.Metrics)
        {
            ui.MetricCard($"{name}:Metric:{metric.Label}")
                .SetStyle(PorticoSkin.RaisedPanelStyle)
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, "Budget")
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"{name}:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();
    }

    private static void BuildDailyPace(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, float> buildExpandedWidget)
    {
        ui.SectionPanel(
            "Section:daily_budget_pace",
            "Daily budget pace",
            "Cumulative spending compared with a straight-line share of the selected budget.");
        buildExpandedWidget(Widget(page, "pace"), ReportFor(report, "budget.pace"), 1f);
        ui.EndSectionPanel();
    }

    private void BuildPlanComparison(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        BudgetPageView view,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, float> buildExpandedWidget,
        Func<string?, string> display)
    {
        DashboardWidgetReport performance = ReportFor(report, "budget.performance");
        ui.SectionPanel(
            "Section:plan_comparison",
            "This month against the plan",
            "Compare spending with each group budget, then select a group for detail.");
        buildExpandedWidget(Widget(page, "comparison"), ReportFor(report, "budget.comparison"), 1f);
        if (performance.Rows.Count == 0)
        {
            ui.EmptyPanel("No budget groups", performance.EmptyMessage ?? "Select budget groups to continue.", "BudgetPerformanceEmpty");
        }
        else
        {
            int selected = IndexOf(performance.Rows.Select(row => row.Values[0]).ToArray(), view.SelectedGroup);
            PorticoTableRenderer.BuildSelectable(
                ui,
                "budget-performance",
                performance.Columns,
                performance.Rows,
                display,
                selected < 0 ? null : selected,
                index =>
                {
                    _session.SetBudgetSelectedGroup(performance.Rows[index].Values[0]);
                    _requestRebuild();
                },
                maximumRows: 24);
        }
        ui.EndSectionPanel();
    }

    private void BuildGroupDetail(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        BudgetPageView view,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, float> buildExpandedWidget,
        Func<string?, string> display)
    {
        if (view.SelectedGroup is null)
            return;

        ui.SectionPanel(
            "Section:budget_group_detail",
            view.SelectedGroup,
            "Inspect history, category drivers, and the current transactions for this group.");
        BuildMetricDeck(ui, ReportFor(report, "budget.group_summary"), display, "BudgetGroupMetricDeck");
        buildExpandedWidget(Widget(page, "history"), ReportFor(report, "budget.history"), 1f);
        ui.HStack(PorticoSkin.SectionGap, "BudgetCategorySplit")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.SectionGap)
            .SetCrossAlign(CrossAlignment.Start);
        buildExpandedWidget(Widget(page, "categories"), ReportFor(report, "budget.categories"), 1f);
        ui.VStack(PorticoSkin.CompactGap, "BudgetCategoryTablePanel")
            .SetFlexBasis(PorticoSkin.WidgetMinimumWidth)
            .SetFlexGrow(1.45f)
            .SetFlexShrink(1f)
            .SetMinSize(0f, 320f)
            .SetPadding(PorticoSkin.WidgetPadding)
            .SetCornerRadius(PorticoSkin.CardCornerRadius)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.Text("Category detail", "BudgetCategoryTableTitle")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        DashboardWidgetReport categories = ReportFor(report, "budget.category_table");
        if (categories.Rows.Count == 0)
            ui.EmptyPanel("No category data", categories.EmptyMessage ?? "No category spending is available.", "BudgetCategoryEmpty");
        else
            PorticoTableRenderer.Build(ui, "budget-category", categories.Columns, categories.Rows, display, maximumRows: 16);
        ui.End();
        ui.End();

        BuildTransactionCategoryControl(ui, page);
        DashboardWidgetReport transactions = ReportFor(report, "budget.transactions");
        if (transactions.Rows.Count == 0)
            ui.EmptyPanel("No transactions", transactions.EmptyMessage ?? "No transactions match this category selection.", "BudgetTransactionsEmpty");
        else
            PorticoTableRenderer.Build(ui, "budget-transactions", transactions.Columns, transactions.Rows, display, maximumRows: 80);
        ui.EndSectionPanel();
    }

    private void BuildTransactionCategoryControl(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "transaction_category");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Budget, control.Id);
        string selected = _session.ControlValue(DashboardPageId.Budget, control.Id);
        ui.HStack(PorticoSkin.FilterGap, "BudgetTransactionCategoryControl")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(control.Label, "BudgetTransactionCategoryControl:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.Dropdown("Control:Budget:transaction_category")
            .SetFlexBasis(260f)
            .SetFlexGrow(0f)
            .Text(selected == "all" ? "All categories" : selected, "Control:Budget:transaction_category:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in options)
            ui.Option(option == "all" ? "All categories" : option);
        ui.SetSelectedOption(IndexOf(options, selected))
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Budget, control.Id, options[index]);
                _requestRebuild();
            })
        .EndDropdown();
        ui.End();
    }

    private void BuildYearToDate(UiBuilder ui, DashboardPageDefinition page, DashboardPageReport report, Func<string?, string> display)
    {
        DashboardControlDefinition control = Control(page, "year_to_date");
        ui.Collapsible(control.Label, _session.Presentation.Budget.YearToDateOpen)
            .SetOnCollapsibleToggled(open =>
            {
                _session.SetBudgetYearToDateOpen(open);
                _requestRebuild();
            });
        ui.VStack(PorticoSkin.SectionGap, "BudgetYearToDateContent")
            .SetPadding(PorticoSkin.ControlBarPadding)
            .SetCrossAlign(CrossAlignment.Stretch);
        BuildMetricDeck(ui, ReportFor(report, "budget.ytd_summary"), display, "BudgetYearToDateMetricDeck");
        DashboardWidgetReport table = ReportFor(report, "budget.ytd_table");
        if (table.Rows.Count == 0)
            ui.EmptyPanel("No year-to-date data", table.EmptyMessage ?? "No selected groups have year-to-date data.", "BudgetYtdEmpty");
        else
            PorticoTableRenderer.Build(ui, "budget-ytd", table.Columns, table.Rows, display);
        ui.End();
        ui.EndCollapsible();
    }

    private static BudgetPageView View(DashboardPageReport report)
        => report.BudgetView ?? throw new InvalidOperationException("Budget view is missing.");

    private static DashboardWidgetReport ReportFor(DashboardPageReport report, string id)
        => report.Widgets.TryGetValue(id, out DashboardWidgetReport? widget)
            ? widget
            : throw new InvalidOperationException($"Budget report '{id}' is missing.");

    private static DashboardWidgetDefinition Widget(DashboardPageDefinition page, string id)
        => page.Widgets.Single(widget => string.Equals(widget.Id, id, StringComparison.Ordinal));

    private static DashboardControlDefinition Control(DashboardPageDefinition page, string id)
        => page.Controls.Single(control => string.Equals(control.Id, id, StringComparison.Ordinal));

    private static bool HasControls(DashboardPageDefinition page, params string[] ids)
        => ids.All(id => page.Controls.Any(control => string.Equals(control.Id, id, StringComparison.Ordinal)));

    private static int IndexOf(IReadOnlyList<string> values, string? selected)
    {
        for (int index = 0; index < values.Count; index++)
        {
            if (string.Equals(values[index], selected, StringComparison.Ordinal))
                return index;
        }

        return values.Count == 0 ? -1 : 0;
    }
}
