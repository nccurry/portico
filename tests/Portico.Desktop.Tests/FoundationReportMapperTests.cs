using Portico.Application;
using Portico.Finance;

namespace Portico.Desktop.Tests;

public sealed class FoundationReportMapperTests
{
    [Fact]
    public async Task IncomeUsesSelectedMonthAndKeepsTheEightConfiguredWidgets()
    {
        Workspace workspace = await OpenWorkspace();

        DashboardPageReport january = IncomeSavingsDashboardReport.Build(workspace.Income(new IncomeReportRequest(
            LookbackMonths: 2, RegularIncome: false, DetailMonth: new YearMonth(2026, 1))), 2);
        DashboardPageReport february = IncomeSavingsDashboardReport.Build(workspace.Income(new IncomeReportRequest(
            LookbackMonths: 2, RegularIncome: false, DetailMonth: new YearMonth(2026, 2))), 2);

        Assert.Equal(DashboardPageId.IncomeSavings, january.PageId);
        Assert.Equal(8, january.Widgets.Count);
        Assert.Equal("2026-01", january.IncomeSavingsView?.DetailMonth);
        Assert.Equal("2026-02", february.IncomeSavingsView?.DetailMonth);
        Assert.Equal("$1,000", january.Widgets["income.detail"].Metrics.Single(metric => metric.Label == "Income").Display);
        Assert.Equal("$1,100", february.Widgets["income.detail"].Metrics.Single(metric => metric.Label == "Income").Display);
        Assert.Equal("No excluded transactions for this month.", january.Widgets["income.excluded_transactions"].EmptyMessage);
        Assert.Equal(["2026-02", "2026-01"], january.IncomeSavingsView?.DetailMonths);
        Assert.Equal("Jan 10, 2026", january.Widgets["income.included_transactions"].Rows
            .Single(row => row.Values[1] == "food-jan").Values[0]);
    }

    [Fact]
    public async Task IncomeExplainsTypedExclusionsWithoutUsingFinanceDisplayCopy()
    {
        Workspace workspace = await OpenWorkspace();
        var adjustments = IncomeSavingsAdjustments.Default(Settings(), regular: false) with
        {
            ExcludedExpenseCategories = ["Food"]
        };

        DashboardPageReport page = IncomeSavingsDashboardReport.Build(workspace.Income(new IncomeReportRequest(
            LookbackMonths: 2, RegularIncome: false, Adjustments: adjustments,
            DetailMonth: new YearMonth(2026, 2))), 2);

        ReportTableRow excluded = Assert.Single(page.Widgets["income.excluded_transactions"].Rows);
        Assert.Contains("Excluded expense category: Food", excluded.Values[^1], StringComparison.Ordinal);
        Assert.Equal(2, page.IncomeSavingsView?.ExcludedCount);
    }

    [Fact]
    public async Task SpendingMapsGroupDetailAndChangedEntitySelection()
    {
        Workspace workspace = await OpenWorkspace();
        DashboardPageReport group = SpendingDashboardReport.Build(workspace.Spending(new SpendingReportRequest(
            LookbackMonths: 2, Breakdown: SpendingBreakdown.Group, Entity: "Living",
            DetailMonth: new YearMonth(2026, 2))), 2, SpendingComparison.PreviousPeriod);
        DashboardPageReport category = SpendingDashboardReport.Build(workspace.Spending(new SpendingReportRequest(
            LookbackMonths: 2, Breakdown: SpendingBreakdown.Category, Entity: "Food")),
            2, SpendingComparison.PreviousPeriod);

        Assert.Equal(12, group.Widgets.Count);
        Assert.Equal("$300", group.Widgets["spending.detail_summary"].Metrics.Single(metric => metric.Label == "Spending").Display);
        Assert.Equal("Food", Assert.Single(group.Widgets["spending.detail_categories"].Rows).Values[0]);
        Assert.Equal("Categories are part of the selected category.", category.Widgets["spending.detail_categories"].EmptyMessage);
        Assert.Equal("Category", category.Widgets["spending.overview"].Columns[0]);
    }

    [Fact]
    public async Task SpendingExplainsTypedExclusions()
    {
        Workspace workspace = await OpenWorkspace();
        var adjustments = new SpendingAdjustments(["Living"], [], [], [], false, 100m);

        DashboardPageReport page = SpendingDashboardReport.Build(workspace.Spending(new SpendingReportRequest(
            LookbackMonths: 2, Adjustments: adjustments)), 2, SpendingComparison.PreviousPeriod);

        Assert.Equal(2, page.Widgets["spending.excluded"].Rows.Count);
        Assert.All(page.Widgets["spending.excluded"].Rows,
            row => Assert.Equal("Excluded group: Living", row.Values[^1]));
    }

    [Fact]
    public async Task SpendingLastYearUsesMatchedHistoryAndLabels()
    {
        Workspace workspace = await OpenWorkspace();
        SpendingReport report = workspace.Spending(new SpendingReportRequest(
            LookbackMonths: 2, Comparison: SpendingComparison.LastYear,
            Breakdown: SpendingBreakdown.Group, Entity: "Living"));

        DashboardPageReport page = SpendingDashboardReport.Build(report, 2, SpendingComparison.LastYear);

        Assert.Contains("same months last year", page.Widgets["spending.overview"].Columns);
        ReportSeries comparison = page.Widgets["spending.detail_history"].Series[1];
        Assert.Equal("same months last year", comparison.Label);
        Assert.Equal(50m, comparison.Points[^1].Y);
    }

