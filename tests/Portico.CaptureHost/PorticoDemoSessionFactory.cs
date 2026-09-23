using Portico.Application;
using Portico.Configuration;
using Portico.Data;
using Portico.Desktop;

namespace Portico.CaptureHost;

/// <summary>Loads the fixed synthetic dashboard session used by local captures.</summary>
public static class PorticoDemoSessionFactory
{
    /// <summary>Fixed date supplied to dashboard reports during every capture run.</summary>
    public static readonly DateOnly CaptureDate = new(2026, 8, 1);

    /// <summary>Loads the checked-in demo data from the repository that started the capture process.</summary>
    public static DashboardSession Create()
        => Create(FindRepositoryRoot());

    /// <summary>Loads the checked-in demo data from an explicit repository root.</summary>
    public static DashboardSession Create(string repositoryRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);

        string configPath = Path.Combine(repositoryRoot, "portico.toml");
        string dashboardPath = Path.Combine(repositoryRoot, "dashboard.toml");
        using var httpClient = new HttpClient();
        var application = new PorticoApplication(
            new TomlConfigurationReader(repositoryRoot),
            new DataPortfolioReader(httpClient));
        OpenWorkspaceOutcome opened = application.OpenWorkspaceAsync(
            new ConfigurationSelection(configPath), CaptureDate).GetAwaiter().GetResult();
        Workspace workspace = opened switch
        {
            WorkspaceOpened success => success.GetWorkspace(),
            PorticoFailure failure => throw new InvalidOperationException(failure.Problems[0].Message),
            _ => throw new InvalidOperationException("Could not open the demo workspace.")
        };
        DashboardReadOutcome read = DashboardConfigurationReader.Read(dashboardPath, workspace.ReportChoices);
        DashboardDefinition definition = read switch
        {
            DashboardReadSuccess success => success.Definition,
            PorticoFailure failure => throw new InvalidOperationException(failure.Problems[0].Message),
            _ => throw new InvalidOperationException("Could not read the demo dashboard.")
        };

        return new DashboardSession(workspace, definition);
    }

    private static string FindRepositoryRoot()
    {
        var current = new DirectoryInfo(Path.GetFullPath(Directory.GetCurrentDirectory()));
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "Portico.Roci.slnx"))
                && File.Exists(Path.Combine(current.FullName, "portico.toml"))
                && File.Exists(Path.Combine(current.FullName, "dashboard.toml")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        throw new DirectoryNotFoundException("Could not find the Portico repository root.");
    }
}
