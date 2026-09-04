using Portico.Dashboard;

namespace Portico.App;

/// <summary>Owns the desktop presentation boundary for the Roci dashboard.</summary>
public static class DesktopDashboardHost
{
    /// <summary>Starts the desktop dashboard from a fully built report.</summary>
    public static Task<int> RunAsync(
        DashboardDefinition definition,
        DashboardReport report,
        TextWriter output,
        TextWriter error)
    {
        ArgumentNullException.ThrowIfNull(definition);
        ArgumentNullException.ThrowIfNull(report);
        ArgumentNullException.ThrowIfNull(output);
        ArgumentNullException.ThrowIfNull(error);

        error.WriteLine("The desktop renderer is being connected to the Roci chart worktree.");
        return Task.FromResult(4);
    }
}
