using Portico.Finance;

namespace Portico.Application;

/// <summary>Selects the Income and savings calculation and detail month.</summary>
public sealed record IncomeReportRequest(
    int? LookbackMonths = null,
    bool? RegularIncome = null,
    IncomeSavingsAdjustments? Adjustments = null,
    YearMonth? DetailMonth = null);

/// <summary>One included income or expense category total for the detail month.</summary>
public sealed record IncomeCategoryTotal(TransactionKind Kind, string Category, decimal Amount);

/// <summary>Average monthly values and their matched-prior changes.</summary>
public sealed record IncomePeriodComparison(
    decimal Income,
    decimal NetExpenses,
    decimal Surplus,
    decimal? SavingsRatePercent,
    decimal? IncomeChange,
    decimal? NetExpensesChange,
    decimal? SurplusChange,
    decimal? SavingsRateChange);

/// <summary>Financial values and the selected detail for Income and savings.</summary>
public sealed record IncomeReport(
    IncomeSavingsAnalysisResult Analysis,
    IncomeSavingsAdjustments Adjustments,
    IncomePeriodComparison Comparison,
    YearMonth? DetailMonth,
    IncomeSavingsMonth? Detail,
    IReadOnlyList<IncomeCategoryTotal> Categories,
    IReadOnlyList<IncomeSavingsLedgerEntry> IncludedTransactions,
    IReadOnlyList<IncomeSavingsLedgerEntry> ExcludedTransactions)
{
    public int ExcludedCount => Analysis.CurrentLedger.Count(entry => !entry.Included);

    public decimal ExcludedIncome => Analysis.CurrentLedger
        .Where(entry => !entry.Included && entry.Transaction.Kind == TransactionKind.Income)
        .Sum(entry => entry.Transaction.Amount);

    public decimal ExcludedSpending => Analysis.CurrentLedger
        .Where(entry => !entry.Included && entry.Transaction.Kind == TransactionKind.Expense)
        .Sum(entry => -entry.Transaction.Amount);
}

public sealed partial class Workspace
{
    /// <summary>Calculates Income and savings from visible transactions.</summary>
    public IncomeReport Income(IncomeReportRequest? request = null)
    {
        request ??= new IncomeReportRequest();
        int lookback = request.LookbackMonths ?? _settings.Lookback.DefaultMonths;
        if (lookback <= 0)
            throw new ArgumentOutOfRangeException(nameof(request), "Income lookback must be positive.");

        bool regular = request.RegularIncome
            ?? string.Equals(_settings.IncomeSavings.DefaultView, "regular", StringComparison.OrdinalIgnoreCase);
        IncomeSavingsAdjustments adjustments = request.Adjustments
            ?? IncomeSavingsAdjustments.Default(_settings, regular);
        IncomeSavingsAnalysisResult analysis = IncomeSavingsAnalysisCalculator.Build(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden),
            lookback,
            adjustments);
        CashFlowSummary current = analysis.CurrentSummary;
        CashFlowSummary previous = analysis.PreviousSummary;
        static decimal Average(decimal value, int months) => months == 0 ? 0m : value / months;
        decimal income = Average(current.Income, current.Months);
        decimal expenses = Average(current.NetExpenses, current.Months);
        decimal surplus = Average(current.Surplus, current.Months);
        var comparison = new IncomePeriodComparison(
            income,
            expenses,
            surplus,
            current.SavingsRatePercent,
            analysis.HasFullPreviousPeriod ? income - Average(previous.Income, previous.Months) : null,
            analysis.HasFullPreviousPeriod ? expenses - Average(previous.NetExpenses, previous.Months) : null,
            analysis.HasFullPreviousPeriod ? surplus - Average(previous.Surplus, previous.Months) : null,
            analysis.HasFullPreviousPeriod && current.SavingsRatePercent is decimal currentRate
                && previous.SavingsRatePercent is decimal previousRate
                ? currentRate - previousRate
                : null);
        YearMonth? month = request.DetailMonth is YearMonth selected
            && analysis.Period.CurrentMonths.Contains(selected)
            ? selected
            : analysis.Period.CurrentMonths.Count > 0
                ? analysis.Period.CurrentMonths[^1]
                : null;
        IncomeSavingsLedgerEntry[] entries = month is YearMonth detailMonth
            ? analysis.CurrentLedger.Where(entry => entry.Transaction.Month == detailMonth).ToArray()
            : [];
        IncomeSavingsLedgerEntry[] included = entries.Where(entry => entry.Included)
            .OrderByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .ToArray();
        IncomeSavingsLedgerEntry[] excluded = entries.Where(entry => !entry.Included)
            .OrderByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .ToArray();
        IncomeCategoryTotal[] categories = included
            .GroupBy(entry => (entry.Transaction.Kind, entry.Transaction.Category))
            .Select(group => new IncomeCategoryTotal(
                group.Key.Kind,
                group.Key.Category,
                group.Key.Kind == TransactionKind.Income
                    ? group.Sum(entry => entry.Transaction.Amount)
                    : -group.Sum(entry => entry.Transaction.Amount)))
            .OrderBy(total => total.Kind == TransactionKind.Expense ? 0 : 1)
            .ThenByDescending(total => decimal.Abs(total.Amount))
            .ThenBy(total => total.Category, StringComparer.Ordinal)
            .ToArray();

        return new IncomeReport(
            analysis,
            adjustments,
            comparison,
            month,
            month is YearMonth value
                ? analysis.CurrentMonthly.FirstOrDefault(row => row.Month == value)
                : null,
            categories,
            included,
            excluded);
    }
}
