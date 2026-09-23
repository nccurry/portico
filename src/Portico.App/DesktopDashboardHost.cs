using Portico.Application;
using Portico.Desktop;
using Cli = Portico.Cli;

namespace Portico.App;

/// <summary>Opens the configured desktop after Application loads a workspace.</summary>
public static class DesktopDashboardHost
{
    public static Task<int> RunAsync(
        Workspace workspace,
        string? dashboardPath,
        TextWriter output,
        TextWriter error,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(workspace);
        ArgumentException.ThrowIfNullOrWhiteSpace(dashboardPath);
        ArgumentNullException.ThrowIfNull(output);
        ArgumentNullException.ThrowIfNull(error);
        cancellationToken.ThrowIfCancellationRequested();

        DashboardReadOutcome read = DashboardConfigurationReader.Read(
            dashboardPath, workspace.ReportChoices);
        if (read is PorticoFailure failure)
            return Task.FromResult(Cli.PorticoCli.WriteRunFailure(failure, output));
        if (read is not DashboardReadSuccess success)
            throw new InvalidOperationException("The dashboard reader returned no outcome.");

        var session = new DashboardSession(workspace, success.Definition);
        output.WriteLine("Opening the Portico desktop dashboard.");
        PorticoDesktopWindow.Run(session);
        return Task.FromResult(0);
    }
}
