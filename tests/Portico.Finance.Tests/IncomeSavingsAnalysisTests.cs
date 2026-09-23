using Portico.Finance;

namespace Portico.Finance.Tests;

public sealed class IncomeSavingsAnalysisTests
{
    [Fact]
    public void Build_UsesMatchedPeriodsZeroFilledMonthsAndSignedRefunds()
    {
        FinancialTransaction[] rows =
        [
            new FinancialTransaction(
                "history",
                new DateOnly(2025, 2, 15),
                "Transfer",
                "Transfer",
                "Checking",
                "Internal move",
                -1m,
                TransactionKind.Transfer),
            Income("prior-income", 2025, 3, "Salary", "Income", "Salary", 900m),
            Expense("prior-expense", 2025, 3, "Food", "Living", "Market", -100m),
            Income("june-income", 2025, 6, "Salary", "Income", "Salary", 1_000m),
            Expense("june-expense", 2025, 6, "Food", "Living", "Market", -200m),
            Income("august-income", 2025, 8, "Salary", "Income", "Salary", 1_200m),
            Expense("august-charge", 2025, 8, "Food", "Living", "Market", -300m),
            Expense("august-refund", 2025, 8, "Food", "Living", "Refund", 50m)
        ];

        IncomeSavingsAnalysisResult result = IncomeSavingsAnalysisCalculator.Build(rows, 3, Adjustments());

        Assert.Equal(
            [new YearMonth(2025, 6), new YearMonth(2025, 7), new YearMonth(2025, 8)],
            result.Period.CurrentMonths);
        Assert.Equal(
            [new YearMonth(2025, 3), new YearMonth(2025, 4), new YearMonth(2025, 5)],
            result.Period.PreviousMonths);
        Assert.True(result.HasFullPreviousPeriod);
        Assert.Collection(
            result.CurrentMonthly,
            june =>
            {
                Assert.Equal(1_000m, june.Income);
                Assert.Equal(200m, june.NetExpenses);
                Assert.Equal(800m, june.Surplus);
                Assert.Equal(80m, june.SavingsRatePercent);
            },
            july =>
            {
                Assert.Equal(0m, july.Income);
                Assert.Equal(0m, july.NetExpenses);
                Assert.Equal(0m, july.Surplus);
                Assert.Null(july.SavingsRatePercent);
            },
            august =>
            {
                Assert.Equal(1_200m, august.Income);
                Assert.Equal(250m, august.NetExpenses);
                Assert.Equal(950m, august.Surplus);
                Assert.Equal(decimal.Round(950m / 1_200m * 100m, 10), decimal.Round(august.SavingsRatePercent!.Value, 10));
            });
        Assert.Equal(2_200m, result.CurrentSummary.Income);
        Assert.Equal(450m, result.CurrentSummary.NetExpenses);
        Assert.Equal(1_750m, result.CurrentSummary.Surplus);
        Assert.Equal(900m, result.PreviousSummary.Income);
        Assert.Equal(100m, result.PreviousSummary.NetExpenses);
    }

    [Fact]
    public void Build_HandlesEmptyInputWithoutInventingAMonth()
    {
        IncomeSavingsAnalysisResult result = IncomeSavingsAnalysisCalculator.Build([], 3, Adjustments());

        Assert.False(result.Period.HasMonths);
        Assert.Empty(result.CurrentLedger);
        Assert.Empty(result.CurrentMonthly);
        Assert.Equal(0m, result.CurrentSummary.Income);
        Assert.Null(result.CurrentSummary.SavingsRatePercent);
        Assert.False(result.HasFullPreviousPeriod);
    }

    [Fact]
    public void Build_AppliesCategoriesGroupsLimitsAndTransferExclusionsAtTheirBoundaries()
    {
        FinancialTransaction[] rows =
        [
            Income("salary", 2025, 6, "Salary", "Income", "Salary", 1_000m),
            Income("income-boundary", 2025, 6, "Bonus", "Income", "Bonus", 5_000m),
            Income("income-over", 2025, 6, "Bonus", "Income", "Bonus", 5_001m),
            Expense("food", 2025, 6, "Food", "Living", "Market", -40m),
            Expense("travel", 2025, 6, "Flight", "Travel", "Flight", -80m),
            Expense("expense-boundary", 2025, 6, "Rent", "Housing", "Rent", -1_000m),
            Expense("expense-over", 2025, 6, "Rent", "Housing", "Rent", -1_001m),
            Expense("transfer", 2025, 6, "Transfer", "Transfer", "Internal move", -300m)
        ];
        IncomeSavingsAdjustments adjustments = Adjustments() with
        {
            ExcludedIncomeCategories = ["Salary"],
            ExcludedExpenseGroups = ["Travel"],
            ExcludedExpenseCategories = ["Food"],
            ExcludeLargeIncome = true,
            IncomeLimit = 5_000m,
            ExcludeLargeExpenses = true,
            ExpenseLimit = 1_000m
        };

        IncomeSavingsAnalysisResult result = IncomeSavingsAnalysisCalculator.Build(rows, 1, adjustments);

        Assert.False(Entry(result, "salary").Included);
        Assert.Contains("Excluded income category: Salary", Entry(result, "salary").ExclusionReason, StringComparison.Ordinal);
        Assert.True(Entry(result, "income-boundary").Included);
        Assert.False(Entry(result, "income-over").Included);
        Assert.Contains("Income over $5,000", Entry(result, "income-over").ExclusionReason, StringComparison.Ordinal);
        Assert.False(Entry(result, "food").Included);
        Assert.Contains("Excluded expense category: Food", Entry(result, "food").ExclusionReason, StringComparison.Ordinal);
        Assert.False(Entry(result, "travel").Included);
        Assert.Contains("Excluded group: Travel", Entry(result, "travel").ExclusionReason, StringComparison.Ordinal);
        Assert.True(Entry(result, "expense-boundary").Included);
        Assert.False(Entry(result, "expense-over").Included);
        Assert.Contains("Expense over $1,000", Entry(result, "expense-over").ExclusionReason, StringComparison.Ordinal);
        Assert.False(Entry(result, "transfer").Included);
        Assert.Contains("Transfer group", Entry(result, "transfer").ExclusionReason, StringComparison.Ordinal);
        Assert.Equal(5_000m, result.CurrentSummary.Income);
        Assert.Equal(1_000m, result.CurrentSummary.NetExpenses);
    }

