namespace Portico.Finance;

/// <summary>Specifies the exclusions applied to an income and expense report.</summary>
public sealed record IncomeExpensePolicy(
    IReadOnlyList<string> ExcludeCategories,
    IReadOnlyList<string> ExcludeGroups)
{
    /// <summary>Creates a policy from the configured regular income view.</summary>
    public static IncomeExpensePolicy From(IncomeSavingsSettings settings)
        => new(settings.ExcludeCategories, settings.ExcludeGroups);
}

/// <summary>Represents one monthly cash-flow result.</summary>
public sealed record MonthlyCashFlow(
    YearMonth Month,
    decimal Income,
    decimal SignedExpense,
    decimal NetExpenses,
    decimal Surplus,
    decimal? SavingsRatePercent);

/// <summary>Represents summary values for a cash-flow period.</summary>
public sealed record CashFlowSummary(
    decimal Income,
    decimal NetExpenses,
    decimal Surplus,
    decimal? SavingsRatePercent,
    decimal AverageMonthlySurplus,
    int PositiveSurplusMonths,
    int Months);

/// <summary>Represents one ranked spending aggregate.</summary>
public sealed record SpendingItem(
    string Entity,
    string Group,
    decimal Spending,
    decimal SharePercent,
    int TransactionCount);

/// <summary>Calculates cash flow and standard spending aggregates from normalized transactions.</summary>
public static class CashFlowCalculator
{
    /// <summary>Builds monthly cash flow, including empty months in a requested range.</summary>
    public static IReadOnlyList<MonthlyCashFlow> BuildMonthly(
        IEnumerable<FinancialTransaction> transactions,
        IncomeExpensePolicy policy,
        YearMonth? start = null,
        YearMonth? end = null)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(policy);
        if (start.HasValue != end.HasValue)
            throw new ArgumentException("Start and end months must be provided together.");
        if (start.HasValue && start.Value.CompareTo(end!.Value) > 0)
            return [];

        var totals = new Dictionary<YearMonth, (decimal Income, decimal Expense)>();
        foreach (FinancialTransaction transaction in transactions)
        {
            if (transaction.Kind is not (TransactionKind.Income or TransactionKind.Expense)
                || IsExcluded(transaction, policy)
                || !IsInside(transaction.Month, start, end))
            {
                continue;
            }

            totals.TryGetValue(transaction.Month, out (decimal Income, decimal Expense) current);
            totals[transaction.Month] = transaction.Kind == TransactionKind.Income
                ? (current.Income + transaction.Amount, current.Expense)
                : (current.Income, current.Expense + transaction.Amount);
        }

        IReadOnlyList<YearMonth> months = start.HasValue
            ? YearMonth.InclusiveRange(start.Value, end!.Value)
            : totals.Keys.Order().ToArray();
        var result = new List<MonthlyCashFlow>(months.Count);
        foreach (YearMonth month in months)
        {
            totals.TryGetValue(month, out (decimal Income, decimal Expense) total);
            decimal netExpenses = -total.Expense;
            decimal surplus = total.Income - netExpenses;
            decimal? savingsRate = total.Income > 0m ? surplus / total.Income * 100m : null;
            result.Add(new MonthlyCashFlow(month, total.Income, total.Expense, netExpenses, surplus, savingsRate));
        }

        return result;
    }

    /// <summary>Summarizes a sequence of monthly cash-flow values.</summary>
    public static CashFlowSummary Summarize(IEnumerable<MonthlyCashFlow> monthly)
    {
        ArgumentNullException.ThrowIfNull(monthly);

        decimal income = 0m;
        decimal expenses = 0m;
        decimal surplus = 0m;
        int positiveMonths = 0;
        int months = 0;
        foreach (MonthlyCashFlow value in monthly)
        {
            income += value.Income;
            expenses += value.NetExpenses;
            surplus += value.Surplus;
            positiveMonths += value.Surplus > 0m ? 1 : 0;
            months++;
        }

        return new CashFlowSummary(
            income,
            expenses,
            surplus,
            income > 0m ? surplus / income * 100m : null,
            months > 0 ? surplus / months : 0m,
            positiveMonths,
            months);
    }

    /// <summary>Builds ranked category or group spending with positive display amounts.</summary>
    public static IReadOnlyList<SpendingItem> AggregateSpending(
        IEnumerable<FinancialTransaction> transactions,
        Func<FinancialTransaction, string> dimension,
        YearMonth? start = null,
        YearMonth? end = null)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(dimension);
        if (start.HasValue != end.HasValue)
            throw new ArgumentException("Start and end months must be provided together.");

        var totals = new Dictionary<string, (string Group, decimal Spending, int Count)>(StringComparer.Ordinal);
        foreach (FinancialTransaction transaction in transactions)
        {
            if (transaction.Kind != TransactionKind.Expense || !IsInside(transaction.Month, start, end))
                continue;

            string entity = dimension(transaction);
            if (string.IsNullOrWhiteSpace(entity))
                entity = "Uncategorized";
            totals.TryGetValue(entity, out (string Group, decimal Spending, int Count) current);
            totals[entity] = (transaction.Group, current.Spending - transaction.Amount, current.Count + 1);
        }

        decimal overall = totals.Values.Sum(value => value.Spending);
        return totals
            .Select(pair => new SpendingItem(
                pair.Key,
                pair.Value.Group,
                pair.Value.Spending,
                overall == 0m ? 0m : pair.Value.Spending / overall * 100m,
                pair.Value.Count))
            .OrderByDescending(item => item.Spending)
            .ThenBy(item => item.Entity, StringComparer.Ordinal)
            .ToArray();
    }

    private static bool IsExcluded(FinancialTransaction transaction, IncomeExpensePolicy policy)
        => Contains(policy.ExcludeCategories, transaction.Category) || Contains(policy.ExcludeGroups, transaction.Group);

    private static bool IsInside(YearMonth month, YearMonth? start, YearMonth? end)
        => !start.HasValue || (month.CompareTo(start.Value) >= 0 && month.CompareTo(end!.Value) <= 0);

    private static bool Contains(IReadOnlyList<string> values, string value)
    {
        foreach (string current in values)
        {
            if (string.Equals(current, value, StringComparison.Ordinal))
                return true;
        }

        return false;
    }
}
