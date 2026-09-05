namespace Portico.Finance;

/// <summary>Chooses the source transaction type view.</summary>
public enum TransactionExplorerType
{
    /// <summary>Shows every transaction type.</summary>
    All,

    /// <summary>Shows expense rows.</summary>
    Expenses,

    /// <summary>Shows income rows.</summary>
    Income,

    /// <summary>Shows transfer rows.</summary>
    Transfers
}

/// <summary>Chooses one source transaction quick-focus view.</summary>
public enum TransactionExplorerFocus
{
    /// <summary>Shows all matching transactions.</summary>
    AllTransactions,

    /// <summary>Shows the largest matching transactions.</summary>
    Largest,

    /// <summary>Shows merchants that occur once in the current inventory.</summary>
    OneOffMerchants,

    /// <summary>Shows merchant charges with unusual magnitudes.</summary>
    UnusualAmounts,

    /// <summary>Shows refund and reversal rows.</summary>
    RefundsReversals
}

/// <summary>Chooses the dimension used for the source transaction breakdown.</summary>
public enum TransactionExplorerBreakdown
{
    /// <summary>Groups rows by group.</summary>
    Group,

    /// <summary>Groups rows by category.</summary>
    Category,

    /// <summary>Groups rows by normalized merchant.</summary>
    Merchant,

    /// <summary>Groups rows by account.</summary>
    Account,

    /// <summary>Groups rows by transaction type.</summary>
    Type
}

/// <summary>Holds the source-shaped transaction workbench inputs.</summary>
public sealed record TransactionExplorerFilters(
    int? LookbackDays,
    TransactionExplorerType Type,
    TransactionExplorerFocus Focus,
    IReadOnlyList<string> Groups,
    IReadOnlyList<string> Categories,
    IReadOnlyList<string> Accounts,
    string Search,
    decimal MinimumMagnitude,
    decimal? MaximumMagnitude,
    int LargestCount,
    TransactionExplorerBreakdown Breakdown)
{
    /// <summary>Creates the source page's initial filter values.</summary>
    public static TransactionExplorerFilters Default { get; } = new(
        365,
        TransactionExplorerType.All,
        TransactionExplorerFocus.AllTransactions,
        [],
        [],
        [],
        string.Empty,
        0m,
        null,
        25,
        TransactionExplorerBreakdown.Group);
}

/// <summary>Represents one filtered transaction with its source inspection flags.</summary>
public sealed record TransactionExplorerEntry(
    FinancialTransaction Transaction,
    string Merchant,
    decimal Magnitude,
    int Occurrences,
    bool IsOneOff,
    bool IsUnusual,
    bool IsReversal);

/// <summary>Represents one source transaction-result summary value.</summary>
public sealed record TransactionExplorerSummary(
    int TransactionCount,
    decimal Inflow,
    decimal Outflow,
    decimal NetAmount,
    decimal MedianMagnitude);

/// <summary>Represents one current transaction breakdown row.</summary>
public sealed record TransactionExplorerBreakdownEntry(
    string Entity,
    int Transactions,
    decimal Inflow,
    decimal Outflow,
    decimal NetAmount,
    decimal Magnitude,
    decimal SharePercent);

/// <summary>Contains the typed financial output for the source Transactions page.</summary>
public sealed record TransactionExplorerAnalysisResult(
    DateOnly? StartDate,
    DateOnly? EndDate,
    IReadOnlyList<TransactionExplorerEntry> Inventory,
    IReadOnlyList<TransactionExplorerEntry> Results,
    TransactionExplorerSummary Summary,
    IReadOnlyList<TransactionExplorerBreakdownEntry> Breakdown);

/// <summary>Builds the source transaction workbench inventory, focus results, and breakdown.</summary>
public static class TransactionExplorerAnalysisCalculator
{
    /// <summary>Builds the current source-shaped transaction inspection result.</summary>
    public static TransactionExplorerAnalysisResult Build(
        IEnumerable<FinancialTransaction> transactions,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases,
        TransactionExplorerFilters filters)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(aliases);
        ArgumentNullException.ThrowIfNull(filters);
        if (filters.MinimumMagnitude < 0m)
            throw new ArgumentOutOfRangeException(nameof(filters));
        if (filters.LargestCount is < 5 or > 500)
            throw new ArgumentOutOfRangeException(nameof(filters));

