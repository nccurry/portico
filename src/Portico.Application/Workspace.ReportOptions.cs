using Portico.Finance;

namespace Portico.Application;

/// <summary>Names the transaction fields exposed as report choices.</summary>
public enum TransactionChoiceField
{
    Group,
    Category,
    Account
}

public sealed partial class Workspace
{
    /// <summary>Gets distinct values in visible transactions for a report control.</summary>
    public IReadOnlyList<string> TransactionChoices(TransactionChoiceField field, bool expensesOnly = false)
        => _snapshot.Transactions
            .Where(transaction => !transaction.IsHidden
                && (!expensesOnly || transaction.Kind == TransactionKind.Expense))
            .Select(transaction => field switch
            {
                TransactionChoiceField.Group => transaction.Group,
                TransactionChoiceField.Category => transaction.Category,
                TransactionChoiceField.Account => transaction.Account,
                _ => throw new ArgumentOutOfRangeException(nameof(field))
            })
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value.Trim())
            .Distinct(StringComparer.Ordinal)
            .OrderBy(value => value, StringComparer.Ordinal)
            .ToArray();

    /// <summary>Gets categories for the selected transaction kind.</summary>
    public IReadOnlyList<string> IncomeCategories(TransactionKind kind)
        => IncomeSavingsAnalysisCalculator.Categories(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden), kind);

    /// <summary>Gets expense groups for Income calculation controls.</summary>
    public IReadOnlyList<string> IncomeExpenseGroups()
        => IncomeSavingsAnalysisCalculator.ExpenseGroups(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden));

    /// <summary>Gets all months with visible transactions or budgets.</summary>
    public IReadOnlyList<YearMonth> BudgetMonths()
        => _snapshot.Transactions.Where(transaction => !transaction.IsHidden)
            .Select(transaction => transaction.Month)
            .Concat(_snapshot.Budgets.Where(entry => !entry.IsHidden).Select(entry => entry.Month))
            .Distinct()
            .OrderByDescending(month => month)
            .ToArray();

    /// <summary>Gets groups with visible expense transactions or budgets.</summary>
    public IReadOnlyList<string> BudgetGroups()
        => _snapshot.Budgets
            .Where(entry => !entry.IsHidden && entry.Kind == TransactionKind.Expense)
            .Select(entry => entry.Group)
            .Concat(_snapshot.Transactions
                .Where(transaction => !transaction.IsHidden && transaction.Kind == TransactionKind.Expense)
                .Select(transaction => transaction.Group))
            .Where(group => !string.IsNullOrWhiteSpace(group))
            .Distinct(StringComparer.Ordinal)
            .OrderBy(group => group, StringComparer.Ordinal)
            .ToArray();

    /// <summary>Gets categories with a visible row in the selected budget group and month.</summary>
    public IReadOnlyList<string> BudgetCategories(string group, YearMonth month)
        => _snapshot.Budgets.Where(entry => !entry.IsHidden && entry.Group == group && entry.Month == month)
            .Select(entry => entry.Category)
            .Concat(_snapshot.Transactions.Where(transaction => !transaction.IsHidden
                && transaction.Kind == TransactionKind.Expense
                && transaction.Group == group && transaction.Month == month)
                .Select(transaction => transaction.Category))
            .Where(category => !string.IsNullOrWhiteSpace(category))
            .Distinct(StringComparer.Ordinal)
            .OrderBy(category => category, StringComparer.Ordinal)
            .ToArray();

    /// <summary>Gets the visible latest-balance account names for FI controls.</summary>
    public IReadOnlyList<string> FinancialIndependenceAccounts()
        => PortfolioCalculator.LatestBalances(_snapshot.Balances)
            .Select(account => account.Account)
            .Where(account => !string.IsNullOrWhiteSpace(account))
            .Distinct(StringComparer.Ordinal)
            .OrderBy(account => account, StringComparer.Ordinal)
            .ToArray();

    /// <summary>Gets configured subscription categories that exist in visible transactions.</summary>
    public IReadOnlyList<string> SubscriptionCategoryDefaults()
    {
        IReadOnlyList<string> available = TransactionChoices(TransactionChoiceField.Category);
        return _settings.Subscriptions.KnownCategories.Where(available.Contains).ToArray();
    }

    /// <summary>Gets configured discovery exclusions after selected subscription categories are removed.</summary>
    public IReadOnlyList<string> SubscriptionDiscoveryDefaults(IReadOnlyList<string> selected)
    {
        IReadOnlyList<string> available = TransactionChoices(TransactionChoiceField.Category);
        return _settings.Subscriptions.DefaultExcludeCategories
            .Where(available.Contains)
            .Where(category => !category.EndsWith("bill", StringComparison.OrdinalIgnoreCase))
            .Where(category => !selected.Contains(category, StringComparer.Ordinal))
            .ToArray();
    }

    /// <summary>Gets configured Data Health check thresholds.</summary>
    public DataHealthCheckOptions DefaultDataHealthOptions() => DataHealthCheckOptions.From(_settings);

    /// <summary>Gets the configured FI target used by the compact desktop card.</summary>
    public decimal DefaultFinancialIndependenceTargetAmount => _settings.FinancialIndependence.TargetAmount;
}
