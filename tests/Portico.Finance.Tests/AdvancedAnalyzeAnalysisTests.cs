using Portico.Finance;

namespace Portico.Finance.Tests;

public sealed class AdvancedAnalyzeAnalysisTests
{
    [Fact]
    public void MerchantAnalysis_BuildsMatchedPeriodsAndSelectedMerchantDetail()
    {
        FinancialTransaction[] rows =
        [
            Expense("previous-one", 2025, 2, 15, "Coffee", "Living", "COFFEE SHOP 101", -40m),
            Expense("previous-two", 2025, 3, 15, "Coffee", "Living", "COFFEE SHOP 102", -60m),
            Expense("current-one", 2025, 4, 15, "Coffee", "Living", "COFFEE SHOP 103", -100m),
            Expense("current-refund", 2025, 5, 15, "Coffee", "Living", "COFFEE SHOP REFUND", 20m),
            Expense("other", 2025, 5, 20, "Food", "Living", "MARKET 998", -30m)
        ];

        MerchantAnalysisResult analysis = MerchantAnalysisCalculator.Build(
            rows,
            Settings(),
            "all",
            2,
            SpendingComparison.PreviousPeriod,
            SpendingAdjustments.Default(1_000m));

        Assert.Equal([new YearMonth(2025, 4), new YearMonth(2025, 5)], analysis.Period.CurrentMonths);
        MerchantOverviewEntry coffee = Assert.Single(analysis.Overview, entry => entry.Merchant == "COFFEE SHOP");
        Assert.Equal(80m, coffee.Spending);
        Assert.Equal(100m, coffee.ComparisonSpending);
        Assert.Equal(-20m, coffee.Change);
        Assert.Equal(2, coffee.TransactionCount);
        Assert.Equal("Coffee", coffee.PrimaryCategory);
        Assert.Equal(110m, analysis.Summary.TotalSpending);

        IReadOnlyList<MerchantHistoryEntry> history = MerchantAnalysisCalculator.History(
            analysis,
            "COFFEE SHOP",
            Settings().MerchantAliases);
        Assert.Equal((100m, 40m), (history[0].CurrentSpending, history[0].ComparisonSpending));
        Assert.Equal((-20m, 60m), (history[1].CurrentSpending, history[1].ComparisonSpending));

        MerchantDetailBreakdownEntry category = Assert.Single(MerchantAnalysisCalculator.Breakdown(
            analysis.CurrentLedger,
            "COFFEE SHOP",
            "Category",
            Settings().MerchantAliases));
        Assert.Equal(("Coffee", 80m, 2), (category.Entity, category.Spending, category.Transactions));
    }

    [Fact]
    public void MerchantAnalysis_UsesAliasRulesAndSharedSpendingExclusions()
    {
        FinanceSettings settings = Settings() with
        {
            MerchantAliases = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
            {
                ["Whole Foods"] = ["WHOLE FOODS", "WFDS"]
            }
        };
        FinancialTransaction[] rows =
        [
            Expense("one", 2025, 6, 1, "Food", "Living", "WHOLE FOODS #123", -30m),
            Expense("two", 2025, 6, 2, "Food", "Living", "WFDS 456", -20m),
            Expense("rent", 2025, 6, 3, "Rent", "Housing", "RENT", -900m)
        ];

        MerchantAnalysisResult analysis = MerchantAnalysisCalculator.Build(
            rows,
            settings,
            "all",
            1,
            SpendingComparison.PreviousPeriod,
            SpendingAdjustments.Default(1_000m) with { ExcludedGroups = ["Housing"] });

        MerchantOverviewEntry wholeFoods = Assert.Single(analysis.Overview);
        Assert.Equal("WHOLE FOODS", wholeFoods.Merchant);
        Assert.Equal(50m, wholeFoods.Spending);
        Assert.Contains(analysis.CurrentLedger, entry => entry.Transaction.Id == "rent" && !entry.Included);
    }

