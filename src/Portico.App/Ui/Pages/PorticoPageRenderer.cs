using System.Globalization;
using Portico.App.Ui.Components;
using Portico.Dashboard;
using Roci.Core;
using Roci.Input;
using Roci.Ui;
using Roci.Ui.Widgets;

namespace Portico.App.Ui.Pages;

/// <summary>Builds the common configured header, controls, and section sequence for a Portico page.</summary>
internal sealed class PorticoPageRenderer
{
    private readonly DashboardSession _session;
    private readonly Action _requestRebuild;
    private readonly Dictionary<string, PorticoMultiSelectState<string>> _multiSelectStates = new(StringComparer.Ordinal);

    /// <summary>Creates the renderer around the session owned by the desktop scene.</summary>
    public PorticoPageRenderer(DashboardSession session, Action requestRebuild)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
        _requestRebuild = requestRebuild ?? throw new ArgumentNullException(nameof(requestRebuild));
    }

    /// <summary>Builds the title and description without page-specific controls.</summary>
    public void BuildHeader(UiBuilder ui, DashboardPageDefinition page)
    {
        ui.PageHeader()
            .SetPageHeaderText(PageHeading(page), page.Description)
        .EndPageHeader();
    }

    /// <summary>Builds configured controls and section panels in their configured order.</summary>
    public void BuildContent(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool> buildWidget)
    {
        ArgumentNullException.ThrowIfNull(buildWidget);
        BuildControlBar(ui, page);

        foreach (DashboardSectionDefinition section in page.Sections.OrderBy(section => section.Order))
        {
            DashboardWidgetDefinition[] widgets = page.Widgets
                .Where(widget => string.Equals(widget.Section, section.Id, StringComparison.Ordinal))
                .ToArray();
            DashboardControlDefinition[] controls = page.Controls
                .Where(control => string.Equals(control.Section, section.Id, StringComparison.Ordinal))
                .ToArray();
            if (widgets.Length == 0 && controls.Length == 0)
                continue;

            ui.SectionPanel($"Section:{section.Id}", section.Title, section.Description);
            foreach (DashboardControlDefinition control in controls)
                BuildConfiguredControl(ui, page, control);
            BuildWidgetRows(ui, widgets, report, buildWidget, section.Id);
            ui.EndSectionPanel();
        }

        DashboardWidgetDefinition[] unsectionedWidgets = page.Widgets
            .Where(widget => widget.Section is null)
            .ToArray();
        BuildWidgetRows(ui, unsectionedWidgets, report, buildWidget, "body");
    }

    /// <summary>Returns a local multi-select state for automation and interaction tests.</summary>
    public PorticoMultiSelectState<string>? MultiSelectState(DashboardPageId pageId, string controlId)
        => _multiSelectStates.GetValueOrDefault(Key(pageId, controlId));

    private void BuildControlBar(UiBuilder ui, DashboardPageDefinition page)
    {
        DashboardControlDefinition[] headerControls = page.Controls.Where(control => control.Section is null).ToArray();
        if (page.Filters.Count == 0 && headerControls.Length == 0)
            return;

        ui.ControlBar();
        foreach (DashboardFilterDefinition filter in page.Filters)
            BuildLegacyFilter(ui, filter);
        foreach (DashboardControlDefinition control in headerControls)
            BuildConfiguredControl(ui, page, control);
        ui.EndControlBar();
    }

    private void BuildLegacyFilter(UiBuilder ui, DashboardFilterDefinition filter)
    {
        ui.ControlGroup($"Filter:{filter.Id}", fullWidth: false)
            .ControlLabel(filter.Label, $"FilterLabel:{filter.Id}");
        string selected = FilterValue(filter.Source);
        foreach (string option in filter.Options)
        {
            string capturedOption = option;
            bool active = string.Equals(selected, capturedOption, StringComparison.Ordinal);
            AddActionButton(
                ui,
                $"Filter:{filter.Id}:{capturedOption}",
                DisplayValue(capturedOption),
                () =>
                {
                    _session.SetFilter(filter.Source, capturedOption);
                    _requestRebuild();
                },
                active ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle,
                compact: true);
        }
        ui.EndControlGroup();
    }

    private void BuildConfiguredControl(UiBuilder ui, DashboardPageDefinition page, DashboardControlDefinition control)
    {
        string name = $"Control:{page.Id}:{control.Id}";
        bool fullWidth = control.Width == DashboardControlWidth.Full;
        ui.ControlGroup($"{name}:Group", fullWidth)
            .ControlLabel(control.Label, $"{name}:Label", center: !fullWidth);

        switch (control.Kind)
        {
            case DashboardControlKind.Select:
                BuildSelect(ui, page.Id, control, name);
                break;
            case DashboardControlKind.SegmentedChoice:
                BuildSegmentedChoice(ui, page.Id, control, name);
                break;
            case DashboardControlKind.MultiSelect:
                BuildMultiSelect(ui, page.Id, control, name);
                break;
            case DashboardControlKind.NumberInput:
                BuildNumberInput(ui, page.Id, control, name);
                break;
            case DashboardControlKind.Slider:
                BuildSlider(ui, page.Id, control, name);
                break;
            case DashboardControlKind.Toggle:
                BuildToggle(ui, page.Id, control, name);
                break;
            case DashboardControlKind.TabChoice:
                BuildTabChoice(ui, page.Id, control, name);
                break;
            case DashboardControlKind.ActionReset:
                AddActionButton(
                    ui,
                    name,
                    control.Label,
                    () =>
                    {
                        _session.InvokeControlAction(page.Id, control.Id);
                        _requestRebuild();
                    },
                    PorticoSkin.SecondaryActionStyle,
                    compact: true);
                break;
            default:
                throw new ArgumentOutOfRangeException(nameof(control));
        }

        ui.EndControlGroup();
    }

    private void BuildSelect(UiBuilder ui, DashboardPageId pageId, DashboardControlDefinition control, string name)
    {
        string selected = _session.ControlValue(pageId, control.Id);
        int selectedIndex = IndexOf(control.ChoiceOptions, selected);
        ui.Dropdown(name)
            .SetFlexGrow(1f)
            .Text(DisplayValue(selected), $"{name}:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        foreach (string option in control.ChoiceOptions)
            ui.Option(DisplayValue(option));
        ui.SetSelectedOption(selectedIndex)
            .SetOnSelectionChanged((index, _) =>
            {
                _session.SetControlValue(pageId, control.Id, control.ChoiceOptions[index]);
                _requestRebuild();
            })
        .EndDropdown();
    }

    private void BuildSegmentedChoice(UiBuilder ui, DashboardPageId pageId, DashboardControlDefinition control, string name)
    {
        string selected = _session.ControlValue(pageId, control.Id);
        ui.SegmentedControl(name)
            .SetFlexGrow(1f);
        foreach (string option in control.ChoiceOptions)
            ui.Segment(DisplayValue(option));
        ui.SetSelectedSegment(IndexOf(control.ChoiceOptions, selected))
            .SetOnSegmentChanged((index, _) =>
            {
                _session.SetControlValue(pageId, control.Id, control.ChoiceOptions[index]);
                _requestRebuild();
            })
        .EndSegmentedControl();
    }

    private void BuildMultiSelect(UiBuilder ui, DashboardPageId pageId, DashboardControlDefinition control, string name)
    {
        PorticoMultiSelectState<string> state = _multiSelectStates.GetValueOrDefault(Key(pageId, control.Id))
            ?? new PorticoMultiSelectState<string>();
        _multiSelectStates[Key(pageId, control.Id)] = state;

        PorticoMultiSelectItem<string>[] items = control.ChoiceOptions
            .Select(value => new PorticoMultiSelectItem<string>(value, value, DisplayValue(value)))
            .ToArray();
        ui.MultiSelect(
            name,
            control.Label,
            items,
            _session.ControlValues(pageId, control.Id),
            state,
            values => _session.SetControlValues(pageId, control.Id, values),
            _requestRebuild);
    }

    private void BuildNumberInput(UiBuilder ui, DashboardPageId pageId, DashboardControlDefinition control, string name)
    {
        decimal value = decimal.Parse(_session.ControlValue(pageId, control.Id), CultureInfo.InvariantCulture);
        ui.NumberInput(
                name,
                (double)control.Minimum!.Value,
                (double)control.Maximum!.Value,
                (double)value,
                (double)control.Step!.Value)
            .SetFlexGrow(1f)
            .SetOnNumberValueChanged(next =>
            {
                _session.SetControlNumber(pageId, control.Id, (decimal)next);
                _requestRebuild();
            })
        .EndNumberInput();
    }

    private void BuildSlider(UiBuilder ui, DashboardPageId pageId, DashboardControlDefinition control, string name)
    {
        decimal value = decimal.Parse(_session.ControlValue(pageId, control.Id), CultureInfo.InvariantCulture);
        ui.Slider(
                name,
                (float)control.Minimum!.Value,
                (float)control.Maximum!.Value,
                (float)value,
                (float)control.Step!.Value)
            .SetFlexGrow(1f)
            .SetOnValueChanged(next =>
            {
                _session.SetControlNumber(pageId, control.Id, (decimal)next);
                _requestRebuild();
            })
        .End();
    }

    private void BuildToggle(UiBuilder ui, DashboardPageId pageId, DashboardControlDefinition control, string name)
    {
        bool selected = bool.Parse(_session.ControlValue(pageId, control.Id));
        ui.ToggleButton(name, selected, next =>
        {
            _session.SetControlToggle(pageId, control.Id, next);
            _requestRebuild();
        })
            .SetFlexGrow(1f);
        ui.Text(selected ? "On" : "Off", $"{name}:Value")
            .SetTextStyle(PorticoSkin.ActionText)
        .End();
        ui.EndButton();
    }

    private void BuildTabChoice(UiBuilder ui, DashboardPageId pageId, DashboardControlDefinition control, string name)
    {
        int selectedIndex = IndexOf(control.ChoiceOptions, _session.ControlValue(pageId, control.Id));
        ui.TabPanel(name)
            .AsWidget(out WidgetRef<TabPanelState> tabPanel)
            .SetFlexGrow(1f)
            .SetOnTabChanged(index =>
            {
                _session.SetControlValue(pageId, control.Id, control.ChoiceOptions[index]);
                _requestRebuild();
            });
        foreach (string option in control.ChoiceOptions)
        {
            ui.Tab(DisplayValue(option));
            ui.Text($"{DisplayValue(option)} details", $"{name}:TabContent:{option}")
                .SetTextStyle(PorticoSkin.HelperText)
            .End();
            ui.EndTab();
        }
        tabPanel.SetActiveTab(selectedIndex);
        ui.EndTabPanel();
    }

    private static void BuildWidgetRows(
        UiBuilder ui,
        IReadOnlyList<DashboardWidgetDefinition> widgets,
        DashboardPageReport report,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool> buildWidget,
        string scope)
    {
        for (int index = 0; index < widgets.Count;)
        {
            DashboardWidgetDefinition widget = widgets[index];
            if (widget.Span == 2)
            {
                buildWidget(widget, report.Widgets[widget.Report], false);
                index++;
                continue;
            }

            ui.HStack(PorticoSkin.SectionGap, $"WidgetRow:{scope}:{index}")
                .SetFlexWrap()
                .SetCrossGap(PorticoSkin.SectionGap)
                .SetCrossAlign(CrossAlignment.Start);
            buildWidget(widget, report.Widgets[widget.Report], true);
            index++;
            if (index < widgets.Count && widgets[index].Span == 1)
            {
                DashboardWidgetDefinition next = widgets[index];
                buildWidget(next, report.Widgets[next.Report], true);
                index++;
            }
            else
            {
                ui.Panel($"WidgetRowSpacer:{scope}:{index}")
                    .SetFlexGrow(1f)
                .End();
            }
            ui.End();
        }
    }

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

    private string FilterValue(string source)
        => source switch
        {
            "lookback" => _session.Filters.LookbackMonths.ToString(CultureInfo.InvariantCulture),
            "spending" => _session.Filters.SpendingSet,
            "year_over_year" => _session.Filters.YearOverYearSet,
            "income_view" => _session.Filters.RegularIncome ? "regular" : "actual",
            _ => throw new ArgumentException($"Unsupported dashboard filter source '{source}'.", nameof(source))
        };

    private static string PageHeading(DashboardPageDefinition page)
        => page.PageHeading ?? page.Title;

    private static int IndexOf(IReadOnlyList<string> values, string selected)
    {
        for (int index = 0; index < values.Count; index++)
        {
            if (string.Equals(values[index], selected, StringComparison.Ordinal))
                return index;
        }

        throw new InvalidOperationException($"Configured control has no selected option '{selected}'.");
    }

    private static string DisplayValue(string value)
        => value switch
        {
            "3m" => "3M",
            "6m" => "6M",
            "1y" => "1Y",
            "2y" => "2Y",
            "5y" => "5Y",
            "all" => "All",
            "regular" => "Regular income",
            "actual" => "All income",
            _ when int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int months) => $"{months} mo",
            _ => value.Replace('_', ' ')
        };

    private static string Key(DashboardPageId pageId, string controlId) => $"{pageId}:{controlId}";
}
