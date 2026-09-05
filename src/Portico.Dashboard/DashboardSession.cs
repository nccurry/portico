using Portico.Finance;

using System.Globalization;

namespace Portico.Dashboard;

/// <summary>Owns the small mutable view state that connects configured controls to rebuilt reports.</summary>
public sealed class DashboardSession
{
    private readonly PortfolioSnapshot _snapshot;
    private readonly FinanceSettings _settings;
    private readonly DateOnly? _asOfDate;

    /// <summary>Creates a session with the first visible configured page and default filter values.</summary>
    public DashboardSession(
        PortfolioSnapshot snapshot,
        FinanceSettings settings,
        DashboardDefinition definition,
        DateOnly? asOfDate = null)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        ArgumentNullException.ThrowIfNull(settings);
        ArgumentNullException.ThrowIfNull(definition);

        _snapshot = snapshot;
        _settings = settings;
        _asOfDate = asOfDate;
        Definition = definition;
        CurrentPage = definition.FirstVisiblePage().Id;
        Filters = DashboardFilters.From(settings);
        foreach (DashboardFilterDefinition filter in definition.Pages
                     .SelectMany(page => page.Filters)
                     .GroupBy(filter => filter.Source, StringComparer.Ordinal)
                     .Select(group => group.First()))
        {
            Filters = ApplyFilter(Filters, filter.Source, filter.DefaultValue);
        }
        Presentation = new DashboardPresentationState();
        foreach (DashboardPageDefinition page in definition.Pages)
        {
            foreach (DashboardControlDefinition control in page.Controls)
                ApplyConfiguredControlDefault(page.Id, control);
        }
        Report = DashboardReportBuilder.Build(_snapshot, _settings, Filters, _asOfDate);
    }

    /// <summary>Gets the configuration used to render pages and controls.</summary>
    public DashboardDefinition Definition { get; }

    /// <summary>Gets the page currently shown in the main content area.</summary>
    public DashboardPageId CurrentPage { get; private set; }

    /// <summary>Gets the current report filter values.</summary>
    public DashboardFilters Filters { get; private set; }

    /// <summary>Gets the typed per-page state used by configured presentation controls.</summary>
    public DashboardPresentationState Presentation { get; }

    /// <summary>Gets the report rebuilt after the most recent filter change.</summary>
    public DashboardReport Report { get; private set; }

    /// <summary>Selects a visible configured page.</summary>
    public void SelectPage(DashboardPageId pageId)
    {
        DashboardPageDefinition? page = Definition.Pages.FirstOrDefault(page => page.Id == pageId);
        if (page is null || !page.Visible)
            throw new ArgumentException($"Page '{pageId}' is not visible in the dashboard configuration.", nameof(pageId));
        CurrentPage = pageId;
    }

    /// <summary>Changes a control using its configuration source and rebuilds the report when needed.</summary>
    public void SetFilter(string source, string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(source);
        ArgumentNullException.ThrowIfNull(value);

        DashboardFilters updated = ApplyFilter(Filters, source, value);
        if (updated == Filters)
            return;

        Filters = updated;
        Report = DashboardReportBuilder.Build(_snapshot, _settings, Filters, _asOfDate);
    }

    /// <summary>Changes a configured single-choice control.</summary>
    public void SetControlValue(DashboardPageId pageId, string controlId, string value)
    {
        ArgumentNullException.ThrowIfNull(value);
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind is not (DashboardControlKind.Select or DashboardControlKind.SegmentedChoice or DashboardControlKind.TabChoice))
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not accept one choice value.", nameof(controlId));
        if (!control.ChoiceOptions.Contains(value, StringComparer.Ordinal))
            throw new ArgumentException($"Value '{value}' is not configured for dashboard control '{pageId}.{controlId}'.", nameof(value));

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        ApplySingleValue(mapping, value);
    }

    /// <summary>Changes a configured multi-select control.</summary>
    public void SetControlValues(DashboardPageId pageId, string controlId, IEnumerable<string> values)
    {
        ArgumentNullException.ThrowIfNull(values);
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind != DashboardControlKind.MultiSelect)
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not a multi-select.", nameof(controlId));

        string[] selected = values.Distinct(StringComparer.Ordinal).ToArray();
        if (selected.Any(value => !control.ChoiceOptions.Contains(value, StringComparer.Ordinal)))
            throw new ArgumentException($"A selected value is not configured for dashboard control '{pageId}.{controlId}'.", nameof(values));

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        if (mapping.Source != DashboardControlSource.IncomeExcludedCategories)
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not accept multiple values.", nameof(controlId));
        Presentation.SetIncomeExcludedCategories(selected);
    }

    /// <summary>Changes a configured number input or slider.</summary>
    public void SetControlNumber(DashboardPageId pageId, string controlId, decimal value)
    {
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind is not (DashboardControlKind.NumberInput or DashboardControlKind.Slider))
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not numeric.", nameof(controlId));
        if (control.Minimum is null
            || control.Maximum is null
            || control.Step is null
            || value < control.Minimum
            || value > control.Maximum
            || decimal.Remainder(value - control.Minimum.Value, control.Step.Value) != 0m)
        {
            throw new ArgumentOutOfRangeException(nameof(value), value, $"Value must use the configured range and step for '{pageId}.{controlId}'.");
        }

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        switch (mapping.Source)
        {
            case DashboardControlSource.FinancialIndependenceTargetAmount:
                Presentation.SetFinancialIndependenceTargetAmount(value);
                return;
            case DashboardControlSource.DataHealthStaleThreshold:
                Presentation.SetDataHealthStaleThreshold(value);
                return;
            default:
                throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not accept a number.", nameof(controlId));
        }
    }

    /// <summary>Changes a configured toggle.</summary>
    public void SetControlToggle(DashboardPageId pageId, string controlId, bool value)
    {
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind != DashboardControlKind.Toggle)
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not a toggle.", nameof(controlId));

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        if (mapping.Source != DashboardControlSource.DataHealthIncludeInactive)
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not accept a toggle value.", nameof(controlId));
        Presentation.SetDataHealthIncludeInactive(value);
    }

    /// <summary>Runs one configured reset action.</summary>
    public void InvokeControlAction(DashboardPageId pageId, string controlId)
    {
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind != DashboardControlKind.ActionReset)
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not an action.", nameof(controlId));

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        if (mapping.Source != DashboardControlSource.FinancialIndependenceReset)
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not have a reset action.", nameof(controlId));
        Presentation.ResetFinancialIndependence(ConfiguredNumberDefault(
            DashboardPageId.FinancialIndependence,
            "target_amount"));
    }

    /// <summary>Gets the visible value for a configured single-value control.</summary>
    public string ControlValue(DashboardPageId pageId, string controlId)
    {
        Control(pageId, controlId);
        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        return mapping.Behavior == DashboardControlBehavior.ReportInput
            ? FilterValue(mapping.ReportFilterSource!)
            : Presentation.ValueFor(mapping.Source);
    }

    /// <summary>Gets the visible selected values for a configured multi-select.</summary>
    public IReadOnlySet<string> ControlValues(DashboardPageId pageId, string controlId)
    {
        Control(pageId, controlId);
        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        return Presentation.ValuesFor(mapping.Source);
    }

    private int ParseLookback(string value)
    {
        if (!int.TryParse(value, out int months) || !_settings.Lookback.Months.Contains(months))
            throw new ArgumentException($"Lookback '{value}' is not configured.", nameof(value));
        return months;
    }

    private string ValidateFilterSet(string filterSet, string value)
    {
        FilterSetDefinition definition = _settings.FilterSet(filterSet);
        if (!definition.Options.Contains(value, StringComparer.Ordinal))
            throw new ArgumentException($"Value '{value}' is not an option for '{filterSet}'.", nameof(value));
        return value;
    }

    private static bool ParseIncomeView(string value)
        => value switch
        {
            "regular" => true,
            "actual" => false,
            _ => throw new ArgumentException("Income view must be 'regular' or 'actual'.", nameof(value))
        };

    private DashboardFilters ApplyFilter(DashboardFilters filters, string source, string value)
        => source switch
        {
            "lookback" => filters with { LookbackMonths = ParseLookback(value) },
            "spending" => filters with { SpendingSet = ValidateFilterSet("spending", value) },
            "year_over_year" => filters with { YearOverYearSet = ValidateFilterSet("year_over_year", value) },
            "income_view" => filters with { RegularIncome = ParseIncomeView(value) },
            _ => throw new ArgumentException($"Unsupported dashboard filter source '{source}'.", nameof(source))
        };

    private void ApplyConfiguredControlDefault(DashboardPageId pageId, DashboardControlDefinition control)
    {
        switch (control.Kind)
        {
            case DashboardControlKind.Select:
            case DashboardControlKind.SegmentedChoice:
            case DashboardControlKind.TabChoice:
                SetControlValue(pageId, control.Id, control.DefaultValue!);
                break;
            case DashboardControlKind.MultiSelect:
                SetControlValues(pageId, control.Id, control.MultiSelectDefaults);
                break;
            case DashboardControlKind.NumberInput:
            case DashboardControlKind.Slider:
                SetControlNumber(
                    pageId,
                    control.Id,
                    decimal.Parse(control.DefaultValue!, CultureInfo.InvariantCulture));
                break;
            case DashboardControlKind.Toggle:
                SetControlToggle(pageId, control.Id, bool.Parse(control.DefaultValue!));
                break;
            case DashboardControlKind.ActionReset:
                break;
            default:
                throw new ArgumentOutOfRangeException(nameof(control));
        }
    }

    private void ApplySingleValue(DashboardControlMapping mapping, string value)
    {
        if (mapping.Behavior == DashboardControlBehavior.ReportInput)
        {
            SetFilter(mapping.ReportFilterSource!, value);
            return;
        }

        switch (mapping.Source)
        {
            case DashboardControlSource.HomeTimeFrame:
                Presentation.SetHomeTimeFrame(value);
                return;
            case DashboardControlSource.IncomeDetailTab:
                Presentation.SetIncomeDetailTab(value);
                return;
            default:
                throw new ArgumentException($"Dashboard control source '{mapping.Source}' does not accept one choice value.", nameof(mapping));
        }
    }

    private DashboardControlDefinition Control(DashboardPageId pageId, string controlId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(controlId);
        DashboardPageDefinition? page = Definition.Pages.FirstOrDefault(candidate => candidate.Id == pageId);
        DashboardControlDefinition? control = page?.Controls.FirstOrDefault(candidate => string.Equals(candidate.Id, controlId, StringComparison.Ordinal));
        return control ?? throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not configured.", nameof(controlId));
    }

    private string FilterValue(string source)
        => source switch
        {
            "lookback" => Filters.LookbackMonths.ToString(CultureInfo.InvariantCulture),
            "spending" => Filters.SpendingSet,
            "year_over_year" => Filters.YearOverYearSet,
            "income_view" => Filters.RegularIncome ? "regular" : "actual",
            _ => throw new ArgumentException($"Unsupported report filter source '{source}'.", nameof(source))
        };

    private decimal ConfiguredNumberDefault(DashboardPageId pageId, string controlId)
    {
        DashboardControlDefinition control = Control(pageId, controlId);
        return decimal.Parse(control.DefaultValue!, CultureInfo.InvariantCulture);
    }
}
