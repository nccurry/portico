namespace Portico.Finance;

/// <summary>Names the source column used for one year-over-year comparison.</summary>
public enum YearOverYearDimension
{
    /// <summary>Compares one expense category.</summary>
    Category,

    /// <summary>Compares one expense group.</summary>
    Group
}

/// <summary>Represents one calendar-month point in a year-over-year spending line.</summary>
public sealed record YearOverYearHistoryPoint(
    int Year,
    int Month,
    decimal Spending,
    bool IsCurrentYear);

/// <summary>Represents one yearly total through the source data's current month.</summary>
public sealed record YearOverYearTotal(
    int Year,
    decimal SpendingThroughMonth,
    decimal? Change,
    decimal? ChangePercent);

/// <summary>Represents the three metrics displayed at the top of a comparison card.</summary>
public sealed record YearOverYearSummary(
    int CurrentYear,
    decimal CurrentTotal,
    int? PreviousYear,
    decimal? PreviousTotal,
    decimal? Change,
    decimal? ChangePercent,
    int ThroughMonth);

/// <summary>Contains one source-compatible category or group comparison.</summary>
public sealed record YearOverYearComparison(
    YearOverYearDimension Dimension,
    string Entity,
    IReadOnlyList<YearOverYearHistoryPoint> History,
    IReadOnlyList<YearOverYearTotal> Totals,
    YearOverYearSummary Summary,
    IReadOnlyList<FinancialTransaction> Transactions);

/// <summary>Builds source-compatible calendar-year expense comparisons.</summary>
public static class YearOverYearAnalysisCalculator
{
    /// <summary>Gets expense categories ranked by included net spending for a configured set.</summary>
    public static IReadOnlyList<string> PresetCategories(
        IEnumerable<FinancialTransaction> transactions,
        FinanceSettings settings,
        string transactionSetKey)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(settings);
        ArgumentException.ThrowIfNullOrWhiteSpace(transactionSetKey);

        return IncludedExpenses(transactions, settings, transactionSetKey)
            .Where(transaction => !string.IsNullOrWhiteSpace(transaction.Category))
            .GroupBy(transaction => transaction.Category.Trim(), StringComparer.Ordinal)
            .Select(group => new
            {
                Category = group.Key,
                Spending = group.Sum(transaction => -transaction.Amount)
            })
            .OrderByDescending(value => value.Spending)
            .ThenBy(value => value.Category, StringComparer.Ordinal)
            .Select(value => value.Category)
            .ToArray();
    }

    /// <summary>Gets all source-visible single category or group choices.</summary>
    public static IReadOnlyList<string> Entities(
        IEnumerable<FinancialTransaction> transactions,
        YearOverYearDimension dimension)
    {
        ArgumentNullException.ThrowIfNull(transactions);

        return transactions
            .Where(transaction => transaction.Kind == TransactionKind.Expense)
            .Select(transaction => ValueFor(transaction, dimension))
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value.Trim())
            .Distinct(StringComparer.Ordinal)
            .OrderBy(value => value, StringComparer.Ordinal)
            .ToArray();
    }

    /// <summary>Builds one selected comparison or returns null when no included source rows match it.</summary>
    public static YearOverYearComparison? Build(
        IEnumerable<FinancialTransaction> transactions,
        FinanceSettings settings,
        string? transactionSetKey,
        YearOverYearDimension dimension,
        string entity)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(settings);
        ArgumentException.ThrowIfNullOrWhiteSpace(entity);

        FinancialTransaction[] source = transactions.ToArray();
        if (source.Length == 0)
            return null;

        FinancialTransaction[] selected = IncludedExpenses(source, settings, transactionSetKey)
            .Where(transaction => string.Equals(ValueFor(transaction, dimension).Trim(), entity.Trim(), StringComparison.Ordinal))
            .ToArray();
        if (selected.Length == 0)
            return null;

        YearMonth coverageStart = source.Min(transaction => transaction.Month);
        YearMonth coverageEnd = source.Max(transaction => transaction.Month);
        int firstYear = selected.Min(transaction => transaction.Date.Year);
        int currentYear = coverageEnd.Year;
        var spendingByMonth = selected
            .GroupBy(transaction => transaction.Month)
            .ToDictionary(group => group.Key, group => group.Sum(transaction => -transaction.Amount));
        var history = new List<YearOverYearHistoryPoint>();
        for (int year = firstYear; year <= currentYear; year++)
        {
            for (int month = 1; month <= 12; month++)
            {
                var current = new YearMonth(year, month);
                if (current.CompareTo(coverageStart) < 0 || current.CompareTo(coverageEnd) > 0)
                    continue;

                history.Add(new YearOverYearHistoryPoint(
                    year,
                    month,
                    spendingByMonth.GetValueOrDefault(current),
                    year == currentYear));
            }
        }

        IReadOnlyList<YearOverYearTotal> totals = BuildTotals(history, coverageEnd.Month);
        YearOverYearTotal currentTotal = totals.Single(total => total.Year == currentYear);
        YearOverYearTotal? previousTotal = totals.FirstOrDefault(total => total.Year == currentYear - 1);
        var summary = new YearOverYearSummary(
            currentYear,
            currentTotal.SpendingThroughMonth,
            previousTotal?.Year,
            previousTotal?.SpendingThroughMonth,
            previousTotal is null ? null : currentTotal.SpendingThroughMonth - previousTotal.SpendingThroughMonth,
            previousTotal is null || previousTotal.SpendingThroughMonth == 0m
                ? null
                : (currentTotal.SpendingThroughMonth - previousTotal.SpendingThroughMonth)
                    / decimal.Abs(previousTotal.SpendingThroughMonth) * 100m,
            coverageEnd.Month);

        return new YearOverYearComparison(
            dimension,
            entity.Trim(),
            history,
            totals,
            summary,
            selected.OrderByDescending(transaction => transaction.Date).ToArray());
    }

    private static IReadOnlyList<FinancialTransaction> IncludedExpenses(
        IEnumerable<FinancialTransaction> transactions,
        FinanceSettings settings,
        string? transactionSetKey)
    {
        FinancialTransaction[] values = transactions.ToArray();
        IReadOnlyList<FinancialTransaction> selected = transactionSetKey is null
            ? values
            : TransactionSetMatcher.Select(values, transactionSetKey, settings.TransactionSets, settings.MerchantAliases);
        return selected
            .Where(transaction => transaction.Kind == TransactionKind.Expense)
            .Where(transaction => !string.Equals(transaction.Group, "Transfer", StringComparison.Ordinal))
            .ToArray();
    }

    private static IReadOnlyList<YearOverYearTotal> BuildTotals(
        IReadOnlyList<YearOverYearHistoryPoint> history,
        int throughMonth)
    {
        var totals = new List<YearOverYearTotal>();
        decimal? previous = null;
        foreach (IGrouping<int, YearOverYearHistoryPoint> year in history.GroupBy(point => point.Year).OrderBy(group => group.Key))
        {
            decimal spending = year
                .Where(point => point.Month <= throughMonth)
                .Sum(point => point.Spending);
            decimal? change = previous is null ? null : spending - previous.Value;
            decimal? changePercent = previous is null || previous.Value == 0m
                ? null
                : change!.Value / decimal.Abs(previous.Value) * 100m;
            totals.Add(new YearOverYearTotal(year.Key, spending, change, changePercent));
            previous = spending;
        }

        return totals;
    }

    private static string ValueFor(FinancialTransaction transaction, YearOverYearDimension dimension)
        => dimension == YearOverYearDimension.Category ? transaction.Category : transaction.Group;
}
