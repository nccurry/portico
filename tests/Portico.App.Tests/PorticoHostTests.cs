using Portico.Application;
using Portico.Finance;

namespace Portico.App.Tests;

public sealed class PorticoHostTests
{
    [Fact]
    public async Task ParsedRun_OpensWorkspaceAndHandsItToDesktop()
    {
        var configuration = new FakeConfigurationReader();
        var portfolio = new FakePortfolioReader();
        Workspace? opened = null;
        string? dashboardPath = null;
        var host = new PorticoHost(
            new PorticoApplication(configuration, portfolio),
            (workspace, path, _, _, _) =>
            {
                opened = workspace;
                dashboardPath = path;
                return Task.FromResult(0);
            });
        var output = new StringWriter();
        var error = new StringWriter();

        int exitCode = await host.RunAsync(
            ["run", "--config", "selected.toml", "--secrets", "selected.secrets.toml", "--dashboard", "layout.toml"],
            output, error, TestContext.Current.CancellationToken);

        Assert.Equal(0, exitCode);
        Assert.NotNull(opened);
        Assert.Equal("layout.toml", dashboardPath);
        Assert.Equal("selected.toml", configuration.Selection?.ConfigurationPath);
        Assert.Equal("selected.secrets.toml", configuration.Selection?.SecretsPath);
        Assert.Equal(1, configuration.Calls);
        Assert.Equal(1, portfolio.Calls);
        Assert.Empty(output.ToString());
        Assert.Empty(error.ToString());
    }

    [Fact]
    public async Task ParsedCheck_UsesApplicationAndDoesNotStartDesktop()
    {
        var configuration = new FakeConfigurationReader();
        var portfolio = new FakePortfolioReader();
        var host = new PorticoHost(
            new PorticoApplication(configuration, portfolio),
            (_, _, _, _, _) => throw new InvalidOperationException("Desktop must not start."));
        var output = new StringWriter();
        var error = new StringWriter();

        int exitCode = await host.RunAsync(
            ["config", "check", "--output", "json"], output, error,
            TestContext.Current.CancellationToken);

        Assert.Equal(0, exitCode);
        Assert.Contains("\"command\":\"config-check\"", output.ToString(), StringComparison.Ordinal);
        Assert.Empty(error.ToString());
        Assert.Equal(1, configuration.Calls);
        Assert.Equal(0, portfolio.Calls);
    }

    [Fact]
    public async Task UsageFailure_DoesNotReadConfigurationOrStartDesktop()
    {
        var configuration = new FakeConfigurationReader();
        var host = new PorticoHost(
            new PorticoApplication(configuration, new FakePortfolioReader()),
            (_, _, _, _, _) => throw new InvalidOperationException("Desktop must not start."));
        var output = new StringWriter();
        var error = new StringWriter();

        int exitCode = await host.RunAsync(
            ["run", "--output", "json"], output, error,
            TestContext.Current.CancellationToken);

        Assert.Equal(2, exitCode);
        Assert.Empty(output.ToString());
        Assert.Contains("Argument error", error.ToString(), StringComparison.Ordinal);
        Assert.Equal(0, configuration.Calls);
    }

    private sealed class FakeConfigurationReader : IConfigurationReader
    {
        public int Calls { get; private set; }

        public ConfigurationSelection? Selection { get; private set; }

        public Task<ConfigurationReadOutcome> ReadAsync(
            ConfigurationSelection selection, CancellationToken cancellationToken)
        {
            Calls++;
            Selection = selection;
            return Task.FromResult<ConfigurationReadOutcome>(new ConfigurationReadSuccess(
                new WorkspaceConfiguration(Settings(), new LocalCsvSourceRequest("unused"))));
        }
    }

    private sealed class FakePortfolioReader : IPortfolioReader
    {
        public int Calls { get; private set; }

        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
        {
            Calls++;
            return Task.FromResult<PortfolioReadOutcome>(new PortfolioReadSuccess(new PortfolioSnapshot([], [], [])));
        }
    }

    private static FinanceSettings Settings()
        => new(
            new LookbackSettings([3, 6, 12], 12),
            new ThresholdSettings(3000m, 20000m, 10m, 1),
            new IncomeSavingsSettings("regular", 20m, [], []),
            [new TransactionSetDefinition("all", "All", [], [], [], [], [], [], [])],
            [new FilterSetDefinition("spending", ["all"], "all"),
                new FilterSetDefinition("year_over_year", ["all"], "all")],
            new SubscriptionSettings([], 80, 45, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 50, [], []),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal));
}
