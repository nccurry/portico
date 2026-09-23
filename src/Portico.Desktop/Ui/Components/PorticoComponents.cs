using Roci.Core;
using Roci.Input;
using Roci.Ui;
using Roci.Ui.Widgets;

namespace Portico.Desktop.Ui.Components;

/// <summary>Builds the small app-owned presentation pieces shared by Portico pages.</summary>
public static class PorticoComponents
{
    /// <summary>Makes a native segmented control divide its available width evenly between its segments.</summary>
    public static WidgetRef<SegmentedControlState> SetEqualSegmentWidths(
        this WidgetRef<SegmentedControlState> control)
    {
        foreach (LayoutNode segment in control.State.Segments)
        {
            FlexItem item = segment.FlexItem ?? new FlexItem();
            item.Basis = UiLength.Px(0f);
            item.Grow = 1f;
            item.Shrink = 1f;
            segment.FlexItem = item;
        }

        return control;
    }

    /// <summary>Starts a page header.</summary>
    public static UiBuilder PageHeader(this UiBuilder ui, string name = "PageHeader")
        => ui.VStack(PorticoSkin.CompactGap, name)
            .SetPadding(PorticoSkin.MainPadding, PorticoSkin.HeaderTopPadding, PorticoSkin.MainPadding, PorticoSkin.ShellPadding)
            .SetFlexShrink(0f)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.HeaderPanelStyle);

    /// <summary>Adds the page title and description to the current page header.</summary>
    public static UiBuilder SetPageHeaderText(this UiBuilder ui, string title, string description)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(title);
        ArgumentException.ThrowIfNullOrWhiteSpace(description);

        ui.VStack(PorticoSkin.HeadingGap, "PageHeading");
        ui.Text(title, "PageTitle")
            .SetTextStyle(PorticoSkin.PageTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.Text(description, "PageDescription")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        return ui.End();
    }

    /// <summary>Ends the current page header.</summary>
    public static UiBuilder EndPageHeader(this UiBuilder ui) => ui.End();

    /// <summary>Starts a wrapping control bar.</summary>
    public static UiBuilder ControlBar(this UiBuilder ui, string name = "ControlBar")
        => ui.HStack(PorticoSkin.CompactGap, name)
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetPadding(PorticoSkin.ControlBarPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetCrossAlign(CrossAlignment.Center)
            .SetStyle(PorticoSkin.MutedPanelStyle);

    /// <summary>Starts a compact or full-width control group inside the current control bar.</summary>
    public static UiBuilder ControlGroup(this UiBuilder ui, string name, bool fullWidth)
    {
        float minimumWidth = fullWidth ? PorticoSkin.FullControlMinimumWidth : PorticoSkin.ControlMinimumWidth;
        if (fullWidth)
        {
            return ui.VStack(PorticoSkin.FilterGap, name)
                .SetFlexBasis(minimumWidth)
                .SetFlexGrow(1f)
                .SetFlexShrink(1f)
                .SetCrossAlign(CrossAlignment.Stretch);
        }

        return ui.HStack(PorticoSkin.FilterGap, name)
            .SetFlexBasis(minimumWidth)
            .SetFlexGrow(0f)
            .SetFlexShrink(1f)
            .SetCrossAlign(CrossAlignment.Center);
    }

    /// <summary>Adds a label to the current control group.</summary>
    public static UiBuilder ControlLabel(this UiBuilder ui, string label, string name, bool center = true)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(label);
        UiBuilder text = ui.Text(label, name)
            .SetTextStyle(PorticoSkin.HelperText);
        if (center)
            text.SetAlignSelf(CrossAlignment.Center);
        return text.End();
    }

    /// <summary>Ends the current control group.</summary>
    public static UiBuilder EndControlGroup(this UiBuilder ui) => ui.End();

    /// <summary>Ends the current control bar.</summary>
    public static UiBuilder EndControlBar(this UiBuilder ui) => ui.End();

    /// <summary>Starts a compact metric card.</summary>
    public static UiBuilder MetricCard(this UiBuilder ui, string name)
        => ui.VStack(PorticoSkin.MetricGap, name)
            .SetFlexBasis(PorticoSkin.MetricMinimumWidth)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetPadding(PorticoSkin.MetricPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(PorticoSkin.MutedPanelStyle);

    /// <summary>Adds one metric label and formatted value to the current card.</summary>
    public static UiBuilder SetMetric(
        this UiBuilder ui,
        string label,
        string value,
        string? tone = null,
        string? namePrefix = null)
    {
        string metricName = namePrefix is null ? label : $"{namePrefix}:{label}";
        ui.Text(label, $"MetricLabel:{metricName}")
            .SetTextStyle(PorticoSkin.MetricLabelText)
        .End();
        ui.Text(value, $"MetricValue:{metricName}")
            .SetTextStyle(PorticoSkin.MetricToneTextStyle(tone))
            .SetFontStyle(FontStyle.Bold)
        .End();
        return ui;
    }

    /// <summary>Adds an optional supporting value beneath a metric.</summary>
    public static UiBuilder SetMetricDetail(
        this UiBuilder ui,
        string? detail,
        string? tone = null,
        string? namePrefix = null)
    {
        if (string.IsNullOrWhiteSpace(detail))
            return ui;

        string metricName = namePrefix ?? detail;
        ui.Text(detail, $"MetricDetail:{metricName}")
            .SetTextStyle(PorticoSkin.HelperText.Overlay(PorticoSkin.ToneTextStyle(tone)))
        .End();
        return ui;
    }

    /// <summary>Ends the current metric card.</summary>
    public static UiBuilder EndMetricCard(this UiBuilder ui) => ui.End();

    /// <summary>Starts a flat metric band for a report that already owns its outer panel.</summary>
    public static UiBuilder MetricBand(this UiBuilder ui, string name)
        => ui.HStack(PorticoSkin.CompactGap, name)
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.CompactGap)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetFlexGrow(1f);

    /// <summary>Starts one plain metric column inside a metric band.</summary>
    public static UiBuilder MetricBandItem(this UiBuilder ui, string name)
        => ui.VStack(PorticoSkin.MetricGap, name)
            .SetFlexBasis(PorticoSkin.MetricMinimumWidth)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f);

    /// <summary>Ends one metric band column.</summary>
    public static UiBuilder EndMetricBandItem(this UiBuilder ui) => ui.End();

    /// <summary>Adds a plain title and optional description before a report group.</summary>
    public static UiBuilder SectionHeading(
        this UiBuilder ui,
        string name,
        string title,
        string? description = null)
    {
        ui.VStack(PorticoSkin.HeadingGap, name)
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.Text(title, $"{name}:Title")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        if (!string.IsNullOrWhiteSpace(description))
        {
            ui.Text(description, $"{name}:Description")
                .SetTextStyle(PorticoSkin.HelperText)
                .SetTextWrap()
            .End();
        }

        return ui.End();
    }

    /// <summary>Starts a section panel with a title, optional helper text, and optional header actions.</summary>
    public static UiBuilder SectionPanel(
        this UiBuilder ui,
        string name,
        string title,
        string? description = null,
        Action<UiBuilder>? actions = null)
    {
        ui.VStack(PorticoSkin.SectionGap, name)
            .SetPadding(PorticoSkin.SectionPadding)
            .SetCornerRadius(PorticoSkin.CardCornerRadius)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.HStack(PorticoSkin.SectionHeaderGap, $"{name}:Header")
            .SetCrossAlign(CrossAlignment.Center);
        ui.VStack(PorticoSkin.HeadingGap, $"{name}:Heading")
            .SetFlexGrow(1f);
        ui.Text(title, $"{name}:Title")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        if (!string.IsNullOrWhiteSpace(description))
        {
            ui.Text(description, $"{name}:Description")
                .SetTextStyle(PorticoSkin.HelperText)
                .SetTextWrap()
            .End();
        }
        ui.End();
        if (actions is not null)
            ui.Do(actions);
        ui.End();
        return ui;
    }

    /// <summary>Ends the current section panel.</summary>
    public static UiBuilder EndSectionPanel(this UiBuilder ui) => ui.End();

    /// <summary>Adds a readable no-results panel to the current parent.</summary>
    public static UiBuilder EmptyPanel(this UiBuilder ui, string title, string message, string name = "EmptyPanel")
    {
        ui.VStack(PorticoSkin.CompactGap, name)
            .SetPadding(PorticoSkin.StatusPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(PorticoSkin.MutedPanelStyle);
        ui.Text(title, $"{name}:Title")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.Text(message, $"{name}:Message")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        return ui.End();
    }

    /// <summary>Adds a readable error panel and optional retry action to the current parent.</summary>
    public static UiBuilder ErrorPanel(
        this UiBuilder ui,
        string title,
        string message,
        string name = "ErrorPanel",
        Action? retry = null)
    {
        ui.VStack(PorticoSkin.CompactGap, name)
            .SetPadding(PorticoSkin.StatusPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(PorticoSkin.NegativePanelStyle);
        ui.Text(title, $"{name}:Title")
            .SetTextStyle(PorticoSkin.SectionTitleText.Overlay(PorticoSkin.NegativeText))
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.Text(message, $"{name}:Message")
            .SetTextStyle(PorticoSkin.HelperText)
            .SetTextWrap()
        .End();
        if (retry is not null)
            ActionButton(ui, $"{name}:Retry", "Try again", retry, PorticoSkin.SecondaryActionStyle, compact: true);
        return ui.End();
    }

    /// <summary>Builds a local multi-select from a normal button, popover, and checkboxes.</summary>
    public static UiBuilder MultiSelect<T>(
        this UiBuilder ui,
        string name,
        string label,
        IReadOnlyList<PorticoMultiSelectItem<T>> items,
        IEnumerable<T> selected,
        PorticoMultiSelectState<T> state,
        Action<IReadOnlySet<T>> onSelectionChanged,
        Action requestRebuild)
        where T : notnull
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(name);
        ArgumentException.ThrowIfNullOrWhiteSpace(label);
        ArgumentNullException.ThrowIfNull(items);
        ArgumentNullException.ThrowIfNull(selected);
        ArgumentNullException.ThrowIfNull(state);
        ArgumentNullException.ThrowIfNull(onSelectionChanged);
        ArgumentNullException.ThrowIfNull(requestRebuild);
        if (items.Any(item => string.IsNullOrWhiteSpace(item.Id) || string.IsNullOrWhiteSpace(item.Label))
            || items.Select(item => item.Id).Distinct(StringComparer.Ordinal).Count() != items.Count)
        {
            throw new ArgumentException("Multi-select items need unique non-empty ids and labels.", nameof(items));
        }

        state.ReplaceSelection(selected);
        PopoverState? popover = null;

        ui.Button(name)
            .SetFlexBasis(PorticoSkin.MultiSelectMinimumWidth)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetPadding(PorticoSkin.CompactActionHorizontalPadding, PorticoSkin.CompactActionVerticalPadding)
            .SetCornerRadius(PorticoSkin.SmallCornerRadius)
            .SetStyle(PorticoSkin.QuietActionStyle)
            .SetCommandSurface(pointer: true, focus: true);
        ui.HStack(PorticoSkin.FilterGap, $"{name}:Content")
            .SetCrossAlign(CrossAlignment.Center)
            .SetFlexGrow(1f);
        ui.Text(SelectionSummary(items, state.SelectedValues), $"{name}:Summary")
            .SetFlexGrow(1f)
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        ui.End();

        ui.SetPopover(
                content => BuildMultiSelectPopover(
                    content,
                    name,
                    label,
                    items,
                    state,
                    onSelectionChanged,
                    requestRebuild,
                    () => popover),
                PopoverOpenMode.Manual)
            .Configure(node =>
            {
                popover = node.GetStateOrDefault<PopoverState>()
                    ?? throw new InvalidOperationException("Multi-select trigger needs a popover state.");
                popover.OnOpened = () => state.SetOpen(true);
                popover.OnClosed = () => state.SetOpen(false);
                UiBuilder.SetPopoverOpen(popover, state.IsOpen);
            })
            .SetOnCommand(_ =>
            {
                PopoverState current = popover
                    ?? throw new InvalidOperationException("Multi-select trigger needs a popover state.");
                bool open = !state.IsOpen;
                state.SetOpen(open);
                UiBuilder.SetPopoverOpen(current, open);
                return true;
            }, (int)InputCommands.ClickLeft, (int)InputCommands.Accept);

        return ui.EndButton();
    }

    private static void BuildMultiSelectPopover<T>(
        UiBuilder ui,
        string name,
        string label,
        IReadOnlyList<PorticoMultiSelectItem<T>> items,
        PorticoMultiSelectState<T> state,
        Action<IReadOnlySet<T>> onSelectionChanged,
        Action requestRebuild,
        Func<PopoverState?> popover)
        where T : notnull
    {
        ui.VStack(PorticoSkin.CompactGap, $"MultiSelectPanel:{name}")
            .SetWidth(PorticoSkin.MultiSelectPopoverWidth)
            .SetMaxHeight(PorticoSkin.MultiSelectPopoverMaximumHeight)
            .SetPadding(PorticoSkin.ControlBarPadding)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.Text(label, $"MultiSelectPanel:{name}:Title")
            .SetTextStyle(PorticoSkin.SectionTitleText)
            .SetFontStyle(FontStyle.Bold)
        .End();

        if (items.Count >= PorticoSkin.MultiSelectSearchThreshold)
        {
            ui.TextInput($"MultiSelectSearch:{name}", "Filter options")
                .Configure(node =>
                {
                    TextInputState input = node.GetStateOrDefault<TextInputState>()
                        ?? throw new InvalidOperationException("Multi-select search needs a text input state.");
                    input.Text = state.SearchText;
                })
                .SetOnTextChanged(value =>
                {
                    if (state.SetSearchText(value))
                        requestRebuild();
                })
            .End();
        }

        PorticoMultiSelectItem<T>[] visible = items.Where(item => state.Matches(item.Label)).ToArray();
        if (visible.Length == 0)
        {
            ui.Text("No matching options.", $"MultiSelectPanel:{name}:Empty")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
        }
        else
        {
            ui.VStack(PorticoSkin.FilterGap, $"MultiSelectOptions:{name}")
                .SetScrollable(vertical: true, horizontal: false)
                .SetFlexGrow(1f)
                .SetCrossAlign(CrossAlignment.Stretch);
            foreach (PorticoMultiSelectItem<T> item in visible)
            {
                ui.HStack(PorticoSkin.FilterGap, $"MultiSelectOption:{name}:{item.Id}")
                    .SetCrossAlign(CrossAlignment.Center);
                ui.Checkbox(
                    $"MultiSelectCheckbox:{name}:{item.Id}",
                    state.SelectedValues.Contains(item.Value),
                    selected =>
                    {
                        if (state.SetSelected(item.Value, selected, onSelectionChanged))
                            requestRebuild();
                    });
                ui.Text(item.Label, $"MultiSelectOptionLabel:{name}:{item.Id}")
                    .SetTextStyle(PorticoSkin.ActionText)
                .End();
                ui.End();
            }
            ui.End();
        }

        ui.HStack(PorticoSkin.CompactGap, $"MultiSelectActions:{name}")
            .SetCrossAlign(CrossAlignment.Center);
        ActionButton(ui, $"MultiSelectClear:{name}", "Clear", () =>
        {
            if (state.Clear(onSelectionChanged))
                requestRebuild();
        }, PorticoSkin.QuietActionStyle, compact: true, enabled: state.SelectedValues.Count > 0);
        ActionButton(ui, $"MultiSelectClose:{name}", "Close", () =>
        {
            state.SetOpen(false);
            if (popover() is { } current)
                UiBuilder.SetPopoverOpen(current, false);
        }, PorticoSkin.SecondaryActionStyle, compact: true);
        ui.End();
        ui.End();
    }

    private static string SelectionSummary<T>(IReadOnlyList<PorticoMultiSelectItem<T>> items, IReadOnlySet<T> selected)
        where T : notnull
    {
        if (selected.Count == 0)
            return "All";
        if (selected.Count == 1)
            return items.FirstOrDefault(item => selected.Contains(item.Value))?.Label ?? "1 selected";
        return $"{selected.Count} selected";
    }

    private static void ActionButton(
        UiBuilder ui,
        string name,
        string label,
        Action action,
        string style,
        bool compact,
        bool enabled = true)
    {
        ui.Button(name)
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
        ui.Text(label, $"{name}:Text")
            .SetTextStyle(compact ? PorticoSkin.CompactActionText : PorticoSkin.ActionText)
            .SetFontStyle(FontStyle.Bold)
        .End();
        ui.EndButton();
    }
}
