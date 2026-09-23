namespace Portico.Finance;

/// <summary>Provides default large-transaction and duplicate thresholds.</summary>
public sealed record ThresholdSettings(decimal Expense, decimal Income, decimal DuplicateMinimum, int DuplicateDays);

/// <summary>Provides the baseline policy for income and savings reports.</summary>
public sealed record IncomeSavingsSettings(
    decimal TargetRate,
    IReadOnlyList<string> ExcludeCategories,
    IReadOnlyList<string> ExcludeGroups);

/// <summary>Defines one named reusable transaction selection.</summary>
public sealed record TransactionSetDefinition(
    string Key,
    IReadOnlyList<string> Groups,
    IReadOnlyList<string> Categories,
    IReadOnlyList<string> Accounts,
    IReadOnlyList<string> Merchants,
    IReadOnlyList<string> TransactionsLike,
    IReadOnlyList<string> Includes,
    IReadOnlyList<string> Excludes);

/// <summary>Provides subscription detection policy.</summary>
public sealed record SubscriptionSettings(
    IReadOnlyList<string> KnownCategories,
    int MinimumConfidence,
    int StaleAfterDays,
    IReadOnlyList<string> DetectionExcludedCategories);

/// <summary>Provides the number of budget history months.</summary>
public sealed record BudgetSettings(int HistoryMonths);

/// <summary>Provides data-health policies.</summary>
public sealed record DataHealthSettings(
    int StaleAccountDays,
    bool DuplicateRequireSameAccount,
    bool DuplicateRequireSameCategory,
    bool DuplicateRequireSameDescription);

/// <summary>Provides emergency-fund and debt policies.</summary>
public sealed record FinancialSafetySettings(
    int EmergencyFundTargetMonths,
    IReadOnlyList<string> EmergencyFundIncludedGroups,
    IReadOnlyList<string> EmergencyFundIncludedAccountPatterns,
    int EmergencyFundSpendingLookbackMonths,
    IReadOnlyList<string> EmergencyFundExcludeCategories,
    IReadOnlyList<string> EmergencyFundExcludeGroups,
    IReadOnlyList<string> DebtIncludedGroups,
    IReadOnlyList<string> DebtIncludedAccountPatterns,
    DateOnly? DebtBaselineDate);

/// <summary>Provides financial-independence assumptions.</summary>
public sealed record FinancialIndependenceSettings(
    decimal ExpectedReturnRate,
    decimal WithdrawalRate,
    decimal TargetAmount,
    int SpendingLookbackMonths,
    int ProjectionYears,
    IReadOnlyList<string> IncludedAccountPatterns,
    IReadOnlyList<string> IncludedGroups);

/// <summary>Holds the supported financial calculation settings.</summary>
public sealed record FinanceSettings(
    ThresholdSettings Thresholds,
    IncomeSavingsSettings IncomeSavings,
    IReadOnlyList<TransactionSetDefinition> TransactionSets,
    SubscriptionSettings Subscriptions,
    BudgetSettings Budget,
    DataHealthSettings DataHealth,
    FinancialSafetySettings FinancialSafety,
    FinancialIndependenceSettings FinancialIndependence,
    IReadOnlyDictionary<string, IReadOnlyList<string>> MerchantAliases)
{
    /// <summary>Gets one transaction set by its stable key.</summary>
    public TransactionSetDefinition TransactionSet(string key)
    {
        foreach (TransactionSetDefinition definition in TransactionSets)
        {
            if (string.Equals(definition.Key, key, StringComparison.Ordinal))
                return definition;
        }

        throw new ArgumentException($"Unknown transaction set '{key}'.", nameof(key));
    }
}
