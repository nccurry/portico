using Portico.Finance;

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
        Report = DashboardReportBuilder.Build(_snapshot, _settings, Filters, _asOfDate);
    }

    /// <summary>Gets the configuration used to render pages and controls.</summary>
    public DashboardDefinition Definition { get; }

    /// <summary>Gets the page currently shown in the main content area.</summary>
    public DashboardPageId CurrentPage { get; private set; }

    /// <summary>Gets the current report filter values.</summary>
    public DashboardFilters Filters { get; private set; }

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
}
