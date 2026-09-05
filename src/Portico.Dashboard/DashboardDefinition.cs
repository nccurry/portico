namespace Portico.Dashboard;

/// <summary>Identifies one of the dashboard pages supported by the Portico report builder.</summary>
public enum DashboardPageId
{
    /// <summary>The financial overview page.</summary>
    Home,

    /// <summary>The income and savings page.</summary>
    IncomeSavings,

    /// <summary>The spending by category page.</summary>
    Spending,

    /// <summary>The year-over-year comparison page.</summary>
    YearOverYear,

    /// <summary>The subscription page.</summary>
    Subscriptions,

    /// <summary>The merchant analysis page.</summary>
    Merchants,

    /// <summary>The budget page.</summary>
    Budget,

    /// <summary>The top transactions page.</summary>
    TopTransactions,

    /// <summary>The financial-independence page.</summary>
    FinancialIndependence,

    /// <summary>The data-health page.</summary>
    DataHealth
}

/// <summary>Identifies the fixed groups shown in the permanent navigation rail.</summary>
public enum DashboardNavigationGroup
{
    /// <summary>Leaves a direct page outside of a labeled group.</summary>
    Standalone,

    /// <summary>Groups analysis reports.</summary>
    Analyze,

    /// <summary>Groups financial planning reports.</summary>
    Plan,

    /// <summary>Groups maintenance reports.</summary>
    Maintain,

    /// <summary>Marks an older direct definition that has no rail metadata.</summary>
    Unspecified
}

/// <summary>Identifies a source navigation icon through a finite C# mapping.</summary>
public enum DashboardNavigationIcon
{
    /// <summary>No icon was supplied by an older direct definition.</summary>
    None,

    /// <summary>The source home icon.</summary>
    Home,

    /// <summary>The source savings icon.</summary>
    Savings,

    /// <summary>The source storefront icon.</summary>
    Storefront,

    /// <summary>The source category icon.</summary>
    Category,

    /// <summary>The source comparison icon.</summary>
    CompareArrows,

    /// <summary>The source subscriptions icon.</summary>
    Subscriptions,

    /// <summary>The source receipt icon.</summary>
    ReceiptLong,

    /// <summary>The source wallet icon.</summary>
    AccountBalanceWallet,

    /// <summary>The source monitoring icon.</summary>
    Monitoring,

    /// <summary>The source health and safety icon.</summary>
    HealthAndSafety
}

/// <summary>Specifies the finite widget grammar accepted by the dashboard configuration.</summary>
public enum DashboardWidgetKind
{
    /// <summary>A small numeric or text value.</summary>
    Metric,

    /// <summary>A connected time-series chart.</summary>
    LineChart,

    /// <summary>A filled connected time-series chart.</summary>
    AreaChart,

    /// <summary>A category bar chart.</summary>
    BarChart,

    /// <summary>A categorical bar chart with one or more connected line overlays.</summary>
    ComboChart,

    /// <summary>An x/y point chart.</summary>
    ScatterChart,

    /// <summary>A compact connected value chart.</summary>
    Sparkline,

    /// <summary>A tabular list of report rows.</summary>
    Table,

    /// <summary>An interval chart.</summary>
    Timeline,

    /// <summary>A two-dimensional comparison grid.</summary>
    Heatmap
}

/// <summary>Specifies a control that can change a configured page report.</summary>
public enum DashboardFilterKind
{
    /// <summary>Select one value from a configured list.</summary>
    Select
}

/// <summary>Specifies the finite set of controls that a configured page can show.</summary>
public enum DashboardControlKind
{
    /// <summary>Selects one value from a list.</summary>
    Select,

    /// <summary>Selects one value from adjacent segments.</summary>
    SegmentedChoice,

    /// <summary>Selects zero or more values from a popover list.</summary>
    MultiSelect,

    /// <summary>Edits a bounded numeric value.</summary>
    NumberInput,

    /// <summary>Edits a bounded numeric value with a slider.</summary>
    Slider,

    /// <summary>Turns a display or report setting on or off.</summary>
    Toggle,

    /// <summary>Selects one visible tab.</summary>
    TabChoice,

    /// <summary>Runs one named reset action.</summary>
    ActionReset
}

