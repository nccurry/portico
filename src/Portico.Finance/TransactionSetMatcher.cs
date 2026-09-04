namespace Portico.Finance;

/// <summary>Resolves named transaction-set rules against normalized transactions.</summary>
public static class TransactionSetMatcher
{
    /// <summary>Returns the transactions included by the named set.</summary>
    public static IReadOnlyList<FinancialTransaction> Select(
        IEnumerable<FinancialTransaction> transactions,
        string setKey,
        IReadOnlyList<TransactionSetDefinition> definitions,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentException.ThrowIfNullOrWhiteSpace(setKey);
        ArgumentNullException.ThrowIfNull(definitions);
        ArgumentNullException.ThrowIfNull(aliases);

        FinancialTransaction[] values = transactions.ToArray();
        var byKey = new Dictionary<string, TransactionSetDefinition>(StringComparer.Ordinal);
        foreach (TransactionSetDefinition definition in definitions)
        {
            if (!byKey.TryAdd(definition.Key, definition))
                throw new ArgumentException($"Transaction set '{definition.Key}' is duplicated.", nameof(definitions));
        }

        if (!byKey.ContainsKey(setKey))
            throw new ArgumentException($"Unknown transaction set '{setKey}'.", nameof(setKey));

        var cache = new Dictionary<string, bool[]>(StringComparer.Ordinal);
        var active = new HashSet<string>(StringComparer.Ordinal);
        bool[] included = Resolve(setKey);
        var result = new List<FinancialTransaction>();
        for (int index = 0; index < values.Length; index++)
        {
            if (included[index])
                result.Add(values[index]);
        }

        return result;

        bool[] Resolve(string key)
        {
            if (cache.TryGetValue(key, out bool[]? cached))
                return cached;
            if (!active.Add(key))
                throw new ArgumentException($"Transaction set references contain a cycle at '{key}'.", nameof(definitions));

            TransactionSetDefinition definition = byKey[key];
            bool hasDirectSelectors = definition.Groups.Count > 0
                || definition.Categories.Count > 0
                || definition.Accounts.Count > 0
                || definition.Merchants.Count > 0
                || definition.TransactionsLike.Count > 0;
            var result = new bool[values.Length];

            for (int index = 0; index < values.Length; index++)
            {
                FinancialTransaction transaction = values[index];
                result[index] = !hasDirectSelectors && definition.Includes.Count == 0
                    || MatchesDirect(transaction, definition, aliases);
            }

            foreach (string include in definition.Includes)
                Or(result, ResolveKnown(include));
            foreach (string exclude in definition.Excludes)
                Except(result, ResolveKnown(exclude));

            active.Remove(key);
            cache.Add(key, result);
            return result;
        }

        bool[] ResolveKnown(string key)
        {
            if (!byKey.ContainsKey(key))
                throw new ArgumentException($"Transaction set references unknown set '{key}'.", nameof(definitions));
            return Resolve(key);
        }
    }

    /// <summary>Returns a stable merchant name after applying configured aliases.</summary>
    public static string NormalizeMerchant(
        string description,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        ArgumentNullException.ThrowIfNull(description);
        ArgumentNullException.ThrowIfNull(aliases);

        foreach ((string merchant, IReadOnlyList<string> fragments) in aliases)
        {
            foreach (string fragment in fragments)
            {
                if (!string.IsNullOrWhiteSpace(fragment)
                    && description.Contains(fragment, StringComparison.OrdinalIgnoreCase))
                {
                    return merchant;
                }
            }
        }

        return description.Trim();
    }

    private static bool MatchesDirect(
        FinancialTransaction transaction,
        TransactionSetDefinition definition,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        return Contains(definition.Groups, transaction.Group)
            || Contains(definition.Categories, transaction.Category)
            || Contains(definition.Accounts, transaction.Account)
            || Contains(definition.Merchants, NormalizeMerchant(transaction.Description, aliases))
            || ContainsText(definition.TransactionsLike, transaction.Description);
    }

    private static bool Contains(IReadOnlyList<string> values, string value)
    {
        foreach (string current in values)
        {
            if (string.Equals(current, value, StringComparison.Ordinal))
                return true;
        }

        return false;
    }

    private static bool ContainsText(IReadOnlyList<string> fragments, string value)
    {
        foreach (string fragment in fragments)
        {
            if (value.Contains(fragment, StringComparison.OrdinalIgnoreCase))
                return true;
        }

        return false;
    }

    private static void Or(bool[] destination, bool[] source)
    {
        for (int index = 0; index < destination.Length; index++)
            destination[index] |= source[index];
    }

    private static void Except(bool[] destination, bool[] source)
    {
        for (int index = 0; index < destination.Length; index++)
            destination[index] &= !source[index];
    }
}
