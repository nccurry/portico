using Portico.Finance;

namespace Portico.Adapters;

/// <summary>Loads one normalized four-tab Portico workbook.</summary>
public interface IPortfolioSnapshotSource
{
    /// <summary>Loads a consistent normalized snapshot.</summary>
    Task<PortfolioSnapshot> LoadAsync(CancellationToken cancellationToken = default);
}

/// <summary>Loads the four committed or user-supplied CSV files from a directory.</summary>
public sealed class LocalCsvSnapshotSource : IPortfolioSnapshotSource
{
    private readonly string _directory;

    /// <summary>Creates a local CSV source rooted at the supplied directory.</summary>
    public LocalCsvSnapshotSource(string directory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(directory);
        _directory = directory;
    }

    /// <inheritdoc />
    public async Task<PortfolioSnapshot> LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!Directory.Exists(_directory))
            throw new DataLoadException("The local data directory does not exist.");

        var files = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (string name in WorkbookTabs.Required)
        {
            string path = Path.Combine(_directory, $"{name}.csv");
            if (!File.Exists(path))
                throw new DataLoadException($"The local data directory is missing '{name}.csv'.");
            files.Add(name, await File.ReadAllTextAsync(path, cancellationToken));
        }

        return WorkbookNormalizer.Normalize(WorkbookTabs.Parse(files));
    }
}

/// <summary>Loads public Google Sheets tabs through their CSV export endpoints.</summary>
public sealed class GoogleSheetsSnapshotSource : IPortfolioSnapshotSource
{
    private readonly HttpClient _client;
    private readonly SheetUrlSettings _settings;

    /// <summary>Creates a public Google Sheets source with an injected HTTP client.</summary>
    public GoogleSheetsSnapshotSource(HttpClient client, SheetUrlSettings settings)
    {
        ArgumentNullException.ThrowIfNull(client);
        ArgumentNullException.ThrowIfNull(settings);
        _client = client;
        _settings = settings;
    }

    /// <inheritdoc />
    public async Task<PortfolioSnapshot> LoadAsync(CancellationToken cancellationToken = default)
    {
        var files = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (string tab in WorkbookTabs.Required)
        {
            string? rawUrl = _settings.Get(tab);
            if (string.IsNullOrWhiteSpace(rawUrl))
                throw new DataLoadException($"No public Google Sheets URL was supplied for '{tab}'.");
            GoogleSheetExportUrl url = GoogleSheetExportUrl.Parse(rawUrl);
            using HttpResponseMessage response = await _client.GetAsync(url.ExportUri, cancellationToken);
            if (!response.IsSuccessStatusCode)
                throw new DataLoadException($"Could not read public sheet '{tab}' (HTTP {(int)response.StatusCode}).");
            files.Add(tab, await response.Content.ReadAsStringAsync(cancellationToken));
        }

        return WorkbookNormalizer.Normalize(WorkbookTabs.Parse(files));
    }
}

/// <summary>Stores validated Google spreadsheet identity without retaining an unsafe diagnostic URL.</summary>
public sealed record GoogleSheetExportUrl(string DocumentId, long Gid, Uri ExportUri)
{
    /// <summary>Parses a Google Sheets page URL and creates its CSV export URL.</summary>
    public static GoogleSheetExportUrl Parse(string value)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out Uri? uri)
            || !string.Equals(uri.Scheme, Uri.UriSchemeHttps, StringComparison.OrdinalIgnoreCase)
            || !string.Equals(uri.Host, "docs.google.com", StringComparison.OrdinalIgnoreCase))
        {
            throw new DataLoadException("A public sheet URL must be an HTTPS docs.google.com spreadsheet URL.");
        }

        string[] segments = uri.AbsolutePath.Split('/', StringSplitOptions.RemoveEmptyEntries);
        int documentIndex = Array.FindIndex(segments, segment => string.Equals(segment, "d", StringComparison.Ordinal));
        if (documentIndex < 0 || documentIndex + 1 >= segments.Length || string.IsNullOrWhiteSpace(segments[documentIndex + 1]))
            throw new DataLoadException("The public sheet URL does not identify a spreadsheet document.");
        string documentId = segments[documentIndex + 1];
        string? gidText = FindQueryValue(uri.Query, "gid") ?? FindQueryValue(uri.Fragment.TrimStart('#'), "gid");
        if (!long.TryParse(gidText, out long gid) || gid < 0)
            throw new DataLoadException("The public sheet URL needs a numeric gid for the tab to export.");

        Uri exportUri = new($"https://docs.google.com/spreadsheets/d/{Uri.EscapeDataString(documentId)}/export?format=csv&gid={gid}");
        return new GoogleSheetExportUrl(documentId, gid, exportUri);
    }

    private static string? FindQueryValue(string query, string key)
    {
        foreach (string part in query.TrimStart('?', '#').Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            string[] pair = part.Split('=', 2);
            if (pair.Length == 2 && string.Equals(Uri.UnescapeDataString(pair[0]), key, StringComparison.OrdinalIgnoreCase))
                return Uri.UnescapeDataString(pair[1]);
        }

        return null;
    }
}

internal static class WorkbookTabs
{
    public static readonly IReadOnlyList<string> Required = ["transactions", "balance_history", "categories", "accounts"];

    public static IReadOnlyDictionary<string, CsvTable> Parse(IReadOnlyDictionary<string, string> documents)
    {
        var tables = new Dictionary<string, CsvTable>(StringComparer.OrdinalIgnoreCase);
        foreach (string tab in Required)
        {
            if (!documents.TryGetValue(tab, out string? content))
                throw new DataLoadException($"Workbook does not contain '{tab}'.");
            tables[tab] = CsvTable.Parse(content, tab);
        }

        return tables;
    }
}