    [Fact]
    public void MerchantAnalysis_ReturnsNoOverviewWhenEveryCurrentExpenseIsExcluded()
    {
        FinancialTransaction[] rows =
        [
            Expense("food", 2025, 6, 1, "Food", "Living", "MARKET", -50m),
            Expense("travel", 2025, 6, 2, "Flight", "Travel", "AIRLINE", -300m)
        ];

        MerchantAnalysisResult analysis = MerchantAnalysisCalculator.Build(
            rows,
            Settings(),
            "all",
            1,
            SpendingComparison.PreviousPeriod,
            SpendingAdjustments.Default(1_000m) with { ExcludedGroups = ["Living", "Travel"] });

        Assert.Empty(analysis.Overview);
        Assert.Equal(0m, analysis.Summary.TotalSpending);
        Assert.All(analysis.CurrentLedger, entry => Assert.False(entry.Included));
    }

    [Fact]
    public void MerchantAnalysis_DetailKeepsRawDescriptionsAndFiltersSelectedMonth()
    {
        FinancialTransaction[] rows =
        [
            Expense("april", 2025, 4, 1, "Coffee", "Living", "COFFEE SHOP 101", -10m),
            Expense("may-one", 2025, 5, 1, "Coffee", "Living", "COFFEE SHOP 101", -20m),
            Expense("may-two", 2025, 5, 2, "Coffee", "Living", "COFFEE SHOP 102", -30m),
            Expense("other", 2025, 5, 3, "Food", "Living", "MARKET 10", -100m)
        ];
        MerchantAnalysisResult analysis = MerchantAnalysisCalculator.Build(
            rows, Settings(), "all", 2, SpendingComparison.PreviousPeriod, SpendingAdjustments.Default(1_000m));

        IReadOnlyList<MerchantDescriptionEntry> descriptions = MerchantAnalysisCalculator.Descriptions(
            analysis.CurrentLedger, "COFFEE SHOP", EmptyAliases());
        IReadOnlyList<SpendingLedgerEntry> may = MerchantAnalysisCalculator.Transactions(
            analysis.CurrentLedger, "COFFEE SHOP", new YearMonth(2025, 5), EmptyAliases());
        IReadOnlyList<MerchantDetailBreakdownEntry> accounts = MerchantAnalysisCalculator.Breakdown(
            analysis.CurrentLedger, "COFFEE SHOP", "Account", EmptyAliases());
        IReadOnlyList<MerchantDetailBreakdownEntry> groups = MerchantAnalysisCalculator.Breakdown(
            analysis.CurrentLedger, "COFFEE SHOP", "Group", EmptyAliases());

        Assert.Equal(["COFFEE SHOP 101", "COFFEE SHOP 102"], descriptions.Select(entry => entry.Description));
        Assert.Equal((30m, 2, new DateOnly(2025, 5, 1)),
            (descriptions[0].Spending, descriptions[0].Transactions, descriptions[0].LastTransaction));
        Assert.Equal(["may-two", "may-one"], may.Select(entry => entry.Transaction.Id));
        Assert.Equal(("Checking", 60m, 3),
            (Assert.Single(accounts).Entity, accounts[0].Spending, accounts[0].Transactions));
        Assert.Equal("Living", Assert.Single(groups).Entity);
        Assert.Throws<ArgumentException>(() => MerchantAnalysisCalculator.Breakdown(
            analysis.CurrentLedger, "COFFEE SHOP", "Merchant", EmptyAliases()));
    }

    [Fact]
    public void TransactionExplorer_SeparatesQuickFocusModesAndUsesPreThresholdMerchantStatistics()
    {
        FinancialTransaction[] rows =
        [
            Expense("coffee-one", 2025, 6, 1, "Coffee", "Living", "COFFEE SHOP 100", -10m),
            Expense("coffee-two", 2025, 6, 5, "Coffee", "Living", "COFFEE SHOP 101", -10m),
            Expense("coffee-unusual", 2025, 6, 10, "Coffee", "Living", "COFFEE SHOP 102", -100m),
            Expense("refund", 2025, 6, 12, "Coffee", "Living", "COFFEE SHOP REFUND", 10m),
            Expense("one-off", 2025, 6, 20, "Food", "Living", "MARKET 123", -25m),
            Income("income-reversal", 2025, 6, 25, "Salary", "Income", "PAYROLL REVERSAL", -500m)
        ];

        TransactionExplorerAnalysisResult unusual = TransactionExplorerAnalysisCalculator.Build(
            rows,
            EmptyAliases(),
            TransactionExplorerFilters.Default with { Focus = TransactionExplorerFocus.UnusualAmounts });
        TransactionExplorerAnalysisResult oneOff = TransactionExplorerAnalysisCalculator.Build(
            rows,
            EmptyAliases(),
            TransactionExplorerFilters.Default with { Focus = TransactionExplorerFocus.OneOffMerchants });
        TransactionExplorerAnalysisResult reversals = TransactionExplorerAnalysisCalculator.Build(
            rows,
            EmptyAliases(),
            TransactionExplorerFilters.Default with { Focus = TransactionExplorerFocus.RefundsReversals });

        Assert.Contains(unusual.Results, entry => entry.Transaction.Id == "coffee-unusual");
        Assert.Contains(oneOff.Results, entry => entry.Transaction.Id == "one-off");
        Assert.Equal(["income-reversal", "refund"], reversals.Results.Select(entry => entry.Transaction.Id).Order());
    }

