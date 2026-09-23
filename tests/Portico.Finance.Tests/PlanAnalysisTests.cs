using Portico.Finance;

namespace Portico.Finance.Tests;

public sealed class PlanAnalysisTests
{
    [Fact]
    public void BudgetBuild_ReconcilesBudgetTrackedSpendingAndUnbudgetedSpending()
    {
        BudgetAnalysisResult result = BudgetAnalysisCalculator.Build(
            [
                Budget(2025, 4, "Food", "Living", 120m),
                Budget(2025, 4, "Rent", "Housing", 1_000m),
                Budget(2025, 3, "Food", "Living", 100m),
                Budget(2025, 3, "Rent", "Housing", 900m)
            ],
            [
                Expense("food", 2025, 4, 4, "Food", "Living", -90m),
                Expense("refund", 2025, 4, 6, "Food", "Living", 10m),
                Expense("coffee", 2025, 4, 9, "Coffee", "Living", -15m),
                Expense("rent", 2025, 4, 1, "Rent", "Housing", -1_000m),
                Expense("march-food", 2025, 3, 4, "Food", "Living", -80m)
            ],
            Request(new YearMonth(2025, 4), ["Living", "Housing"], throughDate: new DateOnly(2025, 4, 15)));

        Assert.Equal(1_120m, result.Summary.Budget);
        Assert.Equal(1_080m, result.Summary.TrackedSpent);
        Assert.Equal(15m, result.Summary.OutsidePlan);
        Assert.Equal(1_095m, result.Summary.Spent);
        Assert.Equal(25m, result.Summary.Remaining);
        Assert.Equal(97.77m, decimal.Round(result.Summary.PercentUsed, 2));
        BudgetPerformanceEntry living = Assert.Single(result.Groups, entry => entry.Entity == "Living");
        Assert.Equal(80m, living.TrackedSpent);
        Assert.Equal(15m, living.OutsidePlan);
        Assert.Equal(80m, living.TypicalSpending);
        Assert.Equal(50m, decimal.Round(result.MonthProgress * 100m, 0));
    }

    [Fact]
    public void BudgetBuild_ClampsHistoryToTheFirstObservedMonth()
    {
        BudgetAnalysisResult result = BudgetAnalysisCalculator.Build(
            [
                Budget(2025, 3, "Food", "Living", 100m),
                Budget(2025, 4, "Food", "Living", 120m)
            ],
            [
                Expense("march-food", 2025, 3, 4, "Food", "Living", -80m),
                Expense("april-food", 2025, 4, 4, "Food", "Living", -90m)
            ],
            Request(new YearMonth(2025, 4), ["Living"]));

        BudgetGroupDetail living = result.GroupDetails["Living"];

        Assert.Equal(
            [new YearMonth(2025, 3), new YearMonth(2025, 4)],
            living.History.Select(entry => entry.Month));
        Assert.Equal(80m, living.Performance.TypicalSpending);
        Assert.Equal([80m, 90m], living.Performance.Trend);
    }

    [Fact]
    public void BudgetBuild_AppliesAllAdjustmentRulesAndKeepsExactLimit()
    {
        SpendingAdjustments adjustments = SpendingAdjustments.Default(100m) with
        {
            ExcludedCategories = ["Travel"],
            IncludedDescriptions = ["market"],
            ExcludedDescriptions = ["delivery"],
            ExcludeLargeExpenses = true
        };
        BudgetAnalysisResult result = BudgetAnalysisCalculator.Build(
            [
                Budget(2025, 6, "Food", "Living", 500m),
                Budget(2025, 6, "Travel", "Living", 300m)
            ],
            [
                Expense("market", 2025, 6, 2, "Food", "Living", -100m, "Market shop"),
                Expense("over", 2025, 6, 3, "Food", "Living", -101m, "Market bulk"),
                Expense("delivery", 2025, 6, 4, "Food", "Living", -50m, "Market delivery"),
                Expense("travel", 2025, 6, 5, "Travel", "Living", -200m, "Market flight")
            ],
            Request(new YearMonth(2025, 6), ["Living"], adjustments: adjustments));

        BudgetPerformanceEntry living = Assert.Single(result.Groups);
        Assert.Equal(500m, living.Budget);
        Assert.Equal(100m, living.Spent);
        Assert.Single(result.GroupDetails["Living"].Transactions);
        Assert.Equal("market", Assert.Single(result.GroupDetails["Living"].Transactions).Id);
    }

    [Fact]
    public void BudgetBuild_UsesCompleteDailyPaceAndFutureMonthsHaveNoPace()
    {
        BudgetEntry[] budgets = [Budget(2025, 5, "Food", "Living", 310m)];
        FinancialTransaction[] transactions = [Expense("food", 2025, 5, 2, "Food", "Living", -20m)];

        BudgetAnalysisResult current = BudgetAnalysisCalculator.Build(
            budgets,
            transactions,
            Request(new YearMonth(2025, 5), ["Living"], throughDate: new DateOnly(2025, 5, 3)));
        BudgetAnalysisResult future = BudgetAnalysisCalculator.Build(
            budgets,
            transactions,
            Request(new YearMonth(2025, 6), ["Living"], throughDate: new DateOnly(2025, 5, 3)));

        Assert.Equal(3, current.DailyPace.Count);
        Assert.Equal(20m, current.DailyPace[^1].ActualCumulative);
        Assert.Equal(30m, current.DailyPace[^1].IdealCumulative);
        Assert.Empty(future.DailyPace);
        Assert.Equal(0m, future.MonthProgress);
    }

