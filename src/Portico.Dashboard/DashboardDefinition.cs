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

/// <summary>Defines one filter displayed on a dashboard page.</summary>
public sealed record DashboardFilterDefinition(
    string Id,
    string Label,
    DashboardFilterKind Kind,
    string Source,
    string DefaultValue,
    IReadOnlyList<string> Options);

/// <summary>Defines one chart, metric, or grid displayed on a dashboard page.</summary>
public sealed record DashboardWidgetDefinition(
    string Id,
    string Title,
    DashboardWidgetKind Kind,
    string Report,
    int Span = 1,
    string? Description = null,
    IReadOnlyList<string>? BarSeries = null);

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
        var filterDefaults = new Dictionary<string, string>(StringComparer.Ordinal);
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
                if (filterDefaults.TryGetValue(filter.Source, out string? current)
                    && !string.Equals(current, filter.DefaultValue, StringComparison.Ordinal))
                {
                    problems.Add($"dashboard filter source '{filter.Source}' has conflicting defaults.");
                }
                else
                {
                    filterDefaults[filter.Source] = filter.DefaultValue;
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
