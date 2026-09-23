using Portico.Application;
using Portico.Configuration;
using Portico.Data;

namespace Portico.App;

/// <summary>Starts the command-line and desktop entry points from an STA thread.</summary>
public static class Program
{
    /// <summary>Runs Portico and returns its stable process exit code.</summary>
    [STAThread]
    public static async Task<int> Main(string[] args)
    {
        using var httpClient = new HttpClient();
        var application = new PorticoApplication(
            new TomlConfigurationReader(),
            new DataPortfolioReader(httpClient));
        var host = new PorticoHost(application, DesktopDashboardHost.RunAsync);
        return await host.RunAsync(args, Console.Out, Console.Error);
    }
}
