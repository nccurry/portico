using Portico.Finance;

namespace Portico.Application;

/// <summary>Selects complete configuration files; null uses the documented default.</summary>
public sealed class ConfigurationSelection(string? configurationPath = null, string? secretsPath = null)
{
    public string? ConfigurationPath { get; } = configurationPath;

    public string? SecretsPath { get; } = secretsPath;
}

/// <summary>The supported source selected by configuration.</summary>
public enum SourceKind
{
    LocalCsv,
    GoogleSheets
}

/// <summary>Validated source details whose default text and JSON omit private locations.</summary>
public abstract class SourceRequest
{
    private protected SourceRequest()
    {
    }

    public abstract SourceKind Kind { get; }
}

/// <summary>Reads the four workbook CSV files from one directory.</summary>
public sealed class LocalCsvSourceRequest : SourceRequest
{
    private readonly string _directory;

    public LocalCsvSourceRequest(string directory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(directory);
        _directory = directory;
    }

    public override SourceKind Kind => SourceKind.LocalCsv;

    public string GetDirectory() => _directory;
}

/// <summary>Reads the four workbook tabs from separate Google Sheets URLs.</summary>
public sealed class GoogleSheetsSourceRequest : SourceRequest
{
    private readonly string _transactionsUrl;
    private readonly string _balanceHistoryUrl;
    private readonly string _categoriesUrl;
    private readonly string _accountsUrl;

    public GoogleSheetsSourceRequest(
        string transactionsUrl,
        string balanceHistoryUrl,
        string categoriesUrl,
        string accountsUrl)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(transactionsUrl);
        ArgumentException.ThrowIfNullOrWhiteSpace(balanceHistoryUrl);
        ArgumentException.ThrowIfNullOrWhiteSpace(categoriesUrl);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountsUrl);

        _transactionsUrl = transactionsUrl;
        _balanceHistoryUrl = balanceHistoryUrl;
        _categoriesUrl = categoriesUrl;
        _accountsUrl = accountsUrl;
    }

    public override SourceKind Kind => SourceKind.GoogleSheets;

    public string UrlFor(string tab) => tab switch
    {
        "transactions" => _transactionsUrl,
        "balance_history" => _balanceHistoryUrl,
        "categories" => _categoriesUrl,
        "accounts" => _accountsUrl,
        _ => throw new ArgumentOutOfRangeException(nameof(tab), "Unknown workbook tab.")
    };
}

/// <summary>Validated settings and source details for an in-process handoff.</summary>
public sealed class WorkspaceConfiguration(FinanceSettings settings, ReportChoiceSettings reportChoices, SourceRequest source)
{
    public FinanceSettings Settings { get; } = settings ?? throw new ArgumentNullException(nameof(settings));

    public ReportChoiceSettings ReportChoices { get; } = reportChoices ?? throw new ArgumentNullException(nameof(reportChoices));

    public SourceRequest Source { get; } = source ?? throw new ArgumentNullException(nameof(source));
}

/// <summary>Reads and validates the selected main and secret configuration files.</summary>
public interface IConfigurationReader
{
    Task<ConfigurationReadOutcome> ReadAsync(ConfigurationSelection selection, CancellationToken cancellationToken);
}

/// <summary>Loads a normalized portfolio from a configured source.</summary>
public interface IPortfolioReader
{
    Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken);
}

/// <summary>Validated configuration from the outer reader.</summary>
public sealed class ConfigurationReadSuccess(WorkspaceConfiguration configuration)
{
    private readonly WorkspaceConfiguration _configuration = configuration ?? throw new ArgumentNullException(nameof(configuration));

    public WorkspaceConfiguration GetConfiguration() => _configuration;
}

/// <summary>Normalized data from the outer reader.</summary>
public sealed class PortfolioReadSuccess(PortfolioSnapshot snapshot)
{
    private readonly PortfolioSnapshot _snapshot = snapshot ?? throw new ArgumentNullException(nameof(snapshot));

    public PortfolioSnapshot GetSnapshot() => _snapshot;
}

/// <summary>Expected result of reading configuration.</summary>
public union ConfigurationReadOutcome(ConfigurationReadSuccess, PorticoFailure);

/// <summary>Expected result of reading a portfolio.</summary>
public union PortfolioReadOutcome(PortfolioReadSuccess, PorticoFailure);
