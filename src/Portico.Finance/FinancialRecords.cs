namespace Portico.Finance;

/// <summary>Classifies a transaction after category data is applied.</summary>
public enum TransactionKind
{
    /// <summary>Income that increases cash flow.</summary>
    Income,

    /// <summary>An expense; a negative amount is a charge and a positive amount is a refund.</summary>
    Expense,

    /// <summary>A transfer that is excluded from income and spending reports.</summary>
    Transfer,

    /// <summary>A row that cannot be classified for financial reports.</summary>
    Unknown
}

/// <summary>Classifies an account balance for net-worth reporting.</summary>
public enum AccountClass
{
    /// <summary>A balance that increases net worth.</summary>
    Asset,

    /// <summary>A balance that decreases net worth.</summary>
    Liability
}

/// <summary>Represents one normalized financial transaction.</summary>
public sealed record FinancialTransaction(
    string Id,
    DateOnly Date,
    string Category,
    string Group,
    string Account,
    string Description,
    decimal Amount,
    TransactionKind Kind,
    bool IsHidden = false)
{
    /// <summary>Gets the calendar month that contains this transaction.</summary>
    public YearMonth Month => YearMonth.From(Date);
}

/// <summary>Represents one normalized balance observation.</summary>
public sealed record BalanceObservation(
    string AccountId,
    string Account,
    string Group,
    DateOnly Date,
    TimeOnly Time,
    decimal Balance,
    AccountClass AccountClass,
    bool IsHidden);

/// <summary>Represents one configured monthly category budget.</summary>
public sealed record BudgetEntry(
    YearMonth Month,
    string Category,
    string Group,
    TransactionKind Kind,
    decimal Amount,
    bool IsHidden);

/// <summary>Represents the four normalized sheets used by the dashboard.</summary>
public sealed record PortfolioSnapshot(
    IReadOnlyList<FinancialTransaction> Transactions,
    IReadOnlyList<BalanceObservation> Balances,
    IReadOnlyList<BudgetEntry> Budgets)
{
    /// <summary>Gets the latest date available in any loaded sheet.</summary>
    public DateOnly? LatestDate
    {
        get
        {
            DateOnly? latest = null;
            foreach (FinancialTransaction transaction in Transactions)
                latest = !latest.HasValue || transaction.Date > latest.Value ? transaction.Date : latest;
            foreach (BalanceObservation balance in Balances)
                latest = !latest.HasValue || balance.Date > latest.Value ? balance.Date : latest;
            return latest;
        }
    }
}