/// <summary>Identifies the fixed C# state or report input used by a configured control.</summary>
public enum DashboardControlSource
{
    /// <summary>Uses the shared spending transaction-set setting.</summary>
    Spending,

    /// <summary>Uses the shared year-over-year transaction-set setting.</summary>
    YearOverYear,

    /// <summary>Uses the shared income-view setting.</summary>
    IncomeView,

    /// <summary>Uses the Home page time-frame display state.</summary>
    HomeTimeFrame,

    /// <summary>Uses the Income and savings excluded-income-category display state.</summary>
    IncomeExcludedCategories,

    /// <summary>Uses the Financial independence target display state.</summary>
    FinancialIndependenceTargetAmount,

    /// <summary>Uses the Data health stale-account threshold display state.</summary>
    DataHealthStaleThreshold,

    /// <summary>Uses the Data health inactive-item display state.</summary>
    DataHealthIncludeInactive,

    /// <summary>Uses the Income and savings selected-detail-tab state.</summary>
    IncomeDetailTab,

    /// <summary>Runs the Financial independence scenario reset.</summary>
    FinancialIndependenceReset
}

/// <summary>Identifies how a control gets its finite set of visible choices.</summary>
public enum DashboardControlOptionSource
{
    /// <summary>Reads fixed strings from the dashboard TOML file.</summary>
    Static
}

/// <summary>Describes the requested horizontal footprint of a control in a wrapping control bar.</summary>
public enum DashboardControlWidth
{
    /// <summary>Uses a compact control group.</summary>
    Compact,

    /// <summary>Uses a full control-bar row when space permits.</summary>
    Full
}

/// <summary>Specifies the fixed visual arrangement of a configured section.</summary>
public enum DashboardSectionLayout
{
    /// <summary>Places the section body in normal document order.</summary>
    Flow
}

/// <summary>Defines one filter displayed on a dashboard page.</summary>
public sealed record DashboardFilterDefinition(
    string Id,
    string Label,
    DashboardFilterKind Kind,
    string Source,
    string DefaultValue,
    IReadOnlyList<string> Options);

/// <summary>Defines one configured page section.</summary>
public sealed record DashboardSectionDefinition(
    string Id,
    string Title,
    DashboardSectionLayout Layout,
    int Order,
    string? Description = null);

/// <summary>Defines one typed control shown by a configured page.</summary>
public sealed record DashboardControlDefinition(
    string Id,
    string Label,
    DashboardControlKind Kind,
    DashboardControlSource Source,
    DashboardControlOptionSource OptionSource = DashboardControlOptionSource.Static,
    IReadOnlyList<string>? Options = null,
    string? DefaultValue = null,
    IReadOnlyList<string>? DefaultValues = null,
    decimal? Minimum = null,
    decimal? Maximum = null,
    decimal? Step = null,
    DashboardControlWidth Width = DashboardControlWidth.Compact,
    string? Section = null)
{
    /// <summary>Gets the configured single-choice values without exposing a null collection.</summary>
    public IReadOnlyList<string> ChoiceOptions => Options ?? [];

    /// <summary>Gets the configured multi-choice defaults without exposing a null collection.</summary>
    public IReadOnlyList<string> MultiSelectDefaults => DefaultValues ?? [];
}

/// <summary>Defines one chart, metric, or grid displayed on a dashboard page.</summary>
public sealed record DashboardWidgetDefinition(
    string Id,
    string Title,
    DashboardWidgetKind Kind,
    string Report,
    int Span = 1,
    string? Description = null,
    IReadOnlyList<string>? BarSeries = null,
    string? Section = null);

/// <summary>Defines one drawer destination and its configuration-driven content.</summary>
public sealed record DashboardPageDefinition(
    DashboardPageId Id,
    string Title,
    string Description,
    IReadOnlyList<DashboardFilterDefinition> Filters,
    IReadOnlyList<DashboardWidgetDefinition> Widgets,
    bool Visible = true,
    DashboardNavigationGroup NavigationGroup = DashboardNavigationGroup.Unspecified,
    int NavigationOrder = 0,
    string? RailLabel = null,
    string? PageHeading = null,
    DashboardNavigationIcon Icon = DashboardNavigationIcon.None)
{
    /// <summary>Gets the configured section panels in display order.</summary>
    public IReadOnlyList<DashboardSectionDefinition> Sections { get; init; } = [];

    /// <summary>Gets the typed controls drawn before this page's report sections.</summary>
    public IReadOnlyList<DashboardControlDefinition> Controls { get; init; } = [];

    /// <summary>Gets whether this page supplies any navigation metadata that needs validation.</summary>
    public bool HasNavigationMetadata => NavigationGroup != DashboardNavigationGroup.Unspecified
        || NavigationOrder != 0
        || RailLabel is not null
        || PageHeading is not null
        || Icon != DashboardNavigationIcon.None;
}