    [Fact]
    public void TransactionExplorer_AppliesAllFiltersAndBuildsMagnitudeBreakdown()
    {
        FinancialTransaction[] rows =
        [
            Expense("food", 2025, 6, 1, "Food", "Living", "MARKET", -50m),
            Expense("travel", 2025, 6, 2, "Flight", "Travel", "AIRLINE", -300m),
            Income("income", 2025, 6, 3, "Salary", "Income", "PAYROLL", 1_000m),
            new FinancialTransaction("transfer", new DateOnly(2025, 6, 4), "Transfer", "Transfer", "Savings", "MOVE", -200m, TransactionKind.Transfer)
        ];
        TransactionExplorerFilters filters = TransactionExplorerFilters.Default with
        {
            Type = TransactionExplorerType.Expenses,
            Groups = ["Travel"],
            Search = "air",
            MinimumMagnitude = 100m,
            LargestCount = 5,
            Breakdown = TransactionExplorerBreakdown.Category
        };

        TransactionExplorerAnalysisResult analysis = TransactionExplorerAnalysisCalculator.Build(rows, EmptyAliases(), filters);

        TransactionExplorerEntry result = Assert.Single(analysis.Results);
        Assert.Equal("travel", result.Transaction.Id);
        TransactionExplorerBreakdownEntry breakdown = Assert.Single(analysis.Breakdown);
        Assert.Equal(("Flight", 1, 300m, 100m), (breakdown.Entity, breakdown.Transactions, breakdown.Magnitude, breakdown.SharePercent));
        Assert.Equal((1, 0m, 300m, -300m), (
            analysis.Summary.TransactionCount,
            analysis.Summary.Inflow,
            analysis.Summary.Outflow,
            analysis.Summary.NetAmount));

        TransactionExplorerAnalysisResult noResults = TransactionExplorerAnalysisCalculator.Build(
            rows,
            EmptyAliases(),
            filters with { MinimumMagnitude = 500m, MaximumMagnitude = 100m });
        Assert.Empty(noResults.Results);
    }

