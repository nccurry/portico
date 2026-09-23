using Portico.Dashboard;
using Portico.Finance;

namespace Portico.Dashboard.Tests;

public sealed class DashboardYearOverYearTests
{
    [Fact]
    public void Build_PresetViewCreatesOneComparisonForEachSelectedEligibleCategory()
    {
        PortfolioSnapshot snapshot = new(
        [
            Income("coverage-start", 2024, 1, 1_000m),
            Expense("prior-food", 2024, 4, "Food", "Living", -20m),
            Expense("current-food", 2025, 4, "Food", "Living", -60m),
            Expense("prior-rent", 2024, 4, "Rent", "Housing", -500m),
            Expense("current-rent", 2025, 4, "Rent", "Housing", -700m),
            Income("coverage-end", 2025, 6, 1_000m)
        ], [], []);
        var presentation = new DashboardPresentationState();
        presentation.SetYearOverYearPresetCategories("all", ["Food", "Rent"]);

        YearOverYearPageView view = Assert.IsType<YearOverYearPageView>(
            DashboardReportBuilder.Build(
                    snapshot,
                    Settings(),
                    new DashboardFilters(12, "all", "all", true),
                    presentation)
                .Page(DashboardPageId.YearOverYear)
                .YearOverYearView);

        Assert.Equal(["Rent", "Food"], view.Comparisons.Select(comparison => comparison.Entity));
        Assert.All(view.Comparisons, comparison =>
        {
            Assert.Equal("June", comparison.ThroughMonthLabel);
            Assert.Equal(3, comparison.Metrics.Count);
            Assert.Equal(["2025", "2024"], comparison.Series.Select(series => series.Label));
            Assert.NotEmpty(comparison.TotalRows);
            Assert.NotEmpty(comparison.TransactionRows);
        });
    }

    [Fact]
    public void Build_SingleCategoryAndGroupUseTheRawEntityChoiceButApplyIncludedSpending()
    {
        PortfolioSnapshot snapshot = new(
        [
            Expense("food", 2025, 6, "Food", "Living", -50m),
            Expense("rent", 2025, 6, "Rent", "Housing", -900m),
            Expense("transfer", 2025, 6, "Transfer", "Transfer", -400m)
        ], [], []);
        var categoryPresentation = new DashboardPresentationState();
        categoryPresentation.SetYearOverYearViewMode(YearOverYearViewMode.SingleCategory);
        categoryPresentation.SetYearOverYearSingleCategory("Food");
        var groupPresentation = new DashboardPresentationState();
        groupPresentation.SetYearOverYearViewMode(YearOverYearViewMode.SingleGroup);
        groupPresentation.SetYearOverYearSingleGroup("Housing");

        YearOverYearPageView category = View(snapshot, categoryPresentation);
        YearOverYearPageView group = View(snapshot, groupPresentation);

        Assert.Equal(["Food", "Rent", "Transfer"], category.Categories);
        Assert.Equal(["Housing", "Living", "Transfer"], group.Groups);
        Assert.Equal("Food", Assert.Single(category.Comparisons).Entity);
        Assert.Equal("Housing", Assert.Single(group.Comparisons).Entity);

        categoryPresentation.SetYearOverYearSingleCategory("Transfer");
        Assert.Empty(View(snapshot, categoryPresentation).Comparisons);
    }

    [Fact]
    public void Build_WhenAnEntityFirstAppearsThisYearMakesTheMissingPreviousComparisonExplicit()
    {
        PortfolioSnapshot snapshot = new(
        [
            Income("coverage", 2024, 1, 1_000m),
            Expense("current-food", 2025, 6, "Food", "Living", -100m)
        ], [], []);
        var presentation = new DashboardPresentationState();
        presentation.SetYearOverYearViewMode(YearOverYearViewMode.SingleCategory);
        presentation.SetYearOverYearSingleCategory("Food");

        YearOverYearComparisonView comparison = Assert.Single(View(snapshot, presentation).Comparisons);
        ReportMetric previous = comparison.Metrics.Single(metric => metric.Label == "Previous year");
        ReportMetric change = comparison.Metrics.Single(metric => metric.Label == "Change");

        Assert.Null(previous.Value);
        Assert.Equal("Not available", previous.Display);
        Assert.Null(change.Value);
        Assert.Equal("Not available", change.Display);
    }

    private static YearOverYearPageView View(
        PortfolioSnapshot snapshot,
        DashboardPresentationState presentation)
        => Assert.IsType<YearOverYearPageView>(
            DashboardReportBuilder.Build(
                    snapshot,
                    Settings(),
                    new DashboardFilters(12, "all", "all", true),
                    presentation)
                .Page(DashboardPageId.YearOverYear)
                .YearOverYearView);

    private static FinancialTransaction Income(string id, int year, int month, decimal amount)
        => new(id, new DateOnly(year, month, 15), "Salary", "Income", "Checking", "Salary", amount, TransactionKind.Income);

    private static FinancialTransaction Expense(
        string id,
        int year,
        int month,
        string category,
        string group,
        decimal amount)
        => new(id, new DateOnly(year, month, 15), category, group, "Checking", category, amount, TransactionKind.Expense);

    private static FinanceSettings Settings()
    {
        TransactionSetDefinition[] sets =
        [
            new TransactionSetDefinition("all", "All", [], [], [], [], [], [], []),
            new TransactionSetDefinition("living", "Living", ["Living"], [], [], [], [], [], [])
        ];
        return new FinanceSettings(
            new LookbackSettings([3, 6, 12], 12),
            new ThresholdSettings(3_000m, 20_000m, 10m, 1),
            new IncomeSavingsSettings("regular", 20m, [], []),
            sets,
            [
                new FilterSetDefinition("spending", ["all", "living"], "all"),
                new FilterSetDefinition("year_over_year", ["all", "living"], "all")
            ],
            new SubscriptionSettings([], 80, 45, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 5, [], []),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal));
    }
}
