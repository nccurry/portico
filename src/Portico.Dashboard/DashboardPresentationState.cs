using System.Globalization;

namespace Portico.Dashboard;

/// <summary>Describes whether a typed control changes a report, visible state, or an action.</summary>
public enum DashboardControlBehavior
{
    /// <summary>Changes a typed report request and rebuilds the report.</summary>
    ReportInput,

    /// <summary>Changes retained page presentation only.</summary>
    DisplayState,

    /// <summary>Runs a named page action.</summary>
    Action
}

/// <summary>Maps one known TOML control to a typed C# target.</summary>
public sealed record DashboardControlMapping(
    DashboardControlKind Kind,
    DashboardControlSource Source,
    DashboardControlBehavior Behavior,
    string? ReportFilterSource = null);

/// <summary>Holds the finite control map accepted by the desktop dashboard.</summary>
public static class DashboardControlMappings
{
    private static readonly IReadOnlyDictionary<(DashboardPageId PageId, string ControlId), DashboardControlMapping> Mappings =
        new Dictionary<(DashboardPageId PageId, string ControlId), DashboardControlMapping>
        {
            [(DashboardPageId.Home, "time_frame")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.HomeTimeFrame,
                DashboardControlBehavior.ReportInput,
                "home_time_frame"),
            [(DashboardPageId.IncomeSavings, "income_view")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.IncomeView,
                DashboardControlBehavior.ReportInput,
                "income_view"),
            [(DashboardPageId.IncomeSavings, "exclude_income_categories")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.IncomeExcludedCategories,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.IncomeSavings, "detail_tab")] = new(
                DashboardControlKind.TabChoice,
                DashboardControlSource.IncomeDetailTab,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Spending, "spending_view")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.Spending,
                DashboardControlBehavior.ReportInput,
                "spending"),
            [(DashboardPageId.YearOverYear, "spending_view")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.YearOverYear,
                DashboardControlBehavior.ReportInput,
                "year_over_year"),
            [(DashboardPageId.FinancialIndependence, "target_amount")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.FinancialIndependenceTargetAmount,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.FinancialIndependence, "reset_scenario")] = new(
                DashboardControlKind.ActionReset,
                DashboardControlSource.FinancialIndependenceReset,
                DashboardControlBehavior.Action),
            [(DashboardPageId.DataHealth, "stale_threshold")] = new(
                DashboardControlKind.Slider,
                DashboardControlSource.DataHealthStaleThreshold,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.DataHealth, "include_inactive")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.DataHealthIncludeInactive,
                DashboardControlBehavior.DisplayState)
        };

    /// <summary>Returns the C# mapping for one configured page control.</summary>
    public static bool TryResolve(
        DashboardPageId pageId,
        string controlId,
        out DashboardControlMapping? mapping)
        => Mappings.TryGetValue((pageId, controlId), out mapping);

    /// <summary>Returns the C# mapping or throws a clear configuration error.</summary>
    public static DashboardControlMapping Resolve(DashboardPageId pageId, string controlId)
        => TryResolve(pageId, controlId, out DashboardControlMapping? mapping)
            ? mapping!
            : throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not supported.", nameof(controlId));

    /// <summary>Checks that a mapping has a real typed route before a page tries to draw it.</summary>
    public static bool TryValidate(DashboardControlMapping mapping, out string? problem)
    {
        ArgumentNullException.ThrowIfNull(mapping);

        switch (mapping.Behavior)
        {
            case DashboardControlBehavior.ReportInput:
                string? expectedRoute = ReportFilterRouteFor(mapping.Source);
                if (expectedRoute is null
                    || !string.Equals(expectedRoute, mapping.ReportFilterSource, StringComparison.Ordinal))
                {
                    problem = "needs a supported report-filter route";
                    return false;
                }

                problem = null;
                return true;
            case DashboardControlBehavior.DisplayState:
                if (!HasDisplaySetter(mapping.Source, mapping.Kind))
                {
                    problem = "needs a typed display-state setter";
                    return false;
                }

                problem = null;
                return true;
            case DashboardControlBehavior.Action:
                if (mapping.Kind != DashboardControlKind.ActionReset
                    || mapping.Source != DashboardControlSource.FinancialIndependenceReset)
                {
                    problem = "needs a named action handler";
                    return false;
                }

                problem = null;
                return true;
            default:
                problem = "uses an unsupported control behavior";
                return false;
        }
    }

    /// <summary>Checks the finite options owned by a typed control route.</summary>
    public static bool TryValidateConfiguredOptions(
        DashboardControlMapping mapping,
        IReadOnlyList<string> options,
        out string? problem)
    {
        ArgumentNullException.ThrowIfNull(mapping);
        ArgumentNullException.ThrowIfNull(options);

        if (mapping.Source == DashboardControlSource.HomeTimeFrame)
        {
            string? unsupported = options.FirstOrDefault(option => !HomeReportRange.TryParse(option, out _));
            if (unsupported is not null)
            {
                problem = $"has unsupported Home time-frame option '{unsupported}'";
                return false;
            }
        }

        problem = null;
        return true;
    }

    private static bool HasDisplaySetter(DashboardControlSource source, DashboardControlKind kind)
        => (source, kind) switch
        {
            (DashboardControlSource.IncomeExcludedCategories, DashboardControlKind.MultiSelect) => true,
            (DashboardControlSource.IncomeDetailTab, DashboardControlKind.TabChoice) => true,
            (DashboardControlSource.FinancialIndependenceTargetAmount, DashboardControlKind.NumberInput) => true,
            (DashboardControlSource.DataHealthStaleThreshold, DashboardControlKind.Slider) => true,
            (DashboardControlSource.DataHealthIncludeInactive, DashboardControlKind.Toggle) => true,
            _ => false
        };

    private static string? ReportFilterRouteFor(DashboardControlSource source)
        => source switch
        {
            DashboardControlSource.Spending => "spending",
            DashboardControlSource.YearOverYear => "year_over_year",
            DashboardControlSource.IncomeView => "income_view",
            DashboardControlSource.HomeTimeFrame => "home_time_frame",
            _ => null
        };
}

