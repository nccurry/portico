using Portico.Application;
using Portico.Configuration;
using Portico.Data;

namespace Portico.Data.Tests;

public sealed class FoundationInputSmokeTests
{
    [Fact]
    public async Task NewDemoConfiguration_OpensThroughApplicationFromAnotherWorkingDirectory()
    {
        string root = FindRepositoryRoot();
        using var client = new HttpClient(new NoNetworkHandler());
        var application = new PorticoApplication(
            new TomlConfigurationReader(Path.GetTempPath()),
            new DataPortfolioReader(client));
        var selection = new ConfigurationSelection(Path.Combine(root, "portico.toml"));
        CancellationToken cancellationToken = TestContext.Current.CancellationToken;

        DataCheckOutcome checkedOutcome = await application.CheckDataAsync(selection, cancellationToken);
        DataChecked checkedData = checkedOutcome switch
        {
            DataChecked value => value,
            PorticoFailure failure => throw new InvalidOperationException(
                $"Demo data check failed: {string.Join(", ", failure.Problems.Select(problem => $"{problem.Code}: {problem.Message}"))}"),
            _ => throw new InvalidOperationException("Expected a data check result.")
        };
        Assert.Equal(SourceKind.LocalCsv, checkedData.Summary.Source);
        Assert.Equal(986, checkedData.Summary.Transactions);
        Assert.Equal(432, checkedData.Summary.Balances);
        Assert.Equal(1344, checkedData.Summary.Budgets);

        OpenWorkspaceOutcome opened = await application.OpenWorkspaceAsync(selection, cancellationToken: cancellationToken);
        Workspace workspace = opened switch
        {
            WorkspaceOpened value => value.GetWorkspace(),
            PorticoFailure failure => throw new InvalidOperationException(
                $"Demo workspace failed: {string.Join(", ", failure.Problems.Select(problem => $"{problem.Code}: {problem.Message}"))}"),
            _ => throw new InvalidOperationException("Expected an opened workspace.")
        };
        Assert.NotNull(workspace.Home().Closing);
    }

    private static string FindRepositoryRoot()
    {
        for (DirectoryInfo? directory = new(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            if (File.Exists(Path.Combine(directory.FullName, "portico.toml"))
                && Directory.Exists(Path.Combine(directory.FullName, "demo", "data")))
                return directory.FullName;
        }

        throw new InvalidOperationException("The synthetic Portico demo was not found.");
    }

    private sealed class NoNetworkHandler : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
            => throw new InvalidOperationException("The local demo must not make HTTP requests.");
    }
}
