namespace Portico.Finance;

/// <summary>Holds category, group, description, and amount filters for the Income and savings calculation.</summary>
public sealed record IncomeSavingsAdjustments(
    IReadOnlyList<string> ExcludedIncomeCategories,
    IReadOnlyList<string> ExcludedExpenseGroups,
    IReadOnlyList<string> ExcludedExpenseCategories,
    IReadOnlyList<string> IncludedDescriptions,
    IReadOnlyList<string> ExcludedDescriptions,
    bool ExcludeLargeIncome,
    decimal IncomeLimit,
    bool ExcludeLargeExpenses,
    decimal ExpenseLimit,
    decimal TargetRate)
{
    /// <summary>Creates the configured default filters for the selected calculation view.</summary>
    public static IncomeSavingsAdjustments Default(FinanceSettings settings, bool regular)
    {
        ArgumentNullException.ThrowIfNull(settings);

        IReadOnlyList<string> categories = regular ? settings.IncomeSavings.ExcludeCategories : [];
        IReadOnlyList<string> groups = regular ? settings.IncomeSavings.ExcludeGroups : [];
        return new IncomeSavingsAdjustments(
            categories,
            groups,
            categories,
            [],
            [],
            false,
            settings.Thresholds.Income,
            false,
            settings.Thresholds.Expense,
            settings.IncomeSavings.TargetRate);
    }

    /// <summary>Gets whether the source Adjust calculation label should show that filters changed.</summary>
    public bool IsModifiedFrom(IncomeSavingsAdjustments defaults)
    {
        ArgumentNullException.ThrowIfNull(defaults);
        return !SameValues(ExcludedIncomeCategories, defaults.ExcludedIncomeCategories)
            || !SameValues(ExcludedExpenseGroups, defaults.ExcludedExpenseGroups)
            || !SameValues(ExcludedExpenseCategories, defaults.ExcludedExpenseCategories)
            || IncludedDescriptions.Count > 0
            || ExcludedDescriptions.Count > 0
            || ExcludeLargeIncome
            || ExcludeLargeExpenses;
    }

    private static bool SameValues(IEnumerable<string> first, IEnumerable<string> second)
        => first.ToHashSet(StringComparer.Ordinal).SetEquals(second);
}

/// <summary>Describes the current and preceding calendar month sequences for an income report.</summary>
public sealed record IncomeSavingsPeriod(
    IReadOnlyList<YearMonth> CurrentMonths,
    IReadOnlyList<YearMonth> PreviousMonths)
{
    /// <summary>Gets whether the source has a current period to display.</summary>
    public bool HasMonths => CurrentMonths.Count > 0;
}

/// <summary>Records whether an income or expense transaction was included in the calculation.</summary>
public sealed record IncomeSavingsLedgerEntry(
    FinancialTransaction Transaction,
    bool Included,
    IReadOnlyList<LedgerExclusion> Exclusions)
{
    /// <summary>Gets the row's positive income contribution when it is included.</summary>
    public decimal Income => Included && Transaction.Kind == TransactionKind.Income ? Transaction.Amount : 0m;

    /// <summary>Gets the row's positive or negative spending contribution when it is included.</summary>
    public decimal NetExpenses => Included && Transaction.Kind == TransactionKind.Expense ? -Transaction.Amount : 0m;
}

/// <summary>Represents one month of included income, spending, surplus, and savings rate.</summary>
public sealed record IncomeSavingsMonth(
    YearMonth Month,
    decimal Income,
    decimal NetExpenses,
    decimal Surplus,
    decimal? SavingsRatePercent);

/// <summary>Contains the typed financial values needed by the Income and savings page.</summary>
public sealed record IncomeSavingsAnalysisResult(
    IncomeSavingsPeriod Period,
    IReadOnlyList<IncomeSavingsLedgerEntry> CurrentLedger,
    IReadOnlyList<IncomeSavingsLedgerEntry> PreviousLedger,
    IReadOnlyList<IncomeSavingsMonth> CurrentMonthly,
    IReadOnlyList<IncomeSavingsMonth> PreviousMonthly,
    CashFlowSummary CurrentSummary,
    CashFlowSummary PreviousSummary,
    bool HasFullPreviousPeriod);

