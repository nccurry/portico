using Portico.Finance;

namespace Portico.Application.Tests;

internal static class ReportWorkspaceFixture
{
    public static async Task<Workspace> Open(
        PortfolioSnapshot snapshot,
        FinanceSettings? settings = null,
        DateOnly? asOfDate = null)
    {
        var application = new PorticoApplication(
            new ConfigurationReader(settings ?? Settings()),
            new PortfolioReader(snapshot));
        OpenWorkspaceOutcome outcome = await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), asOfDate, TestContext.Current.CancellationToken);
        return outcome switch
        {
            WorkspaceOpened opened => opened.GetWorkspace(),
            _ => throw new InvalidOperationException("Expected an open workspace.")
        };
    }

    public static FinancialTransaction Transaction(
        string id, int year, int month, int day, string group, string category,
        decimal amount, TransactionKind kind = TransactionKind.Expense, bool hidden = false)
        => new(id, new DateOnly(year, month, day), category, group, "Checking", id, amount, kind, hidden);

    public static BudgetEntry Budget(
        int year, int month, string group, string category, decimal amount, bool hidden = false)
        => new(new YearMonth(year, month), category, group, TransactionKind.Expense, amount, hidden);

    public static FinanceSettings Settings()
        => new(
            new LookbackSettings([1, 3, 12], 3),
            new ThresholdSettings(100m, 100m, 10m, 1),
            new IncomeSavingsSettings("regular", 25m, ["Gift"], ["Transfer"]),
            [new TransactionSetDefinition("all", "All", [], [], [], [], [], [], [])],
            [new FilterSetDefinition("spending", ["all"], "all")],
            new SubscriptionSettings([], 0, 1, [], []),
            new BudgetSettings(3),
            new DataHealthSettings(1, false, false, false),
            new FinancialSafetySettings(3, ["Cash"], [], 3, [], [], ["Debt"], [], null),
            new FinancialIndependenceSettings(0.05m, 0.04m, 1000m, 12, 10, [], []),
            new Dictionary<string, IReadOnlyList<string>>());

    private sealed class ConfigurationReader(FinanceSettings settings) : IConfigurationReader
    {
        public Task<ConfigurationReadOutcome> ReadAsync(
            ConfigurationSelection selection, CancellationToken cancellationToken)
            => Task.FromResult<ConfigurationReadOutcome>(new ConfigurationReadSuccess(
                new WorkspaceConfiguration(settings, new LocalCsvSourceRequest("fixture"))));
    }

    private sealed class PortfolioReader(PortfolioSnapshot snapshot) : IPortfolioReader
    {
        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
            => Task.FromResult<PortfolioReadOutcome>(new PortfolioReadSuccess(snapshot));
    }
}
