using Roci.Hosting.MonoGame;
using Roci.Launch;

namespace Portico.Desktop;

/// <summary>Runs the retained Roci dashboard window for an open session.</summary>
public static class PorticoDesktopWindow
{
    public static void Run(DashboardSession session)
    {
        ArgumentNullException.ThrowIfNull(session);

        MonoGameHost.Run(
            PorticoDashboardGame.CreateHostSettings(),
            _ => new PorticoDashboardGame(
                session,
                GameRunContext.Empty,
                new PorticoDashboardDisplayState(session.Definition.IsDemoData)));
    }
}
