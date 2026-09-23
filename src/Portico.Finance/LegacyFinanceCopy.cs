using System.Globalization;

namespace Portico.Finance;

// Remove after the old Dashboard is replaced by Desktop.
internal static class LegacyFinanceCopy
{
    public static string Exclusions(IEnumerable<LedgerExclusion> exclusions)
        => string.Join("; ", exclusions.Select(Exclusion));

    public static string? BudgetEmpty(BudgetEmptyReason? reason)
        => reason switch
        {
            null => null,
            BudgetEmptyReason.NoGroupsSelected => "Select at least one budget group.",
            _ => throw new ArgumentOutOfRangeException(nameof(reason))
        };

    public static string HealthName(DataHealthCheckKind kind)
        => kind switch
        {
            DataHealthCheckKind.Uncategorized => "Missing classifications",
            DataHealthCheckKind.IncompleteTransactions => "Missing transaction details",
            DataHealthCheckKind.AccountMapping => "Account mapping gaps",
            DataHealthCheckKind.StaleAccounts => "Stale balance accounts",
            DataHealthCheckKind.Duplicates => "Potential duplicate transactions",
            DataHealthCheckKind.Reversals => "Refunds and income reversals",
            _ => throw new ArgumentOutOfRangeException(nameof(kind))
        };

    public static string HealthAction(DataHealthCheckKind kind)
        => kind switch
        {
            DataHealthCheckKind.Uncategorized => "Assign a category with a valid group and type.",
            DataHealthCheckKind.IncompleteTransactions => "Fill the missing identifying fields in the Transactions sheet.",
            DataHealthCheckKind.AccountMapping => "Map each account to an ID, group, and asset or liability class.",
            DataHealthCheckKind.StaleAccounts => "Refresh or reconnect accounts that stopped reporting balances.",
            DataHealthCheckKind.Duplicates => "Confirm whether each pair represents the same underlying charge.",
            DataHealthCheckKind.Reversals => "Confirm that refunds, clawbacks, and corrections are categorized as intended.",
            _ => throw new ArgumentOutOfRangeException(nameof(kind))
        };

    public static string HealthStatus(DataHealthCheckStatus status)
        => status switch
        {
            DataHealthCheckStatus.Passed => "Passed",
            DataHealthCheckStatus.NeedsAttention => "Needs attention",
            DataHealthCheckStatus.Review => "Review",
            _ => throw new ArgumentOutOfRangeException(nameof(status))
        };

    private static string Exclusion(LedgerExclusion exclusion)
        => exclusion.Reason switch
        {
            LedgerExclusionReason.TransferGroup => "Transfer group",
            LedgerExclusionReason.OutsideConfiguredSet => $"Outside configured set: {exclusion.Value}",
            LedgerExclusionReason.OutsideIncludedDescriptions => "Outside included groups/categories/transactions",
            LedgerExclusionReason.ExcludedIncomeCategory => $"Excluded income category: {exclusion.Value}",
            LedgerExclusionReason.ExcludedExpenseGroup => $"Excluded group: {exclusion.Value}",
            LedgerExclusionReason.ExcludedExpenseCategory => $"Excluded expense category: {exclusion.Value}",
            LedgerExclusionReason.ExcludedCategory => $"Excluded category: {exclusion.Value}",
            LedgerExclusionReason.ExcludedDescription => $"Excluded transaction like: {exclusion.Value}",
            LedgerExclusionReason.IncomeOverLimit => $"Income over {Money(exclusion.Limit)}",
            LedgerExclusionReason.ExpenseOverLimit => $"Expense over {Money(exclusion.Limit)}",
            _ => throw new ArgumentOutOfRangeException(nameof(exclusion))
        };

    private static string Money(decimal? value)
        => value?.ToString("C0", CultureInfo.GetCultureInfo("en-US"))
            ?? throw new ArgumentException("An exclusion limit is required.", nameof(value));
}
