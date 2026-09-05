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

/// <summary>Builds the source-shaped Data Health page from typed health checks.</summary>
internal sealed class PorticoDataHealthPageRenderer
{
    private static readonly string[] RequiredWidgets = ["summary", "queue", "detail"];

    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;

    /// <summary>Creates the Data Health renderer around the dashboard session.</summary>
    public PorticoDataHealthPageRenderer(DashboardSession session, Action requestRebuild)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
    }

    /// <summary>Gets whether a page declares the full source-shaped Data Health grammar.</summary>
    public bool CanRender(DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(page);
        return page.Id == DashboardPageId.DataHealth
            && RequiredWidgets.All(id => page.Widgets.Any(widget => string.Equals(widget.Id, id, StringComparison.Ordinal)))
            && HasControls(
                page,
                "check_settings",
                "stale_threshold",
                "duplicate_days",
                "duplicate_minimum",
                "same_account",
                "same_category",
                "same_description",
                "include_inactive",
                "selected_check");
    }

    /// <summary>Builds the source page heading.</summary>
    public void BuildHeader(UiBuilder ui, DashboardPageDefinition page, DashboardPageReport report)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);

        View(report);
        ui.PageHeader();
        ui.Text(page.PageHeading ?? page.Title, "PageTitle")
            .SetTextStyle(PorticoSkin.PageTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.EndPageHeader();
    }

    /// <summary>Builds the source caption, check settings, summary, queue, and selected detail.</summary>
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

        DataHealthPageView view = View(report);
        BuildControlBar(ui, page, view);
        if (view.EmptyMessage is not null)
        {
            ui.EmptyPanel("No data health data", view.EmptyMessage, "DataHealthEmpty");
            return;
        }

        BuildMetricDeck(ui, ReportFor(report, "health.summary"), display);
        BuildQueue(ui, report, view, display);
        BuildDetail(ui, page, report, view, display);
    }

    private void BuildControlBar(UiBuilder ui, DashboardPageDefinition page, DataHealthPageView view)
    {
        DashboardControlDefinition control = Control(page, "check_settings");
        bool open = _session.Presentation.DataHealth.CheckSettingsOpen;
        PopoverState? popover = null;
        ui.HStack(PorticoSkin.CompactGap, "DataHealthControlBar")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(view.LatestDataCaption ?? "Review source freshness, mapping gaps, and suspicious records.", "DataHealthPageCaption")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        ui.Button("Control:DataHealth:CheckSettings")
            .SetPadding(PorticoSkin.CompactActionHorizontalPadding, PorticoSkin.CompactActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(open ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle)
            .SetCommandSurface(pointer: true, focus: true);
        ui.Text(control.Label, "Control:DataHealth:CheckSettings:Text")
            .SetTextStyle(PorticoSkin.ActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.SetPopover(content => BuildSettingsPopover(content, page, () => popover), PopoverOpenMode.Manual)
            .Configure(node =>
            {
                popover = node.GetStateOrDefault<PopoverState>()
                    ?? throw new InvalidOperationException("Data Health check settings need a popover state.");
                popover.OnOpened = () => _session.SetDataHealthCheckSettingsOpen(true);
                popover.OnClosed = () => _session.SetDataHealthCheckSettingsOpen(false);
                UiBuilder.SetPopoverOpen(popover, open);
            })
            .SetOnCommand(
                _ =>
                {
                    bool next = !_session.Presentation.DataHealth.CheckSettingsOpen;
                    _session.SetDataHealthCheckSettingsOpen(next);
                    UiBuilder.SetPopoverOpen(popover!, next);
                    _requestRebuild();
                    return true;
                },
                (int)InputCommands.ClickLeft,
                (int)InputCommands.Accept);
        ui.EndButton();
        ui.End();
    }

    private void BuildSettingsPopover(UiBuilder ui, DashboardPageDefinition page, Func<PopoverState?> popover)
    {
        ui.VStack(PorticoSkin.SectionGap, "DataHealthCheckSettingsPopover")
            .SetWidth(460f)
            .SetMaxHeight(620f)
            .SetScrollable(vertical: true, horizontal: false)
            .SetPadding(PorticoSkin.ControlBarPadding)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.HStack(PorticoSkin.CompactGap, "DataHealthCheckSettingsPopover:Header")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text("Check settings", "DataHealthCheckSettingsPopover:Title")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        AddActionButton(
            ui,
            "Control:DataHealth:CloseCheckSettings",
            "Close",
            () =>
            {
                _session.SetDataHealthCheckSettingsOpen(false);
                if (popover() is { } state)
                    UiBuilder.SetPopoverOpen(state, false);
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle);
        ui.End();

        BuildNumberControl(ui, page, "stale_threshold");
        ui.Text("Duplicate detection", "DataHealthCheckSettingsPopover:DuplicateTitle")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        BuildNumberControl(ui, page, "duplicate_days");
        BuildNumberControl(ui, page, "duplicate_minimum");
        BuildToggleControl(ui, page, "same_account");
        BuildToggleControl(ui, page, "same_category");
        BuildToggleControl(ui, page, "same_description");
        BuildToggleControl(ui, page, "include_inactive");
        ui.End();
    }

    private void BuildNumberControl(UiBuilder ui, DashboardPageDefinition page, string controlId)
    {
        DashboardControlDefinition control = Control(page, controlId);
        decimal value = decimal.Parse(_session.ControlValue(DashboardPageId.DataHealth, control.Id), CultureInfo.InvariantCulture);
        ui.VStack(PorticoSkin.FilterGap, $"DataHealthSettings:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        string label = control.Kind == DashboardControlKind.Slider
            ? $"{control.Label}: {value:0} days"
            : control.Label;
        ui.Text(label, $"DataHealthSettings:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        if (control.Kind == DashboardControlKind.Slider)
        {
            ui.Slider(
                    $"Control:DataHealth:{controlId}",
                    (float)control.Minimum!.Value,
                (float)control.Maximum!.Value,
                (float)value,
                (float)control.Step!.Value)
                .SetSliderMinTrackLength(280f)
                .SetOnValueChanged(next =>
                {
                    _session.SetControlNumber(DashboardPageId.DataHealth, control.Id, (decimal)next);
                    _requestRebuild();
                })
            .End();
        }
        else
        {
            ui.NumberInput(
                    $"Control:DataHealth:{controlId}",
                    (double)control.Minimum!.Value,
                    (double)control.Maximum!.Value,
                    (double)value,
                    (double)control.Step!.Value)
                .SetOnNumberValueChanged(next =>
                {
                    _session.SetControlNumber(DashboardPageId.DataHealth, control.Id, (decimal)next);
                    _requestRebuild();
                })
            .EndNumberInput();
        }
        ui.End();
    }

    private void BuildToggleControl(UiBuilder ui, DashboardPageDefinition page, string controlId)
    {
        DashboardControlDefinition control = Control(page, controlId);
        bool selected = bool.Parse(_session.ControlValue(DashboardPageId.DataHealth, control.Id));
        ui.HStack(PorticoSkin.FilterGap, $"DataHealthSettings:{controlId}")
            .SetCrossAlign(CrossAlignment.Center);
        ui.ToggleButton($"Control:DataHealth:{controlId}", selected, next =>
        {
            _session.SetControlToggle(DashboardPageId.DataHealth, control.Id, next);
            _requestRebuild();
        });
        ui.Text(control.Label, $"DataHealthSettings:{controlId}:Label")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.ActionText)
            .SetTextWrap()
        .End();
        ui.EndButton();
        ui.End();
    }

    private static void BuildMetricDeck(UiBuilder ui, DashboardWidgetReport summary, Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.CompactGap, "DataHealthMetricDeck")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in summary.Metrics)
        {
            ui.MetricCard($"DataHealthMetric:{metric.Label}")
                .SetStyle(PorticoSkin.RaisedPanelStyle)
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, "DataHealth")
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"DataHealth:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();
    }

    private void BuildQueue(
        UiBuilder ui,
        DashboardPageReport report,
        DataHealthPageView view,
        Func<string?, string> display)
    {
        DashboardWidgetReport queue = ReportFor(report, "health.queue");
        ui.SectionPanel("Section:health_checks", "Health checks", "Review each source check and its next step.");
        ui.VStack(PorticoSkin.CompactGap, "DataHealthQueuePanel")
            .SetMinSize(0f, 292f)
            .SetPadding(PorticoSkin.WidgetPadding)
            .SetCornerRadius(PorticoSkin.CardCornerRadius)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        if (queue.Rows.Count == 0)
        {
            ui.EmptyPanel("No health checks", queue.EmptyMessage ?? "No health checks are available.", "DataHealthQueueEmpty");
        }
        else
        {
            int selected = IndexOf(view.Analysis.Checks.Select(check => check.Id).ToArray(), view.SelectedCheckId);
            PorticoTableRenderer.BuildSelectable(
                ui,
                "health-queue",
                queue.Columns,
                queue.Rows,
                display,
                selected < 0 ? null : selected,
                index =>
                {
                    _session.SetDataHealthSelectedCheck(view.Analysis.Checks[index].Id);
                    _requestRebuild();
                },
                maximumRows: 12);
        }
        ui.End();
        ui.EndSectionPanel();
    }

    private void BuildDetail(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        DataHealthPageView view,
        Func<string?, string> display)
    {
        BuildSelectedCheckControl(ui, page, view);
        DashboardWidgetReport detail = ReportFor(report, "health.detail");
        DataHealthCheckResult selected = view.SelectedCheck;
        ui.SectionPanel("Section:health_detail", selected.Name, selected.Action);
        ui.HStack(PorticoSkin.CompactGap, "DataHealthDetailStatus")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(StatusLabel(selected), "DataHealthDetailStatus:Label")
            .SetTextStyle(PorticoSkin.HelperText.Overlay(PorticoSkin.ToneTextStyle(ToneFor(selected.Status))))
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.End();
        ui.VStack(PorticoSkin.CompactGap, "DataHealthDetailPanel")
            .SetMinSize(0f, 300f)
            .SetPadding(PorticoSkin.WidgetPadding)
            .SetCornerRadius(PorticoSkin.CardCornerRadius)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        if (detail.Rows.Count == 0)
            ui.EmptyPanel("No findings", detail.EmptyMessage ?? "No findings for this check.", "DataHealthDetailEmpty");
        else
            PorticoTableRenderer.Build(ui, "health-detail", detail.Columns, detail.Rows, display, maximumRows: 100);
        ui.End();
        ui.EndSectionPanel();
    }

    private void BuildSelectedCheckControl(UiBuilder ui, DashboardPageDefinition page, DataHealthPageView view)
    {
        DashboardControlDefinition control = Control(page, "selected_check");
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.DataHealth, control.Id);
        ui.HStack(PorticoSkin.FilterGap, "DataHealthSelectedCheckControl")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(control.Label, "DataHealthSelectedCheckControl:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.Dropdown("Control:DataHealth:selected_check")
            .SetFlexBasis(320f)
            .SetFlexGrow(0f)
            .Text(view.SelectedCheck.Name, "Control:DataHealth:selected_check:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in options)
        {
            DataHealthCheckResult check = view.Analysis.Checks.Single(check => string.Equals(check.Id, option, StringComparison.Ordinal));
            ui.Option(check.Name);
        }
        ui.SetSelectedOption(IndexOf(options, view.SelectedCheckId))
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.DataHealth, control.Id, options[index]);
                _requestRebuild();
            })
        .EndDropdown();
        ui.End();
    }

    private static string StatusLabel(DataHealthCheckResult check)
        => check.Status switch
        {
            "Passed" => "Passed",
            "Review" => $"{check.FindingCount.ToString(CultureInfo.InvariantCulture)} to review",
            _ => $"{check.FindingCount.ToString(CultureInfo.InvariantCulture)} need attention"
        };

    private static string ToneFor(string status)
        => status switch
        {
            "Needs attention" => "negative",
            "Review" => "warning",
            _ => "positive"
        };

    private static DataHealthPageView View(DashboardPageReport report)
        => report.DataHealthView ?? throw new InvalidOperationException("Data Health view is missing.");

    private static DashboardWidgetReport ReportFor(DashboardPageReport report, string id)
        => report.Widgets.TryGetValue(id, out DashboardWidgetReport? widget)
            ? widget
            : throw new InvalidOperationException($"Data Health report '{id}' is missing.");

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

        return values.Count == 0 ? -1 : 0;
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
