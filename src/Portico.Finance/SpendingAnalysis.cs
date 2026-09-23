namespace Portico.Finance;

/// <summary>Chooses the matched period used for the Spending by category comparison.</summary>
public enum SpendingComparison
{
    /// <summary>Compares the current months with the immediately preceding months.</summary>
    PreviousPeriod,

    /// <summary>Compares the current months with the same calendar months one year earlier.</summary>
    LastYear
}

/// <summary>Chooses whether the Spending by category page groups rows by group or category.</summary>
public enum SpendingBreakdown
{
    /// <summary>Groups expense rows by their configured group.</summary>
    Group,

    /// <summary>Groups expense rows by their configured category.</summary>
    Category
}

/// <summary>Holds the page-local adjustments applied after a named spending view is selected.</summary>
public sealed record SpendingAdjustments(
    IReadOnlyList<string> ExcludedGroups,
    IReadOnlyList<string> ExcludedCategories,
    IReadOnlyList<string> IncludedDescriptions,
    IReadOnlyList<string> ExcludedDescriptions,
    bool ExcludeLargeExpenses,
    decimal ExpenseLimit)
{
    /// <summary>Creates the source page's empty adjustment set.</summary>
    public static SpendingAdjustments Default(decimal expenseLimit)
        => new([], [], [], [], false, expenseLimit);

    /// <summary>Gets whether the source Adjust view label should show that its defaults changed.</summary>
    public bool IsModified => ExcludedGroups.Count > 0
        || ExcludedCategories.Count > 0
        || IncludedDescriptions.Count > 0
        || ExcludedDescriptions.Count > 0
        || ExcludeLargeExpenses;
}

/// <summary>Describes one current or comparison month range.</summary>
public sealed record SpendingPeriod(
    IReadOnlyList<YearMonth> CurrentMonths,
    IReadOnlyList<YearMonth> ComparisonMonths)
{
    /// <summary>Gets whether the analysis has a source month to display.</summary>
    public bool HasMonths => CurrentMonths.Count > 0;
}

/// <summary>Represents one expense row together with its source-style inclusion result.</summary>
public sealed record SpendingLedgerEntry(
    FinancialTransaction Transaction,
    bool Included,
    decimal NetSpending,
    IReadOnlyList<LedgerExclusion> Exclusions)
{
    /// <summary>Supports the old Dashboard until Desktop owns the wording.</summary>
    public string ExclusionReason => LegacyFinanceCopy.Exclusions(Exclusions);
}

/// <summary>Represents one ranked current and comparison spending row.</summary>
public sealed record SpendingOverviewEntry(
    string Entity,
    string Group,
    decimal Spending,
    decimal SharePercent,
    decimal AverageMonthlySpending,
    decimal ComparisonSpending,
    decimal Change,
    decimal? ChangePercent,
    int TransactionCount,
    IReadOnlyList<decimal> MonthlyTrend);

/// <summary>Represents the metric deck for a matched spending period.</summary>
public sealed record SpendingPeriodSummary(
    decimal TotalSpending,
    decimal AverageMonthlySpending,
    decimal ComparisonSpending,
    decimal Change,
    decimal? ChangePercent,
    int TransactionCount,
    int MonthCount);

/// <summary>Contains all financial values needed by the source-shaped Spending by category page.</summary>
public sealed record SpendingAnalysisResult(
    SpendingPeriod Period,
    IReadOnlyList<SpendingLedgerEntry> CurrentLedger,
    IReadOnlyList<SpendingLedgerEntry> ComparisonLedger,
    SpendingPeriodSummary Summary,
    IReadOnlyList<SpendingOverviewEntry> Overview);

/// <summary>Builds the source-compatible expense ledger, summary, and ranked spending rows.</summary>
public static class SpendingAnalysisCalculator
{
    /// <summary>Builds a complete matched-period spending analysis from normalized transactions.</summary>
    public static SpendingAnalysisResult Build(
        IEnumerable<FinancialTransaction> transactions,
        FinanceSettings settings,
        string transactionSetKey,
        int lookbackMonths,
        SpendingComparison comparison,
        SpendingBreakdown breakdown,
        SpendingAdjustments adjustments)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(settings);
        ArgumentException.ThrowIfNullOrWhiteSpace(transactionSetKey);
        ArgumentNullException.ThrowIfNull(adjustments);
        if (lookbackMonths <= 0)
            throw new ArgumentOutOfRangeException(nameof(lookbackMonths));

