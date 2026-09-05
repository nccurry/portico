using Portico.Dashboard;

namespace Portico.App;

/// <summary>Owns the desktop presentation boundary for the Roci dashboard.</summary>
public static class DesktopDashboardHost
{
    /// <summary>Starts the desktop dashboard from a fully built report.</summary>
    public static Task<int> RunAsync(
        DashboardSession session,
        TextWriter output,
        TextWriter error,
        bool isDemoData = false)
    {
        ArgumentNullException.ThrowIfNull(session);
        ArgumentNullException.ThrowIfNull(output);
        ArgumentNullException.ThrowIfNull(error);

        try
        {
            output.WriteLine("Opening the Portico desktop dashboard.");
            Roci.Hosting.MonoGame.MonoGameHost.Run(
                PorticoDashboardGame.CreateHostSettings(),
                _ => new PorticoDashboardGame(
                    session,
                    Roci.Launch.GameRunContext.Empty,
                    new PorticoDashboardDisplayState(isDemoData)));
            return Task.FromResult(0);
        }
        catch (Exception exception)
        {
            error.WriteLine($"Desktop error: {exception.Message}");
            return Task.FromResult(4);
        }
    }
}
