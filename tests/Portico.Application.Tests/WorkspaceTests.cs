using System.Text.Json;
using Portico.Finance;

namespace Portico.Application.Tests;

public sealed class WorkspaceTests
{
    private const string PrivateLocation = "https://example.invalid/private-sheet-token";
    private const string PrivateRow = "private financial row";

    [Fact]
    public async Task OpenWorkspace_LoadsReadersInOrderAndKeepsPayloadOutOfDefaultOutput()
    {
        var source = new GoogleSheetsSourceRequest(
            PrivateLocation, PrivateLocation, PrivateLocation, PrivateLocation);
        var selection = new ConfigurationSelection("selected.toml");
        var events = new List<string>();
        var configuration = new Reader<ConfigurationReadOutcome>(_ =>
        {
            events.Add("configuration");
            return new ConfigurationReadSuccess(new WorkspaceConfiguration(Settings(), source));
        });
        var portfolio = new Reader<PortfolioReadOutcome>(_ =>
        {
            events.Add("portfolio");
            return new PortfolioReadSuccess(Snapshot());
        });
        var application = new PorticoApplication(
            new ConfigurationReader(configuration), new PortfolioReader(portfolio));

        OpenWorkspaceOutcome outcome = await application.OpenWorkspaceAsync(
            selection, cancellationToken: TestContext.Current.CancellationToken);

        Workspace workspace = Opened(outcome);
        Assert.Equal(new DateOnly(2026, 3, 1), workspace.AsOfDate);
        Assert.Equal(400m, workspace.Home().Closing!.NetWorth);
        Assert.Same(selection, configuration.Selection);
        Assert.Same(source, portfolio.Source);
        Assert.Equal(["configuration", "portfolio"], events);
        WorkspaceOpened opened = outcome switch
        {
            WorkspaceOpened value => value,
            _ => throw new InvalidOperationException("Expected an open workspace.")
        };
        string output = string.Join(' ', outcome, JsonSerializer.Serialize(outcome),
            JsonSerializer.Serialize(opened), JsonSerializer.Serialize(workspace), workspace);
        Assert.DoesNotContain(PrivateLocation, output, StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateRow, output, StringComparison.Ordinal);
        Assert.DoesNotContain("Balances", output, StringComparison.Ordinal);
        Assert.DoesNotContain("ReportChoices", output, StringComparison.Ordinal);
    }

