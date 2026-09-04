namespace Portico.Adapters;

/// <summary>Describes one safe-to-display configuration problem.</summary>
public sealed record ConfigurationError(string Path, string Message)
{
    /// <summary>Formats the problem for a person using the command line.</summary>
    public override string ToString() => string.IsNullOrWhiteSpace(Path) ? Message : $"{Path}: {Message}";
}

/// <summary>Represents one or more invalid configuration values.</summary>
public sealed class ConfigurationException : Exception
{
    /// <summary>Creates an exception from display-safe configuration problems.</summary>
    public ConfigurationException(IReadOnlyList<ConfigurationError> errors)
        : base(string.Join(Environment.NewLine, errors.Select(error => error.ToString())))
    {
        Errors = errors;
    }

    /// <summary>Gets every configuration problem found during parsing or validation.</summary>
    public IReadOnlyList<ConfigurationError> Errors { get; }
}

/// <summary>Contains public-sheet URLs read from an optional secret file or command-line overrides.</summary>
public sealed record SheetUrlSettings(IReadOnlyDictionary<string, string> Sheets)
{
    /// <summary>Gets a URL for the named workbook tab, if supplied.</summary>
    public string? Get(string name) => Sheets.TryGetValue(name, out string? value) ? value : null;
}
