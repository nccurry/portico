using System.Text.Json;
using Portico.Application;
using Portico.Cli;
using Portico.Finance;

namespace Portico.Cli.Tests;

public sealed class CheckCommandTests
{
    private const string PrivateLocation = "https://example.invalid/private-sheet-token";
    private const string PrivateRow = "private financial row";

    [Fact]
    public async Task ConfigCheckUsesOnlyConfigurationReaderAndWritesOneJsonDocument()
    {
        var configuration = new FakeConfigurationReader(_ => ValidConfiguration());
        var portfolio = new FakePortfolioReader(_ => throw new InvalidOperationException("Data must not be read."));
        var command = PorticoCommandLine.Parse(["config", "check", "--output", "json"]);

        Result result = await Run(command, configuration, portfolio, TestContext.Current.CancellationToken);

        Assert.Equal(0, result.ExitCode);
        Assert.Equal("", result.Error);
        Assert.Equal(1, configuration.Calls);
        Assert.Equal(0, portfolio.Calls);
        using JsonDocument document = JsonDocument.Parse(result.Output);
        JsonElement root = document.RootElement;
        Assert.Equal("portico.command-result.v1", root.GetProperty("schema").GetString());
        Assert.Equal("config-check", root.GetProperty("command").GetString());
        Assert.Equal("success", root.GetProperty("outcome").GetString());
        Assert.Equal("google_sheets", root.GetProperty("details").GetProperty("source").GetString());
        Assert.Equal(0, root.GetProperty("problems").GetArrayLength());
        Assert.DoesNotContain(PrivateLocation, result.Output, StringComparison.Ordinal);
        Assert.Single(result.Output.Trim().Split('\n'));
    }

    [Theory]
    [InlineData("data", "check", "data-check")]
    [InlineData("doctor", "", "doctor")]
    public async Task DataChecksWriteStableCountsWithoutPrivateRows(string first, string second, string jsonCommand)
    {
        var portfolio = new FakePortfolioReader(_ => new PortfolioReadSuccess(Snapshot()));
        string[] args = second.Length == 0 ? [first, "--output", "json"] : [first, second, "--output", "json"];

        Result result = await Run(PorticoCommandLine.Parse(args),
            new FakeConfigurationReader(_ => ValidConfiguration()), portfolio, TestContext.Current.CancellationToken);

        Assert.Equal(0, result.ExitCode);
        Assert.Equal("", result.Error);
        Assert.Equal(1, portfolio.Calls);
        using JsonDocument document = JsonDocument.Parse(result.Output);
        JsonElement root = document.RootElement;
        Assert.Equal(jsonCommand, root.GetProperty("command").GetString());
        JsonElement details = root.GetProperty("details");
        Assert.Equal(1, details.GetProperty("transactions").GetInt32());
        Assert.Equal(1, details.GetProperty("balances").GetInt32());
        Assert.Equal(1, details.GetProperty("budgets").GetInt32());
        Assert.DoesNotContain(PrivateRow, result.Output, StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateLocation, result.Output, StringComparison.Ordinal);
    }

    [Fact]
    public async Task DoctorWritesTextResultOnlyToStdout()
    {
        Result result = await Run(PorticoCommandLine.Parse(["doctor"]),
            new FakeConfigurationReader(_ => ValidConfiguration()),
            new FakePortfolioReader(_ => new PortfolioReadSuccess(Snapshot())), TestContext.Current.CancellationToken);

        Assert.Equal(0, result.ExitCode);
        Assert.Equal("", result.Error);
        Assert.Equal("Portico doctor: ready\nSource: google_sheets\nTransactions: 1\nBalances: 1\nBudgets: 1\n",
            result.Output.Replace("\r\n", "\n", StringComparison.Ordinal));
    }

    [Fact]
    public async Task ConfigCheckWritesTextResultOnlyToStdout()
    {
        Result result = await Run(PorticoCommandLine.Parse(["config", "check"]),
            new FakeConfigurationReader(_ => ValidConfiguration()),
            new FakePortfolioReader(_ => throw new InvalidOperationException("Data must not be read.")),
            TestContext.Current.CancellationToken);

        Assert.Equal(0, result.ExitCode);
        Assert.Empty(result.Error);
        Assert.Equal("Portico config check: ready\nSource: google_sheets\n",
            result.Output.Replace("\r\n", "\n", StringComparison.Ordinal));
    }