    [Fact]
    public void SubscriptionAnalysis_BuildsKnownInventoryCandidateHistoryAndPriceChange()
    {
        FinancialTransaction[] rows =
        [
            Expense("video-jan", 2025, 1, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Expense("video-feb", 2025, 2, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Expense("video-mar", 2025, 3, 2, "Streaming", "Fun", "VIDEO SERVICE", -12m),
            Expense("cloud-jan", 2025, 1, 2, "Software", "Fun", "CLOUD BACKUP", -5m),
            Expense("cloud-feb", 2025, 2, 2, "Software", "Fun", "CLOUD BACKUP", -5m),
            Expense("cloud-mar", 2025, 3, 2, "Software", "Fun", "CLOUD BACKUP", -5m),
            Income("latest", 2025, 5, 1, "Salary", "Income", "PAYROLL", 1_000m)
        ];

        SubscriptionAnalysisResult analysis = SubscriptionAnalysisCalculator.Build(
            rows,
            Settings().Subscriptions,
            EmptyAliases(),
            ["Streaming"],
            [],
            80);

        SubscriptionInventoryEntry video = Assert.Single(analysis.Active);
        Assert.Equal(("VIDEO SERVICE", SubscriptionCadence.Monthly, 12m, 2m), (video.Merchant, video.Cadence, video.MonthlyRunRate, video.PriceChange));
        Assert.Equal(SubscriptionOrigin.Categorized, video.Source);
        Assert.Equal(SubscriptionStatus.Active, video.Status);
        Assert.Equal(SubscriptionBundleKind.SingleStream, video.BundleType);
        Assert.Equal(new DateOnly(2025, 3, 2), video.PriceChangeDate);
        SubscriptionInventoryEntry cloud = Assert.Single(analysis.Candidates);
        Assert.Equal(("CLOUD BACKUP", SubscriptionCadence.Monthly), (cloud.Merchant, cloud.Cadence));
        Assert.Equal(SubscriptionOrigin.Detected, cloud.Source);
        Assert.Equal((1, 12m, 32m), (analysis.Summary.ActiveCount, analysis.Summary.MonthlyRunRate, analysis.Summary.TrailingTwelveMonthSpend));
        Assert.Equal([new YearMonth(2025, 1), new YearMonth(2025, 2), new YearMonth(2025, 3), new YearMonth(2025, 4), new YearMonth(2025, 5)], analysis.History.Select(entry => entry.Month));
        Assert.Equal((12m, 10.67m, 1), (analysis.History[2].ActualSpend, decimal.Round(analysis.History[2].RollingAverage, 2), analysis.History[2].ActiveMerchants));
        Assert.Equal(3, SubscriptionAnalysisCalculator.ChargesFor(analysis, "VIDEO SERVICE", candidate: false).Count);
    }

    [Fact]
    public void SubscriptionAnalysis_MarksAStreamInactiveOnlyAfterItsCadenceWindow()
    {
        FinancialTransaction[] rows =
        [
            Expense("jan", 2024, 1, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Expense("feb", 2024, 2, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Expense("mar", 2024, 3, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Income("latest", 2024, 8, 1, "Salary", "Income", "PAYROLL", 1_000m)
        ];

        SubscriptionAnalysisResult analysis = SubscriptionAnalysisCalculator.Build(
            rows,
            Settings().Subscriptions,
            EmptyAliases(),
            ["Streaming"],
            [],
            80);

        SubscriptionInventoryEntry inactive = Assert.Single(analysis.Inactive);
        Assert.Equal(SubscriptionStatus.Inactive, inactive.Status);
        Assert.Empty(analysis.Active);
        Assert.Contains(analysis.Lifecycles, lifecycle => lifecycle.DisplayEnd == new DateOnly(2024, 4, 30));
    }

    [Fact]
    public void SubscriptionAnalysis_LeavesEveryInventorySectionEmptyWhenNoExpenseIsEligible()
    {
        FinancialTransaction[] rows =
        [
            Expense("one", 2025, 1, 1, "Food", "Living", "MARKET", -10m),
            Expense("two", 2025, 2, 1, "Food", "Living", "MARKET", -10m),
            Expense("three", 2025, 3, 1, "Food", "Living", "MARKET", -10m)
        ];

        SubscriptionAnalysisResult analysis = SubscriptionAnalysisCalculator.Build(
            rows,
            Settings().Subscriptions,
            EmptyAliases(),
            [],
            ["Food"],
            70);

        Assert.Empty(analysis.Inventory);
        Assert.Empty(analysis.Active);
        Assert.Empty(analysis.Candidates);
        Assert.Empty(analysis.Inactive);
        Assert.Empty(analysis.History);
    }

    [Fact]
    public void SubscriptionAnalysis_EmptyInputReturnsNoDateOrPendingEstimate()
    {
        SubscriptionAnalysisResult result = SubscriptionAnalysisCalculator.Build(
            [], Settings().Subscriptions, EmptyAliases(), ["Streaming"], [], 80);

        Assert.Null(result.LatestDataDate);
        Assert.Empty(result.Inventory);
        Assert.Empty(result.Lifecycles);
        Assert.Equal(0, result.Summary.ActiveCount);
        Assert.Equal(0, result.Summary.PendingEstimateCount);
        Assert.Null(result.Summary.AnnualChangePercent);
        Assert.Throws<ArgumentOutOfRangeException>(() => SubscriptionAnalysisCalculator.Build(
            [], Settings().Subscriptions, EmptyAliases(), [], [], 69));
        Assert.Throws<ArgumentOutOfRangeException>(() => SubscriptionAnalysisCalculator.Build(
            [], Settings().Subscriptions, EmptyAliases(), [], [], 101));
    }

    [Fact]
    public void SubscriptionAnalysis_PendingCadenceHasNoRunRateUntilMoreDatesExist()
    {
        FinancialTransaction[] rows =
        [
            Expense("jan", 2025, 1, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Expense("feb", 2025, 2, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m)
        ];

        SubscriptionAnalysisResult result = SubscriptionAnalysisCalculator.Build(
            rows, Settings().Subscriptions, EmptyAliases(), ["Streaming"], [], 80);

        SubscriptionInventoryEntry pending = Assert.Single(result.Active);
        Assert.Equal(SubscriptionCadence.Pending, pending.Cadence);
        Assert.Equal(SubscriptionBundleKind.Pending, pending.BundleType);
        Assert.Equal(60, pending.Confidence);
        Assert.Null(pending.MonthlyRunRate);
        Assert.Null(pending.NextExpectedDate);
        Assert.Equal(1, result.Summary.PendingEstimateCount);
        Assert.Equal(0m, result.Summary.MonthlyRunRate);
    }

    [Fact]
    public void SubscriptionAnalysis_ReactivationStartsANewEpisode()
    {
        FinancialTransaction[] rows =
        [
            Expense("jan", 2024, 1, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Expense("feb", 2024, 2, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Expense("mar", 2024, 3, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Expense("sep", 2024, 9, 1, "Streaming", "Fun", "VIDEO SERVICE", -12m),
            Expense("oct", 2024, 10, 1, "Streaming", "Fun", "VIDEO SERVICE", -12m),
            Expense("nov", 2024, 11, 1, "Streaming", "Fun", "VIDEO SERVICE", -12m)
        ];

        SubscriptionAnalysisResult result = SubscriptionAnalysisCalculator.Build(
            rows, Settings().Subscriptions, EmptyAliases(), ["Streaming"], [], 80);

        Assert.Equal(SubscriptionCadence.Monthly, Assert.Single(result.Active).Cadence);
        Assert.Equal([1, 2], result.Lifecycles.Select(row => row.Episode).Order());
        Assert.Equal(SubscriptionStatus.Inactive, Assert.Single(result.Lifecycles, row => row.Episode == 1).Status);
        Assert.True(Assert.Single(result.Lifecycles, row => row.Episode == 2).IsCurrent);
        Assert.Equal(new DateOnly(2024, 9, 1), Assert.Single(result.Lifecycles, row => row.Episode == 2).EpisodeStart);
    }

    [Fact]
    public void SubscriptionAnalysis_MerchantBundleUsesObservedSpendingRunRate()
    {
        FinancialTransaction[] rows =
        [
            Expense("jan-one", 2025, 1, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Expense("jan-two", 2025, 1, 2, "Streaming", "Fun", "VIDEO SERVICE", -20m),
            Expense("feb-one", 2025, 2, 1, "Streaming", "Fun", "VIDEO SERVICE", -10m),
            Expense("feb-two", 2025, 2, 2, "Streaming", "Fun", "VIDEO SERVICE", -20m)
        ];

        SubscriptionAnalysisResult result = SubscriptionAnalysisCalculator.Build(
            rows, Settings().Subscriptions, EmptyAliases(), ["Streaming"], [], 80);

        SubscriptionInventoryEntry bundle = Assert.Single(result.Active);
        Assert.Equal(SubscriptionBundleKind.MerchantBundle, bundle.BundleType);
        Assert.Equal(SubscriptionCadence.Multiple, bundle.Cadence);
        Assert.Equal(60m, bundle.TrailingTwelveMonthSpend);
        Assert.Equal(30m, bundle.MonthlyRunRate);
        Assert.Equal(61, bundle.Confidence);
    }

    private static FinancialTransaction Expense(
        string id,
        int year,
        int month,
        int day,
        string category,
        string group,
        string description,
        decimal amount)
        => new(id, new DateOnly(year, month, day), category, group, "Checking", description, amount, TransactionKind.Expense);

    private static FinancialTransaction Income(
        string id,
        int year,
        int month,
        int day,
        string category,
        string group,
        string description,
        decimal amount)
        => new(id, new DateOnly(year, month, day), category, group, "Checking", description, amount, TransactionKind.Income);

    private static IReadOnlyDictionary<string, IReadOnlyList<string>> EmptyAliases()
        => new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);

    private static FinanceSettings Settings()
        => new(
            new ThresholdSettings(1_000m, 5_000m, 10m, 1),
            new IncomeSavingsSettings(20m, [], []),
            [new TransactionSetDefinition("all", [], [], [], [], [], [], [])],
            new SubscriptionSettings(["Streaming"], 80, 45, []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 5, [], []),
            EmptyAliases());
}
