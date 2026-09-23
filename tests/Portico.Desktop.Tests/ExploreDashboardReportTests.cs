using Portico.Application;
using Portico.Desktop;
using Portico.Finance;

namespace Portico.Desktop.Tests;

public sealed class ExploreDashboardReportTests
{
    [Fact]
    public async Task SubscriptionSelectionChangesOnlyTheSelectedChargeWidgets()
    {
        Workspace workspace = await Open(
        [
            Expense("stream-jan", 2026, 1, 10, "Stream Basic", "Subscriptions", -10m),
            Expense("stream-feb", 2026, 2, 10, "Stream Basic", "Subscriptions", -10m),
            Expense("stream-mar", 2026, 3, 10, "Stream Basic", "Subscriptions", -10m),
            Expense("tune-jan", 2026, 1, 10, "Tune Basic", "Subscriptions", -15m),
            Expense("tune-feb", 2026, 2, 10, "Tune Basic", "Subscriptions", -15m),
            Expense("tune-mar", 2026, 3, 10, "Tune Basic", "Subscriptions", -15m)
        ], new DateOnly(2026, 3, 20));

        DashboardPageReport stream = SubscriptionsDashboardReport.Build(workspace.Subscriptions(
            new SubscriptionsReportRequest(SelectedMerchant: "STREAM BASIC")));
        DashboardPageReport tune = SubscriptionsDashboardReport.Build(workspace.Subscriptions(
            new SubscriptionsReportRequest(SelectedMerchant: "TUNE BASIC")));

        Assert.Equal(DashboardPageId.Subscriptions, stream.PageId);
        Assert.Equal(11, stream.Widgets.Count);
        Assert.Equal("STREAM BASIC", stream.SubscriptionsView?.SelectedMerchant);
        Assert.Equal("TUNE BASIC", tune.SubscriptionsView?.SelectedMerchant);
        Assert.Equal(2m, stream.Widgets["subscriptions.summary"].Metrics[0].Value);
        Assert.Equal(3, stream.Widgets["subscriptions.detail_charges"].Rows.Count);
        Assert.All(stream.Widgets["subscriptions.detail_charges"].Rows,
            row => Assert.Contains("Stream Basic", row.Values));
        Assert.All(tune.Widgets["subscriptions.detail_charges"].Rows,
            row => Assert.Contains("Tune Basic", row.Values));
        Assert.Equal(2, tune.Widgets["subscriptions.active"].Rows.Count);
        Assert.NotEmpty(tune.Widgets["subscriptions.lifecycle"].TimelineRanges);
    }

    [Fact]
    public async Task EmptySubscriptionsKeepTheEmptyCopyAndAllWidgets()
    {
        DashboardPageReport page = SubscriptionsDashboardReport.Build((await Open([])).Subscriptions());

        Assert.Equal(11, page.Widgets.Count);
        Assert.NotNull(page.SubscriptionsView?.EmptyMessage);
        Assert.Null(page.SubscriptionsView?.SelectedMerchant);
        Assert.Equal("No active subscriptions are present in the selected categories.",
            page.Widgets["subscriptions.active"].EmptyMessage);
        Assert.Equal("No subscription charges are available for this merchant.",
            page.Widgets["subscriptions.detail_charges"].EmptyMessage);
    }

    [Fact]
    public async Task MerchantSelectionChangesDetailAndKeepsTheOverview()
    {
        Workspace workspace = await Open(
        [
            Expense("coffee-jan", 2026, 1, 5, "Coffee", "Food", -20m),
            Expense("coffee-feb", 2026, 2, 5, "Coffee", "Food", -30m),
            Expense("market-feb", 2026, 2, 6, "Market", "Food", -50m)
        ], new DateOnly(2026, 2, 28));

        DashboardPageReport coffee = MerchantsDashboardReport.Build(workspace.Merchants(
            new MerchantsReportRequest(LookbackMonths: 2, SelectedMerchant: "COFFEE",
                DetailMonth: new YearMonth(2026, 2))), SpendingComparison.PreviousPeriod);
        DashboardPageReport market = MerchantsDashboardReport.Build(workspace.Merchants(
            new MerchantsReportRequest(LookbackMonths: 2, SelectedMerchant: "MARKET")),
            SpendingComparison.LastYear);

        Assert.Equal(DashboardPageId.Merchants, coffee.PageId);
        Assert.Equal(11, coffee.Widgets.Count);
        Assert.Equal("COFFEE", coffee.MerchantsView?.SelectedMerchant);
        Assert.Equal("2026-02", coffee.MerchantsView?.DetailMonth);
        Assert.Equal("MARKET", market.MerchantsView?.SelectedMerchant);
        Assert.Equal(2, market.Widgets["merchants.overview"].Rows.Count);
        Assert.Single(coffee.Widgets["merchants.detail_transactions"].Rows);
        Assert.Contains("Coffee", coffee.Widgets["merchants.detail_transactions"].Rows[0].Values);
        Assert.Contains("Market", market.Widgets["merchants.detail_transactions"].Rows[0].Values);
        Assert.Contains("last year", market.Widgets["merchants.detail_summary"].Metrics[1].Label);
    }