/// <summary>Builds source-compatible Income and savings ledger and monthly results.</summary>
public static class IncomeSavingsAnalysisCalculator
{
    /// <summary>Builds the selected and matched-prior cash-flow analysis.</summary>
    public static IncomeSavingsAnalysisResult Build(
        IEnumerable<FinancialTransaction> transactions,
        int lookbackMonths,
        IncomeSavingsAdjustments adjustments)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(adjustments);
        if (lookbackMonths <= 0)
            throw new ArgumentOutOfRangeException(nameof(lookbackMonths));

        FinancialTransaction[] source = transactions.ToArray();
        IncomeSavingsPeriod period = Period(source, lookbackMonths);
        if (!period.HasMonths)
            return Empty(period);

        IReadOnlyList<IncomeSavingsLedgerEntry> current = BuildLedger(
            source,
            period.CurrentMonths[0],
            period.CurrentMonths[^1],
            adjustments);
        IReadOnlyList<IncomeSavingsLedgerEntry> previous = BuildLedger(
            source,
            period.PreviousMonths[0],
            period.PreviousMonths[^1],
            adjustments);
        IReadOnlyList<IncomeSavingsMonth> monthly = BuildMonthly(current, period.CurrentMonths);
        IReadOnlyList<IncomeSavingsMonth> priorMonthly = BuildMonthly(previous, period.PreviousMonths);
        bool fullPreviousPeriod = source.Length > 0 && source.Min(transaction => transaction.Date) <= period.PreviousMonths[0].Start;

