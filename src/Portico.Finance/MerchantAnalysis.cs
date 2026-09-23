namespace Portico.Finance;

/// <summary>Represents one merchant's spending rank and totals.</summary>
public sealed record MerchantOverviewEntry(
    string Merchant,
    decimal Spending,
    decimal SharePercent,
    decimal AverageMonthlySpending,
    decimal ComparisonSpending,
    decimal Change,
    decimal? ChangePercent,
    int TransactionCount,
    decimal AverageTransaction,
    string PrimaryCategory,
    string PrimaryGroup,
    string PrimaryAccount,
    DateOnly FirstTransaction,
    DateOnly LastTransaction,
    IReadOnlyList<decimal> MonthlyTrend);

/// <summary>Represents the source merchant-period metric deck.</summary>
public sealed record MerchantPeriodSummary(
    decimal TotalSpending,
    decimal AverageMonthlySpending,
    int MerchantCount,
    decimal RepeatSpendingSharePercent);

/// <summary>Represents one aligned merchant history month.</summary>
public sealed record MerchantHistoryEntry(
    YearMonth CurrentMonth,
    YearMonth ComparisonMonth,
    decimal CurrentSpending,
    decimal ComparisonSpending,
    int CurrentTransactions,
    int ComparisonTransactions);

/// <summary>Represents one merchant detail breakdown row.</summary>
public sealed record MerchantDetailBreakdownEntry(string Entity, decimal Spending, decimal SharePercent, int Transactions);

/// <summary>Represents one raw-description merchant detail row.</summary>
public sealed record MerchantDescriptionEntry(string Description, decimal Spending, int Transactions, DateOnly LastTransaction);

/// <summary>Contains the typed financial output for the source Spending by merchant page.</summary>
public sealed record MerchantAnalysisResult(
    SpendingPeriod Period,
    IReadOnlyList<SpendingLedgerEntry> CurrentLedger,
    IReadOnlyList<SpendingLedgerEntry> ComparisonLedger,
    MerchantPeriodSummary Summary,
    IReadOnlyList<MerchantOverviewEntry> Overview);

/// <summary>Builds source-compatible merchant rankings and selected detail from the shared spending ledger.</summary>
public static class MerchantAnalysisCalculator
{
    /// <summary>Builds the matched current and comparison merchant analysis.</summary>
    public static MerchantAnalysisResult Build(
        IEnumerable<FinancialTransaction> transactions,
        FinanceSettings settings,
        string transactionSetKey,
        int lookbackMonths,
        SpendingComparison comparison,
        SpendingAdjustments adjustments)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(settings);
        ArgumentNullException.ThrowIfNull(adjustments);