    [Fact]
    public void Build_AppliesDescriptionIncludeAndExcludeTermsIndependently()
    {
        FinancialTransaction[] rows =
        [
            Income("keep", 2025, 6, "Salary", "Income", "Keep salary", 1_000m),
            Expense("outside", 2025, 6, "Food", "Living", "Market", -100m),
            Expense("excluded", 2025, 6, "Food", "Living", "Keep ignore", -50m)
        ];
        IncomeSavingsAdjustments adjustments = Adjustments() with
        {
            IncludedDescriptions = ["keep"],
            ExcludedDescriptions = ["ignore"]
        };

        IncomeSavingsAnalysisResult result = IncomeSavingsAnalysisCalculator.Build(rows, 1, adjustments);

        Assert.True(Entry(result, "keep").Included);
        Assert.False(Entry(result, "outside").Included);
        Assert.Contains("Outside included groups/categories/transactions", Entry(result, "outside").ExclusionReason, StringComparison.Ordinal);
        Assert.False(Entry(result, "excluded").Included);
        Assert.Contains("Excluded transaction like: ignore", Entry(result, "excluded").ExclusionReason, StringComparison.Ordinal);
        Assert.Equal(1_000m, result.CurrentSummary.Income);
        Assert.Equal(0m, result.CurrentSummary.NetExpenses);
    }

    [Fact]
    public void Build_LeavesPreviousComparisonAbsentWhenSourceHistoryStartsTooLate()
    {
        FinancialTransaction[] rows =
        [
            Income("april", 2025, 4, "Salary", "Income", "Salary", 1_000m),
            Income("june", 2025, 6, "Salary", "Income", "Salary", 1_000m)
        ];

        IncomeSavingsAnalysisResult result = IncomeSavingsAnalysisCalculator.Build(rows, 2, Adjustments());

        Assert.Equal([new YearMonth(2025, 5), new YearMonth(2025, 6)], result.Period.CurrentMonths);
        Assert.Equal([new YearMonth(2025, 3), new YearMonth(2025, 4)], result.Period.PreviousMonths);
        Assert.False(result.HasFullPreviousPeriod);
        Assert.Equal(1_000m, result.PreviousSummary.Income);
    }

    [Fact]
    public void Default_UsesConfiguredRegularExclusionsAndKeepsActualUnadjusted()
    {
        FinanceSettings settings = Settings();

        IncomeSavingsAdjustments regular = IncomeSavingsAdjustments.Default(settings, regular: true);
        IncomeSavingsAdjustments actual = IncomeSavingsAdjustments.Default(settings, regular: false);

        Assert.Equal(["Bonus"], regular.ExcludedIncomeCategories);
        Assert.Equal(["Travel"], regular.ExcludedExpenseGroups);
        Assert.Equal(["Bonus"], regular.ExcludedExpenseCategories);
        Assert.Empty(actual.ExcludedIncomeCategories);
        Assert.Empty(actual.ExcludedExpenseGroups);
        Assert.False(actual.IsModifiedFrom(actual));
        Assert.False(regular.IsModifiedFrom(regular));
        Assert.False((regular with { TargetRate = 30m }).IsModifiedFrom(regular));
        Assert.True((regular with { ExcludeLargeIncome = true }).IsModifiedFrom(regular));
    }

    private static IncomeSavingsLedgerEntry Entry(IncomeSavingsAnalysisResult result, string id)
        => Assert.Single(result.CurrentLedger, entry => entry.Transaction.Id == id);

    private static IncomeSavingsAdjustments Adjustments()
        => new([], [], [], [], [], false, 5_000m, false, 1_000m, 20m);

    private static FinancialTransaction Income(
        string id,
        int year,
        int month,
        string category,
        string group,
        string description,
        decimal amount)
        => new(id, new DateOnly(year, month, 15), category, group, "Checking", description, amount, TransactionKind.Income);

    private static FinancialTransaction Expense(
        string id,
        int year,
        int month,
        string category,
        string group,
        string description,
        decimal amount)
        => new(id, new DateOnly(year, month, 15), category, group, "Checking", description, amount, TransactionKind.Expense);

    private static FinanceSettings Settings()
        => new(
            new LookbackSettings([3, 6, 12, 24], 12),
            new ThresholdSettings(3_000m, 20_000m, 10m, 1),
            new IncomeSavingsSettings("regular", 20m, ["Bonus"], ["Travel"]),
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
