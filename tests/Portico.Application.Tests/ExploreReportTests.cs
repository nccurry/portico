using Portico.Finance;

namespace Portico.Application.Tests;

public sealed class ExploreReportTests
{
    [Fact]
    public async Task YearOverYear_PresetsFollowRankAndSelectionWhileSingleViewsIgnorePresetSet()
    {
        Workspace workspace = await Open([
            Expense("food-old", 2025, 3, 2, "Store", "Food", "Living", -40m),
            Expense("food-new", 2026, 3, 2, "Store", "Food", "Living", -70m),
            Expense("rent", 2026, 3, 3, "Landlord", "Rent", "Housing", -120m),
            Expense("hidden", 2026, 3, 4, "Secret", "Food", "Living", -999m, hidden: true)
        ]);

        YearOverYearReport initial = workspace.YearOverYear();
        Assert.Equal(["Rent", "Food"], initial.PresetCategories);
        Assert.Equal(["Food", "Rent"], initial.Categories);
        Assert.Equal(["Housing", "Living"], initial.Groups);
        Assert.Empty(initial.Comparisons);
        Assert.Equal(YearOverYearEmptyReason.NoPresetSelection, initial.EmptyReason);

        YearOverYearReport preset = workspace.YearOverYear(new YearOverYearReportRequest(
            PresetCategories: new HashSet<string>(["Food", "Rent"], StringComparer.Ordinal)));
        Assert.Equal(["Rent", "Food"], preset.Comparisons.Select(comparison => comparison.Entity));
        Assert.Equal(120m, preset.Comparisons[0].Summary.CurrentTotal);
        Assert.Equal(70m, preset.Comparisons[1].Summary.CurrentTotal);
        Assert.Equal(30m, preset.Comparisons[1].Summary.Change);
        Assert.Null(preset.EmptyReason);

        YearOverYearReport group = workspace.YearOverYear(new YearOverYearReportRequest(
            YearOverYearSelection.Group, PresetSetKey: "living", Entity: "Housing"));
        Assert.Equal(120m, Assert.Single(group.Comparisons).Summary.CurrentTotal);
        Assert.Equal(YearOverYearDimension.Group, group.Comparisons[0].Dimension);
        Assert.DoesNotContain(group.Comparisons[0].Transactions, transaction => transaction.IsHidden);
    }

    [Fact]
    public async Task YearOverYear_EmptyReasonsAndInvalidModeAreTyped()
    {
        Workspace empty = await Open([]);
        Assert.Equal(YearOverYearEmptyReason.NoPresetCategories, empty.YearOverYear().EmptyReason);
        Assert.Equal(YearOverYearEmptyReason.NoCategories, empty.YearOverYear(
            new YearOverYearReportRequest(YearOverYearSelection.Category, Entity: "Food")).EmptyReason);
        Assert.Equal(YearOverYearEmptyReason.NoGroups, empty.YearOverYear(
            new YearOverYearReportRequest(YearOverYearSelection.Group, Entity: "Living")).EmptyReason);

        Workspace populated = await Open([Expense("food", 2026, 3, 1, "Store", "Food", "Living", -10m)]);
        Assert.Equal(YearOverYearEmptyReason.NoMatchingHistory, populated.YearOverYear(
            new YearOverYearReportRequest(YearOverYearSelection.Category, Entity: "Missing")).EmptyReason);
        Assert.Throws<ArgumentOutOfRangeException>(() => populated.YearOverYear(
            new YearOverYearReportRequest((YearOverYearSelection)99)));
    }

    [Fact]
    public async Task Subscriptions_SelectsKnownMerchantAndMeasuresStalenessFromWorkspaceDate()
    {
        Workspace workspace = await Open([
            Expense("charge-1", 2026, 1, 10, "Stream Basic", "Subscriptions", "Stream", -10m),
            Expense("charge-2", 2026, 2, 10, "Stream Basic", "Subscriptions", "Stream", -10m),
            Expense("charge-3", 2026, 3, 10, "Stream Basic", "Subscriptions", "Stream", -10m),
            Expense("hidden", 2026, 4, 1, "Secret", "Subscriptions", "Stream", -999m, hidden: true)
        ], asOf: new DateOnly(2026, 3, 20));

        SubscriptionsReport report = workspace.Subscriptions();

        Assert.Equal(new DateOnly(2026, 3, 10), report.Analysis.LatestDataDate);
        Assert.Equal(10, report.DataAgeDays);
        Assert.True(report.DataIsStale);
        Assert.Equal("STREAM BASIC", report.SelectedMerchant);
        Assert.False(report.SelectedMerchantIsCandidate);
        Assert.Equal(3, report.SelectedCharges.Count);
        Assert.Equal("charge-3", report.SelectedCharges[0].Transaction.Id);
        Assert.Equal(report.SelectedMerchant, workspace.Subscriptions(
            new SubscriptionsReportRequest(SelectedMerchant: "Missing")).SelectedMerchant);
        Assert.Empty(workspace.Subscriptions(new SubscriptionsReportRequest(Categories: [])).Analysis.KnownCharges);
    }

