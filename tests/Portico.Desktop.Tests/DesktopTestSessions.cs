using Portico.Application;
using Portico.Configuration;
using Portico.Data;
using Portico.Desktop;
using Portico.Finance;

namespace Portico.Desktop.Tests;

internal static class DesktopTestSessions
{
    public static FinanceSettings LoadSettings(string repositoryRoot)
    {
        ConfigurationReadOutcome read = new TomlConfigurationReader(repositoryRoot)
            .ReadAsync(new ConfigurationSelection(Path.Combine(repositoryRoot, "portico.toml")), default)
            .GetAwaiter().GetResult();
        return read switch
        {
            ConfigurationReadSuccess success => success.GetConfiguration().Settings,
            _ => throw new InvalidOperationException("Could not load the demo settings.")
        };
    }

    public static DashboardDefinition LoadDefinition(string repositoryRoot)
    {
        DashboardReadOutcome read = DashboardConfigurationReader.Read(
            Path.Combine(repositoryRoot, "dashboard.toml"));
        return read switch
        {
            DashboardReadSuccess success => success.Definition,
            _ => throw new InvalidOperationException("Could not load the demo dashboard.")
        };
    }

    public static async Task<PortfolioSnapshot> LoadSnapshotAsync(string repositoryRoot)
    {
        using var httpClient = new HttpClient();
        PortfolioReadOutcome read = await new DataPortfolioReader(httpClient).ReadAsync(
            new LocalCsvSourceRequest(Path.Combine(repositoryRoot, "demo", "data")), default);
        return read switch
        {
            PortfolioReadSuccess success => success.GetSnapshot(),
            _ => throw new InvalidOperationException("Could not load the demo data.")
        };
    }

    public static DashboardSession Create(
        PortfolioSnapshot snapshot,
        FinanceSettings settings,
        DashboardDefinition definition,
        DateOnly? asOfDate = null)
    {
        var application = new PorticoApplication(
            new FixedConfigurationReader(settings), new FixedPortfolioReader(snapshot));
        OpenWorkspaceOutcome opened = application.OpenWorkspaceAsync(
            new ConfigurationSelection(), asOfDate).GetAwaiter().GetResult();
        Workspace workspace = opened switch
        {
            WorkspaceOpened success => success.GetWorkspace(),
            _ => throw new InvalidOperationException("Could not open the test workspace.")
        };
        return new DashboardSession(workspace, definition);
    }

    private sealed class FixedConfigurationReader(FinanceSettings settings) : IConfigurationReader
    {
        public Task<ConfigurationReadOutcome> ReadAsync(
            ConfigurationSelection selection, CancellationToken cancellationToken)
            => Task.FromResult<ConfigurationReadOutcome>(new ConfigurationReadSuccess(
                new WorkspaceConfiguration(settings, new LocalCsvSourceRequest("unused"))));
    }

    private sealed class FixedPortfolioReader(PortfolioSnapshot snapshot) : IPortfolioReader
    {
        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
            => Task.FromResult<PortfolioReadOutcome>(new PortfolioReadSuccess(snapshot));
    }
}