    [Fact]
    public async Task YearOverYearShowsEmptyChoiceThenSelectedComparison()
    {
        Workspace workspace = await OpenWorkspace();
        DashboardPageReport noSelection = YearOverYearDashboardReport.Build(workspace.YearOverYear());
        DashboardPageReport selected = YearOverYearDashboardReport.Build(workspace.YearOverYear(
            new YearOverYearReportRequest(YearOverYearSelection.Category, Entity: "Food")));

        Assert.Equal(2, noSelection.Widgets.Count);
        Assert.Equal("Choose at least one category to compare.", noSelection.YearOverYearView?.EmptyMessage);
        YearOverYearComparisonView comparison = Assert.Single(selected.YearOverYearView!.Comparisons);
        Assert.Equal("Food", comparison.Entity);
        Assert.NotEmpty(comparison.Series);
        Assert.NotEmpty(comparison.TotalRows);
        Assert.Contains("Latest data", selected.YearOverYearView.LatestDataCaption, StringComparison.Ordinal);
    }

    [Fact]
    public async Task EmptyWorkspaceKeepsPageMessagesAndNoSelectedDetail()
    {
        Workspace workspace = await OpenWorkspace(new PortfolioSnapshot([], [], []));

        DashboardPageReport income = IncomeSavingsDashboardReport.Build(workspace.Income(), 2);
        DashboardPageReport spending = SpendingDashboardReport.Build(workspace.Spending(), 2, SpendingComparison.PreviousPeriod);
        DashboardPageReport yearOverYear = YearOverYearDashboardReport.Build(workspace.YearOverYear());

        Assert.Equal("No categorized income or expense transactions are available.", income.IncomeSavingsView?.EmptyMessage);
        Assert.Equal(string.Empty, income.IncomeSavingsView?.DetailMonth);
        Assert.Equal("No expense transactions are available.", spending.Widgets["spending.summary"].EmptyMessage);
        Assert.Equal("No spending matches these controls.", spending.Widgets["spending.overview"].EmptyMessage);
        Assert.Equal("No expense transactions are available.", yearOverYear.YearOverYearView?.EmptyMessage);
    }

    [Fact]
    public async Task WorkspaceGivesIndependentConfiguredAdjustmentDefaults()
    {
        FinanceSettings settings = Settings() with
        {
            IncomeSavings = Settings().IncomeSavings with { ExcludeCategories = ["Gift"] }
        };
        Workspace workspace = await OpenWorkspace(settings: settings);

        Assert.True(workspace.DefaultIncomeIsRegular);
        IncomeSavingsAdjustments regular = workspace.IncomeAdjustments(regular: true);
        Assert.Equal(["Gift"], regular.ExcludedIncomeCategories);
        Assert.Empty(workspace.IncomeAdjustments(regular: false).ExcludedIncomeCategories);
        ((string[])regular.ExcludedIncomeCategories)[0] = "Changed";
        Assert.Equal(["Gift"], workspace.IncomeAdjustments(regular: true).ExcludedIncomeCategories);
        Assert.Equal(100m, workspace.DefaultSpendingAdjustments().ExpenseLimit);
    }

    private static async Task<Workspace> OpenWorkspace(PortfolioSnapshot? source = null, FinanceSettings? settings = null)
    {
        FinancialTransaction[] transactions =
        [
            Tx("prior", 2025, 2, 10, "Living", "Food", -50m),
            Tx("income-jan", 2026, 1, 5, "Pay", "Salary", 1000m, TransactionKind.Income),
            Tx("food-jan", 2026, 1, 10, "Living", "Food", -200m),
            Tx("income-feb", 2026, 2, 5, "Pay", "Salary", 1100m, TransactionKind.Income),
            Tx("food-feb", 2026, 2, 10, "Living", "Food", -300m)
        ];
        var application = new PorticoApplication(new ConfigReader(settings ?? Settings()),
            new DataReader(source ?? new PortfolioSnapshot(transactions, [], [])));
        OpenWorkspaceOutcome outcome = await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken);
        return outcome switch
        {
            WorkspaceOpened opened => opened.GetWorkspace(),
            _ => throw new InvalidOperationException("Expected a workspace.")
        };
    }

    private static FinancialTransaction Tx(
        string id, int year, int month, int day, string group, string category,
        decimal amount, TransactionKind kind = TransactionKind.Expense)
        => new(id, new DateOnly(year, month, day), category, group, "Checking", id, amount, kind);

    private static FinanceSettings Settings() => new(
        new LookbackSettings([1, 2, 3, 12], 2),
        new ThresholdSettings(100m, 100m, 10m, 1),
        new IncomeSavingsSettings("regular", 25m, [], []),
        [new TransactionSetDefinition("all", "All", [], [], [], [], [], [], [])],
        [new FilterSetDefinition("spending", ["all"], "all"),
            new FilterSetDefinition("year_over_year", ["all"], "all")],
        new SubscriptionSettings([], 0, 1, [], []),
        new BudgetSettings(3),
        new DataHealthSettings(1, false, false, false),
        new FinancialSafetySettings(3, ["Cash"], [], 3, [], [], ["Debt"], [], null),
        new FinancialIndependenceSettings(0.05m, 0.04m, 1000m, 12, 10, [], []),
        new Dictionary<string, IReadOnlyList<string>>());

    private sealed class ConfigReader(FinanceSettings settings) : IConfigurationReader
    {
        public Task<ConfigurationReadOutcome> ReadAsync(ConfigurationSelection selection, CancellationToken cancellationToken)
            => Task.FromResult<ConfigurationReadOutcome>(new ConfigurationReadSuccess(
                new WorkspaceConfiguration(settings, new LocalCsvSourceRequest("fixture"))));
    }

    private sealed class DataReader(PortfolioSnapshot snapshot) : IPortfolioReader
    {
        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
            => Task.FromResult<PortfolioReadOutcome>(new PortfolioReadSuccess(snapshot));
    }
}
