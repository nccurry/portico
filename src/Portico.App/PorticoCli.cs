using System.Text.Json;
using System.Text.Json.Serialization;
using Portico.Adapters;
using Portico.Dashboard;
using Portico.Finance;

namespace Portico.App;

/// <summary>Provides the command-line entry point for the desktop dashboard.</summary>
public static class PorticoCli
{
    /// <summary>Runs one command and returns its stable process exit code.</summary>
    public static async Task<int> RunAsync(string[] args, TextWriter output, TextWriter error)
    {
        ArgumentNullException.ThrowIfNull(args);
        ArgumentNullException.ThrowIfNull(output);
        ArgumentNullException.ThrowIfNull(error);

        try
        {
            PorticoCommand command = PorticoCommandLine.Parse(args);
            return command.Kind switch
            {
                PorticoCommandKind.Help => WriteHelp(output),
                PorticoCommandKind.Doctor => await DoctorAsync(command, output),
                PorticoCommandKind.Run => await RunDesktopAsync(command, output, error),
                _ => throw new InvalidOperationException("Unknown Portico command.")
            };
        }
        catch (CommandLineException exception)
        {
            error.WriteLine($"Argument error: {exception.Message}");
            error.WriteLine("Run 'portico --help' for usage.");
            return 2;
        }
        catch (ConfigurationException exception)
        {
            error.WriteLine("Configuration errors:");
            foreach (ConfigurationError configurationError in exception.Errors)
                error.WriteLine($"- {configurationError}");
            return 2;
        }
        catch (DataLoadException exception)
        {
            error.WriteLine($"Data error: {exception.Message}");
            return 3;
        }
        catch (OperationCanceledException)
        {
            error.WriteLine("The operation was cancelled.");
            return 4;
        }
        catch (Exception exception)
        {
            error.WriteLine($"Unexpected error: {exception.Message}");
            return 4;
        }
    }

    private static async Task<int> DoctorAsync(PorticoCommand command, TextWriter output)
    {
        DoctorResult result = await InspectAsync(command, loadData: true);
        if (command.Output == DoctorOutput.Json)
        {
            await output.WriteLineAsync(JsonSerializer.Serialize(result, DoctorJsonContext.Default.DoctorResult));
        }
        else
        {
            await output.WriteLineAsync("Portico doctor: ready");
            await output.WriteLineAsync($"Source: {result.Source}");
            await output.WriteLineAsync($"Pages: {result.PageCount}");
            await output.WriteLineAsync($"Transactions: {result.TransactionCount}");
            await output.WriteLineAsync($"Balances: {result.BalanceCount}");
            await output.WriteLineAsync($"Budgets: {result.BudgetCount}");
        }

        return 0;
    }

    private static async Task<int> RunDesktopAsync(PorticoCommand command, TextWriter output, TextWriter error)
    {
        LoadedPortico loaded = await LoadAsync(command, loadData: true);
        bool isDemoData = string.Equals(
            Path.GetFileName(command.ConfigPath),
            "portico-demo.toml",
            StringComparison.OrdinalIgnoreCase);
        return await DesktopDashboardHost.RunAsync(
            new DashboardSession(loaded.Snapshot!, loaded.Settings, loaded.Definition),
            output,
            error,
            isDemoData);
    }

    private static async Task<DoctorResult> InspectAsync(PorticoCommand command, bool loadData)
    {
        LoadedPortico loaded = await LoadAsync(command, loadData);
        PortfolioSnapshot snapshot = loaded.Snapshot ?? new PortfolioSnapshot([], [], []);
        return new DoctorResult(
            true,
            loaded.Settings.Data.Kind == WorkbookSourceKind.LocalCsv ? "local-csv" : "google-sheets",
            loaded.Definition.Pages.Count,
            snapshot.Transactions.Count,
            snapshot.Balances.Count,
            snapshot.Budgets.Count,
            []);
    }

    private static async Task<LoadedPortico> LoadAsync(PorticoCommand command, bool loadData)
    {
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(command.ConfigPath);
        settings = ApplyOverrides(settings, command);
        DashboardDefinition definition = TomlConfigurationLoader.LoadDashboard(command.DashboardPath);
        ValidateReportReferences(definition);
        ValidateDashboardBindings(definition, settings);
        if (!loadData)
            return new LoadedPortico(settings, definition, null);

        IPortfolioSnapshotSource source = CreateSource(settings, command);
        PortfolioSnapshot snapshot = await source.LoadAsync();
        return new LoadedPortico(settings, definition, snapshot);
    }