    [Fact]
    public async Task DataCheckWritesTextResultOnlyToStdout()
    {
        Result result = await Run(PorticoCommandLine.Parse(["data", "check"]),
            new FakeConfigurationReader(_ => ValidConfiguration()),
            new FakePortfolioReader(_ => new PortfolioReadSuccess(Snapshot())),
            TestContext.Current.CancellationToken);

        Assert.Equal(0, result.ExitCode);
        Assert.Empty(result.Error);
        Assert.Equal("Portico data check: ready\nSource: google_sheets\nTransactions: 1\nBalances: 1\nBudgets: 1\n",
            result.Output.Replace("\r\n", "\n", StringComparison.Ordinal));
    }

    [Fact]
    public async Task ConfigProblemsStopBeforeDataAndWriteOneOrderedFailureDocument()
    {
        var portfolio = new FakePortfolioReader(_ => throw new InvalidOperationException("Data must not be read."));
        var failure = new PorticoFailure([
            new PorticoProblem("config.missing-secret", "A setting is missing.", "sheets.transactions"),
            new PorticoProblem("config.unknown-key", "The setting is not supported.", "weekly_summary")
        ]);

        Result result = await Run(PorticoCommandLine.Parse(["doctor", "--output", "json"]),
            new FakeConfigurationReader(_ => failure), portfolio, TestContext.Current.CancellationToken);

        Assert.Equal(3, result.ExitCode);
        Assert.Equal("", result.Error);
        Assert.Equal(0, portfolio.Calls);
        using JsonDocument document = JsonDocument.Parse(result.Output);
        JsonElement root = document.RootElement;
        Assert.Equal("failure", root.GetProperty("outcome").GetString());
        Assert.Equal(JsonValueKind.Null, root.GetProperty("details").ValueKind);
        JsonElement problems = root.GetProperty("problems");
        Assert.Equal(2, problems.GetArrayLength());
        Assert.Equal("sheets.transactions", problems[0].GetProperty("field").GetString());
        Assert.False(problems[0].GetProperty("retryable").GetBoolean());
        Assert.Equal("weekly_summary", problems[1].GetProperty("field").GetString());
        Assert.DoesNotContain(PrivateLocation, result.Output, StringComparison.Ordinal);
        Assert.Single(result.Output.Trim().Split('\n'));
    }

    [Theory]
    [InlineData("data.missing-file", false, 4)]
    [InlineData("source.unavailable", false, 4)]
    [InlineData("source.unavailable", true, 5)]
    [InlineData("operation.cancelled", true, 5)]
    public async Task DataProblemsMapToStableExitCodes(string code, bool retryable, int exitCode)
    {
        var failure = new PorticoFailure([new PorticoProblem(code, "A safe problem.", retryable: retryable)]);

        Result result = await Run(PorticoCommandLine.Parse(["data", "check"]),
            new FakeConfigurationReader(_ => ValidConfiguration()), new FakePortfolioReader(_ => failure),
            TestContext.Current.CancellationToken);

        Assert.Equal(exitCode, result.ExitCode);
        Assert.Equal("", result.Error);
        Assert.Contains($"- {code}: A safe problem.", result.Output, StringComparison.Ordinal);
    }

    [Fact]
    public async Task PreCancelledCheckWritesJsonFailure()
    {
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        var configuration = new FakeConfigurationReader(_ => throw new InvalidOperationException("Reader must not run."));

        Result result = await Run(PorticoCommandLine.Parse(["config", "check", "--output", "json"]),
            configuration, new FakePortfolioReader(_ => throw new InvalidOperationException()), cancellation.Token);

        Assert.Equal(5, result.ExitCode);
        Assert.Equal(0, configuration.Calls);
        Assert.Equal("", result.Error);
        using JsonDocument document = JsonDocument.Parse(result.Output);
        Assert.Equal("operation.cancelled", document.RootElement.GetProperty("problems")[0].GetProperty("code").GetString());
    }

