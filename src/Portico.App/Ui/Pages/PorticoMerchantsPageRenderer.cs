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

/// <summary>Builds the source-shaped Spending by merchant page from typed reports and configured controls.</summary>
internal sealed class PorticoMerchantsPageRenderer
{
    private static readonly string[] RequiredWidgets =
    [
        "summary",
        "ranking",
        "overview",
        "detail-summary",
        "detail-history",
        "detail-categories",
        "detail-accounts",
        "detail-descriptions",
        "detail-transactions",
        "excluded"
    ];

    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;
    private readonly PorticoSpendingAdjustmentsControl _adjustmentsControl;

    /// <summary>Creates the merchant renderer around the dashboard session.</summary>
    public PorticoMerchantsPageRenderer(DashboardSession session, Action requestRebuild)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
        _adjustmentsControl = new PorticoSpendingAdjustmentsControl(_session, _requestRebuild, DashboardPageId.Merchants);
    }

    /// <summary>Gets whether the page declares the complete Spending by merchant grammar.</summary>
    public bool CanRender(DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(page);
        return page.Id == DashboardPageId.Merchants
            && RequiredWidgets.All(id => page.Widgets.Any(widget => string.Equals(widget.Id, id, StringComparison.Ordinal)))
            && HasControls(
                page,
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
                "search",
                "detail_month",
                "detail_tab");
    }

    /// <summary>Builds the source title and the latest spending date.</summary>
    public void BuildHeader(UiBuilder ui, DashboardPageDefinition page, DashboardPageReport report)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);

        MerchantsPageView view = View(report);
        ui.PageHeader();
        ui.Text(page.PageHeading ?? page.Title, "PageTitle")
            .SetTextStyle(PorticoSkin.PageTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.Text(view.LatestDataCaption ?? "Merchant spending", "MerchantsPageCaption")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.EndPageHeader();
    }

    /// <summary>Builds source controls, rankings, selected detail, and excluded source rows.</summary>
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

        MerchantsPageView view = View(report);
        BuildControls(ui, page);
        BuildMetricDeck(ui, "MerchantsMetricDeck", "MerchantsMetric", ReportFor(report, "merchants.summary"), display);
        if (view.EmptyMessage is not null)
        {
            ui.EmptyPanel("No merchant spending", view.EmptyMessage, "MerchantsEmpty");
            return;
        }

        BuildWhereMoneyWent(ui, page, report, view, buildWidget, display);
        BuildSelectedDetail(ui, page, report, view, buildWidget, display);
        BuildExcluded(ui, report, display);
    }

    /// <summary>Returns local adjustment multi-select state for interaction tests.</summary>
    public PorticoMultiSelectState<string>? MultiSelectState(string controlId)
        => _adjustmentsControl.MultiSelectState(controlId);

    private void BuildControls(UiBuilder ui, DashboardPageDefinition page)
    {
        ui.HStack(PorticoSkin.CompactGap, "MerchantsControlBar")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.End);
        BuildSegmentedControl(ui, page, "lookback", "MerchantLookback", LookbackLabel);
        BuildDropdownControl(ui, page, "spending_view", "MerchantSpendingView", _session.SpendingSetLabel);
        BuildSegmentedControl(ui, page, "comparison", "MerchantComparison", ComparisonLabel);
        _adjustmentsControl.Build(ui, page);
        ui.End();
    }

    private void BuildSegmentedControl(
        UiBuilder ui,
        DashboardPageDefinition page,
        string controlId,
        string name,
        Func<string, string> label)
    {
        DashboardControlDefinition control = Control(page, controlId);
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Merchants, controlId);
        string selected = _session.ControlValue(DashboardPageId.Merchants, controlId);
        ui.VStack(PorticoSkin.FilterGap, $"Control:Merchants:{controlId}:Group")
            .SetFlexBasis(controlId == "lookback" ? 232f : PorticoSkin.ControlMinimumWidth)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"Control:Merchants:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.SegmentedControl($"Control:Merchants:{name}")
            .SetFlexGrow(1f)
            .SetFlexShrink(1f);
        foreach (string option in options)
            ui.Segment(label(option));
        ui.SetSelectedSegment(IndexOf(options, selected))
            .SetOnSegmentChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Merchants, controlId, options[index]);
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
        Func<string, string> label)
    {
        DashboardControlDefinition control = Control(page, controlId);
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Merchants, controlId);
        string selected = _session.ControlValue(DashboardPageId.Merchants, controlId);
        ui.VStack(PorticoSkin.FilterGap, $"Control:Merchants:{controlId}:Group")
            .SetFlexBasis(PorticoSkin.ControlMinimumWidth)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"Control:Merchants:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.Dropdown($"Control:Merchants:{name}")
            .SetFlexGrow(1f)
            .Text(label(selected), $"Control:Merchants:{name}:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in options)
            ui.Option(label(option));
        ui.SetSelectedOption(IndexOf(options, selected))
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Merchants, controlId, options[index]);
                _requestRebuild();
            })
        .EndDropdown();
        ui.End();
    }

    private static void BuildMetricDeck(
        UiBuilder ui,
        string deckName,
        string metricName,
        DashboardWidgetReport summary,
        Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.CompactGap, deckName)
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in summary.Metrics)
        {
            ui.MetricCard($"{metricName}:{metric.Label}")
                .SetStyle(PorticoSkin.RaisedPanelStyle)
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, metricName)
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"{metricName}:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();
    }

    private void BuildWhereMoneyWent(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        MerchantsPageView view,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool> buildWidget,
        Func<string?, string> display)
    {
        ui.SectionPanel("Section:merchant_rankings", "Where the money went", "Search and select one merchant to inspect its trend and source rows.");
        BuildSearch(ui, page);
        IReadOnlyList<MerchantOverviewEntry> visible = FilteredOverview(view.Analysis.Overview);
        if (visible.Count == 0)
        {
            ui.EmptyPanel("No merchants match", "Change the search or adjustment controls.", "MerchantsNoResults");
            ui.EndSectionPanel();
            return;
        }

        DashboardWidgetDefinition rankingWidget = Widget(page, "ranking");
        DashboardWidgetReport ranking = ReportFor(report, rankingWidget.Report) with
        {
            Series =
            [
                new ReportSeries(
                    "merchants",
                    "Spending",
                    RankedOverview(view.Analysis.Overview, view.SelectedMerchant)
                        .Select(entry => new ReportPoint(null, entry.Merchant, 0m, entry.Spending))
                        .ToArray())
            ]
        };
        ui.HStack(PorticoSkin.SectionGap, "MerchantsRankingSplit")
            .SetWidth(UiLength.ParentPercent(100))
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.SectionGap)
            .SetCrossAlign(CrossAlignment.Start);
        ui.VStack(PorticoSkin.CompactGap, "MerchantsRankingPane")
            .SetFlexBasis(360f)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch);
        buildWidget(rankingWidget, ranking, false);
        ui.End();
        ui.VStack(PorticoSkin.CompactGap, "MerchantsOverviewPane")
            .SetFlexBasis(560f)
            .SetFlexGrow(1.7f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch);
        BuildOverviewTable(ui, visible, view.SelectedMerchant, display);
        ui.End();
        ui.End();
        ui.EndSectionPanel();
    }

    private void BuildSearch(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "search");
        string search = _session.ControlValue(DashboardPageId.Merchants, control.Id);
        ui.HStack(PorticoSkin.FilterGap, "MerchantsSearch")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(control.Label, "MerchantsSearch:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.TextInput("Control:Merchants:search", "Merchant, category, or group")
            .SetFlexGrow(1f)
            .Configure(node =>
            {
                TextInputState state = node.GetStateOrDefault<TextInputState>()
                    ?? throw new InvalidOperationException("Merchant search needs a text state.");
                state.Text = search;
            })
            .SetOnTextChanged(value =>
            {
                _session.SetControlText(DashboardPageId.Merchants, control.Id, value);
                _requestRebuild();
            })
        .End();
        ui.End();
    }

    private void BuildOverviewTable(
        UiBuilder ui,
        IReadOnlyList<MerchantOverviewEntry> entries,
        string? selectedMerchant,
        Func<string?, string> display)
    {
        IReadOnlyList<ReportTableRow> rows = entries.Select(entry => new ReportTableRow(
        [
            entry.Merchant,
            entry.Spending.ToString("C0", CultureInfo.CurrentCulture),
            entry.SharePercent.ToString("0.0", CultureInfo.InvariantCulture) + "%",
            entry.AverageMonthlySpending.ToString("C0", CultureInfo.CurrentCulture),
            entry.Change.ToString("+C0;-C0;C0", CultureInfo.CurrentCulture),
            entry.TransactionCount.ToString(CultureInfo.InvariantCulture),
            entry.PrimaryCategory
        ],
        entry.Change > 0m ? "negative" : entry.Change < 0m ? "positive" : null)).ToArray();
        string[] columns = ["Merchant", "Spending", "Share", "Average monthly", "Change", "Transactions", "Category"];
        int? selected = IndexOfMerchant(rows, selectedMerchant);
        PorticoTableRenderer.BuildSelectable(
            ui,
            "merchant-overview",
            columns,
            rows,
            display,
            selected,
            index =>
            {
                _session.SetMerchantSelectedMerchant(entries[index].Merchant);
                _requestRebuild();
            },
            maximumRows: 30);
    }

    private void BuildSelectedDetail(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        MerchantsPageView view,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool> buildWidget,
        Func<string?, string> display)
    {
        if (view.SelectedMerchant is null)
            return;

        ui.SectionPanel("Section:merchant_detail", view.SelectedMerchant, "Monthly trend, spending breakdown, and source transaction detail.");
        BuildMetricDeck(ui, "MerchantDetailMetricDeck", "MerchantDetailMetric", ReportFor(report, "merchants.detail_summary"), display);
        buildWidget(Widget(page, "detail-history"), ReportFor(report, "merchants.detail_history"), false);
        BuildDetailMonth(ui, page);
        BuildDetailTabs(ui, page);
        string tab = _session.Presentation.Merchants.DetailTab;
        switch (tab)
        {
            case "Breakdown":
                BuildBreakdown(ui, report, display);
                break;
            case "Descriptions":
                BuildTableOrEmpty(ui, "merchant-descriptions", ReportFor(report, "merchants.detail_descriptions"), display);
                break;
            case "Transactions":
                BuildTableOrEmpty(ui, "merchant-transactions", ReportFor(report, "merchants.detail_transactions"), display);
                break;
            default:
                throw new InvalidOperationException($"Unsupported merchant detail tab '{tab}'.");
        }
        ui.EndSectionPanel();
    }

    private void BuildDetailMonth(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "detail_month");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Merchants, control.Id);
        string selected = _session.ControlValue(DashboardPageId.Merchants, control.Id);
        ui.HStack(PorticoSkin.FilterGap, "MerchantDetailMonth")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(control.Label, "MerchantDetailMonth:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.Dropdown("Control:Merchants:DetailMonth")
            .SetFlexGrow(1f)
            .Text(MonthLabel(selected), "Control:Merchants:DetailMonth:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in options)
            ui.Option(MonthLabel(option));
        ui.SetSelectedOption(IndexOf(options, selected))
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Merchants, control.Id, options[index]);
                _requestRebuild();
            })
        .EndDropdown();
        ui.End();
    }

    private void BuildDetailTabs(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "detail_tab");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Merchants, control.Id);
        string selected = _session.ControlValue(DashboardPageId.Merchants, control.Id);
        ui.SegmentedControl("MerchantDetailTabs")
            .SetFlexGrow(1f);
        foreach (string option in options)
            ui.Segment(option);
        ui.SetSelectedSegment(IndexOf(options, selected))
            .SetOnSegmentChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Merchants, control.Id, options[index]);
                _requestRebuild();
            })
        .EndSegmentedControl();
    }

    private static void BuildBreakdown(UiBuilder ui, DashboardPageReport report, Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.SectionGap, "MerchantBreakdownSplit")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.SectionGap)
            .SetCrossAlign(CrossAlignment.Start);
        BuildTableOrEmpty(ui, "merchant-categories", ReportFor(report, "merchants.detail_categories"), display);
        BuildTableOrEmpty(ui, "merchant-accounts", ReportFor(report, "merchants.detail_accounts"), display);
        ui.End();
    }

    private static void BuildTableOrEmpty(UiBuilder ui, string id, DashboardWidgetReport report, Func<string?, string> display)
    {
        if (report.Rows.Count == 0)
            ui.EmptyPanel("No detail", report.EmptyMessage ?? "No detail is available.", $"{id}:Empty");
        else
            PorticoTableRenderer.Build(ui, id, report.Columns, report.Rows, display);
    }

    private static void BuildExcluded(UiBuilder ui, DashboardPageReport report, Func<string?, string> display)
    {
        DashboardWidgetReport excluded = ReportFor(report, "merchants.excluded");
        if (excluded.Rows.Count == 0)
            return;

        ui.Collapsible($"Excluded transactions ({excluded.Rows.Count})", false);
        PorticoTableRenderer.Build(ui, "merchant-excluded", excluded.Columns, excluded.Rows, display);
        ui.EndCollapsible();
    }

    private IReadOnlyList<MerchantOverviewEntry> FilteredOverview(IReadOnlyList<MerchantOverviewEntry> entries)
    {
        string search = _session.Presentation.Merchants.Search.Trim();
        if (search.Length == 0)
            return entries;

        return entries
            .Where(entry => entry.Merchant.Contains(search, StringComparison.OrdinalIgnoreCase)
                || entry.PrimaryCategory.Contains(search, StringComparison.OrdinalIgnoreCase)
                || entry.PrimaryGroup.Contains(search, StringComparison.OrdinalIgnoreCase)
                || entry.PrimaryAccount.Contains(search, StringComparison.OrdinalIgnoreCase))
            .ToArray();
    }

    private static IReadOnlyList<MerchantOverviewEntry> RankedOverview(
        IReadOnlyList<MerchantOverviewEntry> entries,
        string? selectedMerchant)
    {
        List<MerchantOverviewEntry> ranked = entries.Take(12).ToList();
        if (selectedMerchant is not null
            && !ranked.Any(entry => string.Equals(entry.Merchant, selectedMerchant, StringComparison.Ordinal)))
        {
            MerchantOverviewEntry? selected = entries.FirstOrDefault(
                entry => string.Equals(entry.Merchant, selectedMerchant, StringComparison.Ordinal));
            if (selected is not null)
                ranked.Add(selected);
        }

        return ranked;
    }

    private static MerchantsPageView View(DashboardPageReport report)
        => report.MerchantsView ?? throw new InvalidOperationException("Merchant view is missing.");

    private static DashboardWidgetReport ReportFor(DashboardPageReport report, string id)
        => report.Widgets.TryGetValue(id, out DashboardWidgetReport? widget)
            ? widget
            : throw new InvalidOperationException($"Merchant report '{id}' is missing.");

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

        throw new InvalidOperationException($"Merchant control has no selected option '{selected}'.");
    }

    private static int? IndexOfMerchant(IReadOnlyList<ReportTableRow> rows, string? merchant)
    {
        for (int index = 0; index < rows.Count; index++)
        {
            if (string.Equals(rows[index].Values[0], merchant, StringComparison.Ordinal))
                return index;
        }

        return null;
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

    private static string ComparisonLabel(string value)
        => value == "last_year" ? "Last year" : "Previous period";

    private static string MonthLabel(string value)
        => value == "all"
            ? "All months"
            : YearMonth.TryParse(value, out YearMonth month)
                ? month.Start.ToString("MMMM yyyy", CultureInfo.InvariantCulture)
                : value;
}
