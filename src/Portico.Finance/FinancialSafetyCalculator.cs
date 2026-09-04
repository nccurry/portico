namespace Portico.Finance;

/// <summary>Represents emergency-fund, debt, and financial-independence progress.</summary>
public sealed record FinancialSafetySummary(
    decimal EmergencyFundBalance,
    decimal EmergencyFundAverageMonthlySpending,
    decimal EmergencyFundTarget,
    decimal? EmergencyFundMonthsCovered,
    int EmergencyFundTargetMonths,
    decimal DebtBalance,
    decimal DebtBaselineBalance,
    decimal DebtPaidDown,
    decimal? DebtProgressPercent,
    DateOnly? DebtBaselineDate,
    decimal FinancialIndependencePortfolio,
    decimal FinancialIndependenceTarget,
    decimal? FinancialIndependenceProgressPercent);

/// <summary>Calculates configurable emergency-fund, debt, and funding progress.</summary>
public static class FinancialSafetyCalculator
{
    /// <summary>Builds a financial-safety summary using one explicit report date.</summary>
    public static FinancialSafetySummary Summarize(
        IEnumerable<FinancialTransaction> transactions,
        IEnumerable<BalanceObservation> balances,
        FinancialSafetySettings safety,
        FinancialIndependenceSettings financialIndependence,
        DateOnly asOfDate)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(balances);
        ArgumentNullException.ThrowIfNull(safety);
        ArgumentNullException.ThrowIfNull(financialIndependence);

        FinancialTransaction[] transactionValues = transactions.Where(transaction => !transaction.IsHidden).ToArray();
        BalanceObservation[] balanceValues = balances.Where(balance => !balance.IsHidden).ToArray();
        IReadOnlyList<AccountBalance> latestBalances = PortfolioCalculator.LatestBalances(balanceValues, asOfDate);

        IReadOnlyList<AccountBalance> emergencyAccounts = SelectAccounts(
            latestBalances,
            safety.EmergencyFundIncludedGroups,
            safety.EmergencyFundIncludedAccountPatterns);
        decimal emergencyBalance = emergencyAccounts.Sum(account => account.SignedBalance);
        decimal emergencySpending = AverageMonthlyExpenses(
            transactionValues,
            safety.EmergencyFundSpendingLookbackMonths,
            asOfDate,
            safety.EmergencyFundExcludeCategories,
            safety.EmergencyFundExcludeGroups);
        decimal emergencyTarget = emergencySpending * safety.EmergencyFundTargetMonths;

        IReadOnlyList<AccountBalance> debtAccounts = SelectAccounts(
            latestBalances,
            safety.DebtIncludedGroups,
            safety.DebtIncludedAccountPatterns);
        decimal debtBalance = decimal.Abs(debtAccounts.Sum(account => account.SignedBalance));
        DateOnly? debtBaselineDate = ResolveDebtBaselineDate(
            balanceValues,
            safety,
            debtAccounts.Select(account => account.Account));
        decimal debtBaselineBalance = debtBaselineDate is null
            ? 0m
            : decimal.Abs(PortfolioCalculator.LatestBalances(
                    balanceValues,
                    debtBaselineDate,
                    debtAccounts.Select(account => account.Account))
                .Sum(account => account.SignedBalance));
        decimal debtPaidDown = debtBaselineBalance - debtBalance;

        IReadOnlyList<AccountBalance> financialIndependenceAccounts = SelectFinancialIndependenceAccounts(
            latestBalances,
            financialIndependence);
        decimal financialIndependencePortfolio = financialIndependenceAccounts.Sum(account => account.SignedBalance);
        decimal financialIndependenceTarget = financialIndependence.TargetAmount;