        FinancialTransaction[] values = transactions
            .Where(transaction => transaction.Kind == TransactionKind.Expense)
            .ToArray();
        SpendingPeriod period = Period(values, lookbackMonths, comparison);
        if (!period.HasMonths)
            return Empty(period, lookbackMonths);

        TransactionSetDefinition selectedSet = settings.TransactionSet(transactionSetKey);
        var includedBySet = TransactionSetMatcher.Select(values, transactionSetKey, settings.TransactionSets, settings.MerchantAliases)
            .Select(transaction => transaction.Id)
            .ToHashSet(StringComparer.Ordinal);

        IReadOnlyList<SpendingLedgerEntry> current = BuildLedger(
            values,
            period.CurrentMonths[0],
            period.CurrentMonths[^1],
            selectedSet,
            includedBySet,
            adjustments);
        IReadOnlyList<SpendingLedgerEntry> previous = BuildLedger(
            values,
            period.ComparisonMonths[0],
            period.ComparisonMonths[^1],
            selectedSet,
            includedBySet,
            adjustments);
        IReadOnlyList<SpendingOverviewEntry> overview = BuildOverview(current, previous, period.CurrentMonths, breakdown);
        SpendingPeriodSummary summary = Summarize(current, previous, period.CurrentMonths.Count);
        return new SpendingAnalysisResult(period, current, previous, summary, overview);
    }

    /// <summary>Returns the current month sequence used by a source-shaped spending page.</summary>
    public static IReadOnlyList<YearMonth> CurrentMonths(
        IEnumerable<FinancialTransaction> transactions,
        int lookbackMonths)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        if (lookbackMonths <= 0)
            throw new ArgumentOutOfRangeException(nameof(lookbackMonths));

        FinancialTransaction[] values = transactions
            .Where(transaction => transaction.Kind == TransactionKind.Expense)
            .ToArray();
        return Period(values, lookbackMonths, SpendingComparison.PreviousPeriod).CurrentMonths;
    }

    /// <summary>Builds matching current and comparison monthly values for one selected entity.</summary>
    public static IReadOnlyList<(YearMonth CurrentMonth, YearMonth ComparisonMonth, decimal Current, decimal Comparison)> EntityHistory(
        SpendingAnalysisResult analysis,
        SpendingBreakdown breakdown,
        string entity)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        ArgumentException.ThrowIfNullOrWhiteSpace(entity);

        var current = TotalsByMonth(analysis.CurrentLedger, breakdown, entity);
        var comparison = TotalsByMonth(analysis.ComparisonLedger, breakdown, entity);
        var rows = new List<(YearMonth CurrentMonth, YearMonth ComparisonMonth, decimal Current, decimal Comparison)>(analysis.Period.CurrentMonths.Count);
        for (int index = 0; index < analysis.Period.CurrentMonths.Count; index++)
        {
            YearMonth currentMonth = analysis.Period.CurrentMonths[index];
            YearMonth comparisonMonth = analysis.Period.ComparisonMonths[index];
            rows.Add((
                currentMonth,
                comparisonMonth,
                current.GetValueOrDefault(currentMonth),
                comparison.GetValueOrDefault(comparisonMonth)));
        }

        return rows;
    }

    /// <summary>Builds a stable merchant ranking for currently included ledger rows.</summary>
    public static IReadOnlyList<(string Merchant, decimal Spending, decimal SharePercent, int Transactions, decimal AverageTransaction, DateOnly LastTransaction)> Merchants(
        IEnumerable<SpendingLedgerEntry> ledger,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        ArgumentNullException.ThrowIfNull(ledger);
        ArgumentNullException.ThrowIfNull(aliases);

        SpendingLedgerEntry[] included = ledger.Where(entry => entry.Included).ToArray();
        decimal total = included.Sum(entry => entry.NetSpending);
        return included
            .GroupBy(entry => TransactionSetMatcher.NormalizeMerchant(entry.Transaction.Description, aliases), StringComparer.Ordinal)
            .Select(group =>
            {
                decimal spending = group.Sum(entry => entry.NetSpending);
                int count = group.Count();
                return (
                    Merchant: group.Key,
                    Spending: spending,
                    SharePercent: total == 0m ? 0m : spending / total * 100m,
                    Transactions: count,
                    AverageTransaction: count == 0 ? 0m : spending / count,
                    LastTransaction: group.Max(entry => entry.Transaction.Date));
            })
            .OrderByDescending(item => item.Spending)
            .ThenBy(item => item.Merchant, StringComparer.Ordinal)
            .ToArray();
    }

    private static SpendingAnalysisResult Empty(SpendingPeriod period, int lookbackMonths)
        => new(
            period,
            [],
            [],
            new SpendingPeriodSummary(0m, 0m, 0m, 0m, null, 0, lookbackMonths),
            []);

    private static SpendingPeriod Period(
        IReadOnlyList<FinancialTransaction> transactions,
        int lookbackMonths,
        SpendingComparison comparison)
    {
        if (transactions.Count == 0)
            return new SpendingPeriod([], []);

        YearMonth latest = transactions.Max(transaction => transaction.Month);
        YearMonth currentStart = latest.AddMonths(1 - lookbackMonths);
        IReadOnlyList<YearMonth> current = YearMonth.InclusiveRange(currentStart, latest);
        IReadOnlyList<YearMonth> previous = comparison == SpendingComparison.PreviousPeriod
            ? YearMonth.InclusiveRange(currentStart.AddMonths(-lookbackMonths), currentStart.AddMonths(-1))
            : YearMonth.InclusiveRange(currentStart.AddMonths(-12), latest.AddMonths(-12));
        return new SpendingPeriod(current, previous);
    }

    private static IReadOnlyList<SpendingLedgerEntry> BuildLedger(
        IEnumerable<FinancialTransaction> values,
        YearMonth start,
        YearMonth end,
        TransactionSetDefinition selectedSet,
        IReadOnlySet<string> includedBySet,
        SpendingAdjustments adjustments)
        => values
            .Where(transaction => transaction.Kind == TransactionKind.Expense
                && transaction.Month.CompareTo(start) >= 0
                && transaction.Month.CompareTo(end) <= 0)
            .Select(transaction => CreateLedgerEntry(transaction, selectedSet, includedBySet.Contains(transaction.Id), adjustments))
            .ToArray();

    private static SpendingLedgerEntry CreateLedgerEntry(
        FinancialTransaction transaction,
        TransactionSetDefinition selectedSet,
        bool transactionSetIncluded,
        SpendingAdjustments adjustments)
    {
        var reasons = new List<LedgerExclusion>();
        string group = string.IsNullOrWhiteSpace(transaction.Group) ? "Unknown" : transaction.Group;
        string category = string.IsNullOrWhiteSpace(transaction.Category) ? "Unknown" : transaction.Category;
        bool includeMode = adjustments.IncludedDescriptions.Count > 0;
        bool includedDescription = MatchesAny(transaction.Description, adjustments.IncludedDescriptions);

        if (string.Equals(group, "Transfer", StringComparison.Ordinal))
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.TransferGroup));
        if (!transactionSetIncluded)
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.OutsideConfiguredSet, selectedSet.Label));
        if (includeMode && !includedDescription)
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.OutsideIncludedDescriptions));
        if (Contains(adjustments.ExcludedGroups, group))
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.ExcludedExpenseGroup, group));
        if (Contains(adjustments.ExcludedCategories, category))
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.ExcludedCategory, category));
        foreach (string term in MatchingTerms(transaction.Description, adjustments.ExcludedDescriptions))
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.ExcludedDescription, term));
        if (adjustments.ExcludeLargeExpenses && decimal.Abs(transaction.Amount) > adjustments.ExpenseLimit)
        {
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.ExpenseOverLimit, Limit: adjustments.ExpenseLimit));
        }

        return new SpendingLedgerEntry(transaction, reasons.Count == 0, -transaction.Amount, reasons);
    }

    private static IReadOnlyList<SpendingOverviewEntry> BuildOverview(
        IReadOnlyList<SpendingLedgerEntry> currentLedger,
        IReadOnlyList<SpendingLedgerEntry> comparisonLedger,
        IReadOnlyList<YearMonth> currentMonths,
        SpendingBreakdown breakdown)
    {
        SpendingLedgerEntry[] current = currentLedger.Where(entry => entry.Included).ToArray();
        SpendingLedgerEntry[] comparison = comparisonLedger.Where(entry => entry.Included).ToArray();
        Dictionary<string, decimal> currentTotals = Totals(current, breakdown);
        Dictionary<string, decimal> comparisonTotals = Totals(comparison, breakdown);
        string[] entities = currentTotals.Keys.Union(comparisonTotals.Keys, StringComparer.Ordinal).ToArray();
        if (entities.Length == 0)
            return [];

        Dictionary<string, int> counts = current
            .GroupBy(entry => Entity(entry.Transaction, breakdown), StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Count(), StringComparer.Ordinal);
        Dictionary<string, string> groups = GroupsForCategories(current.Concat(comparison));
        decimal total = currentTotals.Values.Sum();
        return entities
            .Select(entity =>
            {
                decimal spending = currentTotals.GetValueOrDefault(entity);
                decimal comparisonSpending = comparisonTotals.GetValueOrDefault(entity);
                decimal change = spending - comparisonSpending;
                Dictionary<YearMonth, decimal> monthly = TotalsByMonth(current, breakdown, entity);
                return new SpendingOverviewEntry(
                    entity,
                    breakdown == SpendingBreakdown.Category ? groups.GetValueOrDefault(entity, string.Empty) : string.Empty,
                    spending,
                    total == 0m ? 0m : spending / total * 100m,
                    currentMonths.Count == 0 ? 0m : spending / currentMonths.Count,
                    comparisonSpending,
                    change,
                    comparisonSpending == 0m ? null : change / decimal.Abs(comparisonSpending) * 100m,
                    counts.GetValueOrDefault(entity),
                    currentMonths.Select(month => monthly.GetValueOrDefault(month)).ToArray());
            })
            .OrderByDescending(entry => entry.Spending)
            .ThenBy(entry => entry.Entity, StringComparer.Ordinal)
            .ToArray();
    }

    private static SpendingPeriodSummary Summarize(
        IReadOnlyList<SpendingLedgerEntry> current,
        IReadOnlyList<SpendingLedgerEntry> comparison,
        int monthCount)
    {
        decimal total = current.Where(entry => entry.Included).Sum(entry => entry.NetSpending);
        decimal comparisonTotal = comparison.Where(entry => entry.Included).Sum(entry => entry.NetSpending);
        decimal change = total - comparisonTotal;
        return new SpendingPeriodSummary(
            total,
            monthCount == 0 ? 0m : total / monthCount,
            comparisonTotal,
            change,
            comparisonTotal == 0m ? null : change / decimal.Abs(comparisonTotal) * 100m,
            current.Count(entry => entry.Included),
            monthCount);
    }

    private static Dictionary<string, decimal> Totals(
        IEnumerable<SpendingLedgerEntry> ledger,
        SpendingBreakdown breakdown)
        => ledger
            .GroupBy(entry => Entity(entry.Transaction, breakdown), StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Sum(entry => entry.NetSpending), StringComparer.Ordinal);

    private static Dictionary<YearMonth, decimal> TotalsByMonth(
        IEnumerable<SpendingLedgerEntry> ledger,
        SpendingBreakdown breakdown,
        string entity)
        => ledger
            .Where(entry => entry.Included && string.Equals(Entity(entry.Transaction, breakdown), entity, StringComparison.Ordinal))
            .GroupBy(entry => entry.Transaction.Month)
            .ToDictionary(group => group.Key, group => group.Sum(entry => entry.NetSpending));

    private static Dictionary<string, string> GroupsForCategories(IEnumerable<SpendingLedgerEntry> entries)
        => entries
            .GroupBy(entry => Category(entry.Transaction), StringComparer.Ordinal)
            .ToDictionary(
                group => group.Key,
                group => group
                    .GroupBy(entry => Group(entry.Transaction), StringComparer.Ordinal)
                    .OrderByDescending(candidate => candidate.Count())
                    .ThenBy(candidate => candidate.Key, StringComparer.Ordinal)
                    .First()
                    .Key,
                StringComparer.Ordinal);

    private static string Entity(FinancialTransaction transaction, SpendingBreakdown breakdown)
        => breakdown == SpendingBreakdown.Group ? Group(transaction) : Category(transaction);

    private static string Group(FinancialTransaction transaction)
        => string.IsNullOrWhiteSpace(transaction.Group) ? "Unknown" : transaction.Group;

    private static string Category(FinancialTransaction transaction)
        => string.IsNullOrWhiteSpace(transaction.Category) ? "Unknown" : transaction.Category;

    private static bool Contains(IEnumerable<string> values, string value)
        => values.Any(current => string.Equals(current, value, StringComparison.Ordinal));

    private static bool MatchesAny(string value, IEnumerable<string> terms)
        => MatchingTerms(value, terms).Any();

    private static IEnumerable<string> MatchingTerms(string value, IEnumerable<string> terms)
    {
        foreach (string term in terms)
        {
            if (!string.IsNullOrWhiteSpace(term)
                && value.Contains(term, StringComparison.OrdinalIgnoreCase))
            {
                yield return term;
            }
        }
    }
}
