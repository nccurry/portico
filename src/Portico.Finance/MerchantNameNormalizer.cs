using System.Text.RegularExpressions;

namespace Portico.Finance;

/// <summary>Normalizes raw payment descriptions into stable merchant names.</summary>
public static class MerchantNameNormalizer
{
    private static readonly Regex MerchantNoise = new(
        @"\b(POS|DEBIT|CARD|PURCHASE|AUTH|AUTHORIZATION|CHECKCARD|VISA|MC|SQ|TST|PAYPAL|ONLINE|PAYMENT|RECURRING|PPD|CCD|ACH)\b",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);
    private static readonly Regex TrailingIdentifier = new(@"[#*]?\s*\d{3,}\b", RegexOptions.Compiled);
    private static readonly Regex LongCode = new(@"\b(?=[A-Z0-9]*\d)[A-Z0-9]{8,}\b", RegexOptions.Compiled);
    private static readonly Regex NonMerchantCharacter = new(@"[^A-Z0-9#*]+", RegexOptions.Compiled);

    /// <summary>Returns a source-style merchant name after aliases and cleanup are applied.</summary>
    public static string Normalize(
        string? description,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases,
        int wordLimit = 3)
    {
        ArgumentNullException.ThrowIfNull(aliases);
        if (wordLimit <= 0)
            throw new ArgumentOutOfRangeException(nameof(wordLimit));

        string text = Clean(description);
        if (string.IsNullOrEmpty(text))
            return "Unknown";

        string[] words = text.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (words.Length > 1 && string.Equals(words[^1], "REFUND", StringComparison.Ordinal))
        {
            words = words[..^1];
            text = string.Join(' ', words);
        }

        foreach ((string merchant, string pattern) in AliasPatterns(aliases))
        {
            if (text.Contains(pattern, StringComparison.Ordinal))
                return merchant;
        }

        return words.Length == 0 ? "Unknown" : string.Join(' ', words.Take(wordLimit));
    }

    private static IEnumerable<(string Merchant, string Pattern)> AliasPatterns(
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
        => aliases
            .Where(pair => !string.IsNullOrWhiteSpace(pair.Key))
            .SelectMany(pair => pair.Value
                .Select(Clean)
                .Where(pattern => !string.IsNullOrEmpty(pattern))
                .Select(pattern => (pair.Key.Trim().ToUpperInvariant(), pattern)))
            .OrderByDescending(pair => pair.pattern.Length)
            .ThenBy(pair => pair.pattern, StringComparer.Ordinal);

    private static string Clean(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
            return string.Empty;

        string text = value.ToUpperInvariant().Replace("&", " AND ", StringComparison.Ordinal);
        text = NonMerchantCharacter.Replace(text, " ");
        text = MerchantNoise.Replace(text, " ");
        text = TrailingIdentifier.Replace(text, " ");
        text = LongCode.Replace(text, " ");
        return string.Join(' ', text.Replace("#", " ", StringComparison.Ordinal)
            .Replace("*", " ", StringComparison.Ordinal)
            .Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }
}
