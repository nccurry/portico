using System.Text.Json;
using Portico.Application;

namespace Portico.Cli;

/// <summary>Runs checks and owns all terminal output and exit-code policy.</summary>
public static class PorticoCli
{
    private const string Schema = "portico.command-result.v1";
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public static async Task<int> RunCheckAsync(
        PorticoCommand command,
        PorticoApplication application,
        TextWriter output,
        TextWriter error,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(command);
        ArgumentNullException.ThrowIfNull(application);
        ArgumentNullException.ThrowIfNull(output);
        ArgumentNullException.ThrowIfNull(error);
        if (command.Kind is not (PorticoCommandKind.ConfigCheck or PorticoCommandKind.DataCheck or PorticoCommandKind.Doctor))
            throw new ArgumentException("A check command is required.", nameof(command));

        try
        {
            if (command.Kind == PorticoCommandKind.ConfigCheck)
            {
                ConfigurationCheckOutcome result = await application.CheckConfigurationAsync(command.Selection, cancellationToken);
                return result switch
                {
                    ConfigurationChecked checkedResult => WriteSuccess(command, output, checkedResult.Summary.Source),
                    PorticoFailure failure => WriteFailure(command, failure, output),
                    _ => throw new InvalidOperationException("The configuration check returned no outcome.")
                };
            }

            DataCheckOutcome dataResult = await application.CheckDataAsync(command.Selection, cancellationToken);
            return dataResult switch
            {
                DataChecked checkedResult => WriteSuccess(command, output, checkedResult.Summary),
                PorticoFailure failure => WriteFailure(command, failure, output),
                _ => throw new InvalidOperationException("The data check returned no outcome.")
            };
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return WriteFailure(command, new PorticoFailure([
                new PorticoProblem("operation.cancelled", "The operation was cancelled.", retryable: true)
            ]), output);
        }
        catch (Exception)
        {
            return WriteHostFailure(error);
        }
    }

    public static int WriteHelp(TextWriter output)
    {
        ArgumentNullException.ThrowIfNull(output);
        output.WriteLine("Portico personal-finance desktop app");
        output.WriteLine("Usage:");
        output.WriteLine("  portico run [--config PATH] [--secrets PATH] [--dashboard PATH]");
        output.WriteLine("  portico config check [--config PATH] [--secrets PATH] [--output text|json]");
        output.WriteLine("  portico data check [--config PATH] [--secrets PATH] [--output text|json]");
        output.WriteLine("  portico doctor [--config PATH] [--secrets PATH] [--output text|json]");
        output.WriteLine();
        output.WriteLine("Run 'portico --help' to show this help. With no command, Portico runs the desktop app.");
        output.WriteLine("AI_CONTEXT:");
        output.WriteLine("  Checks support --output json and write one portico.command-result.v1 document.");
        output.WriteLine("  Default files: ./portico.toml and sibling portico.secrets.toml; run also uses sibling dashboard.toml.");
        output.WriteLine("  Exit codes: 0 success, 1 internal failure, 2 usage, 3 configuration, 4 data, 5 cancelled or retryable source.");
        output.WriteLine("  run starts an interactive desktop window. No source URL is accepted on the command line.");
        return 0;
    }

    public static int WriteUsageError(CommandLineException exception, TextWriter error)
    {
        ArgumentNullException.ThrowIfNull(exception);
        ArgumentNullException.ThrowIfNull(error);
        error.WriteLine($"Argument error: {exception.Message}");
        error.WriteLine("Run 'portico --help' for usage.");
        return 2;
    }

    public static int WriteRunFailure(PorticoFailure failure, TextWriter output)
    {
        ArgumentNullException.ThrowIfNull(failure);
        ArgumentNullException.ThrowIfNull(output);
        WriteProblems(output, "Portico run: not ready", failure);
        return ExitCode(failure);
    }

