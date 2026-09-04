using Portico.Adapters;
using Portico.Dashboard;
using Portico.Finance;

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

        string configPath = Path.Combine(repositoryRoot, "portico-demo.toml");
        string dashboardPath = Path.Combine(repositoryRoot, "dashboard.toml");
        string dataPath = Path.Combine(repositoryRoot, "demo", "data");
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(configPath);
        DashboardDefinition definition = TomlConfigurationLoader.LoadDashboard(dashboardPath);
        PortfolioSnapshot snapshot = new LocalCsvSnapshotSource(dataPath)
            .LoadAsync()
            .GetAwaiter()
            .GetResult();

        return new DashboardSession(snapshot, settings, definition, CaptureDate);
    }

    private static string FindRepositoryRoot()
    {
        var current = new DirectoryInfo(Path.GetFullPath(Directory.GetCurrentDirectory()));
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "Portico.Roci.slnx"))
                && File.Exists(Path.Combine(current.FullName, "portico-demo.toml"))
                && File.Exists(Path.Combine(current.FullName, "dashboard.toml")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        throw new DirectoryNotFoundException("Could not find the Portico repository root.");
    }
}