    [Fact]
    public void BudgetBuild_ReturnsYearToDateGroupPositionAndHandlesNoGroups()
    {
        BudgetAnalysisResult result = BudgetAnalysisCalculator.Build(
            [
                Budget(2025, 1, "Food", "Living", 100m),
                Budget(2025, 2, "Food", "Living", 100m),
                Budget(2025, 2, "Rent", "Housing", 500m)
            ],
            [
                Expense("jan", 2025, 1, 2, "Food", "Living", -90m),
                Expense("feb", 2025, 2, 2, "Food", "Living", -110m),
                Expense("rent", 2025, 2, 2, "Rent", "Housing", -500m)
            ],
            Request(new YearMonth(2025, 2), ["Living", "Housing"]));
        BudgetAnalysisResult empty = BudgetAnalysisCalculator.Build(
            [],
            [],
            Request(new YearMonth(2025, 2), []));

        BudgetPerformanceEntry living = Assert.Single(result.YearToDate, entry => entry.Entity == "Living");
        Assert.Equal(200m, living.Budget);
        Assert.Equal(200m, living.Spent);
        Assert.Equal(100m, living.PercentUsed);
        Assert.Empty(empty.Groups);
        Assert.Equal(BudgetEmptyReason.NoGroupsSelected, empty.EmptyReason);
    }

    [Fact]
    public void BudgetBuild_KeepsAZeroValuedSelectedGroupWhenThereAreNoRows()
    {
        BudgetAnalysisResult result = BudgetAnalysisCalculator.Build(
            [],
            [],
            Request(new YearMonth(2025, 2), ["Living"]));

        Assert.Null(result.EmptyReason);
        Assert.Equal(0m, Assert.Single(result.Groups).Budget);
    }

    [Fact]
    public void FinancialIndependenceSourceBuild_SelectsAccountsAndFillsMissingMonths()
    {
        FinancialIndependenceSourceAnalysis result = FinancialIndependenceSourceAnalysisCalculator.Build(
            [
                new AccountBalance("brokerage", "Brokerage", "Investing", 250_000m, AccountClass.Asset),
                new AccountBalance("checking", "Checking", "Cash", 4_000m, AccountClass.Asset),
                new AccountBalance("loan", "Loan", "Debt", -5_000m, AccountClass.Liability)
            ],
            [
                Expense("apr", 2025, 4, 3, "Food", "Living", -100m),
                Expense("may", 2025, 5, 4, "Food", "Living", -200m),
                Expense("refund", 2025, 5, 7, "Food", "Living", 20m)
            ],
            new FinancialIndependenceSourceFilters(
                ["Brokerage", "Checking"],
                3,
                SpendingAdjustments.Default(1_000m)));

        Assert.Equal(254_000m, result.PortfolioValue);
        Assert.Equal(new YearMonth(2025, 3), result.StartMonth);
        Assert.Equal(new YearMonth(2025, 5), result.EndMonth);
        Assert.Equal([0m, 100m, 180m], result.MonthlySpending.Select(entry => entry.Spending));
        Assert.Equal(1_120m, result.AnnualSpending);
    }

    [Fact]
    public void FinancialIndependenceSourceBuild_AppliesSourceAdjustmentsAndDefaultsScenario()
    {
        FinanceSettings settings = Settings();
        SpendingAdjustments adjustments = SpendingAdjustments.Default(100m) with
        {
            ExcludedGroups = ["Travel"],
            IncludedDescriptions = ["market"],
            ExcludeLargeExpenses = true
        };
        FinancialIndependenceSourceAnalysis source = FinancialIndependenceSourceAnalysisCalculator.Build(
            [
                new AccountBalance("one", "Investing", "Investing", 100_000m, AccountClass.Asset),
                new AccountBalance("two", "Cash", "Cash", 1_000m, AccountClass.Asset)
            ],
            [
                Expense("market", 2025, 6, 1, "Food", "Living", -100m, "Market"),
                Expense("large", 2025, 6, 1, "Food", "Living", -101m, "Market"),
                Expense("travel", 2025, 6, 1, "Flight", "Travel", -20m, "Market")
            ],
            new FinancialIndependenceSourceFilters(["Investing"], 1, adjustments));
        FinancialIndependenceScenario scenario = FinancialIndependenceSourceAnalysisCalculator.DefaultScenario(source, settings.FinancialIndependence);

        Assert.Equal(100m, source.AnnualSpending / 12m);
        Assert.Equal(100_000m, scenario.Assets);
        Assert.Equal(7m, scenario.ExpectedReturnRate);
        Assert.Equal(4m, scenario.WithdrawalRate);
        Assert.Equal(5, scenario.ProjectionYears);
    }

    private static BudgetRequest Request(
        YearMonth month,
        IReadOnlyList<string> groups,
        DateOnly? throughDate = null,
        SpendingAdjustments? adjustments = null)
        => new(
            month,
            groups,
            adjustments ?? SpendingAdjustments.Default(1_000m),
            2,
            throughDate ?? month.End);

    private static BudgetEntry Budget(int year, int month, string category, string group, decimal amount)
        => new(new YearMonth(year, month), category, group, TransactionKind.Expense, amount, false);

    private static FinancialTransaction Expense(
        string id,
        int year,
        int month,
        int day,
        string category,
        string group,
        decimal amount,
        string? description = null)
        => new(id, new DateOnly(year, month, day), category, group, "Checking", description ?? id, amount, TransactionKind.Expense);

    private static FinanceSettings Settings()
        => new(
            new LookbackSettings([1, 3, 6, 12], 3),
            new ThresholdSettings(100m, 1_000m, 10m, 1),
            new IncomeSavingsSettings("regular", 20m, [], []),
            [new TransactionSetDefinition("all", "All", [], [], [], [], [], [], [])],
            [new FilterSetDefinition("spending", ["all"], "all")],
            new SubscriptionSettings([], 80, 45, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 5, ["invest"], []),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal));
}
