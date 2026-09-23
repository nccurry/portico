using System.Globalization;

using Portico.Desktop.Ui;
using Roci.Core;
using Roci.Input;
using Roci.Ui;
using Roci.Ui.Widgets;

namespace Portico.Desktop.Ui.Components;

/// <summary>Builds the shared source-style adjustment popover used by spending and Budget pages.</summary>
internal sealed class PorticoSpendingAdjustmentsControl
{
    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;
    private readonly DashboardPageId _pageId;
    private readonly Dictionary<string, PorticoMultiSelectState<string>> _multiSelectStates = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _termDrafts = new(StringComparer.Ordinal);

    /// <summary>Creates the shared popover for a page with the configured expense-adjustment grammar.</summary>
    public PorticoSpendingAdjustmentsControl(DashboardSession session, Action requestRebuild, DashboardPageId pageId)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
        if (pageId is not (DashboardPageId.Spending or DashboardPageId.Merchants or DashboardPageId.Budget))
            throw new ArgumentOutOfRangeException(nameof(pageId));
        _pageId = pageId;
    }

    /// <summary>Returns retained multi-select state for focused interaction tests.</summary>
    public PorticoMultiSelectState<string>? MultiSelectState(string controlId)
        => _multiSelectStates.GetValueOrDefault(controlId);

    /// <summary>Builds the adjustment trigger and its configured popover.</summary>
    public void Build(UiBuilder ui, DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);

        DashboardControlDefinition control = Control(page, "adjust_view");
        bool modified = IsModified;
        string label = modified ? $"{control.Label} · modified" : control.Label;
        PopoverState? popover = null;

        ui.HStack(PorticoSkin.FilterGap, $"Control:{Prefix}:adjust_view:Group")
            .SetFlexBasis(320f)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Center);
        ui.Button($"Control:{Prefix}:AdjustView")
            .SetFlexBasis(320f)
            .SetFlexGrow(0f)
            .SetFlexShrink(0f)
            .SetPadding(PorticoSkin.CompactActionHorizontalPadding, PorticoSkin.CompactActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(modified ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle)
            .SetCommandSurface(pointer: true, focus: true);
        ui.Text(label, $"Control:{Prefix}:AdjustView:Text")
            .SetTextStyle(PorticoSkin.ActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.SetPopover(
                content => BuildPopover(content, page, () => popover),
                PopoverOpenMode.Manual)
            .Configure(node =>
            {
                popover = node.GetStateOrDefault<PopoverState>()
                    ?? throw new InvalidOperationException("Adjust view needs a popover state.");
                popover.OnOpened = () => SetOpen(true);
                popover.OnClosed = () => SetOpen(false);
                UiBuilder.SetPopoverOpen(popover, IsOpen);
            })
            .SetOnCommand(_ =>
            {
                PopoverState current = popover
                    ?? throw new InvalidOperationException("Adjust view needs a popover state.");
                bool open = !IsOpen;
                SetOpen(open);
                UiBuilder.SetPopoverOpen(current, open);
                _requestRebuild();
                return true;
            }, (int)InputCommands.ClickLeft, (int)InputCommands.Accept);
        ui.EndButton();
        ui.End();
    }

    private void BuildPopover(UiBuilder ui, DashboardPageDefinition page, Func<PopoverState?> popover)
    {
        ui.VStack(PorticoSkin.SectionGap, $"{Prefix}AdjustPopover")
            .SetWidth(400f)
            .SetMaxHeight(520f)
            .SetScrollable(vertical: true, horizontal: false)
            .SetPadding(PorticoSkin.ControlBarPadding)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.HStack(PorticoSkin.CompactGap, $"{Prefix}AdjustPopover:Header")
            .SetCrossAlign(CrossAlignment.Center);
        ui.Text("Adjust view", $"{Prefix}AdjustPopover:Title")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        AddActionButton(
            ui,
            $"Control:{Prefix}:ResetAdjustments",
            Control(page, "reset_adjustments").Label,
            () =>
            {
                _session.InvokeControlAction(_pageId, "reset_adjustments");
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle,
            compact: true);
        ui.End();

        BuildMultiSelect(ui, page, "exclude_groups");
        BuildMultiSelect(ui, page, "exclude_categories");
        BuildTextTerms(ui, page, "include_transaction_names");
        BuildTextTerms(ui, page, "exclude_transaction_names");
        BuildLargeExpenseControl(ui, page);

        AddActionButton(
            ui,
            $"Control:{Prefix}:CloseAdjustments",
            "Close",
            () =>
            {
                SetOpen(false);
                if (popover() is { } current)
                    UiBuilder.SetPopoverOpen(current, false);
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle,
            compact: true);
        ui.End();
    }

    private void BuildMultiSelect(UiBuilder ui, DashboardPageDefinition page, string controlId)
    {
        DashboardControlDefinition control = Control(page, controlId);
        PorticoMultiSelectState<string> state = _multiSelectStates.GetValueOrDefault(controlId)
            ?? new PorticoMultiSelectState<string>(comparer: StringComparer.Ordinal);
        _multiSelectStates[controlId] = state;
        PorticoMultiSelectItem<string>[] items = _session.ControlOptions(_pageId, controlId)
            .Select(value => new PorticoMultiSelectItem<string>(value, value, value))
            .ToArray();

        ui.VStack(PorticoSkin.FilterGap, $"{Prefix}Adjustment:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"{Prefix}Adjustment:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
        .End();
        ui.MultiSelect(
            $"Control:{Prefix}:{controlId}",
            control.Label,
            items,
            _session.ControlValues(_pageId, controlId),
            state,
            values => _session.SetControlValues(_pageId, controlId, values),
            _requestRebuild);
        ui.End();
    }

    private void BuildTextTerms(UiBuilder ui, DashboardPageDefinition page, string controlId)
    {
        DashboardControlDefinition control = Control(page, controlId);
        IReadOnlySet<string> values = _session.ControlValues(_pageId, controlId);
        string draft = _termDrafts.GetValueOrDefault(controlId) ?? string.Empty;
        ui.VStack(PorticoSkin.FilterGap, $"{Prefix}Terms:{controlId}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(control.Label, $"{Prefix}Terms:{controlId}:Label")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        ui.HStack(PorticoSkin.FilterGap, $"{Prefix}Terms:{controlId}:Input")
            .SetCrossAlign(CrossAlignment.Center);
        ui.TextInput($"Control:{Prefix}:{controlId}:Input", "Type text")
            .SetFlexGrow(1f)
            .Configure(node =>
            {
                TextInputState state = node.GetStateOrDefault<TextInputState>()
                    ?? throw new InvalidOperationException("Adjustment term input needs a text state.");
                state.Text = draft;
            })
            .SetOnTextChanged(value => _termDrafts[controlId] = value)
        .End();
        AddActionButton(
            ui,
            $"Control:{Prefix}:{controlId}:Add",
            "Add",
            () =>
            {
                string next = _termDrafts.GetValueOrDefault(controlId) ?? string.Empty;
                if (string.IsNullOrWhiteSpace(next))
                    return;
                _session.SetControlValues(_pageId, controlId, values.Append(next));
                _termDrafts[controlId] = string.Empty;
                _requestRebuild();
            },
            PorticoSkin.SecondaryActionStyle,
            compact: true);
        ui.End();

        if (values.Count > 0)
        {
            ui.HStack(PorticoSkin.FilterGap, $"{Prefix}Terms:{controlId}:Values")
                .SetFlexWrap()
                .SetCrossGap(PorticoSkin.FilterGap)
                .SetCrossAlign(CrossAlignment.Center);
            foreach (string value in values.OrderBy(value => value, StringComparer.Ordinal))
            {
                string captured = value;
                AddActionButton(
                    ui,
                    $"Control:{Prefix}:{controlId}:Remove:{captured}",
                    $"Remove {captured}",
                    () =>
                    {
                        _session.SetControlValues(_pageId, controlId, values.Where(value => !string.Equals(value, captured, StringComparison.Ordinal)));
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
        bool selected = bool.Parse(_session.ControlValue(_pageId, "exclude_large_expenses"));
        ui.VStack(PorticoSkin.FilterGap, $"{Prefix}LargeExpense")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.ToggleButton($"Control:{Prefix}:exclude_large_expenses", selected, next =>
        {
            _session.SetControlToggle(_pageId, "exclude_large_expenses", next);
            _requestRebuild();
        })
            .SetFlexGrow(1f);
        ui.Text(toggle.Label, $"Control:{Prefix}:exclude_large_expenses:Label")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        ui.EndButton();

        if (selected)
        {
            DashboardControlDefinition limit = Control(page, "expense_limit");
            decimal value = decimal.Parse(_session.ControlValue(_pageId, "expense_limit"), CultureInfo.InvariantCulture);
            ui.HStack(PorticoSkin.FilterGap, $"{Prefix}ExpenseLimit")
                .SetCrossAlign(CrossAlignment.Center);
            ui.Text(limit.Label, $"{Prefix}ExpenseLimit:Label")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
            ui.NumberInput(
                    $"Control:{Prefix}:expense_limit",
                    (double)limit.Minimum!.Value,
                    (double)limit.Maximum!.Value,
                    (double)value,
                    (double)limit.Step!.Value)
                .SetFlexGrow(1f)
                .SetOnNumberValueChanged(next =>
                {
                    _session.SetControlNumber(_pageId, "expense_limit", (decimal)next);
                    _requestRebuild();
                })
            .EndNumberInput();
            ui.End();
        }
        ui.End();
    }

    private bool IsOpen
        => _pageId == DashboardPageId.Spending
            ? _session.Presentation.Spending.AdjustViewOpen
            : _pageId == DashboardPageId.Merchants
                ? _session.Presentation.Merchants.AdjustViewOpen
                : _session.Presentation.Budget.AdjustViewOpen;

    private bool IsModified
        => _pageId == DashboardPageId.Spending
            ? _session.Filters.SpendingAdjustments?.IsModified == true
            : _pageId == DashboardPageId.Merchants
                ? _session.Filters.MerchantAdjustments?.IsModified == true
                : _session.Filters.Budget?.Adjustments.IsModified == true;

    private string Prefix => _pageId switch
    {
        DashboardPageId.Spending => "Spending",
        DashboardPageId.Merchants => "Merchants",
        DashboardPageId.Budget => "Budget",
        _ => throw new InvalidOperationException()
    };

    private void SetOpen(bool open)
    {
        if (_pageId == DashboardPageId.Spending)
            _session.SetSpendingAdjustViewOpen(open);
        else if (_pageId == DashboardPageId.Merchants)
            _session.SetMerchantAdjustViewOpen(open);
        else
            _session.SetBudgetAdjustViewOpen(open);
    }

    private static DashboardControlDefinition Control(DashboardPageDefinition page, string id)
        => page.Controls.Single(control => string.Equals(control.Id, id, StringComparison.Ordinal));

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