        return new FinancialSafetySummary(
            emergencyBalance,
            emergencySpending,
            emergencyTarget,
            emergencySpending == 0m ? null : emergencyBalance / emergencySpending,
            safety.EmergencyFundTargetMonths,
            debtBalance,
            debtBaselineBalance,
            debtPaidDown,
            debtBaselineBalance == 0m ? null : debtPaidDown / debtBaselineBalance * 100m,
            debtBaselineDate,
            financialIndependencePortfolio,
            financialIndependenceTarget,
            financialIndependenceTarget == 0m ? null : financialIndependencePortfolio / financialIndependenceTarget * 100m);
    }

    private static decimal AverageMonthlyExpenses(
        IEnumerable<FinancialTransaction> transactions,
        int lookbackMonths,
        DateOnly asOfDate,
        IReadOnlyList<string> excludedCategories,
        IReadOnlyList<string> excludedGroups)
    {
        if (lookbackMonths <= 0)
            return 0m;

        FinancialTransaction[] values = transactions.ToArray();
        if (values.Length == 0)
            return 0m;

        YearMonth latestTransactionMonth = values.Max(transaction => transaction.Month);
        YearMonth reportMonth = YearMonth.From(asOfDate);
        if (reportMonth == new YearMonth(1, 1))
            return 0m;

        YearMonth latestCompletedMonth = reportMonth.AddMonths(-1);
        YearMonth end = latestTransactionMonth.CompareTo(latestCompletedMonth) < 0
            ? latestTransactionMonth
            : latestCompletedMonth;
        YearMonth start = end.AddMonths(1 - lookbackMonths);
        var excludedCategorySet = new HashSet<string>(excludedCategories, StringComparer.Ordinal);
        var excludedGroupSet = new HashSet<string>(excludedGroups, StringComparer.Ordinal);

        return YearMonth.InclusiveRange(start, end)
            .Select(month => -values
                .Where(transaction => transaction.Kind == TransactionKind.Expense
                    && transaction.Month == month
                    && !excludedCategorySet.Contains(transaction.Category)
                    && !excludedGroupSet.Contains(transaction.Group))
                .Sum(transaction => transaction.Amount))
            .Average();
    }

    private static DateOnly? ResolveDebtBaselineDate(
        IEnumerable<BalanceObservation> balances,
        FinancialSafetySettings safety,
        IEnumerable<string> accountNames)
    {
        string[] names = accountNames.ToArray();
        if (names.Length == 0)
            return null;
        if (safety.DebtBaselineDate is DateOnly configured)
            return configured;

        var nameSet = new HashSet<string>(names, StringComparer.Ordinal);
        return balances
            .Where(balance => nameSet.Contains(balance.Account))
            .Select(balance => (DateOnly?)balance.Date)
            .Min();
    }

    private static IReadOnlyList<AccountBalance> SelectAccounts(
        IEnumerable<AccountBalance> accounts,
        IReadOnlyList<string> includedGroups,
        IReadOnlyList<string> includedAccountPatterns)
    {
        if (includedGroups.Count == 0 && includedAccountPatterns.Count == 0)
            return [];

        return accounts
            .Where(account => IsSelected(account, includedGroups, includedAccountPatterns))
            .ToArray();
    }

    private static IReadOnlyList<AccountBalance> SelectFinancialIndependenceAccounts(
        IEnumerable<AccountBalance> accounts,
        FinancialIndependenceSettings settings)
    {
        if (settings.IncludedGroups.Count == 0 && settings.IncludedAccountPatterns.Count == 0)
            return accounts.Where(account => account.AccountClass == AccountClass.Asset).ToArray();

        return accounts
            .Where(account => IsSelected(account, settings.IncludedGroups, settings.IncludedAccountPatterns))
            .ToArray();
    }

    private static bool IsSelected(
        AccountBalance account,
        IReadOnlyList<string> includedGroups,
        IReadOnlyList<string> includedAccountPatterns)
        => includedGroups.Contains(account.Group, StringComparer.Ordinal)
            || includedAccountPatterns.Any(pattern => account.Account.Contains(pattern, StringComparison.OrdinalIgnoreCase));
}
