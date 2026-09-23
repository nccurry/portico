using Portico.Application;

namespace Portico.Cli;

/// <summary>The supported commands.</summary>
public enum PorticoCommandKind
{
    Run,
    ConfigCheck,
    DataCheck,
    Doctor,
    Help
}

/// <summary>How a terminal check writes its result.</summary>
public enum OutputFormat
{
    Text,
    Json
}

/// <summary>A parsed command with complete file selections.</summary>
public sealed record PorticoCommand(
    PorticoCommandKind Kind,
    ConfigurationSelection Selection,
    string? DashboardPath,
    OutputFormat Output);

/// <summary>A safe command-line syntax error.</summary>
public sealed class CommandLineException(string message) : Exception(message);

/// <summary>Parses Portico's finite, non-interactive command grammar.</summary>
public static class PorticoCommandLine
{
    public static PorticoCommand Parse(IReadOnlyList<string> arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);

        if (arguments.Count == 0)
            return NewCommand(PorticoCommandKind.Run);
        if (arguments.Count == 1 && arguments[0] is "help" or "--help" or "-h")
            return NewCommand(PorticoCommandKind.Help);

        PorticoCommandKind kind = arguments[0] switch
        {
            "run" => PorticoCommandKind.Run,
            "doctor" => PorticoCommandKind.Doctor,
            "config" when arguments.Count > 1 && arguments[1] == "check" => PorticoCommandKind.ConfigCheck,
            "data" when arguments.Count > 1 && arguments[1] == "check" => PorticoCommandKind.DataCheck,
            _ => throw new CommandLineException("Choose run, config check, data check, or doctor.")
        };

        int firstOption = kind is PorticoCommandKind.ConfigCheck or PorticoCommandKind.DataCheck ? 2 : 1;
        if (arguments.Count == firstOption + 1 && arguments[firstOption] is "--help" or "-h")
            return NewCommand(PorticoCommandKind.Help);

        string? configPath = null;
        string? secretsPath = null;
        string? dashboardPath = null;
        OutputFormat output = OutputFormat.Text;
        var seen = new HashSet<string>(StringComparer.Ordinal);

        for (int index = firstOption; index < arguments.Count; index++)
        {
            string option = arguments[index];
            if (option is not ("--config" or "--secrets" or "--dashboard" or "--output"))
                throw new CommandLineException("An option is not supported for this command.");
            if (option == "--dashboard" && kind != PorticoCommandKind.Run
                || option == "--output" && kind == PorticoCommandKind.Run)
                throw new CommandLineException($"{option} is not available for this command.");
            if (!seen.Add(option))
                throw new CommandLineException($"{option} may be supplied only once.");
            if (++index == arguments.Count || string.IsNullOrWhiteSpace(arguments[index])
                || arguments[index].StartsWith('-', StringComparison.Ordinal))
                throw new CommandLineException($"{option} requires a value.");

            string value = arguments[index];
            switch (option)
            {
                case "--config": configPath = value; break;
                case "--secrets": secretsPath = value; break;
                case "--dashboard": dashboardPath = value; break;
                case "--output":
                    output = value switch
                    {
                        "text" => OutputFormat.Text,
                        "json" => OutputFormat.Json,
                        _ => throw new CommandLineException("--output must be text or json.")
                    };
                    break;
            }
        }

        return new PorticoCommand(kind, new ConfigurationSelection(configPath, secretsPath), dashboardPath, output);
    }

    private static PorticoCommand NewCommand(PorticoCommandKind kind)
        => new(kind, new ConfigurationSelection(), null, OutputFormat.Text);
}
