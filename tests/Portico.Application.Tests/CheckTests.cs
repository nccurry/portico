using System.Text.Json;
using Portico.Finance;

namespace Portico.Application.Tests;

public sealed class CheckTests
{
    private const string PrivateLocation = "https://example.invalid/private-sheet-token";
    private const string PrivateRow = "private financial row";

    [Fact]
    public async Task ConfigurationCheck_UsesOnlyConfigurationReader()
    {
        var configuration = new FakeConfigurationReader(_ => Success());
        var portfolio = new FakePortfolioReader(_ => throw new InvalidOperationException("Data must not be read."));
        var application = new PorticoApplication(configuration, portfolio);

        var selection = new ConfigurationSelection("selected.toml", "selected.secrets.toml");
        ConfigurationCheckOutcome outcome = await application.CheckConfigurationAsync(
            selection, TestContext.Current.CancellationToken);

        ConfigurationChecked checkedResult = outcome switch
        {
            ConfigurationChecked value => value,
            _ => throw new InvalidOperationException("Expected a checked configuration.")
        };
        Assert.Equal(SourceKind.GoogleSheets, checkedResult.Summary.Source);
        Assert.Same(selection, configuration.Selection);
        Assert.Equal(1, configuration.Calls);
        Assert.Equal(0, portfolio.Calls);
    }

    [Theory]
    [InlineData(0, 0, 0)]
    [InlineData(1, 1, 1)]
    public async Task DataCheck_ReturnsOnlyCounts(int transactions, int balances, int budgets)
    {
        ConfigurationReadSuccess read = Success();
        var portfolio = new FakePortfolioReader(_ => new PortfolioReadSuccess(
            Snapshot(transactions, balances, budgets)));
        var application = new PorticoApplication(new FakeConfigurationReader(_ => read), portfolio);

        DataCheckOutcome outcome = await application.CheckDataAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken);

