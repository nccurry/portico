namespace Portico.Application;

/// <summary>An expected problem whose message and field identify no private input.</summary>
/// <remarks>Readers supply safe text. Field names a setting or option, never a file path or URL.</remarks>
public sealed record PorticoProblem
{
    public PorticoProblem(string code, string message, string? field = null, bool retryable = false)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(code);
        ArgumentException.ThrowIfNullOrWhiteSpace(message);
        if (code.IndexOfAny(['\r', '\n']) >= 0 || message.IndexOfAny(['\r', '\n']) >= 0
            || field?.IndexOfAny(['\r', '\n']) >= 0)
            throw new ArgumentException("A public problem must be one line.");

        Code = code;
        Message = message;
        Field = field;
        Retryable = retryable;
    }

    public string Code { get; }

    public string Message { get; }

    public string? Field { get; }

    public bool Retryable { get; }
}

/// <summary>An ordered, nonempty set of expected problems.</summary>
public sealed class PorticoFailure
{
    public PorticoFailure(IEnumerable<PorticoProblem> problems)
    {
        ArgumentNullException.ThrowIfNull(problems);
        PorticoProblem[] copy = problems.ToArray();
        if (copy.Length == 0 || copy.Any(problem => problem is null))
            throw new ArgumentException("A failure requires at least one problem.", nameof(problems));

        Problems = Array.AsReadOnly(copy
            .OrderBy(problem => problem.Field, StringComparer.Ordinal)
            .ThenBy(problem => problem.Code, StringComparer.Ordinal)
            .ThenBy(problem => problem.Message, StringComparer.Ordinal)
            .ToArray());
    }

    public IReadOnlyList<PorticoProblem> Problems { get; }
}