    public static int WriteHostFailure(TextWriter error)
    {
        ArgumentNullException.ThrowIfNull(error);
        error.WriteLine("Portico could not complete the command because of an internal error.");
        return 1;
    }

    public static int ExitCode(PorticoFailure failure)
    {
        ArgumentNullException.ThrowIfNull(failure);
        if (failure.Problems.Any(problem => problem.Code.StartsWith("config.", StringComparison.Ordinal)))
            return 3;
        if (failure.Problems.Any(problem => problem.Code.StartsWith("data.", StringComparison.Ordinal)
            || problem.Code.StartsWith("source.", StringComparison.Ordinal) && !problem.Retryable))
            return 4;
        if (failure.Problems.Any(problem => problem.Retryable || problem.Code == "operation.cancelled"))
            return 5;
        return 1;
    }

    private static int WriteSuccess(PorticoCommand command, TextWriter output, SourceKind source)
    {
        string sourceName = SourceName(source);
        if (command.Output == OutputFormat.Json)
            WriteJson(output, command, "success", new { source = sourceName }, []);
        else
        {
            output.WriteLine($"Portico {Label(command.Kind)}: ready");
            output.WriteLine($"Source: {sourceName}");
        }
        return 0;
    }

    private static int WriteSuccess(PorticoCommand command, TextWriter output, DataCheckSummary summary)
    {
        string sourceName = SourceName(summary.Source);
        if (command.Output == OutputFormat.Json)
            WriteJson(output, command, "success", new
            {
                source = sourceName,
                transactions = summary.Transactions,
                balances = summary.Balances,
                budgets = summary.Budgets
            }, []);
        else
        {
            output.WriteLine($"Portico {Label(command.Kind)}: ready");
            output.WriteLine($"Source: {sourceName}");
            output.WriteLine($"Transactions: {summary.Transactions}");
            output.WriteLine($"Balances: {summary.Balances}");
            output.WriteLine($"Budgets: {summary.Budgets}");
        }
        return 0;
    }

    private static int WriteFailure(PorticoCommand command, PorticoFailure failure, TextWriter output)
    {
        if (command.Output == OutputFormat.Json)
            WriteJson<object?>(output, command, "failure", null, failure.Problems);
        else
            WriteProblems(output, $"Portico {Label(command.Kind)}: not ready", failure);
        return ExitCode(failure);
    }

    private static void WriteJson<TDetails>(
        TextWriter output,
        PorticoCommand command,
        string outcome,
        TDetails details,
        IReadOnlyList<PorticoProblem> problems)
    {
        output.WriteLine(JsonSerializer.Serialize(new
        {
            schema = Schema,
            command = JsonCommand(command.Kind),
            outcome,
            details,
            problems
        }, JsonOptions));
    }

    private static void WriteProblems(TextWriter output, string heading, PorticoFailure failure)
    {
        output.WriteLine(heading);
        foreach (PorticoProblem problem in failure.Problems)
        {
            string field = problem.Field is null ? "" : $" ({problem.Field})";
            output.WriteLine($"- {problem.Code}{field}: {problem.Message}");
        }
    }

    private static string SourceName(SourceKind source) => source switch
    {
        SourceKind.LocalCsv => "local_csv",
        SourceKind.GoogleSheets => "google_sheets",
        _ => throw new InvalidOperationException("The source kind is not supported.")
    };

    private static string Label(PorticoCommandKind kind) => kind switch
    {
        PorticoCommandKind.ConfigCheck => "config check",
        PorticoCommandKind.DataCheck => "data check",
        PorticoCommandKind.Doctor => "doctor",
        _ => throw new InvalidOperationException("A check command is required.")
    };

    private static string JsonCommand(PorticoCommandKind kind) => kind switch
    {
        PorticoCommandKind.ConfigCheck => "config-check",
        PorticoCommandKind.DataCheck => "data-check",
        PorticoCommandKind.Doctor => "doctor",
        _ => throw new InvalidOperationException("A check command is required.")
    };
}
