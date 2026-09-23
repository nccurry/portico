using Portico.Application;
using Cli = Portico.Cli;

namespace Portico.App;

/// <summary>Opens an Application workspace in the desktop host.</summary>
public delegate Task<int> DesktopRunner(
    Workspace workspace,
    string? dashboardPath,
    TextWriter output,
    TextWriter error,
    CancellationToken cancellationToken);

/// <summary>Connects the typed CLI command to Application and the desktop host.</summary>
public sealed class PorticoHost(PorticoApplication application, DesktopRunner desktop)
{
    private readonly PorticoApplication _application = application ?? throw new ArgumentNullException(nameof(application));
    private readonly DesktopRunner _desktop = desktop ?? throw new ArgumentNullException(nameof(desktop));

    public async Task<int> RunAsync(
        IReadOnlyList<string> arguments,
        TextWriter output,
        TextWriter error,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        ArgumentNullException.ThrowIfNull(output);
        ArgumentNullException.ThrowIfNull(error);

        Cli.PorticoCommand command;
        try
        {
            command = Cli.PorticoCommandLine.Parse(arguments);
        }
        catch (Cli.CommandLineException exception)
        {
            return Cli.PorticoCli.WriteUsageError(exception, error);
        }

        if (command.Kind == Cli.PorticoCommandKind.Help)
            return Cli.PorticoCli.WriteHelp(output);
        if (command.Kind != Cli.PorticoCommandKind.Run)
            return await Cli.PorticoCli.RunCheckAsync(command, _application, output, error, cancellationToken);

        try
        {
            OpenWorkspaceOutcome outcome = await _application.OpenWorkspaceAsync(
                command.Selection, cancellationToken: cancellationToken);
            return outcome switch
            {
                WorkspaceOpened opened => await _desktop(
                    opened.GetWorkspace(), DashboardPath(command), output, error, cancellationToken),
                PorticoFailure failure => Cli.PorticoCli.WriteRunFailure(failure, output),
                _ => throw new InvalidOperationException("The workspace operation returned no outcome.")
            };
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return Cli.PorticoCli.WriteRunFailure(new PorticoFailure([
                new PorticoProblem("operation.cancelled", "The operation was cancelled.", retryable: true)
            ]), output);
        }
        catch (Exception)
        {
            return Cli.PorticoCli.WriteHostFailure(error);
        }
    }

    private static string DashboardPath(Cli.PorticoCommand command)
    {
        if (command.DashboardPath is not null)
            return command.DashboardPath;

        string mainPath = Path.GetFullPath(command.Selection.ConfigurationPath ?? "portico.toml");
        return Path.Combine(Path.GetDirectoryName(mainPath)!, "dashboard.toml");
    }
}