    [Fact]
    public async Task Subscriptions_EmptyDataHasNoSelectionOrAge()
    {
        Workspace workspace = await Open([]);
        SubscriptionsReport report = workspace.Subscriptions();

        Assert.Null(report.Analysis.LatestDataDate);
        Assert.Null(report.DataAgeDays);
        Assert.False(report.DataIsStale);
        Assert.Null(report.SelectedMerchant);
        Assert.Empty(report.SelectedCharges);
    }

    [Fact]
    public async Task Subscriptions_RejectsExplicitInvalidConfidence()
    {
        Workspace workspace = await Open([]);

        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.Subscriptions(
            new SubscriptionsReportRequest(MinimumConfidence: 69)));
        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.Subscriptions(
            new SubscriptionsReportRequest(MinimumConfidence: 101)));
    }

    [Fact]
    public async Task Subscriptions_SelectsDetectedCandidateAndClampsFutureDataAge()
    {
        Workspace workspace = await Open([
            Expense("jan", 2026, 1, 1, "Cloud Backup", "Software", "Fun", -5m),
            Expense("feb", 2026, 2, 1, "Cloud Backup", "Software", "Fun", -5m),
            Expense("mar", 2026, 3, 2, "Cloud Backup", "Software", "Fun", -5m)
        ], asOf: DateOnly.MinValue);

        SubscriptionsReport report = workspace.Subscriptions();

        Assert.Equal("CLOUD BACKUP", report.SelectedMerchant);
        Assert.True(report.SelectedMerchantIsCandidate);
        Assert.Equal(3, report.SelectedCharges.Count);
        Assert.Equal(0, report.DataAgeDays);
        Assert.False(report.DataIsStale);

        SubscriptionsReport excluded = workspace.Subscriptions(new SubscriptionsReportRequest(
            DiscoveryExclusions: ["Software"]));
        Assert.Null(excluded.SelectedMerchant);
        Assert.Empty(excluded.Analysis.Candidates);
    }

    [Fact]
    public async Task Merchants_UsesAliasesComparisonAndSelectedDetailMonth()
    {
        Workspace workspace = await Open([
            Expense("old", 2025, 12, 5, "Coffee Shop", "Food", "Living", -20m),
            Expense("jan", 2026, 1, 5, "Coffee Shop", "Food", "Living", -30m),
            Expense("feb", 2026, 2, 5, "Coffee Inc", "Food", "Living", -40m),
            Expense("other", 2026, 2, 6, "Market", "Food", "Living", -50m),
            Expense("hidden", 2026, 2, 7, "Secret", "Food", "Living", -999m, hidden: true)
        ], settings: Settings() with
        {
            MerchantAliases = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
            {
                ["Coffee"] = ["Coffee Shop", "Coffee Inc"]
            }
        });

        MerchantsReport report = workspace.Merchants(new MerchantsReportRequest(
            LookbackMonths: 2, SelectedMerchant: "Coffee", DetailMonth: new YearMonth(2026, 2)));

        Assert.Equal("COFFEE", report.SelectedMerchant);
        Assert.Equal(70m, report.Analysis.Overview.Single(entry => entry.Merchant == "COFFEE").Spending);
        Assert.Equal(2, report.SelectedHistory.Count);
        Assert.Equal(40m, report.SelectedHistory[1].CurrentSpending);
        Assert.Equal("feb", Assert.Single(report.SelectedTransactions).Transaction.Id);
        Assert.Equal("Coffee Inc", report.SelectedDescriptions.First(entry => entry.Description == "Coffee Inc").Description);
        Assert.DoesNotContain(report.Analysis.Overview, entry => entry.Merchant == "SECRET");

        MerchantsReport fallback = workspace.Merchants(new MerchantsReportRequest(SelectedMerchant: "Missing"));
        Assert.Equal(fallback.Analysis.Overview[0].Merchant, fallback.SelectedMerchant);
        Assert.Equal("MARKET", workspace.Merchants(
            new MerchantsReportRequest(SelectedMerchant: "MARKET")).SelectedMerchant);

        MerchantsReport lastYear = workspace.Merchants(new MerchantsReportRequest(
            LookbackMonths: 2, Comparison: SpendingComparison.LastYear, SelectedMerchant: "COFFEE"));
        Assert.Equal(0m, lastYear.Analysis.Overview.Single(entry => entry.Merchant == "COFFEE").ComparisonSpending);
        Assert.Equal(20m, report.Analysis.Overview.Single(entry => entry.Merchant == "COFFEE").ComparisonSpending);
    }

    [Fact]
    public async Task Merchants_EmptyDataHasNoDetail()
    {
        MerchantsReport report = (await Open([])).Merchants();
        Assert.Null(report.LatestExpenseDate);
        Assert.Empty(report.Analysis.Overview);
        Assert.Null(report.SelectedMerchant);
        Assert.Empty(report.SelectedHistory);
        Assert.Empty(report.SelectedTransactions);
    }

    [Fact]
    public async Task Transactions_AppliesFiltersAliasesAndHiddenRows()
    {
        Workspace workspace = await Open([
            Expense("food", 2026, 3, 1, "Coffee Shop", "Food", "Living", -20m),
            Expense("refund", 2026, 3, 2, "Coffee Inc", "Food", "Living", 10m),
            Expense("hidden", 2026, 3, 3, "Secret", "Food", "Living", -999m, hidden: true)
        ], settings: Settings() with
        {
            MerchantAliases = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
            {
                ["Coffee"] = ["Coffee Shop", "Coffee Inc"]
            }
        });

        TransactionExplorerAnalysisResult all = workspace.Transactions();
        Assert.Equal(2, all.Results.Count);
        Assert.Equal("COFFEE", all.Results[0].Merchant);
        Assert.DoesNotContain(all.Results, entry => entry.Transaction.IsHidden);

        TransactionExplorerFilters filters = TransactionExplorerFilters.Default with
        {
            LookbackDays = 0,
            Focus = TransactionExplorerFocus.RefundsReversals,
            Search = "Coffee",
            Breakdown = TransactionExplorerBreakdown.Merchant
        };
        TransactionExplorerAnalysisResult refunds = workspace.Transactions(filters);
        Assert.Single(refunds.Inventory);
        Assert.Equal("refund", Assert.Single(refunds.Results).Transaction.Id);
        Assert.Equal(10m, refunds.Summary.Inflow);
        Assert.Equal("COFFEE", Assert.Single(refunds.Breakdown).Entity);
    }

    [Fact]
    public async Task Transactions_EmptyAndInvalidFiltersHaveDefinedBehavior()
    {
        Workspace empty = await Open([]);
        Assert.Empty(empty.Transactions().Results);
        Assert.Null(empty.Transactions().EndDate);

        Workspace populated = await Open([Expense("food", 2026, 3, 1, "Store", "Food", "Living", -10m)]);
        Assert.Throws<ArgumentOutOfRangeException>(() => populated.Transactions(
            TransactionExplorerFilters.Default with { MinimumMagnitude = -1m }));
    }

    private static async Task<Workspace> Open(
        IReadOnlyList<FinancialTransaction> transactions,
        FinanceSettings? settings = null,
        DateOnly? asOf = null)
    {
        var application = new PorticoApplication(
            new ConfigurationReader(settings ?? Settings()),
            new PortfolioReader(new PortfolioSnapshot(transactions, [], [])));
        OpenWorkspaceOutcome result = await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), asOf, TestContext.Current.CancellationToken);
        return result switch
        {
            WorkspaceOpened opened => opened.GetWorkspace(),
            _ => throw new InvalidOperationException("Could not open test workspace.")
        };
    }

    private static FinancialTransaction Expense(
        string id, int year, int month, int day, string description, string category, string group,
        decimal amount, bool hidden = false)
        => new(id, new DateOnly(year, month, day), category, group, "Checking", description, amount,
            TransactionKind.Expense, hidden);

    private static FinanceSettings Settings()
        => new(
            new LookbackSettings([3], 3),
            new ThresholdSettings(100m, 100m, 10m, 1),
            new IncomeSavingsSettings("regular", 0.1m, [], []),
            [
                new TransactionSetDefinition("all", "All", [], [], [], [], [], [], []),
                new TransactionSetDefinition("living", "Living", ["Living"], [], [], [], [], [], [])
            ],
            [
                new FilterSetDefinition("spending", ["all"], "all"),
                new FilterSetDefinition("year_over_year", ["all", "living"], "all")
            ],
            new SubscriptionSettings(["Subscriptions"], 70, 5, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(1, false, false, false),
            new FinancialSafetySettings(3, [], [], 3, [], [], [], [], null),
            new FinancialIndependenceSettings(.05m, .04m, 1000m, 12, 10, [], []),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal));

    private sealed class ConfigurationReader(FinanceSettings settings) : IConfigurationReader
    {
        public Task<ConfigurationReadOutcome> ReadAsync(ConfigurationSelection selection, CancellationToken cancellationToken)
            => Task.FromResult<ConfigurationReadOutcome>(new ConfigurationReadSuccess(new WorkspaceConfiguration(
                settings, new LocalCsvSourceRequest("synthetic"))));
    }

    private sealed class PortfolioReader(PortfolioSnapshot snapshot) : IPortfolioReader
    {
        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
            => Task.FromResult<PortfolioReadOutcome>(new PortfolioReadSuccess(snapshot));
    }
}
