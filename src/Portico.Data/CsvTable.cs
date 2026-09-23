using System.Text;

namespace Portico.Data;

/// <summary>Represents a CSV file with its header and named row values.</summary>
internal sealed record CsvTable(IReadOnlyList<string> Headers, IReadOnlyList<IReadOnlyDictionary<string, string>> Rows)
{
    /// <summary>Parses a UTF-8 CSV document, including quoted commas and newlines.</summary>
    public static CsvTable Parse(string content, string sourceName)
    {
        ArgumentNullException.ThrowIfNull(content);
        ArgumentException.ThrowIfNullOrWhiteSpace(sourceName);

        IReadOnlyList<IReadOnlyList<string>> records = CsvRecords.Parse(content, sourceName);
        if (records.Count == 0)
            throw new DataContractException($"{sourceName} is empty.");

        string[] headers = records[0].Select(value => value.Trim()).ToArray();
        if (headers.Length == 0 || headers.Any(string.IsNullOrWhiteSpace))
            throw new DataContractException($"{sourceName} has an empty header name.");
        if (headers.Distinct(StringComparer.OrdinalIgnoreCase).Count() != headers.Length)
            throw new DataContractException($"{sourceName} has duplicate header names.");

        var rows = new List<IReadOnlyDictionary<string, string>>(records.Count - 1);
        for (int rowIndex = 1; rowIndex < records.Count; rowIndex++)
        {
            IReadOnlyList<string> values = records[rowIndex];
            if (values.Count != headers.Length)
                throw new DataContractException($"{sourceName} row {rowIndex + 1} has {values.Count} columns; expected {headers.Length}.");

            var row = new Dictionary<string, string>(headers.Length, StringComparer.OrdinalIgnoreCase);
            for (int column = 0; column < headers.Length; column++)
                row.Add(headers[column], values[column].Trim());
            rows.Add(row);
        }

        return new CsvTable(headers, rows);
    }

    /// <summary>Requires a header to exist before a normalizer accesses it.</summary>
    public void RequireHeaders(string sourceName, params string[] headers)
    {
        foreach (string header in headers)
        {
            if (!Headers.Contains(header, StringComparer.OrdinalIgnoreCase))
                throw new DataContractException($"{sourceName} is missing required column '{header}'.");
        }
    }
}

/// <summary>Represents a safe-to-display failure while reading a workbook.</summary>
internal sealed class DataContractException : Exception
{
    public DataContractException(string message, string code = "data.invalid")
        : base(message)
    {
        Code = code;
    }

    public string Code { get; }
}

internal static class CsvRecords
{
    public static IReadOnlyList<IReadOnlyList<string>> Parse(string content, string sourceName)
    {
        var records = new List<IReadOnlyList<string>>();
        var fields = new List<string>();
        var field = new StringBuilder();
        bool quoted = false;
        bool closedQuote = false;

        for (int index = 0; index < content.Length; index++)
        {
            char current = content[index];
            if (quoted)
            {
                if (current == '"')
                {
                    if (index + 1 < content.Length && content[index + 1] == '"')
                    {
                        field.Append('"');
                        index++;
                    }
                    else
                    {
                        quoted = false;
                        closedQuote = true;
                    }
                }
                else
                {
                    field.Append(current);
                }

                continue;
            }

            if (closedQuote && current is not (',' or '\r' or '\n'))
            {
                if (char.IsWhiteSpace(current))
                    continue;
                throw new DataContractException($"{sourceName} has an invalid quoted field.");
            }

            switch (current)
            {
                case '"' when field.Length == 0:
                    quoted = true;
                    break;
                case '"':
                    throw new DataContractException($"{sourceName} has an invalid quoted field.");
                case ',':
                    fields.Add(field.ToString());
                    field.Clear();
                    closedQuote = false;
                    break;
                case '\r':
                    if (index + 1 < content.Length && content[index + 1] == '\n')
                        index++;
                    AddRecord(records, fields, field);
                    closedQuote = false;
                    break;
                case '\n':
                    AddRecord(records, fields, field);
                    closedQuote = false;
                    break;
                default:
                    field.Append(current);
                    break;
            }
        }

        if (quoted)
            throw new DataContractException($"{sourceName} has an unterminated quoted field.");
        if (field.Length > 0 || fields.Count > 0)
            AddRecord(records, fields, field);
        return records;
    }

    private static void AddRecord(List<IReadOnlyList<string>> records, List<string> fields, StringBuilder field)
    {
        fields.Add(field.ToString());
        field.Clear();
        if (fields.Count > 1 || !string.IsNullOrWhiteSpace(fields[0]))
            records.Add(fields.ToArray());
        fields.Clear();
    }
}