        SpendingAnalysisResult spending = SpendingAnalysisCalculator.Build(
            transactions,
            settings,
            transactionSetKey,
            lookbackMonths,
            comparison,
            SpendingBreakdown.Category,
            adjustments);
        IReadOnlyList<MerchantOverviewEntry> overview = BuildOverview(
            spending.CurrentLedger,
            spending.ComparisonLedger,
            spending.Period.CurrentMonths,
            settings.MerchantAliases);
        return new MerchantAnalysisResult(
            spending.Period,
            spending.CurrentLedger,
            spending.ComparisonLedger,
            Summarize(overview, spending.Period.CurrentMonths.Count),
            overview);
    }

    /// <summary>Builds aligned current and comparison values for one selected merchant.</summary>
    public static IReadOnlyList<MerchantHistoryEntry> History(
        MerchantAnalysisResult analysis,
        string merchant,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        ArgumentException.ThrowIfNullOrWhiteSpace(merchant);
        ArgumentNullException.ThrowIfNull(aliases);

        Dictionary<YearMonth, (decimal Spending, int Transactions)> current = Monthly(analysis.CurrentLedger, merchant, aliases);
        Dictionary<YearMonth, (decimal Spending, int Transactions)> comparison = Monthly(analysis.ComparisonLedger, merchant, aliases);
        var result = new List<MerchantHistoryEntry>(analysis.Period.CurrentMonths.Count);
        for (int index = 0; index < analysis.Period.CurrentMonths.Count; index++)
        {
            YearMonth currentMonth = analysis.Period.CurrentMonths[index];
            YearMonth comparisonMonth = analysis.Period.ComparisonMonths[index];
            (decimal currentSpending, int currentTransactions) = current.GetValueOrDefault(currentMonth);
            (decimal comparisonSpending, int comparisonTransactions) = comparison.GetValueOrDefault(comparisonMonth);
            result.Add(new MerchantHistoryEntry(
                currentMonth,
                comparisonMonth,
                currentSpending,
                comparisonSpending,
                currentTransactions,
                comparisonTransactions));
        }

        return result;
    }

    /// <summary>Builds a source category or account composition for one selected merchant.</summary>
    public static IReadOnlyList<MerchantDetailBreakdownEntry> Breakdown(
        IEnumerable<SpendingLedgerEntry> ledger,
        string merchant,
        string dimension,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        ArgumentNullException.ThrowIfNull(ledger);
        ArgumentException.ThrowIfNullOrWhiteSpace(merchant);
        ArgumentException.ThrowIfNullOrWhiteSpace(dimension);
        ArgumentNullException.ThrowIfNull(aliases);
        if (dimension is not ("Category" or "Account" or "Group"))
            throw new ArgumentException("Merchant detail supports Category, Account, or Group.", nameof(dimension));

        SpendingLedgerEntry[] included = IncludedMerchant(ledger, merchant, aliases).ToArray();
        decimal total = included.Sum(entry => entry.NetSpending);
        return included
            .GroupBy(entry => Dimension(entry.Transaction, dimension), StringComparer.Ordinal)
            .Select(group =>
            {
                SpendingLedgerEntry[] values = group.ToArray();
                decimal spending = values.Sum(entry => entry.NetSpending);
                return new MerchantDetailBreakdownEntry(
                    group.Key,
                    spending,
                    total == 0m ? 0m : spending / total * 100m,
                    values.Length);
            })
            .OrderByDescending(entry => entry.Spending)
            .ThenBy(entry => entry.Entity, StringComparer.Ordinal)
            .ToArray();
    }

    /// <summary>Builds raw description variants for one selected merchant.</summary>
    public static IReadOnlyList<MerchantDescriptionEntry> Descriptions(
        IEnumerable<SpendingLedgerEntry> ledger,
        string merchant,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        ArgumentNullException.ThrowIfNull(ledger);
        ArgumentException.ThrowIfNullOrWhiteSpace(merchant);
        ArgumentNullException.ThrowIfNull(aliases);

        return IncludedMerchant(ledger, merchant, aliases)
            .GroupBy(entry => string.IsNullOrWhiteSpace(entry.Transaction.Description) ? "Unknown" : entry.Transaction.Description.Trim(), StringComparer.Ordinal)
            .Select(group => new MerchantDescriptionEntry(
                group.Key,
                group.Sum(entry => entry.NetSpending),
                group.Count(),
                group.Max(entry => entry.Transaction.Date)))
            .OrderByDescending(entry => entry.Spending)
            .ThenBy(entry => entry.Description, StringComparer.Ordinal)
            .ToArray();
    }

    /// <summary>Returns the included selected-merchant rows for the requested current month.</summary>
    public static IReadOnlyList<SpendingLedgerEntry> Transactions(
        IEnumerable<SpendingLedgerEntry> ledger,
        string merchant,
        YearMonth? month,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        ArgumentNullException.ThrowIfNull(ledger);
        ArgumentException.ThrowIfNullOrWhiteSpace(merchant);
        ArgumentNullException.ThrowIfNull(aliases);

        return IncludedMerchant(ledger, merchant, aliases)
            .Where(entry => month is null || entry.Transaction.Month == month.Value)
            .OrderByDescending(entry => entry.NetSpending)
            .ThenByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .ToArray();
    }

    private static IReadOnlyList<MerchantOverviewEntry> BuildOverview(
        IReadOnlyList<SpendingLedgerEntry> currentLedger,
        IReadOnlyList<SpendingLedgerEntry> comparisonLedger,
        IReadOnlyList<YearMonth> currentMonths,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        SpendingLedgerEntry[] current = currentLedger.Where(entry => entry.Included).ToArray();
        if (current.Length == 0)
            return [];

        Dictionary<string, decimal> comparison = comparisonLedger
            .Where(entry => entry.Included)
            .GroupBy(entry => Merchant(entry.Transaction, aliases), StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Sum(entry => entry.NetSpending), StringComparer.Ordinal);
        decimal total = current.Sum(entry => entry.NetSpending);

        return current
            .GroupBy(entry => Merchant(entry.Transaction, aliases), StringComparer.Ordinal)
            .Select(group =>
            {
                SpendingLedgerEntry[] values = group.ToArray();
                decimal spending = values.Sum(entry => entry.NetSpending);
                decimal comparisonSpending = comparison.GetValueOrDefault(group.Key);
                decimal change = spending - comparisonSpending;
                Dictionary<YearMonth, decimal> monthly = values
                    .GroupBy(entry => entry.Transaction.Month)
                    .ToDictionary(month => month.Key, month => month.Sum(entry => entry.NetSpending));
                return new MerchantOverviewEntry(
                    group.Key,
                    spending,
                    total == 0m ? 0m : spending / total * 100m,
                    currentMonths.Count == 0 ? 0m : spending / currentMonths.Count,
                    comparisonSpending,
                    change,
                    comparisonSpending == 0m ? null : change / decimal.Abs(comparisonSpending) * 100m,
                    values.Length,
                    values.Length == 0 ? 0m : spending / values.Length,
                    Mode(values.Select(entry => entry.Transaction.Category)),
                    Mode(values.Select(entry => entry.Transaction.Group)),
                    Mode(values.Select(entry => entry.Transaction.Account)),
                    values.Min(entry => entry.Transaction.Date),
                    values.Max(entry => entry.Transaction.Date),
                    currentMonths.Select(month => monthly.GetValueOrDefault(month)).ToArray());
            })
            .OrderByDescending(entry => entry.Spending)
            .ThenBy(entry => entry.Merchant, StringComparer.Ordinal)
            .ToArray();
    }

    private static MerchantPeriodSummary Summarize(IReadOnlyList<MerchantOverviewEntry> overview, int monthCount)
    {
        decimal total = overview.Sum(entry => entry.Spending);
        decimal repeat = overview.Where(entry => entry.TransactionCount >= 2).Sum(entry => entry.Spending);
        return new MerchantPeriodSummary(
            total,
            monthCount == 0 ? 0m : total / monthCount,
            overview.Count,
            total == 0m ? 0m : repeat / total * 100m);
    }

    private static Dictionary<YearMonth, (decimal Spending, int Transactions)> Monthly(
        IEnumerable<SpendingLedgerEntry> ledger,
        string merchant,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
        => IncludedMerchant(ledger, merchant, aliases)
            .GroupBy(entry => entry.Transaction.Month)
            .ToDictionary(
                group => group.Key,
                group => (group.Sum(entry => entry.NetSpending), group.Count()));

    private static IEnumerable<SpendingLedgerEntry> IncludedMerchant(
        IEnumerable<SpendingLedgerEntry> ledger,
        string merchant,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
        => ledger.Where(entry => entry.Included
            && string.Equals(Merchant(entry.Transaction, aliases), merchant, StringComparison.Ordinal));

    private static string Merchant(FinancialTransaction transaction, IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
        => MerchantNameNormalizer.Normalize(transaction.Description, aliases);

    private static string Dimension(FinancialTransaction transaction, string dimension)
    {
        string value = dimension switch
        {
            "Category" => transaction.Category,
            "Account" => transaction.Account,
            "Group" => transaction.Group,
            _ => throw new ArgumentOutOfRangeException(nameof(dimension))
        };
        return string.IsNullOrWhiteSpace(value) ? "Unspecified" : value.Trim();
    }

    private static string Mode(IEnumerable<string> values)
        => values
            .Select(value => string.IsNullOrWhiteSpace(value) ? "Unknown" : value.Trim())
            .GroupBy(value => value, StringComparer.Ordinal)
            .OrderByDescending(group => group.Count())
            .ThenBy(group => group.Key, StringComparer.Ordinal)
            .Select(group => group.Key)
            .FirstOrDefault("Unknown");
}
