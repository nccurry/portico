namespace Portico.Finance;

/// <summary>Identifies a rule that removed a transaction from a report.</summary>
public enum LedgerExclusionReason
{
    TransferGroup,
    OutsideConfiguredSet,
    OutsideIncludedDescriptions,
    ExcludedIncomeCategory,
    ExcludedExpenseGroup,
    ExcludedExpenseCategory,
    ExcludedCategory,
    ExcludedDescription,
    IncomeOverLimit,
    ExpenseOverLimit
}

/// <summary>One exclusion rule and the value needed to explain it.</summary>
public sealed record LedgerExclusion(
    LedgerExclusionReason Reason,
    string? Value = null,
    decimal? Limit = null);