/// <summary>Holds Home-only detail state without leaking it into finance calculations.</summary>
public sealed record HomePresentationState(IReadOnlySet<string> ExpandedAccountGroups)
{
    /// <summary>Creates the source page's initially collapsed account details.</summary>
    public static HomePresentationState Default { get; } = new(new HashSet<string>(StringComparer.Ordinal));
}

/// <summary>Holds Income and savings presentation controls.</summary>
public sealed record IncomeSavingsPresentationState(
    IReadOnlySet<string> ExcludedIncomeCategories,
    string DetailTab)
{
    /// <summary>Creates the initial display state.</summary>
    public static IncomeSavingsPresentationState Default { get; } = new(
        new HashSet<string>(StringComparer.Ordinal),
        "Included");
}

/// <summary>Holds Financial independence scenario presentation inputs until Phase 6 connects the report request.</summary>
public sealed record FinancialIndependencePresentationState(decimal TargetAmount)
{
    /// <summary>Creates the initial display state.</summary>
    public static FinancialIndependencePresentationState Default { get; } = new(1_000_000m);
}

/// <summary>Holds Data health presentation settings until Phase 7 connects its report request.</summary>
public sealed record DataHealthPresentationState(decimal StaleThreshold, bool IncludeInactive)
{
    /// <summary>Creates the initial display state.</summary>
    public static DataHealthPresentationState Default { get; } = new(30m, false);
}

/// <summary>Owns typed page state that is separate from finance settings and reports.</summary>
public sealed class DashboardPresentationState
{
    /// <summary>Gets the Home page's retained state.</summary>
    public HomePresentationState Home { get; private set; } = HomePresentationState.Default;

    /// <summary>Gets the Income and savings page's retained state.</summary>
    public IncomeSavingsPresentationState IncomeSavings { get; private set; } = IncomeSavingsPresentationState.Default;

    /// <summary>Gets the Financial independence page's retained state.</summary>
    public FinancialIndependencePresentationState FinancialIndependence { get; private set; } = FinancialIndependencePresentationState.Default;

    /// <summary>Gets the Data health page's retained state.</summary>
    public DataHealthPresentationState DataHealth { get; private set; } = DataHealthPresentationState.Default;

    /// <summary>Gets whether one Home account group's details are expanded.</summary>
    public bool IsHomeAccountGroupExpanded(string group)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(group);
        return Home.ExpandedAccountGroups.Contains(group);
    }

    /// <summary>Sets whether one Home account group's details are expanded.</summary>
    public void SetHomeAccountGroupExpanded(string group, bool expanded)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(group);
        var groups = new HashSet<string>(Home.ExpandedAccountGroups, StringComparer.Ordinal);
        if (expanded)
            groups.Add(group);
        else
            groups.Remove(group);
        Home = Home with { ExpandedAccountGroups = groups };
    }

    /// <summary>Sets the excluded Income and savings categories.</summary>
    public void SetIncomeExcludedCategories(IEnumerable<string> values)
    {
        ArgumentNullException.ThrowIfNull(values);
        IncomeSavings = IncomeSavings with
        {
            ExcludedIncomeCategories = new HashSet<string>(values, StringComparer.Ordinal)
        };
    }

    /// <summary>Sets the selected Income and savings tab.</summary>
    public void SetIncomeDetailTab(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        IncomeSavings = IncomeSavings with { DetailTab = value };
    }

    /// <summary>Sets the Financial independence target shown by the scenario control.</summary>
    public void SetFinancialIndependenceTargetAmount(decimal value)
        => FinancialIndependence = FinancialIndependence with { TargetAmount = value };

    /// <summary>Restores the Financial independence display inputs to their configured initial value.</summary>
    public void ResetFinancialIndependence(decimal targetAmount)
        => FinancialIndependence = FinancialIndependence with { TargetAmount = targetAmount };

    /// <summary>Sets the Data health stale-account threshold.</summary>
    public void SetDataHealthStaleThreshold(decimal value)
        => DataHealth = DataHealth with { StaleThreshold = value };

    /// <summary>Sets whether the Data health page includes inactive items.</summary>
    public void SetDataHealthIncludeInactive(bool value)
        => DataHealth = DataHealth with { IncludeInactive = value };

    /// <summary>Gets the configured control value formatted for a native Roci control.</summary>
    public string ValueFor(DashboardControlSource source)
        => source switch
        {
            DashboardControlSource.IncomeDetailTab => IncomeSavings.DetailTab,
            DashboardControlSource.FinancialIndependenceTargetAmount => FinancialIndependence.TargetAmount.ToString(CultureInfo.InvariantCulture),
            DashboardControlSource.DataHealthStaleThreshold => DataHealth.StaleThreshold.ToString(CultureInfo.InvariantCulture),
            DashboardControlSource.DataHealthIncludeInactive => DataHealth.IncludeInactive.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            _ => throw new ArgumentException($"Control source '{source}' does not hold one display value.", nameof(source))
        };

    /// <summary>Gets the configured multi-select value set.</summary>
    public IReadOnlySet<string> ValuesFor(DashboardControlSource source)
        => source == DashboardControlSource.IncomeExcludedCategories
            ? IncomeSavings.ExcludedIncomeCategories
            : throw new ArgumentException($"Control source '{source}' does not hold multiple values.", nameof(source));
}
