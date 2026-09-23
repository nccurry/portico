using Portico.Finance;

namespace Portico.Finance.Tests;

public sealed class SpendingAnalysisTests
{
    [Fact]
    public void Build_AlignsPreviousPeriodAndLastYearComparisonMonths()
    {
        FinancialTransaction[] rows =
        [
            Expense("last-year-april", 2024, 4, "Food", "Living", "Market", -40m),
            Expense("last-year-may", 2024, 5, "Food", "Living", "Market", -60m),
            Expense("previous-february", 2025, 2, "Food", "Living", "Market", -20m),
            Expense("previous-march", 2025, 3, "Food", "Living", "Market", -30m),
            Expense("current-april", 2025, 4, "Food", "Living", "Market", -80m),
            Expense("current-may", 2025, 5, "Food", "Living", "Market", -120m)
        ];

        SpendingAnalysisResult previous = Analyze(rows, 2, SpendingComparison.PreviousPeriod);
        SpendingAnalysisResult lastYear = Analyze(rows, 2, SpendingComparison.LastYear);

        Assert.Equal([new YearMonth(2025, 4), new YearMonth(2025, 5)], previous.Period.CurrentMonths);
        Assert.Equal([new YearMonth(2025, 2), new YearMonth(2025, 3)], previous.Period.ComparisonMonths);
        Assert.Equal(50m, previous.Summary.ComparisonSpending);
        Assert.Equal([new YearMonth(2024, 4), new YearMonth(2024, 5)], lastYear.Period.ComparisonMonths);
        Assert.Equal(100m, lastYear.Summary.ComparisonSpending);

        IReadOnlyList<(YearMonth CurrentMonth, YearMonth ComparisonMonth, decimal Current, decimal Comparison)> history =
            SpendingAnalysisCalculator.EntityHistory(lastYear, SpendingBreakdown.Category, "Food");
        Assert.Equal((new YearMonth(2025, 4), new YearMonth(2024, 4), 80m, 40m), history[0]);
        Assert.Equal((new YearMonth(2025, 5), new YearMonth(2024, 5), 120m, 60m), history[1]);
    }

    [Fact]
    public void Build_HandlesNoTransactionsAndOneTransactionAcrossEmptyMonths()
    {
        SpendingAnalysisResult empty = Analyze([], 3);
        SpendingAnalysisResult one = Analyze(
            [Expense("one", 2025, 6, "Food", "Living", "Market", -45m)],
            3);

        Assert.False(empty.Period.HasMonths);
        Assert.Empty(empty.CurrentLedger);
        Assert.Empty(empty.Overview);
        Assert.Equal(0m, empty.Summary.TotalSpending);

        Assert.Equal(
            [new YearMonth(2025, 4), new YearMonth(2025, 5), new YearMonth(2025, 6)],
            one.Period.CurrentMonths);
        Assert.Equal(45m, one.Summary.TotalSpending);
        Assert.Equal(15m, one.Summary.AverageMonthlySpending);
        SpendingOverviewEntry food = Assert.Single(one.Overview);
        Assert.Equal([0m, 0m, 45m], food.MonthlyTrend);
        Assert.Equal(1, food.TransactionCount);
    }

    [Fact]
    public void Build_IgnoresIncomeWhenChoosingTheLatestSpendingMonth()
    {
        FinancialTransaction expense = Expense("food", 2025, 6, "Food", "Living", "Market", -45m);
        var income = new FinancialTransaction(
            "salary",
            new DateOnly(2025, 8, 15),
            "Income",
            "Income",
            "Checking",
            "Salary",
            1_000m,
            TransactionKind.Income);

        SpendingAnalysisResult analysis = Analyze([expense, income], 1);

        Assert.Equal([new YearMonth(2025, 6)], analysis.Period.CurrentMonths);
        Assert.Equal(45m, analysis.Summary.TotalSpending);
        Assert.Equal([new YearMonth(2025, 6)], SpendingAnalysisCalculator.CurrentMonths([expense, income], 1));
    }