    private static FinanceSettings ApplyOverrides(FinanceSettings settings, PorticoCommand command)
    {
        WorkbookSourceKind kind = command.SourceOverride ?? settings.Data.Kind;
        string? directory = command.DataDirectory ?? ResolveDataDirectory(settings.Data.Directory, command.ConfigPath);
        return settings with { Data = new DataSourceSettings(kind, directory) };
    }

    private static string? ResolveDataDirectory(string? directory, string configPath)
    {
        if (string.IsNullOrWhiteSpace(directory) || Path.IsPathFullyQualified(directory))
            return directory;
        string fullConfigPath = Path.GetFullPath(configPath);
        string? configDirectory = Path.GetDirectoryName(fullConfigPath);
        return string.IsNullOrWhiteSpace(configDirectory)
            ? directory
            : Path.GetFullPath(Path.Combine(configDirectory, directory));
    }

    private static IPortfolioSnapshotSource CreateSource(FinanceSettings settings, PorticoCommand command)
    {
        if (settings.Data.Kind == WorkbookSourceKind.LocalCsv)
        {
            if (string.IsNullOrWhiteSpace(settings.Data.Directory))
                throw new DataLoadException("A local source needs --data-dir or data.directory.");
            return new LocalCsvSnapshotSource(settings.Data.Directory);
        }

        var urls = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!string.IsNullOrWhiteSpace(command.SecretsPath))
        {
            SheetUrlSettings secretUrls = TomlConfigurationLoader.LoadSheetUrls(command.SecretsPath);
            foreach ((string name, string url) in secretUrls.Sheets)
                urls[name] = url;
        }
        foreach ((string name, string url) in command.SheetOverrides)
            urls[name] = url;
        return new GoogleSheetsSnapshotSource(new HttpClient(), new SheetUrlSettings(urls));
    }

    private static void ValidateReportReferences(DashboardDefinition definition)
    {
        var errors = new List<ConfigurationError>();
        foreach (DashboardPageDefinition page in definition.Pages)
        {
            foreach (DashboardWidgetDefinition widget in page.Widgets)
            {
                if (!DashboardReportBuilder.SupportedWidgetReports.Contains(widget.Report))
                {
                    errors.Add(new ConfigurationError(
                        $"dashboard.pages.{page.Id}.widgets.{widget.Id}.report",
                        $"does not name a supported report ('{widget.Report}')."));
                }
            }
        }

        if (errors.Count > 0)
            throw new ConfigurationException(errors);
    }

    private static void ValidateDashboardBindings(DashboardDefinition definition, FinanceSettings settings)
    {
        var errors = new List<ConfigurationError>();
        foreach (DashboardPageDefinition page in definition.Pages)
        {
            foreach (DashboardFilterDefinition filter in page.Filters)
            {
                foreach (string option in filter.Options)
                {
                    if (IsConfiguredFilterOption(filter.Source, option, settings))
                        continue;

                    errors.Add(new ConfigurationError(
                        $"dashboard.pages.{page.Id}.filters.{filter.Id}.options",
                        $"value '{option}' is not configured for filter source '{filter.Source}'."));
                }
            }

            foreach (DashboardControlDefinition control in page.Controls)
            {
                DashboardControlMapping mapping = DashboardControlMappings.Resolve(page.Id, control.Id);
                if (mapping.Behavior != DashboardControlBehavior.ReportInput
                    || control.OptionSource != DashboardControlOptionSource.Static)
                    continue;

                foreach (string option in control.ChoiceOptions)
                {
                    if (IsConfiguredFilterOption(mapping.ReportFilterSource!, option, settings))
                        continue;

                    errors.Add(new ConfigurationError(
                        $"dashboard.pages.{page.Id}.controls.{control.Id}.options",
                        $"value '{option}' is not configured for report filter '{mapping.ReportFilterSource}'."));
                }
            }
        }

        if (errors.Count > 0)
            throw new ConfigurationException(errors);
    }

    private static bool IsConfiguredFilterOption(string source, string value, FinanceSettings settings)
        => source switch
        {
            "lookback" => int.TryParse(value, out int months) && settings.Lookback.Months.Contains(months),
            "spending" => settings.FilterSet("spending").Options.Contains(value, StringComparer.Ordinal),
            "year_over_year" => settings.FilterSet("year_over_year").Options.Contains(value, StringComparer.Ordinal),
            "income_view" => value is "regular" or "actual",
            "income_lookback" => int.TryParse(value, out int incomeMonths) && settings.Lookback.Months.Contains(incomeMonths),
            "income_calculation" => value is "regular" or "actual",
            "year_over_year_view" => value is "single_category" or "single_group"
                || settings.FilterSet("year_over_year").Options.Contains(value, StringComparer.Ordinal),
            "home_time_frame" => HomeReportRange.TryParse(value, out _),
            "spending_comparison" => DashboardControlMappings.TryParseSpendingComparison(value, out _),
            "spending_breakdown" => DashboardControlMappings.TryParseSpendingBreakdown(value, out _),
            "merchant_lookback" => int.TryParse(value, out int merchantMonths) && settings.Lookback.Months.Contains(merchantMonths),
            "merchant_spending" => settings.FilterSet("spending").Options.Contains(value, StringComparer.Ordinal),
            "merchant_comparison" => DashboardControlMappings.TryParseSpendingComparison(value, out _),
            "transactions_lookback" => value is "3m" or "6m" or "1y" or "2y" or "all",
            "transactions_type" => value is "all" or "expenses" or "income" or "transfers",
            "transactions_focus" => value is "all" or "largest" or "one_off" or "unusual" or "reversals",
            "transactions_breakdown" => value is "group" or "category" or "merchant" or "account" or "type",
            "fi_spending_lookback" => int.TryParse(value, out int fiMonths)
                && fiMonths is 6 or 12 or 24 or 36,
            _ => false
        };

    private static int WriteHelp(TextWriter output)
    {
        output.WriteLine("Portico Roci desktop dashboard");
        output.WriteLine("Usage: portico [run|doctor] [options]");
        output.WriteLine();
        output.WriteLine("Commands:");
        output.WriteLine("  run       Load the workbook and open the desktop dashboard (default).");
        output.WriteLine("  doctor    Validate configuration and load the selected workbook.");
        output.WriteLine();
        output.WriteLine("Options:");
        output.WriteLine("  --config PATH       Finance TOML file (default: portico-demo.toml)");
        output.WriteLine("  --dashboard PATH    Dashboard TOML file (default: dashboard.toml)");
        output.WriteLine("  --source NAME       local-csv or google-sheets");
        output.WriteLine("  --data-dir PATH     Local CSV directory override");
        output.WriteLine("  --secrets PATH      TOML file with [sheets] public URLs");
        output.WriteLine("  --sheet NAME=URL    Override one public sheet URL; repeatable");
        output.WriteLine("  --output FORMAT     doctor output: text or json");
        output.WriteLine();
        output.WriteLine("AI_CONTEXT:");
        output.WriteLine("  Use doctor --output json to read one JSON result.");
        output.WriteLine("  Exit codes: 0 ready, 2 argument or configuration error, 3 data error, 4 cancelled or unexpected error.");
        output.WriteLine("  run opens an interactive desktop window.");
        return 0;
    }

    private sealed record LoadedPortico(FinanceSettings Settings, DashboardDefinition Definition, PortfolioSnapshot? Snapshot);
}

