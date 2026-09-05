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
    IReadOnlyDictionary<string, DashboardWidgetReport> Widgets)
{
    /// <summary>Gets the optional source-shaped Income and savings report view.</summary>
    public IncomeSavingsPageView? IncomeSavingsView { get; init; }

    /// <summary>Gets the optional source-shaped Year over year report view.</summary>
    public YearOverYearPageView? YearOverYearView { get; init; }

    /// <summary>Gets the optional source-shaped Subscriptions report view.</summary>
    public SubscriptionsPageView? SubscriptionsView { get; init; }

    /// <summary>Gets the optional source-shaped Spending by merchant report view.</summary>
    public MerchantsPageView? MerchantsView { get; init; }

    /// <summary>Gets the optional source-shaped Transactions report view.</summary>
    public TransactionsPageView? TransactionsView { get; init; }

    /// <summary>Gets the optional source-shaped Budget report view.</summary>
    public BudgetPageView? BudgetView { get; init; }

    /// <summary>Gets the optional source-shaped Financial Independence report view.</summary>
    public FinancialIndependencePageView? FinancialIndependenceView { get; init; }

    /// <summary>Gets the optional source-shaped Data Health report view.</summary>
    public DataHealthPageView? DataHealthView { get; init; }
}

/// <summary>Contains the source-shaped data regions shown by the Income and savings page.</summary>
public sealed record IncomeSavingsPageView(
    IReadOnlyList<ReportMetric> SummaryMetrics,
    IReadOnlyList<ReportSeries> CashFlowSeries,
    IReadOnlyList<ReportSeries> SavingsRateSeries,
    int PositiveSurplusMonths,
    int MonthCount,
    int ExcludedCount,
    decimal ExcludedIncome,
    decimal ExcludedSpending,
    IReadOnlyList<string> DetailMonths,
    string DetailMonth,
    IReadOnlyList<ReportMetric> DetailMetrics,
    IReadOnlyList<ReportTableRow> IncludedCategories,
    IReadOnlyList<ReportTableRow> IncludedTransactions,
    IReadOnlyList<ReportTableRow> ExcludedTransactions,
    IReadOnlyList<ReportTableRow> MonthlyTotals,
    decimal TargetRate,
    bool HasLedgerRows,
    bool HasIncludedRows,
    string? EmptyMessage = null);

/// <summary>Contains one expandable source-style Year over year comparison card.</summary>
public sealed record YearOverYearComparisonView(
    string Entity,
    string ThroughMonthLabel,
    IReadOnlyList<ReportMetric> Metrics,
    IReadOnlyList<ReportSeries> Series,
    IReadOnlyList<string> TotalColumns,
    IReadOnlyList<ReportTableRow> TotalRows,
    IReadOnlyList<string> TransactionColumns,
    IReadOnlyList<ReportTableRow> TransactionRows);

/// <summary>Contains the dynamic choices and comparison cards shown by the Year over year page.</summary>
public sealed record YearOverYearPageView(
    string? LatestDataCaption,
    IReadOnlyList<string> PresetCategories,
    IReadOnlyList<string> Categories,
    IReadOnlyList<string> Groups,
    IReadOnlyList<YearOverYearComparisonView> Comparisons,
    string? EmptyMessage = null);

/// <summary>Contains the source-shaped data regions shown by the Subscriptions page.</summary>
public sealed record SubscriptionsPageView(
    string? LatestDataCaption,
    int? DataAgeDays,
    bool DataIsStale,
    SubscriptionAnalysisResult Analysis,
    string? SelectedMerchant,
    bool SelectedMerchantIsCandidate,
    IReadOnlyList<SubscriptionChargeEntry> SelectedCharges,
    string? EmptyMessage = null);

/// <summary>Contains the source-shaped data regions shown by the Spending by merchant page.</summary>
public sealed record MerchantsPageView(
    string? LatestDataCaption,
    MerchantAnalysisResult Analysis,
    string? SelectedMerchant,
    string DetailMonth,
    IReadOnlyList<MerchantHistoryEntry> SelectedHistory,
    IReadOnlyList<MerchantDetailBreakdownEntry> SelectedCategories,
    IReadOnlyList<MerchantDetailBreakdownEntry> SelectedAccounts,
    IReadOnlyList<MerchantDescriptionEntry> SelectedDescriptions,
    IReadOnlyList<SpendingLedgerEntry> SelectedTransactions,
    string? EmptyMessage = null);

