namespace Portico.Adapters;

/// <summary>Chooses the source used by the current workbook loader.</summary>
public enum WorkbookSourceKind
{
    /// <summary>Read four CSV files from a local directory.</summary>
    LocalCsv,

    /// <summary>Read four public Google Sheets tabs through CSV export URLs.</summary>
    GoogleSheets
}

/// <summary>Describes the source selected by the current configuration file.</summary>
public sealed record DataSourceSettings(WorkbookSourceKind Kind, string? Directory);