/// <summary>Specifies the recognized top-level Portico commands.</summary>
public enum PorticoCommandKind
{
    /// <summary>Open the dashboard.</summary>
    Run,

    /// <summary>Validate settings and data.</summary>
    Doctor,

    /// <summary>Show command help.</summary>
    Help
}

/// <summary>Specifies the doctor output encoding.</summary>
public enum DoctorOutput
{
    /// <summary>Print a concise human-readable result.</summary>
    Text,

    /// <summary>Print one JSON result on standard output.</summary>
    Json
}

/// <summary>Represents parsed command-line input.</summary>
public sealed record PorticoCommand(
    PorticoCommandKind Kind,
    string ConfigPath,
    string DashboardPath,
    string? SecretsPath,
    WorkbookSourceKind? SourceOverride,
    string? DataDirectory,
    IReadOnlyDictionary<string, string> SheetOverrides,
    DoctorOutput Output);

/// <summary>Provides a deterministic, non-interactive Portico command-line parser.</summary>
public static class PorticoCommandLine
{
    /// <summary>Parses a command line with stable validation errors.</summary>
    public static PorticoCommand Parse(IReadOnlyList<string> arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        if (arguments.Count == 0)
            return Create(PorticoCommandKind.Run, []);
        if (arguments.Count == 1 && arguments[0] is "--help" or "-h" or "help")
            return Create(PorticoCommandKind.Help, []);

        int index = 0;
        PorticoCommandKind kind = arguments[0] switch
        {
            "run" => PorticoCommandKind.Run,
            "doctor" => PorticoCommandKind.Doctor,
            _ when arguments[0].StartsWith('-', StringComparison.Ordinal) => PorticoCommandKind.Run,
            _ => throw new CommandLineException($"Unknown command '{arguments[0]}'.")
        };
        if ((kind is PorticoCommandKind.Run or PorticoCommandKind.Doctor)
            && !arguments[0].StartsWith('-', StringComparison.Ordinal))
        {
            index++;
        }

        return Create(kind, arguments.Skip(index).ToArray());
    }

