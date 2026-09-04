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
    Select,

    /// <summary>Select several values from a configured list.</summary>
    MultiSelect,

    /// <summary>Toggle a true or false option.</summary>
    Toggle
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
    string? Description = null);

/// <summary>Defines one drawer destination and its configuration-driven content.</summary>
public sealed record DashboardPageDefinition(
    DashboardPageId Id,
    string Title,
    string Icon,
    string Description,
    IReadOnlyList<DashboardFilterDefinition> Filters,
    IReadOnlyList<DashboardWidgetDefinition> Widgets,
    bool Visible = true);

/// <summary>Represents the complete versioned dashboard presentation file.</summary>
public sealed record DashboardDefinition(
    int SchemaVersion,
    string AppTitle,
    IReadOnlyList<DashboardPageDefinition> Pages)
{
    /// <summary>The configuration schema supported by this build.</summary>
    public const int SupportedSchemaVersion = 1;

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
        foreach (DashboardPageDefinition page in Pages)
        {
            if (!pageIds.Add(page.Id))
                problems.Add($"dashboard page '{page.Id}' is duplicated.");
            if (string.IsNullOrWhiteSpace(page.Title))
                problems.Add($"dashboard page '{page.Id}' needs a title.");
            if (page.Widgets.Count == 0)
                problems.Add($"dashboard page '{page.Id}' needs at least one widget.");

            ValidatePage(page, problems);
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
            if (filter.Kind == DashboardFilterKind.Select && filter.Options.Count > 0 && !filter.Options.Contains(filter.DefaultValue, StringComparer.Ordinal))
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
        }
    }
}