/// <summary>Represents the complete versioned dashboard presentation file.</summary>
public sealed record DashboardDefinition(
    int SchemaVersion,
    string AppTitle,
    IReadOnlyList<DashboardPageDefinition> Pages)
{
    /// <summary>The configuration schema supported by this build.</summary>
    public const int SupportedSchemaVersion = 1;

    private static readonly IReadOnlySet<string> SupportedFilterSources = new HashSet<string>(StringComparer.Ordinal)
    {
        "lookback",
        "spending",
        "year_over_year",
        "income_view"
    };

    /// <summary>Checks the finite dashboard grammar and reports every independent issue.</summary>
    public IReadOnlyList<string> Validate()
    {
        var problems = new List<string>();
        if (SchemaVersion != SupportedSchemaVersion)
            problems.Add($"dashboard.schema_version must be {SupportedSchemaVersion}.");
        if (string.IsNullOrWhiteSpace(AppTitle))
            problems.Add("dashboard.app_title is required.");
        if (Pages.Count == 0)
            problems.Add("dashboard.pages must contain at least one page.");

        var pageIds = new HashSet<DashboardPageId>();
        var navigationOrders = new HashSet<int>();
        bool requireNavigationMetadata = Pages.Any(page => page.HasNavigationMetadata);
        var reportInputDefaults = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (DashboardPageDefinition page in Pages)
        {
            if (!pageIds.Add(page.Id))
                problems.Add($"dashboard page '{page.Id}' is duplicated.");
            if (string.IsNullOrWhiteSpace(page.Title))
                problems.Add($"dashboard page '{page.Id}' needs a title.");
            if (page.Widgets.Count == 0)
                problems.Add($"dashboard page '{page.Id}' needs at least one widget.");

            ValidatePage(page, problems);
            ValidateNavigation(page, navigationOrders, problems, requireNavigationMetadata);
            foreach (DashboardFilterDefinition filter in page.Filters)
            {
                TrackReportInputDefault(reportInputDefaults, filter.Source, filter.DefaultValue, problems);
            }

            foreach (DashboardControlDefinition control in page.Controls)
            {
                if (DashboardControlMappings.TryResolve(page.Id, control.Id, out DashboardControlMapping? mapping)
                    && mapping is { Behavior: DashboardControlBehavior.ReportInput, ReportFilterSource: not null }
                    && control.DefaultValue is not null)
                {
                    TrackReportInputDefault(reportInputDefaults, mapping.ReportFilterSource, control.DefaultValue, problems);
                }
            }
        }

        if (!Pages.Any(page => page.Visible))
            problems.Add("dashboard must contain at least one visible page.");
        return problems;
    }

    /// <summary>Returns the first visible page or throws when the definition is invalid.</summary>
    public DashboardPageDefinition FirstVisiblePage()
    {
        IReadOnlyList<string> problems = Validate();
        if (problems.Count > 0)
            throw new ArgumentException(string.Join(Environment.NewLine, problems), nameof(Pages));

        foreach (DashboardPageDefinition page in Pages)
        {
            if (page.Visible)
                return page;
        }

        throw new InvalidOperationException("The dashboard has no visible pages.");
    }

    private static void ValidatePage(DashboardPageDefinition page, List<string> problems)
    {
        var filterIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (DashboardFilterDefinition filter in page.Filters)
        {
            if (!filterIds.Add(filter.Id))
                problems.Add($"dashboard page '{page.Id}' has duplicate filter '{filter.Id}'.");
            if (string.IsNullOrWhiteSpace(filter.Id) || string.IsNullOrWhiteSpace(filter.Label))
                problems.Add($"dashboard page '{page.Id}' has a filter without an id or label.");
            if (!SupportedFilterSources.Contains(filter.Source))
                problems.Add($"dashboard filter '{page.Id}.{filter.Id}' has unsupported source '{filter.Source}'.");
            if (filter.Options.Count == 0)
                problems.Add($"dashboard filter '{page.Id}.{filter.Id}' needs at least one option.");
            if (!filter.Options.Contains(filter.DefaultValue, StringComparer.Ordinal))
                problems.Add($"dashboard filter '{page.Id}.{filter.Id}' default must be one of its options.");
        }

        var widgetIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (DashboardWidgetDefinition widget in page.Widgets)
        {
            if (!widgetIds.Add(widget.Id))
                problems.Add($"dashboard page '{page.Id}' has duplicate widget '{widget.Id}'.");
            if (string.IsNullOrWhiteSpace(widget.Id) || string.IsNullOrWhiteSpace(widget.Title) || string.IsNullOrWhiteSpace(widget.Report))
                problems.Add($"dashboard page '{page.Id}' has a widget without an id, title, or report.");
            if (widget.Span is < 1 or > 2)
                problems.Add($"dashboard widget '{page.Id}.{widget.Id}' span must be 1 or 2.");
            if (widget.Kind != DashboardWidgetKind.ComboChart && widget.BarSeries is { Count: > 0 })
                problems.Add($"dashboard widget '{page.Id}.{widget.Id}' can use bar_series only with kind 'combo_chart'.");
            if (widget.Kind == DashboardWidgetKind.ComboChart && widget.BarSeries is not { Count: > 0 })
                problems.Add($"dashboard combo chart '{page.Id}.{widget.Id}' needs at least one bar_series id.");
            if (widget.BarSeries is not null)
            {
                var seriesIds = new HashSet<string>(StringComparer.Ordinal);
                foreach (string seriesId in widget.BarSeries)
                {
                    if (string.IsNullOrWhiteSpace(seriesId) || !seriesIds.Add(seriesId))
                        problems.Add($"dashboard widget '{page.Id}.{widget.Id}' has blank or duplicate bar_series ids.");
                }
            }
        }

        ValidateSectionsAndControls(page, filterIds, problems);
    }

    private static void ValidateSectionsAndControls(
        DashboardPageDefinition page,
        IReadOnlySet<string> filterIds,
        List<string> problems)
    {
        var sectionIds = new HashSet<string>(StringComparer.Ordinal);
        var sectionOrders = new HashSet<int>();
        foreach (DashboardSectionDefinition section in page.Sections)
        {
            if (string.IsNullOrWhiteSpace(section.Id) || string.IsNullOrWhiteSpace(section.Title))
                problems.Add($"dashboard page '{page.Id}' has a section without an id or title.");
            if (!Enum.IsDefined(section.Layout))
                problems.Add($"dashboard section '{page.Id}.{section.Id}' has unsupported layout '{section.Layout}'.");
            if (!sectionIds.Add(section.Id))
                problems.Add($"dashboard page '{page.Id}' has duplicate section '{section.Id}'.");
            if (section.Order < 1)
                problems.Add($"dashboard section '{page.Id}.{section.Id}' order must be positive.");
            else if (!sectionOrders.Add(section.Order))
                problems.Add($"dashboard page '{page.Id}' has duplicate section order '{section.Order}'.");
        }

        foreach (DashboardWidgetDefinition widget in page.Widgets)
        {
            if (widget.Section is not null && !sectionIds.Contains(widget.Section))
                problems.Add($"dashboard widget '{page.Id}.{widget.Id}' refers to unknown section '{widget.Section}'.");
        }

        var controlIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (DashboardControlDefinition control in page.Controls)
        {
            if (string.IsNullOrWhiteSpace(control.Id) || string.IsNullOrWhiteSpace(control.Label))
                problems.Add($"dashboard page '{page.Id}' has a control without an id or label.");
            if (!Enum.IsDefined(control.Kind))
                problems.Add($"dashboard control '{page.Id}.{control.Id}' has unsupported kind '{control.Kind}'.");
            if (!Enum.IsDefined(control.Source))
                problems.Add($"dashboard control '{page.Id}.{control.Id}' has unsupported source '{control.Source}'.");
            if (!Enum.IsDefined(control.Width))
                problems.Add($"dashboard control '{page.Id}.{control.Id}' has unsupported width '{control.Width}'.");
            if (!controlIds.Add(control.Id) || filterIds.Contains(control.Id))
                problems.Add($"dashboard page '{page.Id}' has duplicate control '{control.Id}'.");
            if (control.Section is not null && !sectionIds.Contains(control.Section))
                problems.Add($"dashboard control '{page.Id}.{control.Id}' refers to unknown section '{control.Section}'.");

            ValidateControlShape(page, control, problems);
            if (!DashboardControlMappings.TryResolve(page.Id, control.Id, out DashboardControlMapping? mapping))
            {
                problems.Add($"dashboard control '{page.Id}.{control.Id}' does not have a C# mapping.");
            }
            else if (mapping is null)
            {
                problems.Add($"dashboard control '{page.Id}.{control.Id}' has an invalid C# mapping.");
            }
            else if (mapping.Kind != control.Kind || mapping.Source != control.Source)
            {
                problems.Add($"dashboard control '{page.Id}.{control.Id}' does not match its C# mapping.");
            }
            else if (!DashboardControlMappings.TryValidate(mapping, out string? mappingProblem))
            {
                problems.Add($"dashboard control '{page.Id}.{control.Id}' {mappingProblem}.");
            }
        }

        foreach (DashboardControlDefinition reset in page.Controls.Where(control => control.Kind == DashboardControlKind.ActionReset))
        {
            if (reset.Source == DashboardControlSource.FinancialIndependenceReset
                && !page.Controls.Any(control => control.Id == "target_amount"
                    && control.Kind == DashboardControlKind.NumberInput
                    && control.Source == DashboardControlSource.FinancialIndependenceTargetAmount))
            {
                problems.Add($"dashboard reset action '{page.Id}.{reset.Id}' needs the configured target_amount number input.");
            }
        }
    }

    private static void ValidateControlShape(
        DashboardPageDefinition page,
        DashboardControlDefinition control,
        List<string> problems)
    {
        bool needsOptions = control.Kind is DashboardControlKind.Select
            or DashboardControlKind.SegmentedChoice
            or DashboardControlKind.MultiSelect
            or DashboardControlKind.TabChoice;
        bool isNumeric = control.Kind is DashboardControlKind.NumberInput or DashboardControlKind.Slider;

        if (control.OptionSource != DashboardControlOptionSource.Static)
            problems.Add($"dashboard control '{page.Id}.{control.Id}' has unsupported option source '{control.OptionSource}'.");

        if (needsOptions)
        {
            if (control.ChoiceOptions.Count == 0)
                problems.Add($"dashboard control '{page.Id}.{control.Id}' needs at least one option.");
            if (control.ChoiceOptions.Any(string.IsNullOrWhiteSpace)
                || control.ChoiceOptions.Distinct(StringComparer.Ordinal).Count() != control.ChoiceOptions.Count)
            {
                problems.Add($"dashboard control '{page.Id}.{control.Id}' has blank or duplicate options.");
            }
        }
        else if (control.ChoiceOptions.Count > 0)
        {
            problems.Add($"dashboard control '{page.Id}.{control.Id}' cannot define options for kind '{control.Kind}'.");
        }

        if (control.Kind == DashboardControlKind.MultiSelect)
        {
            if (control.DefaultValue is not null)
                problems.Add($"dashboard multi-select '{page.Id}.{control.Id}' must use defaults instead of default.");
            if (control.MultiSelectDefaults.Any(value => !control.ChoiceOptions.Contains(value, StringComparer.Ordinal)))
                problems.Add($"dashboard multi-select '{page.Id}.{control.Id}' defaults must be configured options.");
            if (control.MultiSelectDefaults.Distinct(StringComparer.Ordinal).Count() != control.MultiSelectDefaults.Count)
                problems.Add($"dashboard multi-select '{page.Id}.{control.Id}' has duplicate defaults.");
        }
        else if (control.Kind is DashboardControlKind.Select or DashboardControlKind.SegmentedChoice or DashboardControlKind.TabChoice)
        {
            if (string.IsNullOrWhiteSpace(control.DefaultValue)
                || !control.ChoiceOptions.Contains(control.DefaultValue, StringComparer.Ordinal))
            {
                problems.Add($"dashboard control '{page.Id}.{control.Id}' default must be one of its options.");
            }
            if (control.MultiSelectDefaults.Count > 0)
                problems.Add($"dashboard control '{page.Id}.{control.Id}' cannot define multi-select defaults.");
        }
        else if (isNumeric)
        {
            if (!TryParseDecimal(control.DefaultValue, out decimal value)
                || control.Minimum is null
                || control.Maximum is null
                || control.Step is null
                || control.Minimum > control.Maximum
                || control.Step <= 0m
                || value < control.Minimum
                || value > control.Maximum
                || !IsStepAligned(value, control.Minimum!.Value, control.Step!.Value)
                || !IsStepAligned(control.Maximum!.Value, control.Minimum.Value, control.Step.Value))
            {
                problems.Add($"dashboard numeric control '{page.Id}.{control.Id}' needs an in-range default, aligned minimum/maximum, and positive step.");
            }
            if (control.MultiSelectDefaults.Count > 0)
                problems.Add($"dashboard numeric control '{page.Id}.{control.Id}' cannot define multi-select defaults.");
        }
        else if (control.Kind == DashboardControlKind.Toggle)
        {
            if (!bool.TryParse(control.DefaultValue, out _))
                problems.Add($"dashboard toggle '{page.Id}.{control.Id}' default must be true or false.");
            if (control.MultiSelectDefaults.Count > 0)
                problems.Add($"dashboard toggle '{page.Id}.{control.Id}' cannot define multi-select defaults.");
        }
        else if (control.Kind == DashboardControlKind.ActionReset)
        {
            if (control.DefaultValue is not null || control.MultiSelectDefaults.Count > 0
                || control.Minimum is not null || control.Maximum is not null || control.Step is not null)
            {
                problems.Add($"dashboard reset action '{page.Id}.{control.Id}' cannot define a value or range.");
            }
        }
    }

    private static bool TryParseDecimal(string? value, out decimal result)
        => decimal.TryParse(value, System.Globalization.NumberStyles.Number, System.Globalization.CultureInfo.InvariantCulture, out result);

    private static bool IsStepAligned(decimal value, decimal minimum, decimal step)
        => decimal.Remainder(value - minimum, step) == 0m;

    private static void TrackReportInputDefault(
        Dictionary<string, string> defaults,
        string source,
        string value,
        List<string> problems)
    {
        if (defaults.TryGetValue(source, out string? current)
            && !string.Equals(current, value, StringComparison.Ordinal))
        {
            problems.Add($"dashboard report input '{source}' has conflicting defaults.");
            return;
        }

        defaults[source] = value;
    }

    private static void ValidateNavigation(
        DashboardPageDefinition page,
        HashSet<int> navigationOrders,
        List<string> problems,
        bool required)
    {
        if (!required)
            return;

        if (page.NavigationGroup == DashboardNavigationGroup.Unspecified)
            problems.Add($"dashboard page '{page.Id}' needs a navigation group.");
        if (page.NavigationOrder < 1)
            problems.Add($"dashboard page '{page.Id}' navigation order must be positive.");
        else if (!navigationOrders.Add(page.NavigationOrder))
            problems.Add($"dashboard navigation order '{page.NavigationOrder}' is duplicated.");
        if (string.IsNullOrWhiteSpace(page.RailLabel))
            problems.Add($"dashboard page '{page.Id}' needs a rail label.");
        if (string.IsNullOrWhiteSpace(page.PageHeading))
            problems.Add($"dashboard page '{page.Id}' needs a page heading.");
        if (page.Icon == DashboardNavigationIcon.None)
            problems.Add($"dashboard page '{page.Id}' needs a navigation icon.");
        if (page.Id == DashboardPageId.Home && page.NavigationGroup != DashboardNavigationGroup.Standalone)
            problems.Add("dashboard page 'Home' must be a standalone navigation item.");
        if (page.Id != DashboardPageId.Home && page.NavigationGroup == DashboardNavigationGroup.Standalone)
            problems.Add($"dashboard page '{page.Id}' cannot use the standalone navigation group.");
    }
}