        FinancialTransaction[] source = transactions.ToArray();
        if (source.Length == 0)
            return Empty();

        DateOnly end = source.Max(transaction => transaction.Date);
        DateOnly start = filters.LookbackDays is int days
            ? end.AddDays(-days)
            : source.Min(transaction => transaction.Date);
        Candidate[] candidates = source
            .Where(transaction => transaction.Date >= start && transaction.Date <= end)
            .Where(transaction => MatchesType(transaction.Kind, filters.Type))
            .Where(transaction => Matches(filters.Groups, transaction.Group))
            .Where(transaction => Matches(filters.Categories, transaction.Category))
            .Where(transaction => Matches(filters.Accounts, transaction.Account))
            .Select(transaction => new Candidate(
                transaction,
                MerchantNameNormalizer.Normalize(transaction.Description, aliases),
                decimal.Abs(transaction.Amount)))
            .ToArray();

        TransactionExplorerEntry[] annotated = Annotate(candidates);
        TransactionExplorerEntry[] inventory = annotated
            .Where(entry => entry.Magnitude >= filters.MinimumMagnitude)
            .Where(entry => filters.MaximumMagnitude is not decimal maximum || entry.Magnitude <= maximum)
            .Where(entry => MatchesSearch(entry, filters.Search))
            .OrderByDescending(entry => entry.Magnitude)
            .ThenByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .ToArray();
        TransactionExplorerEntry[] results = Focus(inventory, filters.Focus, filters.LargestCount);
        TransactionExplorerSummary summary = Summarize(results);
        return new TransactionExplorerAnalysisResult(
            start,
            end,
            inventory,
            results,
            summary,
            BuildBreakdown(results, filters.Breakdown));
    }

    private static TransactionExplorerAnalysisResult Empty()
        => new(null, null, [], [], new TransactionExplorerSummary(0, 0m, 0m, 0m, 0m), []);

    private static TransactionExplorerEntry[] Annotate(IReadOnlyList<Candidate> candidates)
    {
        var details = new Detail[candidates.Count];
        foreach (IGrouping<string, (Candidate Candidate, int Index)> group in candidates
                     .Select((candidate, index) => (candidate, index))
                     .GroupBy(item => item.candidate.Merchant, StringComparer.Ordinal))
        {
            (Candidate Candidate, int Index)[] entries = group.ToArray();
            decimal median = Median(entries.Select(entry => entry.Candidate.Magnitude));
            decimal mad = Median(entries.Select(entry => decimal.Abs(entry.Candidate.Magnitude - median)));
            decimal threshold = mad > 0m ? mad * 1.4826m * 3m : Math.Max(median * .5m, 25m);
            foreach ((Candidate candidate, int index) in entries)
            {
                decimal deviation = decimal.Abs(candidate.Magnitude - median);
                details[index] = new Detail(
                    entries.Length,
                    entries.Length == 1,
                    entries.Length >= 3 && deviation > 0m && deviation >= threshold,
                    IsReversal(candidate.Transaction));
            }
        }

        return candidates
            .Select((candidate, index) => new TransactionExplorerEntry(
                candidate.Transaction,
                candidate.Merchant,
                candidate.Magnitude,
                details[index].Occurrences,
                details[index].IsOneOff,
                details[index].IsUnusual,
                details[index].IsReversal))
            .ToArray();
    }

    private static TransactionExplorerEntry[] Focus(
        IReadOnlyList<TransactionExplorerEntry> inventory,
        TransactionExplorerFocus focus,
        int largestCount)
        => focus switch
        {
            TransactionExplorerFocus.AllTransactions => inventory.ToArray(),
            TransactionExplorerFocus.Largest => inventory.Take(largestCount).ToArray(),
            TransactionExplorerFocus.OneOffMerchants => inventory.Where(entry => entry.IsOneOff).ToArray(),
            TransactionExplorerFocus.UnusualAmounts => inventory.Where(entry => entry.IsUnusual).ToArray(),
            TransactionExplorerFocus.RefundsReversals => inventory.Where(entry => entry.IsReversal).ToArray(),
            _ => throw new ArgumentOutOfRangeException(nameof(focus))
        };

    private static TransactionExplorerSummary Summarize(IReadOnlyList<TransactionExplorerEntry> entries)
    {
        decimal inflow = entries.Sum(entry => Math.Max(entry.Transaction.Amount, 0m));
        decimal outflow = -entries.Sum(entry => Math.Min(entry.Transaction.Amount, 0m));
        return new TransactionExplorerSummary(
            entries.Count,
            inflow,
            outflow,
            entries.Sum(entry => entry.Transaction.Amount),
            Median(entries.Select(entry => entry.Magnitude)));
    }

    private static IReadOnlyList<TransactionExplorerBreakdownEntry> BuildBreakdown(
        IReadOnlyList<TransactionExplorerEntry> entries,
        TransactionExplorerBreakdown breakdown)
    {
        decimal totalMagnitude = entries.Sum(entry => entry.Magnitude);
        return entries
            .GroupBy(entry => Entity(entry, breakdown), StringComparer.Ordinal)
            .Select(group =>
            {
                TransactionExplorerEntry[] values = group.ToArray();
                decimal magnitude = values.Sum(entry => entry.Magnitude);
                decimal inflow = values.Sum(entry => Math.Max(entry.Transaction.Amount, 0m));
                decimal outflow = -values.Sum(entry => Math.Min(entry.Transaction.Amount, 0m));
                return new TransactionExplorerBreakdownEntry(
                    group.Key,
                    values.Length,
                    inflow,
                    outflow,
                    values.Sum(entry => entry.Transaction.Amount),
                    magnitude,
                    totalMagnitude == 0m ? 0m : magnitude / totalMagnitude * 100m);
            })
            .OrderByDescending(entry => entry.Magnitude)
            .ThenBy(entry => entry.Entity, StringComparer.Ordinal)
            .ToArray();
    }

    private static string Entity(TransactionExplorerEntry entry, TransactionExplorerBreakdown breakdown)
    {
        string value = breakdown switch
        {
            TransactionExplorerBreakdown.Group => entry.Transaction.Group,
            TransactionExplorerBreakdown.Category => entry.Transaction.Category,
            TransactionExplorerBreakdown.Merchant => entry.Merchant,
            TransactionExplorerBreakdown.Account => entry.Transaction.Account,
            TransactionExplorerBreakdown.Type => entry.Transaction.Kind.ToString(),
            _ => throw new ArgumentOutOfRangeException(nameof(breakdown))
        };
        return string.IsNullOrWhiteSpace(value) ? "Unspecified" : value.Trim();
    }

    private static bool MatchesSearch(TransactionExplorerEntry entry, string search)
    {
        string query = search.Trim();
        if (string.IsNullOrEmpty(query))
            return true;

        return entry.Transaction.Description.Contains(query, StringComparison.OrdinalIgnoreCase)
            || entry.Merchant.Contains(query, StringComparison.OrdinalIgnoreCase)
            || entry.Transaction.Kind.ToString().Contains(query, StringComparison.OrdinalIgnoreCase)
            || entry.Transaction.Group.Contains(query, StringComparison.OrdinalIgnoreCase)
            || entry.Transaction.Category.Contains(query, StringComparison.OrdinalIgnoreCase)
            || entry.Transaction.Account.Contains(query, StringComparison.OrdinalIgnoreCase);
    }

    private static bool MatchesType(TransactionKind kind, TransactionExplorerType type)
        => type switch
        {
            TransactionExplorerType.All => true,
            TransactionExplorerType.Expenses => kind == TransactionKind.Expense,
            TransactionExplorerType.Income => kind == TransactionKind.Income,
            TransactionExplorerType.Transfers => kind == TransactionKind.Transfer,
            _ => throw new ArgumentOutOfRangeException(nameof(type))
        };

    private static bool Matches(IReadOnlyList<string> selected, string value)
        => selected.Count == 0 || selected.Contains(value, StringComparer.Ordinal);

    private static bool IsReversal(FinancialTransaction transaction)
        => transaction.Kind == TransactionKind.Expense && transaction.Amount > 0m
            || transaction.Kind == TransactionKind.Income && transaction.Amount < 0m;

    private static decimal Median(IEnumerable<decimal> values)
    {
        decimal[] ordered = values.Order().ToArray();
        if (ordered.Length == 0)
            return 0m;
        int middle = ordered.Length / 2;
        return ordered.Length % 2 == 1 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2m;
    }

    private sealed record Candidate(FinancialTransaction Transaction, string Merchant, decimal Magnitude);

    private sealed record Detail(int Occurrences, bool IsOneOff, bool IsUnusual, bool IsReversal);
}
