using System.Globalization;

using Portico.Desktop.Ui;
using Portico.Desktop.Ui.Components;
using Roci.Core;
using Roci.Input;
using Roci.Ui;
using Roci.Ui.Widgets;

namespace Portico.Desktop.Ui.Pages;

/// <summary>Builds the source-shaped Transactions page from typed reports and configured controls.</summary>
internal sealed class PorticoTransactionsPageRenderer
{
    private static readonly string[] RequiredWidgets = ["summary", "history", "breakdown", "transactions"];

    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;
    private readonly Dictionary<string, PorticoMultiSelectState<string>> _multiSelectStates = new(StringComparer.Ordinal);

    /// <summary>Creates the transaction renderer around the dashboard session.</summary>
    public PorticoTransactionsPageRenderer(DashboardSession session, Action requestRebuild)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
    }

    /// <summary>Gets whether the page declares the complete Transactions grammar.</summary>
    public bool CanRender(DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(page);
        return page.Id == DashboardPageId.TopTransactions
            && RequiredWidgets.All(id => page.Widgets.Any(widget => string.Equals(widget.Id, id, StringComparison.Ordinal)))
            && HasControls(
                page,
                "lookback",
                "type",
                "focus",
                "search",
                "more_filters",
                "groups",
                "categories",
                "accounts",
                "minimum_amount",
                "maximum_amount",
                "largest_count",
                "breakdown");
    }

    /// <summary>Builds the source page title and newest transaction caption.</summary>
    public void BuildHeader(UiBuilder ui, DashboardPageDefinition page, DashboardPageReport report)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);

        TransactionsPageView view = View(report);
        ui.PageHeader();
        ui.Text(page.PageHeading ?? page.Title, "PageTitle")
            .SetTextStyle(PorticoSkin.PageTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.Text(view.LatestDataCaption ?? "Transaction inventory", "TransactionsPageCaption")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.EndPageHeader();
    }

    /// <summary>Builds quick controls, expanded filters, charts, and the transaction table.</summary>
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

        BuildControls(ui, page);
        BuildMetricDeck(ui, ReportFor(report, "transactions.summary"), display);
        if (View(report).EmptyMessage is not null)
        {
            ui.EmptyPanel("No transactions match", View(report).EmptyMessage!, "TransactionsEmpty");
            return;
        }

        ui.HStack(PorticoSkin.SectionGap, "TransactionsCharts")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.SectionGap)
            .SetCrossAlign(CrossAlignment.Start);
        buildWidget(Widget(page, "history"), ReportFor(report, "transactions.history"), true);
        buildWidget(Widget(page, "breakdown"), ReportFor(report, "transactions.breakdown"), true);
        ui.End();

        DashboardWidgetReport table = ReportFor(report, "transactions.table");
        ui.SectionPanel("Section:transactions_table", "Matching transactions", "One-off, unusual, and refund or reversal flags follow the current filters.");
        if (table.Rows.Count == 0)
            ui.EmptyPanel("No transactions match", table.EmptyMessage ?? "Change the filters to continue.", "TransactionsTableEmpty");
        else
            PorticoTableRenderer.Build(ui, "transactions-table", table.Columns, table.Rows, display, maximumRows: 150);
        ui.EndSectionPanel();
    }

    /// <summary>Returns local multi-select state for interaction tests.</summary>
    public PorticoMultiSelectState<string>? MultiSelectState(string controlId)
        => _multiSelectStates.GetValueOrDefault(controlId);

    private void BuildControls(UiBuilder ui, DashboardPageDefinition page)
    {
        ui.HStack(PorticoSkin.CompactGap, "TransactionsControlBar")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.End);
        BuildSegmentedControl(ui, page, "lookback", "TransactionsLookback", LookbackLabel);
        BuildSegmentedControl(ui, page, "type", "TransactionsType", TitleLabel);
        BuildSegmentedControl(ui, page, "focus", "TransactionsFocus", FocusLabel);
        BuildSearch(ui, page);
        BuildMoreFilters(ui, page);
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
        IReadOnlyList<string> options = _session.ControlOptions(DashboardPageId.TopTransactions, controlId);
        string selected = _session.ControlValue(DashboardPageId.TopTransactions, controlId);
        ui.VStack(PorticoSkin.FilterGap, $"Control:Transactions:{controlId}:Group")
            .SetFlexBasis(controlId == "focus" ? 332f : 244f)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"Control:Transactions:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.SegmentedControl($"Control:Transactions:{name}")
            .SetFlexGrow(1f)
            .SetFlexShrink(1f);
        foreach (string option in options)
            ui.Segment(label(option));
        ui.SetSelectedSegment(IndexOf(options, selected))
            .SetOnSegmentChanged((index, _) =>
            {
                _session.SetControlValue(DashboardPageId.TopTransactions, controlId, options[index]);
                _requestRebuild();
            })
        .EndSegmentedControl();
        ui.End();
    }

    private void BuildSearch(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "search");
        string search = _session.ControlValue(DashboardPageId.TopTransactions, control.Id);
        ui.VStack(PorticoSkin.FilterGap, "Control:Transactions:search:Group")
            .SetFlexBasis(300f)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, "Control:Transactions:search:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.TextInput("Control:Transactions:search", "Merchant, description, account")
            .SetFlexGrow(1f)
            .Configure(node =>
            {
                TextInputState state = node.GetStateOrDefault<TextInputState>()
                    ?? throw new InvalidOperationException("Transaction search needs a text state.");
                state.Text = search;
            })
            .SetOnTextChanged(value =>
            {
                _session.SetControlText(DashboardPageId.TopTransactions, control.Id, value);
                _requestRebuild();
            })
        .End();
        ui.End();
    }

    private void BuildMoreFilters(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition control = Control(page, "more_filters");
        bool open = _session.Presentation.Transactions.MoreFiltersOpen;
        PopoverState? popover = null;
        ui.Button("Control:Transactions:MoreFilters")
            .SetPadding(PorticoSkin.CompactActionHorizontalPadding, PorticoSkin.CompactActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(open ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle)
            .SetCommandSurface(pointer: true, focus: true);
        ui.Text(control.Label, "Control:Transactions:MoreFilters:Text")
            .SetTextStyle(PorticoSkin.ActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.SetPopover(content => BuildMoreFiltersPopover(content, page, () => popover), PopoverOpenMode.Manual)
            .Configure(node =>
            {
                popover = node.GetStateOrDefault<PopoverState>()
                    ?? throw new InvalidOperationException("Transaction filters need a popover state.");
                popover.OnOpened = () => _session.SetTransactionsMoreFiltersOpen(true);
                popover.OnClosed = () => _session.SetTransactionsMoreFiltersOpen(false);
                UiBuilder.SetPopoverOpen(popover, open);
            })
            .SetOnCommand(
                _ =>
                {
                    bool next = !_session.Presentation.Transactions.MoreFiltersOpen;
                    _session.SetTransactionsMoreFiltersOpen(next);
                    UiBuilder.SetPopoverOpen(popover!, next);
                    _requestRebuild();
                    return true;
                },
                (int)InputCommands.ClickLeft,
                (int)InputCommands.Accept);
        ui.EndButton();
    }

    private void BuildMoreFiltersPopover(UiBuilder ui, DashboardPageDefinition page, Func<PopoverState?> popover)
    {
        ui.VStack(PorticoSkin.SectionGap, "TransactionsMoreFiltersPopover")
            .SetWidth(440f)
            .SetMaxHeight(600f)
            .SetScrollable(vertical: true, horizontal: false)
            .SetPadding(PorticoSkin.ControlBarPadding)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.Text("More filters", "TransactionsMoreFiltersPopover:Title")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        BuildMultiSelect(ui, page, "groups");
        BuildMultiSelect(ui, page, "categories");
        BuildMultiSelect(ui, page, "accounts");
        BuildNumberInput(ui, page, "minimum_amount");
        BuildNumberInput(ui, page, "maximum_amount");
        BuildNumberInput(ui, page, "largest_count");
        BuildSegmentedControl(ui, page, "breakdown", "TransactionsBreakdown", TitleLabel);
        AddActionButton(
            ui,
            "Control:Transactions:CloseMoreFilters",
            "Close",
            () =>
            {
                _session.SetTransactionsMoreFiltersOpen(false);
                if (popover() is { } current)
                    UiBuilder.SetPopoverOpen(current, false);
                _requestRebuild();
            });
        ui.End();
    }

    private void BuildMultiSelect(UiBuilder ui, DashboardPageDefinition page, string controlId)
    {
        DashboardControlDefinition control = Control(page, controlId);
        PorticoMultiSelectState<string> state = _multiSelectStates.GetValueOrDefault(controlId)
            ?? new PorticoMultiSelectState<string>(comparer: StringComparer.Ordinal);
        _multiSelectStates[controlId] = state;
        PorticoMultiSelectItem<string>[] items = _session.ControlOptions(DashboardPageId.TopTransactions, controlId)
            .Select(value => new PorticoMultiSelectItem<string>(value, value, value))
            .ToArray();
        ui.VStack(PorticoSkin.FilterGap, $"TransactionsMoreFilters:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"TransactionsMoreFilters:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.MultiSelect(
            $"Control:Transactions:{controlId}",
            control.Label,
            items,
            _session.ControlValues(DashboardPageId.TopTransactions, controlId),
            state,
            values => _session.SetControlValues(DashboardPageId.TopTransactions, controlId, values),
            _requestRebuild);
        ui.End();
    }

    private void BuildNumberInput(UiBuilder ui, DashboardPageDefinition page, string controlId)
    {
        DashboardControlDefinition control = Control(page, controlId);
        decimal value = decimal.Parse(_session.ControlValue(DashboardPageId.TopTransactions, control.Id), CultureInfo.InvariantCulture);
        ui.HStack(PorticoSkin.FilterGap, $"TransactionsMoreFilters:{controlId}")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text(control.Label, $"TransactionsMoreFilters:{controlId}:Label")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        ui.NumberInput(
                $"Control:Transactions:{controlId}",
                (double)control.Minimum!.Value,
                (double)control.Maximum!.Value,
                (double)value,
                (double)control.Step!.Value)
            .SetFlexBasis(160f)
            .SetFlexGrow(0f)
            .SetOnNumberValueChanged(next =>
            {
                _session.SetControlNumber(DashboardPageId.TopTransactions, control.Id, (decimal)next);
                _requestRebuild();
            })
        .EndNumberInput();
        ui.End();
    }

    private static void BuildMetricDeck(UiBuilder ui, DashboardWidgetReport summary, Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.CompactGap, "TransactionsMetricDeck")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch);
        foreach (ReportMetric metric in summary.Metrics)
        {
            ui.MetricCard($"TransactionsMetric:{metric.Label}")
                .SetStyle(PorticoSkin.RaisedPanelStyle)
                .SetMetric(metric.Label, display(metric.Display), metric.Tone, "Transactions")
                .SetMetricDetail(display(metric.Detail), metric.Tone, $"Transactions:{metric.Label}")
            .EndMetricCard();
        }
        ui.End();
    }

    private static TransactionsPageView View(DashboardPageReport report)
        => report.TransactionsView ?? throw new InvalidOperationException("Transactions view is missing.");

    private static DashboardWidgetReport ReportFor(DashboardPageReport report, string id)
        => report.Widgets.TryGetValue(id, out DashboardWidgetReport? widget)
            ? widget
            : throw new InvalidOperationException($"Transactions report '{id}' is missing.");

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

        throw new InvalidOperationException($"Transactions control has no selected option '{selected}'.");
    }

    private static string LookbackLabel(string value)
        => value switch
        {
            "3m" => "3M",
            "6m" => "6M",
            "1y" => "1Y",
            "2y" => "2Y",
            "all" => "All",
            _ => value
        };

    private static string FocusLabel(string value)
        => value switch
        {
            "all" => "All",
            "largest" => "Largest",
            "one_off" => "One-off",
            "unusual" => "Unusual",
            "reversals" => "Refunds",
            _ => TitleLabel(value)
        };

    private static string TitleLabel(string value)
        => string.Join(' ', value.Split('_').Select(word => word.Length == 0
            ? word
            : char.ToUpperInvariant(word[0]) + word[1..]));

    private static void AddActionButton(UiBuilder ui, string name, string label, Action action)
    {
        ui.Button(name)
            .SetPadding(PorticoSkin.CompactActionHorizontalPadding, PorticoSkin.CompactActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(PorticoSkin.SecondaryActionStyle)
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