    [Fact]
    public void Build_UsesSignedNetSpendingAndStableCategoryTies()
    {
        SpendingAnalysisResult analysis = Analyze(
            [
                Expense("food-charge", 2025, 6, "Food", "Living", "Market", -100m),
                Expense("food-refund", 2025, 6, "Food", "Living", "Refund", 25m),
                Expense("beta", 2025, 6, "Beta", "Living", "Beta", -20m),
                Expense("alpha", 2025, 6, "Alpha", "Living", "Alpha", -20m)
            ],
            1);

        Assert.Equal(115m, analysis.Summary.TotalSpending);
        Assert.Equal(["Food", "Alpha", "Beta"], analysis.Overview.Select(entry => entry.Entity));
        SpendingOverviewEntry food = analysis.Overview[0];
        Assert.Equal(75m, food.Spending);
        Assert.Equal(2, food.TransactionCount);
        Assert.Equal(65.22m, decimal.Round(food.SharePercent, 2));
    }

    [Fact]
    public void Build_AppliesExcludedGroupAndCategoryIndependently()
    {
        FinancialTransaction[] rows = AdjustmentRows();

        SpendingAnalysisResult group = Analyze(
            rows,
            1,
            adjustments: SpendingAdjustments.Default(1_000m) with { ExcludedGroups = ["Housing"] });
        SpendingAnalysisResult category = Analyze(
            rows,
            1,
            adjustments: SpendingAdjustments.Default(1_000m) with { ExcludedCategories = ["Food"] });

        SpendingLedgerEntry rent = Assert.Single(group.CurrentLedger, entry => entry.Transaction.Id == "rent");
        SpendingLedgerEntry grocery = Assert.Single(category.CurrentLedger, entry => entry.Transaction.Id == "grocery");
        Assert.False(rent.Included);
        Assert.Contains("Excluded group: Housing", rent.ExclusionReason, StringComparison.Ordinal);
        Assert.False(grocery.Included);
        Assert.Contains("Excluded category: Food", grocery.ExclusionReason, StringComparison.Ordinal);
        Assert.Equal(2_071m, group.Summary.TotalSpending);
        Assert.Equal(3_021m, category.Summary.TotalSpending);
    }

    [Fact]
    public void Build_AppliesIncludeAndExcludeTransactionTermsIndependentlyAndTogether()
    {
        FinancialTransaction[] rows = AdjustmentRows();

        SpendingAnalysisResult included = Analyze(
            rows,
            1,
            adjustments: SpendingAdjustments.Default(1_000m) with { IncludedDescriptions = ["coffee"] });
        SpendingAnalysisResult excluded = Analyze(
            rows,
            1,
            adjustments: SpendingAdjustments.Default(1_000m) with { ExcludedDescriptions = ["coffee"] });
        SpendingAnalysisResult both = Analyze(
            rows,
            1,
            adjustments: SpendingAdjustments.Default(1_000m) with
            {
                IncludedDescriptions = ["shop"],
                ExcludedDescriptions = ["coffee"]
            });

        Assert.Equal(20m, included.Summary.TotalSpending);
        Assert.Equal(3_051m, excluded.Summary.TotalSpending);
        Assert.Equal(50m, both.Summary.TotalSpending);
        SpendingLedgerEntry coffee = Assert.Single(both.CurrentLedger, entry => entry.Transaction.Id == "coffee");
        Assert.Contains("Excluded transaction like: coffee", coffee.ExclusionReason, StringComparison.Ordinal);
        Assert.DoesNotContain("Outside included groups/categories/transactions", coffee.ExclusionReason, StringComparison.Ordinal);
    }

    [Fact]
    public void Build_AppliesLargeExpenseLimitOnlyAboveItsBoundary()
    {
        SpendingAnalysisResult analysis = Analyze(
            AdjustmentRows(),
            1,
            adjustments: SpendingAdjustments.Default(1_000m) with { ExcludeLargeExpenses = true });

        SpendingLedgerEntry boundary = Assert.Single(analysis.CurrentLedger, entry => entry.Transaction.Id == "boundary");
        SpendingLedgerEntry over = Assert.Single(analysis.CurrentLedger, entry => entry.Transaction.Id == "over-limit");
        Assert.True(boundary.Included);
        Assert.False(over.Included);
        Assert.Contains("Expense over $1,000", over.ExclusionReason, StringComparison.Ordinal);
        Assert.Equal(2_070m, analysis.Summary.TotalSpending);
    }