    [Fact]
    public async Task EmptyMerchantsKeepTheSelectedDetailPrompt()
    {
        DashboardPageReport page = MerchantsDashboardReport.Build((await Open([])).Merchants(),
            SpendingComparison.PreviousPeriod);

        Assert.Equal(11, page.Widgets.Count);
        Assert.NotNull(page.MerchantsView?.EmptyMessage);
        Assert.Equal("Select a merchant to inspect its detail.",
            page.Widgets["merchants.detail_summary"].EmptyMessage);
        Assert.Empty(page.Widgets["merchants.overview"].Rows);
    }

    [Fact]
    public async Task TransactionFilterChangesResultsAndTopWidgets()
    {
        Workspace workspace = await Open(
        [
            Expense("coffee", 2026, 3, 1, "Coffee", "Food", -20m),
            new FinancialTransaction("pay", new DateOnly(2026, 3, 2), "Pay", "Income",
                "Checking", "Salary", 100m, TransactionKind.Income)
        ], new DateOnly(2026, 3, 5));

        DashboardPageReport all = TransactionsDashboardReport.Build(workspace.Transactions());
        DashboardPageReport expenses = TransactionsDashboardReport.Build(workspace.Transactions(
            TransactionExplorerFilters.Default with { Type = TransactionExplorerType.Expenses }));

        Assert.Equal(DashboardPageId.TopTransactions, all.PageId);
        Assert.Equal(7, all.Widgets.Count);
        Assert.Equal(2, all.Widgets["transactions.table"].Rows.Count);
        Assert.Single(expenses.Widgets["transactions.table"].Rows);
        Assert.Equal("$20", expenses.Widgets["transactions.summary"].Metrics[1].Display);
        Assert.Empty(expenses.Widgets["top.incomes"].Series);
        Assert.Single(expenses.Widgets["top.expenses"].Series);
        Assert.Equal("No data is available for this selection.", expenses.Widgets["top.incomes"].EmptyMessage);
        Assert.Same(expenses.Widgets["top.table"], expenses.Widgets["transactions.table"]);
    }

    [Fact]
    public async Task EmptyTransactionsKeepTheMatchingMessage()
    {
        DashboardPageReport page = TransactionsDashboardReport.Build((await Open([])).Transactions());

        Assert.Equal(7, page.Widgets.Count);
        Assert.Equal("No transactions match this view.", page.TransactionsView?.EmptyMessage);
        Assert.Equal("No transactions match this view.", page.Widgets["transactions.table"].EmptyMessage);
    }

    private static async Task<Workspace> Open(
        IReadOnlyList<FinancialTransaction> transactions,
        DateOnly? asOfDate = null)
    {
        var application = new PorticoApplication(new ConfigurationReader(),
            new PortfolioReader(new PortfolioSnapshot(transactions, [], [])));
        OpenWorkspaceOutcome outcome = await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), asOfDate, TestContext.Current.CancellationToken);
        return outcome switch
        {
            WorkspaceOpened opened => opened.GetWorkspace(),
            _ => throw new InvalidOperationException("Expected an open test workspace.")
        };
    }

    private static FinancialTransaction Expense(
        string id, int year, int month, int day, string description, string category, decimal amount)
        => new(id, new DateOnly(year, month, day), category, "Living", "Checking",
            description, amount, TransactionKind.Expense);

    private sealed class ConfigurationReader : IConfigurationReader
    {
        public Task<ConfigurationReadOutcome> ReadAsync(
            ConfigurationSelection selection, CancellationToken cancellationToken)
            => Task.FromResult<ConfigurationReadOutcome>(new ConfigurationReadSuccess(
                new WorkspaceConfiguration(Settings(), new LocalCsvSourceRequest("fixture"))));
    }

    private sealed class PortfolioReader(PortfolioSnapshot snapshot) : IPortfolioReader
    {
        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
            => Task.FromResult<PortfolioReadOutcome>(new PortfolioReadSuccess(snapshot));
    }

    private static FinanceSettings Settings()
        => new(
            new LookbackSettings([1, 2, 12], 2),
            new ThresholdSettings(100m, 100m, 10m, 1),
            new IncomeSavingsSettings("regular", 25m, [], []),
            [new TransactionSetDefinition("all", "All", [], [], [], [], [], [], [])],
            [new FilterSetDefinition("spending", ["all"], "all")],
            new SubscriptionSettings(["Subscriptions"], 70, 1, [], []),
            new BudgetSettings(3),
            new DataHealthSettings(1, false, false, false),
            new FinancialSafetySettings(3, ["Cash"], [], 3, [], [], ["Debt"], [], null),
            new FinancialIndependenceSettings(0.05m, 0.04m, 1000m, 12, 10, [], []),
            new Dictionary<string, IReadOnlyList<string>>());
}