    private static PorticoCommand Create(PorticoCommandKind kind, IReadOnlyList<string> options)
    {
        string config = "portico-demo.toml";
        string dashboard = "dashboard.toml";
        string? secrets = null;
        WorkbookSourceKind? source = null;
        string? dataDirectory = null;
        DoctorOutput output = DoctorOutput.Text;
        var sheets = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        for (int index = 0; index < options.Count; index++)
        {
            string option = options[index];
            if (option is "--help" or "-h")
                return new PorticoCommand(PorticoCommandKind.Help, config, dashboard, secrets, source, dataDirectory, sheets, output);
            string value = RequireValue(options, ref index, option);
            switch (option)
            {
                case "--config":
                    config = value;
                    break;
                case "--dashboard":
                    dashboard = value;
                    break;
                case "--secrets":
                    secrets = value;
                    break;
                case "--data-dir":
                    dataDirectory = value;
                    break;
                case "--source":
                    source = value.ToLowerInvariant() switch
                    {
                        "local-csv" or "local" => WorkbookSourceKind.LocalCsv,
                        "google-sheets" or "remote" => WorkbookSourceKind.GoogleSheets,
                        _ => throw new CommandLineException("--source must be local-csv or google-sheets.")
                    };
                    break;
                case "--output":
                    output = value.ToLowerInvariant() switch
                    {
                        "text" => DoctorOutput.Text,
                        "json" => DoctorOutput.Json,
                        _ => throw new CommandLineException("--output must be text or json.")
                    };
                    break;
                case "--sheet":
                    AddSheet(sheets, value);
                    break;
                default:
                    throw new CommandLineException($"Unknown option '{option}'.");
            }
        }

        if (kind == PorticoCommandKind.Run && output != DoctorOutput.Text)
            throw new CommandLineException("--output is available only with doctor.");
        return new PorticoCommand(kind, config, dashboard, secrets, source, dataDirectory, sheets, output);
    }

    private static string RequireValue(IReadOnlyList<string> options, ref int index, string option)
    {
        if (!option.StartsWith("--", StringComparison.Ordinal))
            throw new CommandLineException($"Unexpected value '{option}'.");
        if (++index >= options.Count || options[index].StartsWith("--", StringComparison.Ordinal))
            throw new CommandLineException($"{option} requires a value.");
        return options[index];
    }

    private static void AddSheet(Dictionary<string, string> sheets, string value)
    {
        string[] parts = value.Split('=', 2);
        if (parts.Length != 2 || string.IsNullOrWhiteSpace(parts[0]) || string.IsNullOrWhiteSpace(parts[1]))
            throw new CommandLineException("--sheet must use NAME=URL.");
        if (!WorkbookTabNames.IsValid(parts[0]))
            throw new CommandLineException("--sheet NAME must be transactions, balance_history, categories, or accounts.");
        sheets[parts[0]] = parts[1];
    }
}

/// <summary>Represents a doctor result that intentionally excludes secret URLs and paths.</summary>
public sealed record DoctorResult(
    bool Ready,
    string Source,
    int PageCount,
    int TransactionCount,
    int BalanceCount,
    int BudgetCount,
    IReadOnlyList<string> Warnings);

/// <summary>Represents invalid command-line input.</summary>
public sealed class CommandLineException : Exception
{
    /// <summary>Creates an argument parsing error.</summary>
    public CommandLineException(string message)
        : base(message)
    {
    }
}

internal static class WorkbookTabNames
{
    public static bool IsValid(string value)
        => value is "transactions" or "balance_history" or "categories" or "accounts";
}

[JsonSerializable(typeof(DoctorResult))]
internal partial class DoctorJsonContext : JsonSerializerContext
{
}