    [Fact]
    public void Build_KeepsComparisonRowsWhenEveryCurrentRowIsExcluded()
    {
        SpendingAnalysisResult analysis = Analyze(
            [
                Expense("comparison", 2025, 5, "Food", "Living", "Market", -40m),
                Expense("current", 2025, 6, "Food", "Travel", "Flight", -100m)
            ],
            1,
            adjustments: SpendingAdjustments.Default(1_000m) with { ExcludedGroups = ["Travel"] });

        Assert.Equal(0m, analysis.Summary.TotalSpending);
        Assert.Equal(40m, analysis.Summary.ComparisonSpending);
        Assert.DoesNotContain(analysis.CurrentLedger, entry => entry.Included);
        SpendingOverviewEntry food = Assert.Single(analysis.Overview);
        Assert.Equal(0m, food.Spending);
        Assert.Equal(40m, food.ComparisonSpending);
    }

    [Fact]
    public void Build_RespectsNamedViewsAndMerchantAliases()
    {
        FinanceSettings settings = SpendingSettings() with
        {
            MerchantAliases = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
            {
                ["Whole Foods"] = ["WHOLE FOODS", "WFDS"]
            }
        };
        FinancialTransaction[] rows =
        [
            Expense("market-one", 2025, 6, "Food", "Living", "WHOLE FOODS 123", -30m),
            Expense("market-two", 2025, 6, "Food", "Living", "WFDS #12", -20m),
            Expense("rent", 2025, 6, "Rent", "Housing", "Rent", -900m)
        ];

        SpendingAnalysisResult living = SpendingAnalysisCalculator.Build(
            rows,
            settings,
            "living",
            1,
            SpendingComparison.PreviousPeriod,
            SpendingBreakdown.Category,
            SpendingAdjustments.Default(1_000m));

        Assert.Equal(50m, living.Summary.TotalSpending);
        SpendingLedgerEntry rent = Assert.Single(living.CurrentLedger, entry => entry.Transaction.Id == "rent");
        Assert.False(rent.Included);
        Assert.Contains("Outside configured set: Living", rent.ExclusionReason, StringComparison.Ordinal);
        (string Merchant, decimal Spending, decimal SharePercent, int Transactions, decimal AverageTransaction, DateOnly LastTransaction) merchant =
            Assert.Single(SpendingAnalysisCalculator.Merchants(living.CurrentLedger, settings.MerchantAliases));
        Assert.Equal("Whole Foods", merchant.Merchant);
        Assert.Equal(50m, merchant.Spending);
        Assert.Equal(2, merchant.Transactions);
        Assert.Equal(25m, merchant.AverageTransaction);
    }

    private static SpendingAnalysisResult Analyze(
        IEnumerable<FinancialTransaction> rows,
        int lookbackMonths,
        SpendingComparison comparison = SpendingComparison.PreviousPeriod,
        SpendingAdjustments? adjustments = null)
        => SpendingAnalysisCalculator.Build(
            rows,
            SpendingSettings(),
            "all",
            lookbackMonths,
            comparison,
            SpendingBreakdown.Category,
            adjustments ?? SpendingAdjustments.Default(1_000m));

    private static FinancialTransaction[] AdjustmentRows()
        =>
        [
            Expense("grocery", 2025, 6, "Food", "Living", "Market shop", -50m),
            Expense("rent", 2025, 6, "Rent", "Housing", "Rent", -1_000m),
            Expense("coffee", 2025, 6, "Dining", "Living", "Coffee shop", -20m),
            Expense("boundary", 2025, 6, "Flight", "Travel", "Boundary flight", -1_000m),
            Expense("over-limit", 2025, 6, "Flight", "Travel", "Long flight", -1_001m),
            Expense("transfer", 2025, 6, "Transfer", "Transfer", "Internal move", -500m)
        ];

    private static FinancialTransaction Expense(
        string id,
        int year,
        int month,
        string category,
        string group,
        string description,
        decimal amount)
        => new(id, new DateOnly(year, month, 15), category, group, "Checking", description, amount, TransactionKind.Expense);

    private static FinanceSettings SpendingSettings()
    {
        TransactionSetDefinition[] sets =
        [
            new TransactionSetDefinition("all", "All", [], [], [], [], [], [], []),
            new TransactionSetDefinition("living", "Living", ["Living"], [], [], [], [], [], [])
        ];
        return new FinanceSettings(
            new LookbackSettings([1, 2, 3, 6, 12, 24], 3),
            new ThresholdSettings(1_000m, 5_000m, 10m, 1),
            new IncomeSavingsSettings("regular", 20m, [], []),
            sets,
            [new FilterSetDefinition("spending", ["all", "living"], "all")],
            new SubscriptionSettings([], 80, 45, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 5, [], []),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal));
    }
}
