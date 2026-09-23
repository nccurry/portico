using Portico.Finance;

namespace Portico.Application.Tests;

public sealed class FinancialIndependenceAndDataHealthTests
{
    [Fact]
    public async Task FinancialIndependence_UsesVisibleSourceRowsAndConfiguredDefaults()
    {
        Workspace workspace = await Open(Snapshot());

        FinancialIndependenceReport report = workspace.FinancialIndependence();

        Assert.Equal(["Checking", "Stale"], report.SourceFilters.IncludedAccounts);
        Assert.Equal(525m, report.Source.PortfolioValue);
        Assert.Equal(120m, report.Source.AnnualSpending);
        Assert.Equal(["expense"], report.Source.Expenses.Select(row => row.Id));
        Assert.Equal(new YearMonth(2025, 4), report.Source.StartMonth);
        Assert.Equal(new YearMonth(2026, 3), report.Source.EndMonth);
        Assert.Equal(525m, report.Scenario.Assets);
        Assert.Equal(120m, report.Scenario.AnnualSpending);
        Assert.Equal(3000m, report.Summary.FinancialIndependenceTarget);
        Assert.Equal(-2475m, report.Summary.FundingGap);
        Assert.Equal(11, report.Projection.Count);
        Assert.Equal(20, report.Sensitivity.Count);
        Assert.Equal(new DateOnly(2026, 3, 10), report.LatestTransactionDate);
        Assert.Equal(new DateOnly(2026, 3, 10), report.LatestBalanceDate);
    }

    [Fact]
    public async Task FinancialIndependence_UsesExplicitSourceAndScenario()
    {
        Workspace workspace = await Open(Snapshot());
        var filters = new FinancialIndependenceSourceFilters(
            ["Checking"], 1, new SpendingAdjustments([], [], [], [], false, 100m));
        var scenario = new FinancialIndependenceScenario(1000m, 240m, 60m, 3m, 5m, 2);

        FinancialIndependenceReport report = workspace.FinancialIndependence(
            new FinancialIndependenceReportRequest(filters, scenario));

        Assert.Same(filters, report.SourceFilters);
        Assert.Same(scenario, report.Scenario);
        Assert.Equal(500m, report.Source.PortfolioValue);
        Assert.Equal(1440m, report.Source.AnnualSpending);
        Assert.Equal(3600m, report.Summary.FinancialIndependenceTarget);
        Assert.Equal(3, report.Projection.Count);
        Assert.Equal(240m, report.Sensitivity[8].AnnualSpending);
        Assert.Equal([0m, 3m, 5m, 9m], report.Sensitivity.Take(4).Select(cell => cell.ReturnRate));
    }

    [Fact]
    public async Task FinancialIndependence_EmptyDataKeepsACompleteScenario()
    {
        Workspace workspace = await Open(new PortfolioSnapshot([], [], []));

        FinancialIndependenceReport report = workspace.FinancialIndependence();

        Assert.Empty(report.Source.Accounts);
        Assert.Empty(report.Source.Expenses);
        Assert.Empty(report.Source.MonthlySpending);
        Assert.Null(report.Source.StartMonth);
        Assert.Null(report.Source.EndMonth);
        Assert.Null(report.LatestTransactionDate);
        Assert.Null(report.LatestBalanceDate);
        Assert.Equal(0m, report.Summary.AnnualSpending);
        Assert.All(report.Projection, point => Assert.Equal(0m, point.Balance));
    }

