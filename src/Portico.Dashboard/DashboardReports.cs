using Portico.Finance;

namespace Portico.Dashboard;

/// <summary>Represents a rendered-friendly point in a dashboard series.</summary>
public sealed record ReportPoint(DateOnly? Date, string? Category, decimal X, decimal Y, string? Label = null);

/// <summary>Represents one named series in a dashboard widget report.</summary>
public sealed record ReportSeries(string Id, string Label, IReadOnlyList<ReportPoint> Points);

/// <summary>Represents one value displayed in a metric strip or card.</summary>
public sealed record ReportMetric(
    string Label,
    decimal? Value,
    string Display,
    string? Tone = null,
    string? Detail = null,
    decimal? Change = null);

/// <summary>Represents one visible row in a dashboard table.</summary>
public sealed record ReportTableRow(IReadOnlyList<string> Values, string? Tone = null);

/// <summary>Represents one category-owned calendar interval for a timeline widget.</summary>
public sealed record ReportTimelineRange(
    string Category,
    DateOnly Start,
    DateOnly End,
    string? Label = null);

/// <summary>Represents one labelled x/y comparison cell for a heatmap widget.</summary>
public sealed record ReportHeatmapCell(
    string XCategory,
    string YCategory,
    decimal Value,
    string? Display = null);

/// <summary>Represents the data consumed by one configured dashboard widget.</summary>
public sealed record DashboardWidgetReport(
    IReadOnlyList<ReportMetric> Metrics,
    IReadOnlyList<ReportSeries> Series,
    IReadOnlyList<string> Columns,
    IReadOnlyList<ReportTableRow> Rows,
    string? EmptyMessage = null)
{
    /// <summary>Gets explicit date intervals when this report renders a timeline.</summary>
    public IReadOnlyList<ReportTimelineRange> TimelineRanges { get; init; } = [];

    /// <summary>Gets explicit x/y cells when this report renders a heatmap.</summary>
    public IReadOnlyList<ReportHeatmapCell> HeatmapCells { get; init; } = [];

    /// <summary>Gets the optional calendar date guide for a date-aware chart.</summary>
    public DateOnly? DateGuide { get; init; }
}

/// <summary>Represents every configured widget report for one page selection.</summary>
public sealed record DashboardPageReport(
    DashboardPageId PageId,
    IReadOnlyDictionary<string, DashboardWidgetReport> Widgets);

/// <summary>Represents the complete report snapshot consumed by the desktop renderer.</summary>
public sealed record DashboardReport(IReadOnlyDictionary<DashboardPageId, DashboardPageReport> Pages)
{
    /// <summary>Gets a configured page report.</summary>
    public DashboardPageReport Page(DashboardPageId id)
        => Pages.TryGetValue(id, out DashboardPageReport? page)
            ? page
            : throw new ArgumentException($"No report was built for page '{id}'.", nameof(id));
}

/// <summary>Captures the page filter state used by report construction.</summary>
public sealed record DashboardFilters(
    int LookbackMonths,
    string SpendingSet,
    string YearOverYearSet,
    bool RegularIncome,
    HomeTimeFrame HomeTimeFrame = HomeTimeFrame.OneYear)
{
    /// <summary>Creates the default filter state from finance settings.</summary>
    public static DashboardFilters From(FinanceSettings settings)
    {
        ArgumentNullException.ThrowIfNull(settings);
        return new DashboardFilters(
            settings.Lookback.DefaultMonths,
            settings.FilterSet("spending").Default,
            settings.FilterSet("year_over_year").Default,
            string.Equals(settings.IncomeSavings.DefaultView, "regular", StringComparison.OrdinalIgnoreCase),
            HomeTimeFrame.OneYear);
    }
}
