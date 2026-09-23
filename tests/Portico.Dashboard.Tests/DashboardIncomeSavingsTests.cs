using Portico.Dashboard;
using Portico.Finance;

namespace Portico.Dashboard.Tests;

public sealed class DashboardIncomeSavingsTests
{
    [Fact]
    public void Build_UsesTheIncomePageLookbackWithoutChangingTheSharedLookback()
    {
        PortfolioSnapshot snapshot = new(
        [
            Income("april", 2025, 4, 1_000m),
            Income("may", 2025, 5, 1_000m),
            Income("june", 2025, 6, 1_000m)
        ], [], []);
        var filters = new DashboardFilters(1, "all", "all", true, IncomeLookbackMonths: 3);

        IncomeSavingsPageView view = Assert.IsType<IncomeSavingsPageView>(
            DashboardReportBuilder.Build(snapshot, Settings(), filters)
                .Page(DashboardPageId.IncomeSavings)
                .IncomeSavingsView);

        Assert.Equal(1, filters.LookbackMonths);
        Assert.Equal(3, filters.EffectiveIncomeLookbackMonths);
        Assert.Equal(["2025-06", "2025-05", "2025-04"], view.DetailMonths);
        Assert.Equal("2025-06", view.DetailMonth);
        Assert.Equal(3, view.MonthCount);
    }

    [Fact]
    public void Build_OmitsPreviousComparisonDetailsWhenFullHistoryIsUnavailable()
    {
        PortfolioSnapshot snapshot = new(
        [
            Income("april", 2025, 4, 1_000m),
            Expense("may", 2025, 5, -100m),
            Income("june", 2025, 6, 1_000m)
        ], [], []);

        IncomeSavingsPageView view = Assert.IsType<IncomeSavingsPageView>(
            DashboardReportBuilder.Build(
                snapshot,
                Settings(),
                new DashboardFilters(2, "all", "all", true, IncomeLookbackMonths: 2))
                .Page(DashboardPageId.IncomeSavings)
                .IncomeSavingsView);

        Assert.All(view.SummaryMetrics, metric =>
        {
            Assert.Null(metric.Change);
            Assert.Null(metric.Detail);
        });
    }

    [Fact]
    public void Build_PreservesSelectedMonthAndIncludesExcludedReasonRows()
    {
        PortfolioSnapshot snapshot = new(
        [
            Income("may-income", 2025, 5, 1_000m),
            Expense("may-travel", 2025, 5, -100m),
            Income("june-income", 2025, 6, 1_000m),
            Expense("june-travel", 2025, 6, -200m)
        ], [], []);
        FinanceSettings settings = Settings();
        var presentation = new DashboardPresentationState();
        presentation.InitializeIncomeSavings(settings);
        presentation.SetIncomeDetailMonth("2025-05");

        IncomeSavingsPageView view = Assert.IsType<IncomeSavingsPageView>(
            DashboardReportBuilder.Build(
                snapshot,
                settings,
                new DashboardFilters(1, "all", "all", true, IncomeLookbackMonths: 2),
                presentation)
                .Page(DashboardPageId.IncomeSavings)
                .IncomeSavingsView);

        Assert.Equal("2025-05", view.DetailMonth);
        Assert.Equal("$1,000", view.DetailMetrics.Single(metric => metric.Label == "Income").Display);
        ReportTableRow excluded = Assert.Single(view.ExcludedTransactions);
        Assert.Equal("Travel", excluded.Values[2]);
        Assert.Contains("Excluded group: Travel", excluded.Values[^1], StringComparison.Ordinal);
    }

    [Fact]
    public void Build_KeepsTheExcludedLedgerWhenEveryCurrentRowIsExcluded()
    {
        PortfolioSnapshot snapshot = new(
        [
            Income("income", 2025, 6, 1_000m),
            Expense("travel", 2025, 6, -200m)
        ], [], []);
        FinanceSettings settings = Settings() with
        {
            IncomeSavings = new IncomeSavingsSettings("regular", 20m, ["Salary"], ["Travel"])
        };

        IncomeSavingsPageView view = Assert.IsType<IncomeSavingsPageView>(
            DashboardReportBuilder.Build(snapshot, settings, new DashboardFilters(1, "all", "all", true))
                .Page(DashboardPageId.IncomeSavings)
                .IncomeSavingsView);

        Assert.True(view.HasLedgerRows);
        Assert.False(view.HasIncludedRows);
        Assert.Equal(2, view.ExcludedTransactions.Count);
        Assert.Contains("All transactions", view.EmptyMessage, StringComparison.Ordinal);
    }

    [Fact]
    public void Build_UsesRegularAndActualAdjustmentSetsIndependently()
    {
        PortfolioSnapshot snapshot = new(
        [
            Income("income", 2025, 6, 1_000m),
            Expense("travel", 2025, 6, -200m)
        ], [], []);
        FinanceSettings settings = Settings();
        var presentation = new DashboardPresentationState();
        presentation.InitializeIncomeSavings(settings);
        presentation.SetIncomeSavingsAdjustments(false, presentation.IncomeSavingsAdjustments(false) with
        {
            ExcludedExpenseCategories = ["Other"]
        });

        IncomeSavingsPageView regular = Assert.IsType<IncomeSavingsPageView>(
            DashboardReportBuilder.Build(snapshot, settings, new DashboardFilters(1, "all", "all", true), presentation)
                .Page(DashboardPageId.IncomeSavings)
                .IncomeSavingsView);
        IncomeSavingsPageView actual = Assert.IsType<IncomeSavingsPageView>(
            DashboardReportBuilder.Build(snapshot, settings, new DashboardFilters(1, "all", "all", false), presentation)
                .Page(DashboardPageId.IncomeSavings)
                .IncomeSavingsView);

        Assert.Equal(0m, regular.DetailMetrics.Single(metric => metric.Label == "Spending").Value);
        Assert.Equal(200m, actual.DetailMetrics.Single(metric => metric.Label == "Spending").Value);
    }

    private static FinancialTransaction Income(string id, int year, int month, decimal amount)
        => new(id, new DateOnly(year, month, 15), "Salary", "Income", "Checking", "Salary", amount, TransactionKind.Income);

    private static FinancialTransaction Expense(string id, int year, int month, decimal amount)
        => new(id, new DateOnly(year, month, 16), "Food", "Travel", "Checking", "Flight", amount, TransactionKind.Expense);

    private static FinanceSettings Settings()
        => new(
            new LookbackSettings([1, 2, 3, 6, 12, 24], 3),
            new ThresholdSettings(3_000m, 20_000m, 10m, 1),
            new IncomeSavingsSettings("regular", 20m, [], ["Travel"]),
            [new TransactionSetDefinition("all", "All", [], [], [], [], [], [], [])],
            [
                new FilterSetDefinition("spending", ["all"], "all"),
                new FilterSetDefinition("year_over_year", ["all"], "all")
            ],
            new SubscriptionSettings([], 80, 45, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 5, [], []),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal));
}