        return new IncomeSavingsAnalysisResult(
            period,
            current,
            previous,
            monthly,
            priorMonthly,
            Summarize(monthly),
            Summarize(priorMonthly),
            fullPreviousPeriod);
    }

    /// <summary>Returns stable nonblank category options for the selected transaction type.</summary>
    public static IReadOnlyList<string> Categories(IEnumerable<FinancialTransaction> transactions, TransactionKind kind)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        return transactions
            .Where(transaction => transaction.Kind == kind)
            .Select(transaction => transaction.Category.Trim())
            .Where(category => !string.IsNullOrWhiteSpace(category))
            .Distinct(StringComparer.Ordinal)
            .OrderBy(category => category, StringComparer.Ordinal)
            .ToArray();
    }

    /// <summary>Returns stable nonblank expense-group options.</summary>
    public static IReadOnlyList<string> ExpenseGroups(IEnumerable<FinancialTransaction> transactions)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        return transactions
            .Where(transaction => transaction.Kind == TransactionKind.Expense)
            .Select(transaction => transaction.Group.Trim())
            .Where(group => !string.IsNullOrWhiteSpace(group))
            .Distinct(StringComparer.Ordinal)
            .OrderBy(group => group, StringComparer.Ordinal)
            .ToArray();
    }

    private static IncomeSavingsAnalysisResult Empty(IncomeSavingsPeriod period)
    {
        CashFlowSummary summary = new(0m, 0m, 0m, null, 0m, 0, 0);
        return new IncomeSavingsAnalysisResult(period, [], [], [], [], summary, summary, false);
    }

    private static IncomeSavingsPeriod Period(IReadOnlyList<FinancialTransaction> transactions, int lookbackMonths)
    {
        if (transactions.Count == 0)
            return new IncomeSavingsPeriod([], []);

        YearMonth latest = transactions.Max(transaction => transaction.Month);
        YearMonth currentStart = latest.AddMonths(1 - lookbackMonths);
        IReadOnlyList<YearMonth> current = YearMonth.InclusiveRange(currentStart, latest);
        IReadOnlyList<YearMonth> previous = YearMonth.InclusiveRange(
            currentStart.AddMonths(-lookbackMonths),
            currentStart.AddMonths(-1));
        return new IncomeSavingsPeriod(current, previous);
    }

    private static IReadOnlyList<IncomeSavingsLedgerEntry> BuildLedger(
        IEnumerable<FinancialTransaction> source,
        YearMonth start,
        YearMonth end,
        IncomeSavingsAdjustments adjustments)
        => source
            .Where(transaction => transaction.Kind is TransactionKind.Income or TransactionKind.Expense)
            .Where(transaction => transaction.Month.CompareTo(start) >= 0 && transaction.Month.CompareTo(end) <= 0)
            .Select(transaction => CreateLedgerEntry(transaction, adjustments))
            .ToArray();

    private static IncomeSavingsLedgerEntry CreateLedgerEntry(
        FinancialTransaction transaction,
        IncomeSavingsAdjustments adjustments)
    {
        string group = Normalize(transaction.Group);
        string category = Normalize(transaction.Category);
        var reasons = new List<LedgerExclusion>();

        if (string.Equals(group, "Transfer", StringComparison.Ordinal))
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.TransferGroup));
        if (transaction.Kind == TransactionKind.Income
            && Contains(adjustments.ExcludedIncomeCategories, category))
        {
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.ExcludedIncomeCategory, category));
        }
        if (transaction.Kind == TransactionKind.Expense
            && Contains(adjustments.ExcludedExpenseGroups, group))
        {
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.ExcludedExpenseGroup, group));
        }
        if (transaction.Kind == TransactionKind.Expense
            && Contains(adjustments.ExcludedExpenseCategories, category))
        {
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.ExcludedExpenseCategory, category));
        }

        bool includeMode = adjustments.IncludedDescriptions.Count > 0;
        if (includeMode && !MatchesAny(transaction.Description, adjustments.IncludedDescriptions))
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.OutsideIncludedDescriptions));
        foreach (string term in MatchingTerms(transaction.Description, adjustments.ExcludedDescriptions))
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.ExcludedDescription, term));

        if (transaction.Kind == TransactionKind.Income
            && adjustments.ExcludeLargeIncome
            && decimal.Abs(transaction.Amount) > adjustments.IncomeLimit)
        {
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.IncomeOverLimit, Limit: adjustments.IncomeLimit));
        }
        if (transaction.Kind == TransactionKind.Expense
            && adjustments.ExcludeLargeExpenses
            && decimal.Abs(transaction.Amount) > adjustments.ExpenseLimit)
        {
            reasons.Add(new LedgerExclusion(LedgerExclusionReason.ExpenseOverLimit, Limit: adjustments.ExpenseLimit));
        }

        return new IncomeSavingsLedgerEntry(transaction, reasons.Count == 0, reasons);
    }

    private static IReadOnlyList<IncomeSavingsMonth> BuildMonthly(
        IEnumerable<IncomeSavingsLedgerEntry> ledger,
        IReadOnlyList<YearMonth> months)
    {
        var totals = ledger
            .Where(entry => entry.Included)
            .GroupBy(entry => entry.Transaction.Month)
            .ToDictionary(
                group => group.Key,
                group => (
                    Income: group.Sum(entry => entry.Income),
                    NetExpenses: group.Sum(entry => entry.NetExpenses)));
        var result = new List<IncomeSavingsMonth>(months.Count);
        foreach (YearMonth month in months)
        {
            (decimal income, decimal netExpenses) = totals.GetValueOrDefault(month);
            decimal surplus = income - netExpenses;
            result.Add(new IncomeSavingsMonth(
                month,
                income,
                netExpenses,
                surplus,
                income > 0m ? surplus / income * 100m : null));
        }

        return result;
    }

    private static CashFlowSummary Summarize(IReadOnlyList<IncomeSavingsMonth> monthly)
    {
        decimal income = monthly.Sum(month => month.Income);
        decimal expenses = monthly.Sum(month => month.NetExpenses);
        decimal surplus = monthly.Sum(month => month.Surplus);
        return new CashFlowSummary(
            income,
            expenses,
            surplus,
            income > 0m ? surplus / income * 100m : null,
            monthly.Count == 0 ? 0m : surplus / monthly.Count,
            monthly.Count(month => month.Surplus > 0m),
            monthly.Count);
    }

    private static string Normalize(string value)
        => string.IsNullOrWhiteSpace(value) ? "Unknown" : value.Trim();

    private static bool Contains(IEnumerable<string> values, string value)
        => values.Any(item => string.Equals(item, value, StringComparison.Ordinal));

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