    [Fact]
    public async Task FinancialIndependence_InvalidSourceAndScenarioRemainProgrammerErrors()
    {
        Workspace workspace = await Open(Snapshot());

        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.FinancialIndependence(
            new FinancialIndependenceReportRequest(new FinancialIndependenceSourceFilters(
                [], 0, SpendingAdjustments.Default(100m)))));
        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.FinancialIndependence(
            new FinancialIndependenceReportRequest(Scenario: new FinancialIndependenceScenario(
                100m, 100m, 0m, 5m, 4m, 101))));
    }

    [Fact]
    public async Task FinancialIndependence_ProjectionUsesYearOffsetsAtCalendarMaximum()
    {
        PortfolioSnapshot snapshot = new([], [Balance("checking", "Checking", "Cash", 9999, 12, 31, 100m)], []);
        Workspace workspace = await Open(snapshot);

        FinancialIndependenceReport report = workspace.FinancialIndependence();

        Assert.Equal(new DateOnly(9999, 12, 31), report.LatestBalanceDate);
        Assert.Equal(10, report.Projection[^1].Year);
        Assert.Equal(11, report.Projection.Count);
    }

    [Fact]
    public async Task DataHealth_UsesLatestDataDateForChecksAndOrdersQueue()
    {
        Workspace workspace = await Open(Snapshot(), asOfDate: new DateOnly(2030, 1, 1));

        DataHealthReport report = workspace.DataHealth();

        Assert.Equal(new DateOnly(2026, 3, 11), report.EvaluationDate);
        Assert.Equal(new DateOnly(2026, 3, 10), report.LatestTransactionDate);
        Assert.Equal([
            "uncategorized", "incomplete", "account_mapping", "stale_accounts", "duplicates", "reversals"
        ], report.Checks.Select(check => check.Id));
        Assert.Equal("uncategorized", report.SelectedCheck.Id);
        Assert.Equal(DataHealthCheckStatus.Passed, report.SelectedCheck.Status);
        Assert.Equal(1, report.Checks[3].FindingCount);
        Assert.Equal(1, report.NeedsAttention);
        Assert.Equal(2, report.TransactionCount);
        Assert.Equal(3, report.AccountCount);
        Assert.False(report.IsEmpty);
    }

    [Fact]
    public async Task DataHealth_SelectsCheckOrFallsBackToFirst()
    {
        PortfolioSnapshot snapshot = new(
            [
                Transaction("one", 2026, 3, 10, "Charge", -20m, TransactionKind.Expense),
                Transaction("two", 2026, 3, 10, "Charge", -20m, TransactionKind.Expense)
            ], [], []);
        Workspace workspace = await Open(snapshot);

        DataHealthReport selected = workspace.DataHealth(new DataHealthReportRequest(
            SelectedCheckId: "duplicates"));
        DataHealthReport fallback = workspace.DataHealth(new DataHealthReportRequest(
            SelectedCheckId: "missing"));

        Assert.Equal("duplicates", selected.SelectedCheck.Id);
        Assert.Equal(DataHealthCheckStatus.Review, selected.SelectedCheck.Status);
        Assert.Equal(DataHealthCheckKind.Duplicates, selected.SelectedCheck.Kind);
        Assert.Single(selected.SelectedCheck.Records);
        Assert.Single(selected.SelectedCheck.DuplicatePairs);
        Assert.Equal(1, selected.ReviewItems);
        Assert.Equal("uncategorized", fallback.SelectedCheck.Id);
    }

    [Fact]
    public async Task DataHealth_MapsNeedsAttentionStatusAndCountsFindings()
    {
        PortfolioSnapshot snapshot = new(
            [new FinancialTransaction("unknown", new DateOnly(2026, 3, 10), "", "Uncategorized",
                "Checking", "Unmapped", -20m, TransactionKind.Unknown)],
            [], []);
        Workspace workspace = await Open(snapshot);

        DataHealthReport report = workspace.DataHealth();

        Assert.Equal(DataHealthCheckStatus.NeedsAttention, report.Checks[0].Status);
        Assert.Equal(1, report.Checks[0].FindingCount);
        Assert.Equal(20m, report.Checks[0].FinancialScope);
        Assert.Equal(1, report.NeedsAttention);
        Assert.Equal(0, report.ReviewItems);
    }

    [Fact]
    public async Task DataHealth_OptionsControlInactiveRowsAndValidateRanges()
    {
        Workspace workspace = await Open(Snapshot());
        DataHealthCheckOptions defaults = DataHealthCheckOptions.From(Settings());
        DataHealthReport normal = workspace.DataHealth();
        DataHealthReport included = workspace.DataHealth(new DataHealthReportRequest(
            defaults with { IncludeInactive = true }));

        Assert.Equal(2, normal.TransactionCount);
        Assert.Equal(3, included.TransactionCount);
        Assert.Equal(3, normal.AccountCount);
        Assert.Equal(4, included.AccountCount);
        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.DataHealth(new DataHealthReportRequest(
            defaults with { DuplicateDays = 8 })));
    }

    [Fact]
    public async Task DataHealth_EmptyDataUsesWorkspaceDateAndHasStableEmptyQueue()
    {
        Workspace workspace = await Open(new PortfolioSnapshot([], [], []), new DateOnly(9999, 12, 31));

        DataHealthReport report = workspace.DataHealth();

        Assert.Equal(new DateOnly(9999, 12, 31), report.EvaluationDate);
        Assert.True(report.IsEmpty);
        Assert.Equal(6, report.Checks.Count);
        Assert.All(report.Checks, check => Assert.Equal(DataHealthCheckStatus.Passed, check.Status));
        Assert.Equal(0, report.NeedsAttention);
        Assert.Equal(0, report.ReviewItems);
        Assert.Null(report.LatestTransactionDate);
        Assert.Null(report.LatestBalanceDate);
    }

    private static async Task<Workspace> Open(PortfolioSnapshot snapshot, DateOnly? asOfDate = null)
    {
        var application = new PorticoApplication(
            new ConfigurationReader(),
            new PortfolioReader(snapshot));
        OpenWorkspaceOutcome outcome = await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), asOfDate, TestContext.Current.CancellationToken);
        return outcome switch
        {
            WorkspaceOpened opened => opened.GetWorkspace(),
            _ => throw new InvalidOperationException("Expected an open workspace.")
        };
    }

    private static PortfolioSnapshot Snapshot() => new(
        [
            Transaction("expense", 2026, 3, 10, "Groceries", -120m, TransactionKind.Expense),
            Transaction("income", 2026, 3, 2, "Pay", 1000m, TransactionKind.Income),
            Transaction("hidden", 2026, 3, 11, "Hidden", -900m, TransactionKind.Expense) with { IsHidden = true }
        ],
        [
            Balance("checking", "Checking", "Cash", 2026, 3, 10, 500m),
            Balance("other", "Other", "Cash", 2026, 3, 10, 100m, hidden: true),
            Balance("card", "Card", "Debt", 2026, 3, 10, 100m, AccountClass.Liability),
            Balance("stale", "Stale", "Cash", 2026, 3, 1, 25m)
        ], []);

    private static FinancialTransaction Transaction(
        string id, int year, int month, int day, string description, decimal amount, TransactionKind kind)
        => new(id, new DateOnly(year, month, day), "Food", "Needs", "Checking", description, amount, kind);

    private static BalanceObservation Balance(
        string id, string account, string group, int year, int month, int day, decimal value,
        AccountClass accountClass = AccountClass.Asset, bool hidden = false)
        => new(id, account, group, new DateOnly(year, month, day), TimeOnly.MinValue, value, accountClass, hidden);

    private static FinanceSettings Settings() => new(
        new ThresholdSettings(100m, 100m, 10m, 1),
        new IncomeSavingsSettings(0.1m, [], []),
        [],
        new SubscriptionSettings([], 0, 1, []),
        new BudgetSettings(12),
        new DataHealthSettings(7, false, false, false),
        new FinancialSafetySettings(3, ["Cash"], [], 3, [], [], ["Debt"], [], null),
        new FinancialIndependenceSettings(5m, 4m, 1000m, 12, 10, [], []),
        new Dictionary<string, IReadOnlyList<string>>());

    private sealed class ConfigurationReader : IConfigurationReader
    {
        public Task<ConfigurationReadOutcome> ReadAsync(
            ConfigurationSelection selection, CancellationToken cancellationToken)
            => Task.FromResult<ConfigurationReadOutcome>(new ConfigurationReadSuccess(
                new WorkspaceConfiguration(Settings(), ReportWorkspaceFixture.Choices(), new LocalCsvSourceRequest("unused"))));
    }

    private sealed class PortfolioReader(PortfolioSnapshot snapshot) : IPortfolioReader
    {
        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
            => Task.FromResult<PortfolioReadOutcome>(new PortfolioReadSuccess(snapshot));
    }
}
