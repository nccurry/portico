using Portico.Finance;

namespace Portico.Finance.Tests;

public sealed class YearOverYearAnalysisTests
{
    [Fact]
    public void Build_AlignsCalendarYearsThroughTheLatestSourceMonthAndZeroFillsGaps()
    {
        FinancialTransaction[] rows =
        [
            Income("coverage-start", 2024, 2, 1_000m),
            Expense("prior-food", 2024, 3, "Food", "Living", -20m),
            Expense("current-food", 2025, 3, "Food", "Living", -50m),
            Income("coverage-end", 2025, 5, 1_000m)
        ];

        YearOverYearComparison comparison = Assert.IsType<YearOverYearComparison>(
            YearOverYearAnalysisCalculator.Build(rows, Settings(), "all", YearOverYearDimension.Category, "Food"));

        Assert.Equal(5, comparison.Summary.ThroughMonth);
        Assert.Equal(2025, comparison.Summary.CurrentYear);
        Assert.Equal(50m, comparison.Summary.CurrentTotal);
        Assert.Equal(2024, comparison.Summary.PreviousYear);
        Assert.Equal(20m, comparison.Summary.PreviousTotal);
        Assert.Equal(30m, comparison.Summary.Change);
        Assert.Equal(150m, comparison.Summary.ChangePercent);
        Assert.Equal(16, comparison.History.Count);
        Assert.Equal(0m, comparison.History.Single(point => point.Year == 2024 && point.Month == 4).Spending);
        Assert.Equal(50m, comparison.History.Single(point => point.Year == 2025 && point.Month == 3).Spending);
        Assert.Equal([2025, 2024], comparison.Totals.Select(total => total.Year).OrderDescending());
        Assert.Equal(20m, comparison.Totals.Single(total => total.Year == 2024).SpendingThroughMonth);
    }

    [Fact]
    public void Build_ReturnsNullForEmptyOrUnmatchedInput()
    {
        Assert.Null(YearOverYearAnalysisCalculator.Build([], Settings(), "all", YearOverYearDimension.Category, "Food"));

        FinancialTransaction[] rows = [Expense("rent", 2025, 6, "Rent", "Housing", -900m)];

        Assert.Null(YearOverYearAnalysisCalculator.Build(rows, Settings(), "all", YearOverYearDimension.Category, "Food"));
    }

    [Fact]
    public void Build_UsesSignedRefundsExcludesTransfersAndKeepsZeroPriorTotalsUnavailable()
    {
        FinancialTransaction[] rows =
        [
            Expense("prior-transfer", 2024, 4, "Transfer", "Transfer", -300m),
            Expense("current-charge", 2025, 4, "Food", "Living", -100m),
            Expense("current-refund", 2025, 4, "Food", "Living", 25m),
            Expense("current-transfer", 2025, 4, "Transfer", "Transfer", -400m)
        ];

        YearOverYearComparison comparison = Assert.IsType<YearOverYearComparison>(
            YearOverYearAnalysisCalculator.Build(rows, Settings(), "all", YearOverYearDimension.Category, "Food"));

        Assert.Equal(75m, comparison.Summary.CurrentTotal);
        Assert.Null(comparison.Summary.PreviousTotal);
        Assert.Null(comparison.Summary.Change);
        Assert.Null(comparison.Summary.ChangePercent);
        Assert.DoesNotContain(comparison.Transactions, transaction => transaction.Group == "Transfer");
        Assert.Equal(2, comparison.Transactions.Count);
    }

    [Fact]
    public void PresetCategories_RanksTheSelectedSetAndUsesStableTies()
    {
        FinancialTransaction[] rows =
        [
            Expense("food", 2025, 6, "Food", "Living", -50m),
            Expense("alpha", 2025, 6, "Alpha", "Living", -20m),
            Expense("beta", 2025, 6, "Beta", "Living", -20m),
            Expense("rent", 2025, 6, "Rent", "Housing", -1_000m),
            Expense("transfer", 2025, 6, "Transfer", "Transfer", -900m)
        ];

        Assert.Equal(
            ["Food", "Alpha", "Beta"],
            YearOverYearAnalysisCalculator.PresetCategories(rows, Settings(), "living"));
        Assert.Equal(
            ["Rent", "Food", "Alpha", "Beta"],
            YearOverYearAnalysisCalculator.PresetCategories(rows, Settings(), "all"));
    }

    [Fact]
    public void Entities_ReturnsRawSingleCategoryAndGroupChoicesInSourceOrder()
    {
        FinancialTransaction[] rows =
        [
            Expense("food", 2025, 6, "Food", "Living", -50m),
            Expense("rent", 2025, 6, "Rent", "Housing", -1_000m),
            Expense("transfer", 2025, 6, "Transfer", "Transfer", -900m),
            Income("income", 2025, 6, 1_000m)
        ];

        Assert.Equal(["Food", "Rent", "Transfer"], YearOverYearAnalysisCalculator.Entities(rows, YearOverYearDimension.Category));
        Assert.Equal(["Housing", "Living", "Transfer"], YearOverYearAnalysisCalculator.Entities(rows, YearOverYearDimension.Group));
    }

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
            new TransactionSetDefinition("all", [], [], [], [], [], [], []),
            new TransactionSetDefinition("living", ["Living"], [], [], [], [], [], [])
        ];
        return new FinanceSettings(
            new ThresholdSettings(3_000m, 20_000m, 10m, 1),
            new IncomeSavingsSettings(20m, [], []),
            sets,
            new SubscriptionSettings([], 80, 45, []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 5, [], []),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal));
    }
}
