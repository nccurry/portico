using Portico.Application;
using Portico.Finance;

namespace Portico.Desktop.Tests;

internal static class MapperWorkspaceFixture
{
    public static async Task<Workspace> Open(PortfolioSnapshot snapshot, DateOnly? asOfDate = null)
    {
        var application = new PorticoApplication(new ConfigurationReader(), new PortfolioReader(snapshot));
        OpenWorkspaceOutcome outcome = await application.OpenWorkspaceAsync(
            new ConfigurationSelection(), asOfDate, TestContext.Current.CancellationToken);
        return outcome switch
        {
            WorkspaceOpened opened => opened.GetWorkspace(),
            _ => throw new InvalidOperationException("Expected an open workspace.")
        };
    }

    public static FinancialTransaction Transaction(
        string id, DateOnly date, string group, string category, decimal amount, bool hidden = false)
        => new(id, date, category, group, "Checking", id, amount, TransactionKind.Expense, hidden);

    public static BudgetEntry Budget(string group, string category, decimal amount)
        => new(new YearMonth(2026, 3), category, group, TransactionKind.Expense, amount, false);

    public static BalanceObservation Balance(string id, DateOnly date, decimal amount)
        => new(id, id, "Cash", date, TimeOnly.MinValue, amount, AccountClass.Asset, false);

    private static FinanceSettings Settings() => new(
        new LookbackSettings([3], 3),
        new ThresholdSettings(100m, 100m, 10m, 1),
        new IncomeSavingsSettings("regular", 0.1m, [], []),
        [], [],
        new SubscriptionSettings([], 0, 1, [], []),
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
                new WorkspaceConfiguration(Settings(), new LocalCsvSourceRequest("unused"))));
    }

    private sealed class PortfolioReader(PortfolioSnapshot snapshot) : IPortfolioReader
    {
        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
            => Task.FromResult<PortfolioReadOutcome>(new PortfolioReadSuccess(snapshot));
    }
}