    [Fact]
    public async Task UnexpectedReaderFailureUsesOnlySafeHostDiagnostic()
    {
        Result result = await Run(PorticoCommandLine.Parse(["doctor", "--output", "json"]),
            new FakeConfigurationReader(_ => throw new InvalidOperationException(PrivateLocation)),
            new FakePortfolioReader(_ => throw new InvalidOperationException()), TestContext.Current.CancellationToken);

        Assert.Equal(1, result.ExitCode);
        Assert.Equal("", result.Output);
        Assert.Contains("internal error", result.Error, StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateLocation, result.Error, StringComparison.Ordinal);
    }

    [Fact]
    public void UsageAndRunFailuresUseCliPolicy()
    {
        var error = new StringWriter();
        Assert.Equal(2, PorticoCli.WriteUsageError(new CommandLineException("--output must be text or json."), error));
        Assert.Contains("Argument error", error.ToString(), StringComparison.Ordinal);
        var output = new StringWriter();
        Assert.Equal(3, PorticoCli.WriteRunFailure(new PorticoFailure([
            new PorticoProblem("config.file-not-found", "The selected file does not exist.", "config")
        ]), output));
        Assert.Contains("Portico run: not ready", output.ToString(), StringComparison.Ordinal);
    }

    [Fact]
    public void ExitCodePrefersEarlierFailureStage()
    {
        Assert.Equal(3, PorticoCli.ExitCode(new PorticoFailure([
            new PorticoProblem("source.timeout", "Timed out.", retryable: true),
            new PorticoProblem("config.invalid-value", "Invalid setting.")
        ])));
        Assert.Equal(4, PorticoCli.ExitCode(new PorticoFailure([
            new PorticoProblem("source.timeout", "Timed out.", retryable: true),
            new PorticoProblem("data.invalid", "Invalid data.")
        ])));
    }

    private static async Task<Result> Run(
        PorticoCommand command,
        IConfigurationReader configuration,
        IPortfolioReader portfolio,
        CancellationToken cancellationToken)
    {
        var output = new StringWriter();
        var error = new StringWriter();
        int exitCode = await PorticoCli.RunCheckAsync(command,
            new PorticoApplication(configuration, portfolio), output, error, cancellationToken);
        return new Result(exitCode, output.ToString(), error.ToString());
    }

    private static ConfigurationReadSuccess ValidConfiguration()
        => new(new WorkspaceConfiguration(Settings(), new GoogleSheetsSourceRequest(
            PrivateLocation, PrivateLocation, PrivateLocation, PrivateLocation)));

    private static PortfolioSnapshot Snapshot()
        => new(
            [new FinancialTransaction("t1", new DateOnly(2026, 1, 1), "Food", "Needs", "Bank", PrivateRow, -12m, TransactionKind.Expense)],
            [new BalanceObservation("a1", "Bank", "Cash", new DateOnly(2026, 1, 1), new TimeOnly(12, 0), 20m, AccountClass.Asset, false)],
            [new BudgetEntry(new YearMonth(2026, 1), "Food", "Needs", TransactionKind.Expense, 100m, false)]);

    private static FinanceSettings Settings()
        => new(
            new LookbackSettings([12], 12),
            new ThresholdSettings(100m, 100m, 10m, 1),
            new IncomeSavingsSettings("regular", 0.1m, [], []),
            [], [],
            new SubscriptionSettings([], 0, 1, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(1, false, false, false),
            new FinancialSafetySettings(3, [], [], 12, [], [], [], [], null),
            new FinancialIndependenceSettings(0.05m, 0.04m, 100m, 12, 10, [], []),
            new Dictionary<string, IReadOnlyList<string>>());

    private sealed record Result(int ExitCode, string Output, string Error);

    private sealed class FakeConfigurationReader(Func<CancellationToken, ConfigurationReadOutcome> read) : IConfigurationReader
    {
        public int Calls { get; private set; }

        public Task<ConfigurationReadOutcome> ReadAsync(ConfigurationSelection selection, CancellationToken cancellationToken)
        {
            Calls++;
            return Task.FromResult(read(cancellationToken));
        }
    }

    private sealed class FakePortfolioReader(Func<CancellationToken, PortfolioReadOutcome> read) : IPortfolioReader
    {
        public int Calls { get; private set; }

        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
        {
            Calls++;
            return Task.FromResult(read(cancellationToken));
        }
    }
}
