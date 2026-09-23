using System.Globalization;
using Portico.Application;
using Portico.Finance;

namespace Portico.Data;

/// <summary>Reads the configured four-table workbook into one finance snapshot.</summary>
public sealed class DataPortfolioReader(HttpClient httpClient) : IPortfolioReader
{
    private readonly HttpClient _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));

    public async Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(source);
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            IReadOnlyDictionary<string, string> documents = source switch
            {
                LocalCsvSourceRequest local => await ReadLocalAsync(local, cancellationToken),
                GoogleSheetsSourceRequest sheets => await ReadSheetsAsync(sheets, cancellationToken),
                _ => throw new ArgumentOutOfRangeException(nameof(source), "Unsupported source request.")
            };
            cancellationToken.ThrowIfCancellationRequested();
            var tables = WorkbookTabs.Parse(documents);
            PortfolioSnapshot snapshot = WorkbookNormalizer.Normalize(tables);
            cancellationToken.ThrowIfCancellationRequested();
            return new PortfolioReadSuccess(snapshot);
        }
        catch (DataContractException error)
        {
            return Failure(error.Code, error.Message);
        }
        catch (SourceReadException error)
        {
            return Failure(error.Code, error.Message, error.Retryable);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return Failure("operation.cancelled", "The operation was cancelled.", retryable: true);
        }
        catch (OperationCanceledException)
        {
            return Failure("source.timeout", "The data source did not respond in time.", retryable: true);
        }
        catch (HttpRequestException)
        {
            return Failure("source.unavailable", "The data source could not be reached.", retryable: true);
        }
        catch (IOException)
        {
            return Failure("source.unavailable", "The data source could not be read.", retryable: true);
        }
        catch (UnauthorizedAccessException)
        {
            return Failure("source.unavailable", "The data source could not be read.");
        }
    }

    private static async Task<IReadOnlyDictionary<string, string>> ReadLocalAsync(
        LocalCsvSourceRequest source,
        CancellationToken cancellationToken)
    {
        string directory = source.GetDirectory();
        if (!Directory.Exists(directory))
            throw new SourceReadException("data.missing-directory", "The local data directory does not exist.");

        var documents = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (string tab in WorkbookTabs.Required)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string file = Path.Combine(directory, $"{tab}.csv");
            if (!File.Exists(file))
                throw new SourceReadException("data.missing-file", $"The local data directory is missing {tab}.csv.");
            documents[tab] = await File.ReadAllTextAsync(file, cancellationToken);
        }

        return documents;
    }

    private async Task<IReadOnlyDictionary<string, string>> ReadSheetsAsync(
        GoogleSheetsSourceRequest source,
        CancellationToken cancellationToken)
    {
        var documents = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (string tab in WorkbookTabs.Required)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Uri export = GoogleSheetExportUrl.Parse(source.UrlFor(tab));
            using HttpResponseMessage response = await _httpClient.GetAsync(export, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                bool retryable = (int)response.StatusCode is 408 or 429 or >= 500;
                throw new SourceReadException(
                    "source.http-error",
                    $"Could not read the {tab} sheet (HTTP {(int)response.StatusCode}).",
                    retryable);
            }
            documents[tab] = await response.Content.ReadAsStringAsync(cancellationToken);
        }

        return documents;
    }

    private static PorticoFailure Failure(string code, string message, bool retryable = false)
        => new([new PorticoProblem(code, message, retryable: retryable)]);
}

internal sealed class SourceReadException(string code, string message, bool retryable = false) : Exception(message)
{
    public string Code { get; } = code;

    public bool Retryable { get; } = retryable;
}

internal static class WorkbookTabs
{
    public static readonly IReadOnlyList<string> Required = ["transactions", "balance_history", "categories", "accounts"];

    public static IReadOnlyDictionary<string, CsvTable> Parse(IReadOnlyDictionary<string, string> documents)
    {
        var tables = new Dictionary<string, CsvTable>(StringComparer.OrdinalIgnoreCase);
        foreach (string tab in Required)
            tables[tab] = CsvTable.Parse(documents[tab], tab);
        return tables;
    }
}

internal static class GoogleSheetExportUrl
{
    public static Uri Parse(string value)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out Uri? uri)
            || uri.Scheme != Uri.UriSchemeHttps
            || !string.Equals(uri.Host, "docs.google.com", StringComparison.OrdinalIgnoreCase))
        {
            throw Invalid();
        }

        string[] segments = uri.AbsolutePath.Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (segments.Length < 3 || segments[0] != "spreadsheets" || segments[1] != "d"
            || segments[2].Length == 0 || segments[2].Any(character =>
                !char.IsAsciiLetterOrDigit(character) && character is not ('-' or '_')))
        {
            throw Invalid();
        }

        string? gidText = QueryValue(uri.Query, "gid") ?? QueryValue(uri.Fragment, "gid");
        if (!long.TryParse(gidText, NumberStyles.None, CultureInfo.InvariantCulture, out long gid))
            throw Invalid();

        return new Uri($"https://docs.google.com/spreadsheets/d/{segments[2]}/export?format=csv&gid={gid}");
    }

    private static string? QueryValue(string query, string key)
    {
        foreach (string part in query.TrimStart('?', '#').Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            string[] pair = part.Split('=', 2);
            if (pair.Length == 2 && string.Equals(pair[0], key, StringComparison.OrdinalIgnoreCase))
                return Uri.UnescapeDataString(pair[1]);
        }
        return null;
    }

    private static SourceReadException Invalid()
        => new("source.invalid-url", "A sheet needs an HTTPS Google Sheets URL with a numeric gid.");
}
