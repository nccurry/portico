namespace Portico.Finance;

/// <summary>Describes the source data selections that feed a Financial Independence scenario.</summary>
public sealed record FinancialIndependenceSourceFilters(
    IReadOnlyList<string> IncludedAccounts,
    int SpendingLookbackMonths,
    SpendingAdjustments Adjustments)
{
    /// <summary>Checks that the source data request stays within a bounded report range.</summary>
    public void Validate()
    {
        ArgumentNullException.ThrowIfNull(IncludedAccounts);
        ArgumentNullException.ThrowIfNull(Adjustments);
        if (SpendingLookbackMonths is < 1 or > 120)
            throw new ArgumentOutOfRangeException(nameof(SpendingLookbackMonths));
    }
}

/// <summary>Describes the editable annual assumptions used by a Financial Independence scenario.</summary>
public sealed record FinancialIndependenceScenario(
    decimal Assets,
    decimal AnnualSpending,
    decimal AnnualIncome,
    decimal ExpectedReturnRate,
    decimal WithdrawalRate,
    int ProjectionYears)
{
    /// <summary>Checks that the scenario can be passed to the financial calculator.</summary>
    public void Validate()
    {
        if (Assets < 0m || AnnualSpending < 0m || AnnualIncome < 0m)
            throw new ArgumentOutOfRangeException(nameof(Assets));
        if (ExpectedReturnRate is < 0m or > 100m)
            throw new ArgumentOutOfRangeException(nameof(ExpectedReturnRate));
        if (WithdrawalRate is <= 0m or > 100m)
            throw new ArgumentOutOfRangeException(nameof(WithdrawalRate));
        if (ProjectionYears is < 1 or > 100)
            throw new ArgumentOutOfRangeException(nameof(ProjectionYears));
    }
}

/// <summary>Describes one complete monthly spending source value.</summary>
public sealed record FinancialIndependenceMonthlySpending(YearMonth Month, decimal Spending);

/// <summary>Contains the account and transaction source values behind a Financial Independence scenario.</summary>
public sealed record FinancialIndependenceSourceAnalysis(
    IReadOnlyList<AccountBalance> Accounts,
    IReadOnlyList<FinancialTransaction> Expenses,
    IReadOnlyList<FinancialIndependenceMonthlySpending> MonthlySpending,
    decimal PortfolioValue,
    decimal AnnualSpending,
    YearMonth? StartMonth,
    YearMonth? EndMonth);

/// <summary>Builds source values for the Financial Independence scenario without UI dependencies.</summary>
public static class FinancialIndependenceSourceAnalysisCalculator
{
    /// <summary>Creates default source selections from the configured FI account rules.</summary>
    public static FinancialIndependenceSourceFilters DefaultFilters(
        IEnumerable<AccountBalance> accounts,
        FinanceSettings settings)
    {
        ArgumentNullException.ThrowIfNull(accounts);
        ArgumentNullException.ThrowIfNull(settings);
        AccountBalance[] available = accounts.ToArray();
        string[] included = available
            .Where(account => IsIncluded(account, settings.FinancialIndependence))
            .Select(account => account.Account)
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        return new FinancialIndependenceSourceFilters(
            included,
            settings.FinancialIndependence.SpendingLookbackMonths,
            SpendingAdjustments.Default(settings.Thresholds.Expense));
    }

    /// <summary>Creates the initial editable scenario from source values and configured assumptions.</summary>
    public static FinancialIndependenceScenario DefaultScenario(
        FinancialIndependenceSourceAnalysis source,
        FinancialIndependenceSettings settings)
    {
        ArgumentNullException.ThrowIfNull(source);
        ArgumentNullException.ThrowIfNull(settings);
        return new FinancialIndependenceScenario(
            source.PortfolioValue,
            source.AnnualSpending,
            0m,
            settings.ExpectedReturnRate,
            settings.WithdrawalRate,
            settings.ProjectionYears);
    }

    /// <summary>Builds selected accounts and trailing adjusted expense data for the scenario.</summary>
    public static FinancialIndependenceSourceAnalysis Build(
        IEnumerable<AccountBalance> accounts,
        IEnumerable<FinancialTransaction> transactions,
        FinancialIndependenceSourceFilters filters)
    {
        ArgumentNullException.ThrowIfNull(accounts);
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(filters);
        filters.Validate();

        var selectedAccounts = new HashSet<string>(filters.IncludedAccounts, StringComparer.Ordinal);
        AccountBalance[] selected = accounts
            .Where(account => selectedAccounts.Contains(account.Account))
            .OrderByDescending(account => account.SignedBalance)
            .ThenBy(account => account.Account, StringComparer.Ordinal)
            .ToArray();
        FinancialTransaction[] values = transactions
            .Where(transaction => !transaction.IsHidden && transaction.Kind == TransactionKind.Expense)
            .ToArray();
        YearMonth? end = values.Length == 0 ? null : values.Max(transaction => transaction.Month);
        if (end is null)
        {
            return new FinancialIndependenceSourceAnalysis(
                selected,
                [],
                [],
                selected.Sum(account => account.SignedBalance),
                0m,
                null,
                null);
        }

        YearMonth start = end.Value.AddMonths(1 - filters.SpendingLookbackMonths);
        FinancialTransaction[] expenses = values
            .Where(transaction => transaction.Month.CompareTo(start) >= 0
                && transaction.Month.CompareTo(end.Value) <= 0
                && MatchesAdjustments(transaction, filters.Adjustments))
            .OrderByDescending(transaction => transaction.Date)
            .ThenBy(transaction => transaction.Id, StringComparer.Ordinal)
            .ToArray();
        IReadOnlyList<FinancialIndependenceMonthlySpending> monthly = YearMonth.InclusiveRange(start, end.Value)
            .Select(month => new FinancialIndependenceMonthlySpending(
                month,
                expenses.Where(transaction => transaction.Month == month).Sum(transaction => -transaction.Amount)))
            .ToArray();
        return new FinancialIndependenceSourceAnalysis(
            selected,
            expenses,
            monthly,
            selected.Sum(account => account.SignedBalance),
            monthly.Sum(entry => entry.Spending) / filters.SpendingLookbackMonths * 12m,
            start,
            end);
    }

    private static bool IsIncluded(AccountBalance account, FinancialIndependenceSettings settings)
    {
        if (settings.IncludedGroups.Count == 0 && settings.IncludedAccountPatterns.Count == 0)
            return account.AccountClass == AccountClass.Asset;
        return settings.IncludedGroups.Contains(account.Group, StringComparer.Ordinal)
            || settings.IncludedAccountPatterns.Any(pattern => account.Account.Contains(pattern, StringComparison.OrdinalIgnoreCase));
    }

    private static bool MatchesAdjustments(FinancialTransaction transaction, SpendingAdjustments adjustments)
    {
        if (adjustments.ExcludedGroups.Contains(transaction.Group, StringComparer.Ordinal)
            || adjustments.ExcludedCategories.Contains(transaction.Category, StringComparer.Ordinal))
        {
            return false;
        }
        if (adjustments.IncludedDescriptions.Count > 0
            && !adjustments.IncludedDescriptions.Any(term => ContainsText(transaction.Description, term)))
        {
            return false;
        }
        if (adjustments.ExcludedDescriptions.Any(term => ContainsText(transaction.Description, term)))
            return false;
        return !adjustments.ExcludeLargeExpenses || decimal.Abs(transaction.Amount) <= adjustments.ExpenseLimit;
    }

    private static bool ContainsText(string value, string term)
        => !string.IsNullOrWhiteSpace(term)
            && value.Contains(term, StringComparison.OrdinalIgnoreCase);
}
