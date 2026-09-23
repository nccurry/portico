using Portico.Desktop;
using Roci.Hosting.MonoGame;
using Roci.Launch;

namespace Portico.CaptureHost;

/// <summary>Starts deterministic Portico dashboard captures for local visual checks.</summary>
public static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        MonoGameHost.Run(
            args,
            "portico-capture",
            PorticoCaptureCatalog.RunCatalog,
            static context => new PorticoDashboardGame(
                PorticoCaptureCatalog.CreateSession(context),
                context,
                PorticoCaptureCatalog.CreateDisplayState(context)),
            features: GameRunFeatures.Automation | GameRunFeatures.Capture);
    }
}
