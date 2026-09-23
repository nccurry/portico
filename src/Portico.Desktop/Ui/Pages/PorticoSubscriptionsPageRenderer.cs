using System.Globalization;

using Portico.Desktop.Ui;
using Portico.Desktop.Ui.Components;
using Portico.Finance;
using Roci.Core;
using Roci.Ui;
using Roci.Ui.Widgets;

namespace Portico.Desktop.Ui.Pages;

/// <summary>Builds the Subscriptions page from report data and configured controls.</summary>
internal sealed class PorticoSubscriptionsPageRenderer
{
    private static readonly string[] RequiredWidgets =
    [
        "summary",
        "active",
        "lifecycle",
        "history-spend",
        "history-active",
        "candidates",
        "inactive",
        "detail-charge-history",
        "detail-charges",
        "detail-monthly-totals"
    ];

    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;
    private readonly Dictionary<string, PorticoMultiSelectState<string>> _multiSelectStates = new(StringComparer.Ordinal);

    /// <summary>Creates the page renderer around its owning dashboard session.</summary>
    public PorticoSubscriptionsPageRenderer(DashboardSession session, Action requestRebuild)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
    }

    /// <summary>Gets whether the page declares every required subscription widget.</summary>
    public bool CanRender(DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(page);
        return page.Id == DashboardPageId.Subscriptions
            && RequiredWidgets.All(id => page.Widgets.Any(widget => string.Equals(widget.Id, id, StringComparison.Ordinal)))
            && HasControls(
                page,
                "subscription_settings",
                "subscription_categories",
                "discovery_exclusions",
                "minimum_confidence",
                "history_lookback",
                "timeline_scope");
    }

    /// <summary>Builds the title, data date, and stale-data warning.</summary>
    public void BuildHeader(UiBuilder ui, DashboardPageDefinition page, DashboardPageReport report)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);

        SubscriptionsPageView view = View(report);
        ui.PageHeader();
        ui.Text(page.PageHeading ?? page.Title, "PageTitle")
            .SetTextStyle(PorticoSkin.PageTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.Text(view.LatestDataCaption ?? "Subscription inventory", "SubscriptionsPageCaption")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.EndPageHeader();
    }

    /// <summary>Builds settings, inventory, lifecycle, history, and selected merchant detail.</summary>
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

        SubscriptionsPageView view = View(report);
        BuildSettings(ui, page);
        BuildMetricDeck(ui, ReportFor(report, "subscriptions.summary"), display);
        if (view.EmptyMessage is not null)
        {
            ui.EmptyPanel("No subscription data", view.EmptyMessage, "SubscriptionsEmpty");
            return;
        }

        BuildInventory(ui, page, report, view, display);
        BuildLifecycle(ui, page, report, view, buildWidget);
        BuildHistory(ui, page, report, buildWidget);
        BuildCandidates(ui, report, view, display);
        BuildInactive(ui, report, view, display);
        BuildSelectedDetail(ui, page, report, view, buildWidget, display);
    }

    /// <summary>Returns local multi-select state for interaction tests.</summary>
    public PorticoMultiSelectState<string>? MultiSelectState(string controlId)
        => _multiSelectStates.GetValueOrDefault(controlId);

    private void BuildSettings(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "subscription_settings");
        ui.VStack(0f, "SubscriptionsControlBar")
            .SetWidth(UiLength.ParentPercent(100))
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Collapsible(control.Label, _session.Presentation.Subscriptions.SettingsOpen)
            .SetOnCollapsibleToggled(next =>
            {
                _session.SetSubscriptionSettingsOpen(next);
                _requestRebuild();
            });
        ui.VStack(PorticoSkin.SectionGap, "SubscriptionSettingsContent")
            .SetPadding(PorticoSkin.ControlBarPadding)
            .SetCrossAlign(CrossAlignment.Stretch);
        BuildMultiSelect(ui, page, "subscription_categories");
        BuildMultiSelect(ui, page, "discovery_exclusions");
        BuildConfidence(ui, page);
        ui.End();
        ui.EndCollapsible();
        ui.End();
    }

    private void BuildMultiSelect(UiBuilder ui, DashboardPageDefinition page, string controlId)
    {
        DashboardControlDefinition control = Control(page, controlId);
        PorticoMultiSelectState<string> state = _multiSelectStates.GetValueOrDefault(controlId)
            ?? new PorticoMultiSelectState<string>(comparer: StringComparer.Ordinal);
        _multiSelectStates[controlId] = state;
        PorticoMultiSelectItem<string>[] items = _session.ControlOptions(DashboardPageId.Subscriptions, controlId)
            .Select(value => new PorticoMultiSelectItem<string>(value, value, value))
            .ToArray();

        ui.VStack(PorticoSkin.FilterGap, $"SubscriptionsSettings:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"SubscriptionsSettings:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.MultiSelect(
            $"Control:Subscriptions:{controlId}",
            control.Label,
            items,
            _session.ControlValues(DashboardPageId.Subscriptions, controlId),
            state,
            values => _session.SetControlValues(DashboardPageId.Subscriptions, controlId, values),
            _requestRebuild);
        ui.End();
    }

    private void BuildConfidence(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "minimum_confidence");
        decimal value = decimal.Parse(
            _session.ControlValue(DashboardPageId.Subscriptions, control.Id),
            CultureInfo.InvariantCulture);
        ui.VStack(PorticoSkin.FilterGap, "SubscriptionsSettings:Confidence")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text($"{control.Label}: {value:0}%", "SubscriptionsSettings:Confidence:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.Slider(
                "Control:Subscriptions:minimum_confidence",
                (float)control.Minimum!.Value,
                (float)control.Maximum!.Value,
                (float)value,
                (float)control.Step!.Value)
            .SetOnValueChanged(next =>
            {
                _session.SetControlNumber(DashboardPageId.Subscriptions, control.Id, (decimal)next);
                _requestRebuild();
            })
        .End();
        ui.End();
    }

    private static void BuildMetricDeck(UiBuilder ui, DashboardWidgetReport summary, Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.CompactGap, "SubscriptionsMetricDeck")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in summary.Metrics)
        {
            ui.MetricCard($"SubscriptionsMetric:{metric.Label}")
                .SetStyle(PorticoSkin.RaisedPanelStyle)
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, "Subscriptions")
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"Subscriptions:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();
    }

    private void BuildInventory(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        SubscriptionsPageView view,
        Func<string?, string> display)
    {
        DashboardWidgetReport active = ReportFor(report, "subscriptions.active");
        ui.SectionPanel(
            "Section:subscription_inventory",
            "Subscription inventory",
            "Select a merchant to inspect its charges and monthly totals.");
        if (active.Rows.Count == 0)
        {
            ui.EmptyPanel("No active subscriptions", active.EmptyMessage ?? "No active subscriptions are present.", "SubscriptionsNoActive");
        }
        else
        {
            int? selected = IndexOfMerchant(active.Rows, view.SelectedMerchant);
            PorticoTableRenderer.BuildSelectable(
                ui,
                "subscriptions-active",
                active.Columns,
                active.Rows,
                display,
                selected,
                index =>
                {
                    _session.SetSubscriptionSelectedMerchant(active.Rows[index].Values[0]);
                    _requestRebuild();
                },
                maximumRows: 24);
        }
        ui.EndSectionPanel();
    }

    private void BuildLifecycle(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        SubscriptionsPageView view,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool> buildWidget)
    {
        DashboardControlDefinition control = Control(page, "timeline_scope");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Subscriptions, control.Id);
        string selected = _session.ControlValue(DashboardPageId.Subscriptions, control.Id);
        ui.SectionPanel("Section:subscription_lifecycle", "Subscription lifecycle", "Observed charges and inferred active periods.");
        ui.SegmentedControl("Control:Subscriptions:TimelineScope")
            .SetFlexGrow(1f);
        foreach (string option in options)
            ui.Segment(option == "active_recent" ? "Active and recent" : "All history");
        ui.SetSelectedSegment(IndexOf(options, selected))
            .SetOnSegmentChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Subscriptions, control.Id, options[index]);
                _requestRebuild();
            })
        .EndSegmentedControl();

        DashboardWidgetDefinition widget = Widget(page, "lifecycle");
        DashboardWidgetReport lifecycle = ReportFor(report, widget.Report);
        if (selected == "active_recent")
        {
            lifecycle = lifecycle with
            {
                TimelineRanges = view.Analysis.Lifecycles
                    .Where(entry => entry.IsCurrent || entry.DisplayEnd >= view.Analysis.LatestDataDate?.AddDays(-365))
                    .Select(entry => new ReportTimelineRange(entry.Merchant, entry.EpisodeStart, entry.DisplayEnd, entry.MonthlyRunRate?.ToString("C0", CultureInfo.CurrentCulture)))
                    .ToArray()
            };
        }
        buildWidget(widget, lifecycle, false);
        ui.EndSectionPanel();
    }

    private void BuildHistory(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool> buildWidget)
    {
        DashboardControlDefinition control = Control(page, "history_lookback");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.Subscriptions, control.Id);
        string selected = _session.ControlValue(DashboardPageId.Subscriptions, control.Id);
        ui.SectionPanel("Section:subscription_history", "Subscription history", "Actual spending, trailing average, and active merchants.");
        ui.HStack(PorticoSkin.FilterGap, "SubscriptionsHistoryControl")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(control.Label, "SubscriptionsHistoryControl:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.Dropdown("Control:Subscriptions:HistoryLookback")
            .SetFlexGrow(1f)
            .Text(HistoryLabel(selected), "Control:Subscriptions:HistoryLookback:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in options)
            ui.Option(HistoryLabel(option));
        ui.SetSelectedOption(IndexOf(options, selected))
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.Subscriptions, control.Id, options[index]);
                _requestRebuild();
            })
        .EndDropdown();
        ui.End();

        int? months = selected switch
        {
            "3m" => 3,
            "6m" => 6,
            "12m" => 12,
            "24m" => 24,
            _ => null
        };
        BuildHistoryWidget(ui, page, report, "history-spend", months, buildWidget);
        BuildHistoryWidget(ui, page, report, "history-active", months, buildWidget);
        ui.EndSectionPanel();
    }

    private static void BuildHistoryWidget(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        string widgetId,
        int? months,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool> buildWidget)
    {
        DashboardWidgetDefinition widget = Widget(page, widgetId);
        DashboardWidgetReport source = ReportFor(report, widget.Report);
        DashboardWidgetReport clipped = months is null
            ? source
            : source with
            {
                Series = source.Series
                    .Select(series => series with { Points = series.Points.TakeLast(months.Value).ToArray() })
                    .ToArray()
            };
        buildWidget(widget, clipped, false);
    }

    private void BuildCandidates(UiBuilder ui, DashboardPageReport report, SubscriptionsPageView view, Func<string?, string> display)
    {
        DashboardWidgetReport candidates = ReportFor(report, "subscriptions.candidates");
        if (candidates.Rows.Count == 0)
            return;

        ui.SectionPanel("Section:subscription_candidates", "Detected subscription candidates", "Repeated uncategorized charges that meet the selected confidence threshold.");
        PorticoTableRenderer.BuildSelectable(
            ui,
            "subscriptions-candidates",
            candidates.Columns,
            candidates.Rows,
            display,
            IndexOfMerchant(candidates.Rows, view.SelectedMerchant),
            index =>
            {
                _session.SetSubscriptionSelectedMerchant(candidates.Rows[index].Values[0]);
                _requestRebuild();
            },
            maximumRows: 20);
        ui.EndSectionPanel();
    }

    private void BuildInactive(UiBuilder ui, DashboardPageReport report, SubscriptionsPageView view, Func<string?, string> display)
    {
        DashboardWidgetReport inactive = ReportFor(report, "subscriptions.inactive");
        if (inactive.Rows.Count == 0)
            return;

        ui.Collapsible($"Inactive subscriptions ({inactive.Rows.Count})", false);
        PorticoTableRenderer.BuildSelectable(
            ui,
            "subscriptions-inactive",
            inactive.Columns,
            inactive.Rows,
            display,
            IndexOfMerchant(inactive.Rows, view.SelectedMerchant),
            index =>
            {
                _session.SetSubscriptionSelectedMerchant(inactive.Rows[index].Values[0]);
                _requestRebuild();
            },
            maximumRows: 20);
        ui.EndCollapsible();
    }

    private void BuildSelectedDetail(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        SubscriptionsPageView view,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool> buildWidget,
        Func<string?, string> display)
    {
        if (view.SelectedMerchant is null)
            return;

        ui.SectionPanel(
            "Section:subscription_detail",
            view.SelectedMerchant,
            view.SelectedMerchantIsCandidate ? "Detected candidate details." : "Categorized subscription details.");
        DashboardWidgetDefinition chargeHistoryWidget = Widget(page, "detail-charge-history");
        DashboardWidgetReport chargeHistory = ReportFor(report, chargeHistoryWidget.Report);
        buildWidget(chargeHistoryWidget, chargeHistory, false);

        DashboardWidgetReport charges = ReportFor(report, "subscriptions.detail_charges");
        bool chargesExpanded = _session.Presentation.Subscriptions.IndividualChargesExpanded;
        ui.Collapsible($"Individual charges ({charges.Rows.Count})", chargesExpanded)
            .SetOnCollapsibleToggled(next =>
            {
                _session.Presentation.SetSubscriptionIndividualChargesExpanded(next);
                _requestRebuild();
            });
        if (charges.Rows.Count == 0)
            ui.EmptyPanel("No charges", charges.EmptyMessage ?? "No charges are available.", "SubscriptionChargesEmpty");
        else
            PorticoTableRenderer.Build(ui, "subscription-detail-charges", charges.Columns, charges.Rows, display);
        ui.EndCollapsible();

        DashboardWidgetReport totals = ReportFor(report, "subscriptions.detail_monthly_totals");
        bool totalsExpanded = _session.Presentation.Subscriptions.MonthlyTotalsExpanded;
        ui.Collapsible("Monthly totals", totalsExpanded)
            .SetOnCollapsibleToggled(next =>
            {
                _session.Presentation.SetSubscriptionMonthlyTotalsExpanded(next);
                _requestRebuild();
            });
        if (totals.Rows.Count == 0)
            ui.EmptyPanel("No monthly totals", totals.EmptyMessage ?? "No totals are available.", "SubscriptionTotalsEmpty");
        else
            PorticoTableRenderer.Build(ui, "subscription-detail-monthly", totals.Columns, totals.Rows, display);
        ui.EndCollapsible();
        ui.EndSectionPanel();
    }

    private static DashboardWidgetReport ReportFor(DashboardPageReport report, string id)
        => report.Widgets.TryGetValue(id, out DashboardWidgetReport? widget)
            ? widget
            : throw new InvalidOperationException($"Subscriptions report '{id}' is missing.");

    private static SubscriptionsPageView View(DashboardPageReport report)
        => report.SubscriptionsView ?? throw new InvalidOperationException("Subscriptions view is missing.");

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

        throw new InvalidOperationException($"Subscriptions control has no selected option '{selected}'.");
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

    private static string HistoryLabel(string value)
        => value switch
        {
            "3m" => "3 months",
            "6m" => "6 months",
            "12m" => "12 months",
            "24m" => "24 months",
            "all" => "All history",
            _ => value
        };

}