/// <summary>Contains the source-shaped data regions shown by the Transactions page.</summary>
public sealed record TransactionsPageView(
    string? LatestDataCaption,
    TransactionExplorerAnalysisResult Analysis,
    string? EmptyMessage = null);

/// <summary>Contains the source-shaped data regions shown by the Budget page.</summary>
public sealed record BudgetPageView(
    string? LatestDataCaption,
    BudgetAnalysisResult Analysis,
    string? SelectedGroup,
    string TransactionCategory,
    IReadOnlyList<FinancialTransaction> VisibleTransactions,
    string? EmptyMessage = null);

/// <summary>Contains the source-shaped data regions shown by the Financial Independence page.</summary>
public sealed record FinancialIndependencePageView(
    string? LatestDataCaption,
    FinancialIndependenceSourceAnalysis Source,
    FinancialIndependenceScenario Scenario,
    FinancialIndependenceSummary Summary,
    IReadOnlyList<PortfolioProjectionPoint> Projection,
    IReadOnlyList<RunwaySensitivityCell> Sensitivity,
    string? EmptyMessage = null);

/// <summary>Contains the source-shaped Data Health queue and selected-check detail.</summary>
public sealed record DataHealthPageView(
    string? LatestDataCaption,
    DataHealthAnalysisResult Analysis,
    string SelectedCheckId,
    DataHealthCheckResult SelectedCheck,
    string? EmptyMessage = null);

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
    HomeTimeFrame HomeTimeFrame = HomeTimeFrame.OneYear,
    SpendingComparison SpendingComparison = SpendingComparison.PreviousPeriod,
    SpendingBreakdown SpendingBreakdown = SpendingBreakdown.Category,
    SpendingAdjustments? SpendingAdjustments = null,
    int IncomeLookbackMonths = 0,
    int MerchantLookbackMonths = 0,
    string? MerchantSet = null,
    SpendingComparison MerchantComparison = SpendingComparison.PreviousPeriod,
    SpendingAdjustments? MerchantAdjustments = null,
    IReadOnlyList<string>? SubscriptionCategories = null,
    IReadOnlyList<string>? SubscriptionDiscoveryExclusions = null,
    int SubscriptionMinimumConfidence = 0,
    TransactionExplorerFilters? TransactionExplorer = null,
    BudgetRequest? Budget = null,
    FinancialIndependenceSourceFilters? FinancialIndependenceSource = null,
    FinancialIndependenceScenario? FinancialIndependenceScenario = null,
    DataHealthCheckOptions? DataHealth = null)
{
    /// <summary>Gets the page-local Income and savings lookback, preserving older direct callers.</summary>
    public int EffectiveIncomeLookbackMonths => IncomeLookbackMonths > 0 ? IncomeLookbackMonths : LookbackMonths;

    /// <summary>Gets the page-local merchant lookback while keeping older callers compatible.</summary>
    public int EffectiveMerchantLookbackMonths => MerchantLookbackMonths > 0 ? MerchantLookbackMonths : LookbackMonths;

    /// <summary>Creates the default filter state from finance settings.</summary>
    public static DashboardFilters From(FinanceSettings settings)
    {
        ArgumentNullException.ThrowIfNull(settings);
        return new DashboardFilters(
            settings.Lookback.DefaultMonths,
            settings.FilterSet("spending").Default,
            settings.FilterSet("year_over_year").Default,
            string.Equals(settings.IncomeSavings.DefaultView, "regular", StringComparison.OrdinalIgnoreCase),
            HomeTimeFrame.OneYear,
            SpendingComparison.PreviousPeriod,
            SpendingBreakdown.Category,
            SpendingAdjustments.Default(settings.Thresholds.Expense),
            settings.Lookback.DefaultMonths,
            MerchantLookbackMonths: settings.Lookback.DefaultMonths,
            MerchantSet: settings.FilterSet("spending").Default,
            MerchantComparison: SpendingComparison.PreviousPeriod,
            MerchantAdjustments: SpendingAdjustments.Default(settings.Thresholds.Expense),
            SubscriptionMinimumConfidence: settings.Subscriptions.MinimumConfidence,
            TransactionExplorer: TransactionExplorerFilters.Default);
    }
}
