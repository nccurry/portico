using Portico.Dashboard;
using Portico.Finance;

namespace Portico.Dashboard.Tests;

public sealed class DashboardReportBuilderTests
{
    [Fact]
    public void Build_ReturnsEveryPorticoPageAndUsesConfiguredFinanceRules()
    {
        FinanceSettings settings = Settings();
        PortfolioSnapshot snapshot = Snapshot();

        DashboardReport report = DashboardReportBuilder.Build(
            snapshot,
            settings,
            new DashboardFilters(3, "discretionary", "all", true));

        Assert.Equal(10, report.Pages.Count);
        DashboardWidgetReport home = report.Page(DashboardPageId.Home).Widgets["home.overview"];
        Assert.Equal(4, home.Metrics.Count);
        Assert.Equal("$2,450", home.Metrics[0].Display);
        DashboardWidgetReport spending = report.Page(DashboardPageId.Spending).Widgets["spending.categories"];
        Assert.Equal("Flight", Assert.Single(spending.Series).Points[0].Category);
        DashboardWidgetReport top = report.Page(DashboardPageId.TopTransactions).Widgets["top.table"];
        Assert.DoesNotContain(top.Rows, row => row.Values.Contains("Hidden charge"));
        Assert.NotEmpty(report.Page(DashboardPageId.FinancialIndependence).Widgets["fi.projection"].Series);
    }

    [Fact]
    public void Build_AppliesLookbackAndRegularIncomeExclusions()
    {
        FinanceSettings settings = Settings();
        PortfolioSnapshot snapshot = Snapshot();

        DashboardReport regular = DashboardReportBuilder.Build(snapshot, settings, new DashboardFilters(1, "all", "all", true));
        DashboardReport actual = DashboardReportBuilder.Build(snapshot, settings, new DashboardFilters(1, "all", "all", false));

        DashboardWidgetReport regularCashFlow = regular.Page(DashboardPageId.IncomeSavings).Widgets["income.cash_flow"];
        DashboardWidgetReport actualCashFlow = actual.Page(DashboardPageId.IncomeSavings).Widgets["income.cash_flow"];
        Assert.Equal(1000m, regularCashFlow.Metrics.Single(metric => metric.Label == "Surplus").Value);
        Assert.Equal(980m, actualCashFlow.Metrics.Single(metric => metric.Label == "Surplus").Value);
        Assert.Single(regularCashFlow.Series.Single(series => series.Id == "income").Points);
    }

    [Fact]
    public void SupportedWidgetReports_CoversTheCheckedInDashboardGrammar()
    {
        string[] expected =
        [
            "home.net_worth", "income.cash_flow", "spending.categories", "yoy.comparison",
            "subscriptions.active", "merchants.ranking", "budget.table", "top.table",
            "fi.sensitivity", "health.findings"
        ];

        foreach (string report in expected)
            Assert.Contains(report, DashboardReportBuilder.SupportedWidgetReports);
    }

    private static FinanceSettings Settings()
    {
        TransactionSetDefinition[] sets =
        [
            Set("all"),
            Set("discretionary", includes: ["all"], excludes: ["housing"]),
            Set("housing", groups: ["Housing"])
        ];
        return new FinanceSettings(
            new DataSourceSettings(WorkbookSourceKind.LocalCsv, "demo/data"),
            new LookbackSettings([1, 3, 12], 3),
            new ThresholdSettings(100m, 1000m, 10m, 1),
            new IncomeSavingsSettings("regular", 20m, [], ["Fun"]),
            sets,
            [new FilterSetDefinition("spending", ["all", "discretionary"], "discretionary"), new FilterSetDefinition("year_over_year", ["all"], "all")],
            new SubscriptionSettings(["Streaming"], 80, 45, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 5, [], ["Investments", "Cash"]),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
            {
                ["Video Service"] = ["VIDEO SERVICE"]
            });
    }

    private static PortfolioSnapshot Snapshot()
        => new(
            [
                Row("salary", 2024, 1, 2, "Salary", "Income", "Pay", 1000m, TransactionKind.Income),
                Row("rent", 2024, 1, 3, "Rent", "Housing", "Rent", -500m, TransactionKind.Expense),
                Row("food", 2024, 1, 4, "Food", "Living", "Market", -100m, TransactionKind.Expense),
                Row("travel", 2024, 1, 5, "Flight", "Travel", "Flight", -300m, TransactionKind.Expense),
                Row("subscription", 2024, 1, 7, "Streaming", "Fun", "VIDEO SERVICE", -20m, TransactionKind.Expense),
                Row("salary2", 2024, 2, 2, "Salary", "Income", "Pay", 1200m, TransactionKind.Income),
                Row("food2", 2024, 2, 4, "Food", "Living", "Market", -200m, TransactionKind.Expense),
                Row("subscription2", 2024, 2, 7, "Streaming", "Fun", "VIDEO SERVICE", -20m, TransactionKind.Expense),
                Row("hidden", 2024, 2, 8, "Food", "Living", "Hidden charge", -999m, TransactionKind.Expense, true)
            ],
            [
                new BalanceObservation("cash", "Checking", "Cash", new DateOnly(2024, 1, 31), new TimeOnly(8, 0), 1500m, AccountClass.Asset, false),
                new BalanceObservation("cash", "Checking", "Cash", new DateOnly(2024, 2, 29), new TimeOnly(8, 0), 1700m, AccountClass.Asset, false),
                new BalanceObservation("invest", "Brokerage", "Investments", new DateOnly(2024, 2, 29), new TimeOnly(8, 0), 1000m, AccountClass.Asset, false),
                new BalanceObservation("card", "Card", "Debt", new DateOnly(2024, 2, 29), new TimeOnly(8, 0), 250m, AccountClass.Liability, false)
            ],
            [
                new BudgetEntry(new YearMonth(2024, 2), "Food", "Living", TransactionKind.Expense, 250m, false),
                new BudgetEntry(new YearMonth(2024, 2), "Streaming", "Fun", TransactionKind.Expense, 25m, false)
            ]);

    private static FinancialTransaction Row(
        string id,
        int year,
        int month,
        int day,
        string category,
        string group,
        string description,
        decimal amount,
        TransactionKind kind,
        bool hidden = false)
        => new(id, new DateOnly(year, month, day), category, group, "Checking", description, amount, kind, hidden);

    private static TransactionSetDefinition Set(
        string key,
        IReadOnlyList<string>? groups = null,
        IReadOnlyList<string>? includes = null,
        IReadOnlyList<string>? excludes = null)
        => new(key, key, groups ?? [], [], [], [], [], includes ?? [], excludes ?? []);
}