    [Fact]
    public async Task OpenWorkspace_UsesExplicitDateAndCopiesReaderOwnedCollections()
    {
        var balances = new List<BalanceObservation> { Balance("bank", "Bank", "Cash", 2026, 3, 1, 100m) };
        var transactions = new List<FinancialTransaction>();
        var snapshot = new PortfolioSnapshot(transactions, balances, []);
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(snapshot))
            .OpenWorkspaceAsync(new ConfigurationSelection(), new DateOnly(2026, 4, 1),
                TestContext.Current.CancellationToken));

        balances.Add(Balance("later", "Later", "Cash", 2026, 3, 2, 500m));
        transactions.Add(Transaction("late", 2026, 3, 2, PrivateRow, -99m, TransactionKind.Expense));

        Assert.Equal(new DateOnly(2026, 4, 1), workspace.AsOfDate);
        Assert.Equal(100m, workspace.Home().Closing!.NetWorth);
        Assert.Equal(0m, workspace.Home().CashFlow.Surplus);
    }

    [Fact]
    public async Task OpenWorkspace_CopiesMutableFinancePolicyBeforeBuildingReports()
    {
        var excludedCategories = new List<string>();
        var emergencyGroups = new List<string> { "Cash" };
        var independenceGroups = new List<string> { "Debt" };
        FinanceSettings original = Settings();
        FinanceSettings settings = original with
        {
            IncomeSavings = original.IncomeSavings with { ExcludeCategories = excludedCategories },
            FinancialSafety = original.FinancialSafety with { EmergencyFundIncludedGroups = emergencyGroups },
            FinancialIndependence = original.FinancialIndependence with { IncludedGroups = independenceGroups }
        };
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(Snapshot()), settings)
            .OpenWorkspaceAsync(new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));
        HomeReport before = workspace.Home();

        excludedCategories.Add("Food");
        emergencyGroups.Clear();
        independenceGroups.Clear();
        HomeReport after = workspace.Home();
        Assert.Equal(1000m, before.CashFlow.Income);
        Assert.Equal(before.CashFlow, after.CashFlow);
        Assert.Equal(5m, before.Safety.EmergencyFundMonthsCovered);
        Assert.Equal(before.Safety, after.Safety);
        Assert.Equal(-10m, after.Safety.FinancialIndependenceProgressPercent);
    }

    [Fact]
    public async Task ReportChoices_AreReadOnlyAndIndependentOfReaderSettings()
    {
        var months = new List<int> { 3, 6, 12 };
        var options = new List<string> { "all", "essential" };
        FinanceSettings settings = Settings() with
        {
            Lookback = new LookbackSettings(months, 6),
            FilterSets = [new FilterSetDefinition("spending", options, "all")],
            TransactionSets = [new TransactionSetDefinition("all", "All spending", [], [], [], [], [], [], [])]
        };
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(Snapshot()), settings)
            .OpenWorkspaceAsync(new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        months[0] = 24;
        options[0] = "changed";

        Assert.Equal([3, 6, 12], workspace.ReportChoices.LookbackMonths);
        Assert.Equal(6, workspace.ReportChoices.DefaultLookbackMonths);
        Assert.Equal(["all", "essential"], workspace.ReportChoices.FilterSets["spending"].Options);
        Assert.Equal("all", workspace.ReportChoices.FilterSets["spending"].Default);
        Assert.Equal("All spending", workspace.ReportChoices.TransactionSetLabels["all"]);
        Assert.Throws<NotSupportedException>(() => ((IList<int>)workspace.ReportChoices.LookbackMonths)[0] = 24);
        Assert.Throws<NotSupportedException>(() => ((IList<string>)workspace.ReportChoices.FilterSets["spending"].Options)[0] = "changed");
    }

    [Fact]
    public async Task OpenWorkspace_EmptySnapshotHasFixedFallbackDate()
    {
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(new PortfolioSnapshot([], [], [])))
            .OpenWorkspaceAsync(new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        Assert.Equal(new DateOnly(2000, 1, 1), workspace.AsOfDate);
        HomeReport home = workspace.Home();
        Assert.Null(home.Window);
        Assert.Empty(home.NetWorthHistory);
        Assert.Empty(home.Groups);
        Assert.Empty(home.Accounts);
        Assert.Equal(0m, home.CashFlow.Surplus);
        Assert.Null(home.Safety.EmergencyFundMonthsCovered);
    }

    [Fact]
    public async Task OpenWorkspace_ConfigurationFailureStopsBeforePortfolioAndSortsProblems()
    {
        var portfolio = new Reader<PortfolioReadOutcome>(_ => throw new InvalidOperationException("Should not read data."));
        var application = new PorticoApplication(
            new ConfigurationReader(new Reader<ConfigurationReadOutcome>(_ => new PorticoFailure(
            [
                new PorticoProblem("config.source", "Unsupported source.", "source.kind"),
                new PorticoProblem("config.version", "Unsupported version.", "schema_version")
            ]))),
            new PortfolioReader(portfolio));

        PorticoFailure failure = Failed(await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        Assert.Equal(["config.version", "config.source"], failure.Problems.Select(problem => problem.Code));
        Assert.Equal(0, portfolio.Calls);
    }

    [Fact]
    public async Task OpenWorkspace_PreservesOrderedDataProblems()
    {
        var application = Application(new PorticoFailure(
        [
            new PorticoProblem("data.second", "Second problem.", "data.transactions"),
            new PorticoProblem("data.first", "First problem.", "data.accounts")
        ]));

        PorticoFailure failure = Failed(await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        Assert.Equal(["data.first", "data.second"], failure.Problems.Select(problem => problem.Code));
    }

    [Fact]
    public async Task OpenWorkspace_PreCancelledTokenSkipsReadersWithOperationNeutralProblem()
    {
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        var configuration = new Reader<ConfigurationReadOutcome>(_ => throw new InvalidOperationException("Should not run."));
        var application = new PorticoApplication(
            new ConfigurationReader(configuration),
            new PortfolioReader(new Reader<PortfolioReadOutcome>(_ => throw new InvalidOperationException())));

        PorticoFailure failure = Failed(await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), cancellationToken: cancellation.Token));

        PorticoProblem problem = Assert.Single(failure.Problems);
        Assert.Equal("operation.cancelled", problem.Code);
        Assert.Equal("The operation was cancelled.", problem.Message);
        Assert.True(problem.Retryable);
        Assert.Equal(0, configuration.Calls);
    }

    [Fact]
    public async Task OpenWorkspace_MidReadCancellationReturnsTypedProblem()
    {
        using var cancellation = new CancellationTokenSource();
        var application = new PorticoApplication(
            new ConfigurationReader(new Reader<ConfigurationReadOutcome>(_ => Success())),
            new PortfolioReader(new Reader<PortfolioReadOutcome>(_ =>
            {
                cancellation.Cancel();
                throw new OperationCanceledException(cancellation.Token);
            })));

        PorticoFailure failure = Failed(await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), cancellationToken: cancellation.Token));

        Assert.Equal("operation.cancelled", Assert.Single(failure.Problems).Code);
    }

    [Fact]
    public async Task OpenWorkspace_CancellationAfterConfigurationSkipsPortfolioReader()
    {
        using var cancellation = new CancellationTokenSource();
        var portfolio = new Reader<PortfolioReadOutcome>(_ => throw new InvalidOperationException("Should not read data."));
        var application = new PorticoApplication(
            new ConfigurationReader(new Reader<ConfigurationReadOutcome>(_ =>
            {
                cancellation.Cancel();
                return Success();
            })),
            new PortfolioReader(portfolio));

        PorticoFailure failure = Failed(await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), cancellationToken: cancellation.Token));

        Assert.Equal("operation.cancelled", Assert.Single(failure.Problems).Code);
        Assert.Equal(0, portfolio.Calls);
    }

    [Fact]
    public async Task OpenWorkspace_UnexpectedFailureReachesHost()
    {
        var exception = new InvalidOperationException("private detail");
        var application = new PorticoApplication(
            new ConfigurationReader(new Reader<ConfigurationReadOutcome>(_ => Success())),
            new PortfolioReader(new Reader<PortfolioReadOutcome>(_ => throw exception)));

        InvalidOperationException observed = await Assert.ThrowsAsync<InvalidOperationException>(() =>
            application.OpenWorkspaceAsync(
                new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        Assert.Same(exception, observed);
    }

    [Theory]
    [InlineData(HomePeriod.ThreeMonths, 2025, 12, 1)]
    [InlineData(HomePeriod.SixMonths, 2025, 9, 2)]
    [InlineData(HomePeriod.OneYear, 2025, 3, 1)]
    [InlineData(HomePeriod.TwoYears, 2024, 3, 1)]
    [InlineData(HomePeriod.FiveYears, 2021, 3, 2)]
    [InlineData(HomePeriod.All, 2020, 1, 1)]
    public async Task Home_UsesExactPeriodDaysAndClipsToVisibleBalances(
        HomePeriod period, int year, int month, int day)
    {
        PortfolioSnapshot snapshot = new([], [
            Balance("early", "Early", "Cash", 2020, 1, 1, 10m),
            Balance("late", "Late", "Cash", 2026, 3, 1, 20m),
            Balance("hidden", "Hidden", "Cash", 2010, 1, 1, 999m, hidden: true)
        ], []);
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(snapshot))
            .OpenWorkspaceAsync(new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        HomeReport report = workspace.Home(new HomeReportRequest(period));

        Assert.Equal(new DateOnly(year, month, day), report.Window!.Start);
        Assert.Equal(new DateOnly(2026, 3, 1), report.Window.End);
        Assert.Equal(report.Window.Start, report.NetWorthHistory[0].Date);
        Assert.Equal(report.Window.End, report.NetWorthHistory[^1].Date);
        Assert.All(report.NetWorthHistory.Skip(1).SkipLast(1), point =>
            Assert.Equal(DayOfWeek.Sunday, point.Date.DayOfWeek));
        Assert.Equal(30m, report.Closing!.NetWorth);
    }

    [Fact]
    public async Task Home_PreservesNetWorthGroupCashFlowAndSafetyValues()
    {
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(Snapshot()))
            .OpenWorkspaceAsync(new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        HomeReport report = workspace.Home(new HomeReportRequest(HomePeriod.ThreeMonths));

        Assert.Equal(new DateOnly(2025, 12, 1), report.Window!.Start);
        Assert.Equal(150m, report.Opening!.NetWorth);
        Assert.Equal(400m, report.Closing!.NetWorth);
        Assert.Equal(500m, report.Closing.Assets);
        Assert.Equal(-100m, report.Closing.Liabilities);
        Assert.Equal(250m, report.Closing.NetWorth - report.Opening.NetWorth);
        Assert.Equal(["Cash", "Debt"], report.Groups.Select(group => group.Group));
        Assert.Equal(200m, report.Groups[0].NetWorthChange);
        Assert.Equal(50m, report.Groups[1].NetWorthChange);
        Assert.True(report.Groups[1].LiabilitiesOnly);
        Assert.Equal(1000m, report.CashFlow.Income);
        Assert.Equal(300m, report.CashFlow.NetExpenses);
        Assert.Equal(700m, report.CashFlow.Surplus);
        Assert.Equal(70m, report.CashFlow.SavingsRatePercent);
        Assert.Equal(3, report.CashFlow.Months);
        Assert.Equal(5m, report.Safety.EmergencyFundMonthsCovered);
        Assert.Equal(50m, report.Safety.DebtPaidDown);
        Assert.Equal(50m, report.Safety.FinancialIndependenceProgressPercent);
    }

    [Fact]
    public async Task Home_CashFlowLookbackAndHiddenRowsAreIndependentOfBalancePeriod()
    {
        PortfolioSnapshot normal = Snapshot();
        PortfolioSnapshot snapshot = normal with
        {
            Transactions =
            [
                Transaction("january", 2026, 1, 1, "Prior income", 200m, TransactionKind.Income),
                .. normal.Transactions,
                Transaction("hidden", 2026, 2, 3, "Hidden income", 999m, TransactionKind.Income) with
                {
                    IsHidden = true
                }
            ]
        };
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(snapshot))
            .OpenWorkspaceAsync(new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        HomeReport oneMonth = workspace.Home(new HomeReportRequest(
            HomePeriod.All, CashFlowLookbackMonths: 1));
        HomeReport twoMonths = workspace.Home(new HomeReportRequest(
            HomePeriod.ThreeMonths, CashFlowLookbackMonths: 2));
        HomeReport threeMonths = workspace.Home(new HomeReportRequest(
            HomePeriod.ThreeMonths, CashFlowLookbackMonths: 3));

        Assert.Equal(0m, oneMonth.CashFlow.Income);
        Assert.Equal(1000m, twoMonths.CashFlow.Income);
        Assert.Equal(1200m, threeMonths.CashFlow.Income);
        Assert.Equal(300m, twoMonths.CashFlow.NetExpenses);
        Assert.Equal(oneMonth.Closing!.NetWorth, twoMonths.Closing!.NetWorth);
    }

    [Fact]
    public async Task Home_RegularIncomeUsesTheConfiguredExclusions()
    {
        FinanceSettings settings = Settings() with
        {
            IncomeSavings = new IncomeSavingsSettings("regular", 0.1m, ["Food"], [])
        };
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(Snapshot()), settings)
            .OpenWorkspaceAsync(new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        Assert.Equal(0m, workspace.Home().CashFlow.Income);
        Assert.Equal(1000m, workspace.Home(new HomeReportRequest(RegularIncome: false)).CashFlow.Income);
    }

    [Fact]
    public async Task Home_UsesAccountIdsForDuplicateNamesAndOmitsHiddenOrUnmappedAccounts()
    {
        PortfolioSnapshot snapshot = new([], [
            Balance("one", "Brokerage", "Investments", 2025, 12, 1, 100m),
            Balance("two", "Brokerage", "Investments", 2025, 12, 1, 300m),
            Balance("one", "Brokerage", "Investments", 2026, 3, 1, 150m),
            Balance("two", "Brokerage", "Investments", 2026, 3, 1, 200m),
            Balance("hidden", "Hidden", "Investments", 2026, 3, 1, 999m, hidden: true),
            Balance("unmapped", "Other", " ", 2026, 3, 1, 40m)
        ], []);
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(snapshot))
            .OpenWorkspaceAsync(new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        HomeReport report = workspace.Home(new HomeReportRequest(HomePeriod.ThreeMonths));

        Assert.Equal(390m, report.Closing!.NetWorth);
        Assert.Equal(3, report.VisibleAccountCount);
        HomeGroupMovement group = Assert.Single(report.Groups);
        Assert.Equal(350m, group.ClosingSignedBalance);
        Assert.Equal(400m, group.OpeningSignedBalance);
        Assert.Equal(-50m, group.NetWorthChange);
        Assert.Equal(["two", "one"], report.Accounts.Select(account => account.AccountId));
        Assert.Equal([-100m, 50m], report.Accounts.Select(account => account.NetWorthChange));
    }

    [Fact]
    public async Task Home_ClipsShortHistoryAndHandlesDateBoundary()
    {
        PortfolioSnapshot snapshot = new([], [
            new BalanceObservation("first", "First", "Cash", DateOnly.MinValue, TimeOnly.MinValue,
                10m, AccountClass.Asset, false),
            new BalanceObservation("latest", "Latest", "Cash", DateOnly.MinValue.AddDays(2), TimeOnly.MinValue,
                20m, AccountClass.Asset, false)
        ], []);
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(snapshot))
            .OpenWorkspaceAsync(new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        HomeReport report = workspace.Home(new HomeReportRequest(HomePeriod.FiveYears));

        Assert.Equal(DateOnly.MinValue, report.Window!.RequestedStart);
        Assert.Equal(DateOnly.MinValue, report.Window.Start);
        Assert.Equal(DateOnly.MinValue.AddDays(2), report.Window.End);
        Assert.Equal(10m, report.Opening!.NetWorth);
        Assert.Equal(30m, report.Closing!.NetWorth);
    }

    [Fact]
    public async Task Home_RejectsUnknownPeriodAsProgrammerError()
    {
        Workspace workspace = Opened(await Application(new PortfolioReadSuccess(Snapshot()))
            .OpenWorkspaceAsync(new ConfigurationSelection(), cancellationToken: TestContext.Current.CancellationToken));

        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.Home(new HomeReportRequest((HomePeriod)100)));
        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.Home(
            new HomeReportRequest(CashFlowLookbackMonths: 0)));
    }

    private static PorticoApplication Application(PortfolioReadOutcome portfolio, FinanceSettings? settings = null)
        => new(
            new ConfigurationReader(new Reader<ConfigurationReadOutcome>(_ => Success(settings))),
            new PortfolioReader(new Reader<PortfolioReadOutcome>(_ => portfolio)));

    private static ConfigurationReadSuccess Success(FinanceSettings? settings = null)
        => new(new WorkspaceConfiguration(settings ?? Settings(), new GoogleSheetsSourceRequest(
            PrivateLocation, PrivateLocation, PrivateLocation, PrivateLocation)));

    private static Workspace Opened(OpenWorkspaceOutcome outcome)
        => outcome switch
        {
            WorkspaceOpened opened => opened.GetWorkspace(),
            _ => throw new InvalidOperationException("Expected an open workspace.")
        };

    private static PorticoFailure Failed(OpenWorkspaceOutcome outcome)
        => outcome switch
        {
            PorticoFailure failure => failure,
            _ => throw new InvalidOperationException("Expected an open failure.")
        };

    private static PortfolioSnapshot Snapshot()
        => new(
            [
                Transaction("income", 2026, 2, 1, PrivateRow, 1000m, TransactionKind.Income),
                Transaction("expense", 2026, 2, 2, "Food", -300m, TransactionKind.Expense)
            ],
            [
                Balance("checking", "Checking", "Cash", 2025, 11, 1, 300m),
                Balance("card", "Card", "Debt", 2025, 11, 1, 150m, AccountClass.Liability),
                Balance("checking", "Checking", "Cash", 2025, 12, 20, 400m),
                Balance("card", "Card", "Debt", 2025, 12, 20, 140m, AccountClass.Liability),
                Balance("checking", "Checking", "Cash", 2026, 3, 1, 500m),
                Balance("card", "Card", "Debt", 2026, 3, 1, 100m, AccountClass.Liability)
            ],
            []);

    private static FinancialTransaction Transaction(
        string id, int year, int month, int day, string description, decimal amount, TransactionKind kind)
        => new(id, new DateOnly(year, month, day), "Food", "Needs", "Checking", description, amount, kind);

    private static BalanceObservation Balance(
        string id, string account, string group, int year, int month, int day, decimal value,
        AccountClass accountClass = AccountClass.Asset, bool hidden = false)
        => new(id, account, group, new DateOnly(year, month, day), TimeOnly.MinValue, value, accountClass, hidden);

    private static FinanceSettings Settings()
        => new(
            new LookbackSettings([3], 3),
            new ThresholdSettings(100m, 100m, 10m, 1),
            new IncomeSavingsSettings("regular", 0.1m, [], []),
            [],
            [],
            new SubscriptionSettings([], 0, 1, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(1, false, false, false),
            new FinancialSafetySettings(3, ["Cash"], [], 3, [], [], ["Debt"], [], null),
            new FinancialIndependenceSettings(0.05m, 0.04m, 1000m, 12, 10, [], []),
            new Dictionary<string, IReadOnlyList<string>>());

    private sealed class Reader<T>(Func<CancellationToken, T> read)
    {
        public int Calls { get; private set; }
        public ConfigurationSelection? Selection { get; set; }
        public SourceRequest? Source { get; set; }

        public Task<T> ReadAsync(CancellationToken cancellationToken)
        {
            Calls++;
            return Task.FromResult(read(cancellationToken));
        }
    }

    private sealed class ConfigurationReader(Reader<ConfigurationReadOutcome> reader) : IConfigurationReader
    {
        public Task<ConfigurationReadOutcome> ReadAsync(
            ConfigurationSelection selection, CancellationToken cancellationToken)
        {
            reader.Selection = selection;
            return reader.ReadAsync(cancellationToken);
        }
    }

    private sealed class PortfolioReader(Reader<PortfolioReadOutcome> reader) : IPortfolioReader
    {
        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
        {
            reader.Source = source;
            return reader.ReadAsync(cancellationToken);
        }
    }
}