        DataChecked checkedResult = outcome switch
        {
            DataChecked value => value,
            _ => throw new InvalidOperationException("Expected checked data.")
        };
        Assert.Equal(SourceKind.GoogleSheets, checkedResult.Summary.Source);
        Assert.Equal(transactions, checkedResult.Summary.Transactions);
        Assert.Equal(balances, checkedResult.Summary.Balances);
        Assert.Equal(budgets, checkedResult.Summary.Budgets);
        Assert.Equal(1, portfolio.Calls);
        Assert.Same(read.GetConfiguration().Source, portfolio.Source);
    }

    [Fact]
    public async Task DataCheck_StopsAfterConfigurationProblemsAndSortsThem()
    {
        PorticoProblem[] problems =
        [
            new("config.source", "Choose a supported source.", "source.kind"),
            new("config.version", "The version is unsupported.", "schema_version")
        ];
        var portfolio = new FakePortfolioReader(_ => throw new InvalidOperationException("Data must not be read."));
        var application = new PorticoApplication(
            new FakeConfigurationReader(_ => new PorticoFailure(problems)),
            portfolio);

        DataCheckOutcome outcome = await application.CheckDataAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken);

        PorticoFailure failure = Failure(outcome);
        Assert.Equal(["config.version", "config.source"], failure.Problems.Select(problem => problem.Code));
        Assert.Equal(0, portfolio.Calls);
    }

    [Fact]
    public async Task ConfigurationCheck_ReturnsAllConfigurationProblems()
    {
        var application = new PorticoApplication(
            new FakeConfigurationReader(_ => new PorticoFailure(
            [
                new PorticoProblem("config.source", "Choose a source.", "source.kind"),
                new PorticoProblem("config.version", "Unsupported version.", "schema_version")
            ])),
            new FakePortfolioReader(_ => throw new InvalidOperationException("Data must not be read.")));

        ConfigurationCheckOutcome outcome = await application.CheckConfigurationAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken);

        Assert.Equal(["config.version", "config.source"], Failure(outcome).Problems.Select(problem => problem.Code));
    }

    [Fact]
    public async Task DataCheck_PreservesRetryableSourceFailure()
    {
        var application = new PorticoApplication(
            new FakeConfigurationReader(_ => Success()),
            new FakePortfolioReader(_ => new PorticoFailure(
            [
                new PorticoProblem("source.unavailable", "The source is unavailable.", retryable: true)
            ])));

        DataCheckOutcome outcome = await application.CheckDataAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken);

        PorticoProblem problem = Assert.Single(Failure(outcome).Problems);
        Assert.Equal("source.unavailable", problem.Code);
        Assert.True(problem.Retryable);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public async Task Check_PreCancelledTokenReturnsTypedProblem(bool checkData)
    {
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        var configuration = new FakeConfigurationReader(_ => throw new InvalidOperationException("Reader must not run."));
        var application = new PorticoApplication(configuration, new FakePortfolioReader(_ => throw new InvalidOperationException()));

        PorticoFailure failure = checkData
            ? Failure(await application.CheckDataAsync(new ConfigurationSelection(), cancellation.Token))
            : Failure(await application.CheckConfigurationAsync(new ConfigurationSelection(), cancellation.Token));

        Assert.Equal("operation.cancelled", Assert.Single(failure.Problems).Code);
        Assert.Equal(0, configuration.Calls);
    }

    [Fact]
    public async Task DataCheck_MidReadCancellationReturnsTypedProblem()
    {
        using var cancellation = new CancellationTokenSource();
        var application = new PorticoApplication(
            new FakeConfigurationReader(_ => Success()),
            new FakePortfolioReader(_ =>
            {
                cancellation.Cancel();
                throw new OperationCanceledException(cancellation.Token);
            }));

        DataCheckOutcome outcome = await application.CheckDataAsync(new ConfigurationSelection(), cancellation.Token);

        Assert.Equal("operation.cancelled", Assert.Single(Failure(outcome).Problems).Code);
    }

    [Fact]
    public async Task ConfigurationCheck_MidReadCancellationReturnsTypedProblem()
    {
        using var cancellation = new CancellationTokenSource();
        var application = new PorticoApplication(
            new FakeConfigurationReader(_ =>
            {
                cancellation.Cancel();
                throw new OperationCanceledException(cancellation.Token);
            }),
            new FakePortfolioReader(_ => throw new InvalidOperationException()));

        ConfigurationCheckOutcome outcome = await application.CheckConfigurationAsync(
            new ConfigurationSelection(), cancellation.Token);

        Assert.Equal("operation.cancelled", Assert.Single(Failure(outcome).Problems).Code);
    }

    [Fact]
    public async Task UnrelatedCancellationExceptionReachesHost()
    {
        var application = new PorticoApplication(
            new FakeConfigurationReader(_ => throw new OperationCanceledException()),
            new FakePortfolioReader(_ => throw new InvalidOperationException()));

        await Assert.ThrowsAsync<OperationCanceledException>(
            () => application.CheckConfigurationAsync(
                new ConfigurationSelection(), TestContext.Current.CancellationToken));
    }

    [Fact]
    public async Task UnexpectedExceptionsAreNotReportedAsExpectedProblems()
    {
        var failure = new InvalidOperationException("private implementation detail");
        var application = new PorticoApplication(
            new FakeConfigurationReader(_ => throw failure),
            new FakePortfolioReader(_ => throw failure));

        InvalidOperationException observed = await Assert.ThrowsAsync<InvalidOperationException>(
            () => application.CheckConfigurationAsync(
                new ConfigurationSelection(), TestContext.Current.CancellationToken));

        Assert.Same(failure, observed);
    }

    [Fact]
    public async Task UnexpectedDataReaderExceptionReachesHost()
    {
        var failure = new InvalidOperationException("private implementation detail");
        var application = new PorticoApplication(
            new FakeConfigurationReader(_ => Success()),
            new FakePortfolioReader(_ => throw failure));

        InvalidOperationException observed = await Assert.ThrowsAsync<InvalidOperationException>(
            () => application.CheckDataAsync(new ConfigurationSelection(), TestContext.Current.CancellationToken));

        Assert.Same(failure, observed);
    }

    [Fact]
    public async Task CheckOutcomesAndReaderPayloadText_DoNotExposeSourceOrRows()
    {
        ConfigurationReadSuccess read = Success();
        var portfolio = new FakePortfolioReader(_ => new PortfolioReadSuccess(Snapshot(1, 0, 0)));
        var application = new PorticoApplication(new FakeConfigurationReader(_ => read), portfolio);

        ConfigurationCheckOutcome configuration = await application.CheckConfigurationAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken);
        DataCheckOutcome data = await application.CheckDataAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken);
        string publicText = string.Join(' ', configuration, data, JsonSerializer.Serialize(configuration), JsonSerializer.Serialize(data));
        string readerText = string.Join(' ', read, read.GetConfiguration(), read.GetConfiguration().Source,
            new PortfolioReadSuccess(Snapshot(1, 0, 0)));

        Assert.DoesNotContain(PrivateLocation, publicText, StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateRow, publicText, StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateLocation, readerText, StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateRow, readerText, StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateLocation, JsonSerializer.Serialize(read.GetConfiguration().Source), StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateLocation, JsonSerializer.Serialize(read), StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateRow, JsonSerializer.Serialize(new PortfolioReadSuccess(Snapshot(1, 0, 0))), StringComparison.Ordinal);

        ConfigurationReadOutcome configurationRead = read;
        PortfolioReadOutcome portfolioRead = new PortfolioReadSuccess(Snapshot(1, 0, 0));
        Assert.DoesNotContain(PrivateLocation, JsonSerializer.Serialize(configurationRead), StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateRow, JsonSerializer.Serialize(portfolioRead), StringComparison.Ordinal);
    }

    [Fact]
    public void SourceRequests_KeepPrivateLocationsOutOfDefaultJson()
    {
        var local = new LocalCsvSourceRequest("C:/private/finance");
        var google = new GoogleSheetsSourceRequest(
            "transactions-secret", "balance-secret", "categories-secret", "accounts-secret");

        Assert.Equal("C:/private/finance", local.GetDirectory());
        Assert.Equal("transactions-secret", google.UrlFor("transactions"));
        Assert.Equal("balance-secret", google.UrlFor("balance_history"));
        Assert.Equal("categories-secret", google.UrlFor("categories"));
        Assert.Equal("accounts-secret", google.UrlFor("accounts"));
        Assert.Throws<ArgumentOutOfRangeException>(() => google.UrlFor("unknown"));
        Assert.DoesNotContain("private", JsonSerializer.Serialize(local), StringComparison.Ordinal);
        Assert.DoesNotContain("secret", JsonSerializer.Serialize(google), StringComparison.Ordinal);
    }

    [Fact]
    public void PublicProblems_RejectBlankAndMultilineText()
    {
        Assert.Throws<ArgumentException>(() => new PorticoProblem("", "Safe message."));
        Assert.Throws<ArgumentException>(() => new PorticoProblem("code", " "));
        Assert.Throws<ArgumentException>(() => new PorticoProblem("code", "unsafe\nsecond line"));
        Assert.Throws<ArgumentException>(() => new PorticoProblem("code", "Safe message.", "source\rkind"));
    }

    [Fact]
    public void Failure_RequiresProblemsAndSortsADefensiveCopy()
    {
        Assert.Throws<ArgumentException>(() => new PorticoFailure([]));
        var input = new List<PorticoProblem>
        {
            new("later", "Later problem.", "source.kind"),
            new("first", "First problem.", "schema_version")
        };
        var failure = new PorticoFailure(input);
        input.Add(new("added", "Added problem."));

        Assert.Equal(["first", "later"], failure.Problems.Select(problem => problem.Code));
    }

    private static ConfigurationReadSuccess Success()
        => new(new WorkspaceConfiguration(Settings(), ReportWorkspaceFixture.Choices(), new GoogleSheetsSourceRequest(
            PrivateLocation, PrivateLocation, PrivateLocation, PrivateLocation)));

    private static PorticoFailure Failure(ConfigurationCheckOutcome outcome)
        => outcome switch
        {
            PorticoFailure failure => failure,
            _ => throw new InvalidOperationException("Expected a configuration failure.")
        };

    private static PorticoFailure Failure(DataCheckOutcome outcome)
        => outcome switch
        {
            PorticoFailure failure => failure,
            _ => throw new InvalidOperationException("Expected a data failure.")
        };

    private static PortfolioSnapshot Snapshot(int transactions, int balances, int budgets)
        => new(
            transactions == 0 ? [] : [new FinancialTransaction("t1", new DateOnly(2026, 1, 1), "Food", "Needs", "Bank", PrivateRow, -12m, TransactionKind.Expense)],
            balances == 0 ? [] : [new BalanceObservation("a1", "Bank", "Cash", new DateOnly(2026, 1, 1), new TimeOnly(12, 0), 20m, AccountClass.Asset, false)],
            budgets == 0 ? [] : [new BudgetEntry(new YearMonth(2026, 1), "Food", "Needs", TransactionKind.Expense, 100m, false)]);

    private static FinanceSettings Settings()
        => new(
            new ThresholdSettings(100m, 100m, 10m, 1),
            new IncomeSavingsSettings(0.1m, [], []),
            [],
            new SubscriptionSettings([], 0, 1, []),
            new BudgetSettings(12),
            new DataHealthSettings(1, false, false, false),
            new FinancialSafetySettings(3, [], [], 12, [], [], [], [], null),
            new FinancialIndependenceSettings(0.05m, 0.04m, 100m, 12, 10, [], []),
            new Dictionary<string, IReadOnlyList<string>>());

    private sealed class FakeConfigurationReader(Func<CancellationToken, ConfigurationReadOutcome> read) : IConfigurationReader
    {
        public int Calls { get; private set; }

        public ConfigurationSelection? Selection { get; private set; }

        public Task<ConfigurationReadOutcome> ReadAsync(ConfigurationSelection selection, CancellationToken cancellationToken)
        {
            Calls++;
            Selection = selection;
            return Task.FromResult(read(cancellationToken));
        }
    }

    private sealed class FakePortfolioReader(Func<CancellationToken, PortfolioReadOutcome> read) : IPortfolioReader
    {
        public int Calls { get; private set; }

        public SourceRequest? Source { get; private set; }

        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
        {
            Calls++;
            Source = source;
            return Task.FromResult(read(cancellationToken));
        }
    }
}
