using Portico.Finance;

namespace Portico.Application;

/// <summary>Selects a Budget analysis and its group and category detail.</summary>
public sealed record BudgetReportRequest(
    BudgetRequest? Budget = null,
    string? Group = null,
    string? Category = null);

/// <summary>Plan and actual values for one category in a broad budget view.</summary>
public sealed record BudgetOverviewCategory(string Category, decimal Budget, decimal Spent)
{
    public decimal Remaining => Budget - Spent;
}

/// <summary>Plan and actual values for one month in a broad budget view.</summary>
public sealed record BudgetOverviewMonth(YearMonth Month, decimal Budget, decimal Spent);

/// <summary>The broad category budget view used by older custom dashboards.</summary>
public sealed record BudgetOverviewReport(
    IReadOnlyList<BudgetOverviewCategory> Categories,
    IReadOnlyList<BudgetOverviewMonth> History)
{
    public decimal Budget => Categories.Sum(category => category.Budget);

    public decimal Spent => Categories.Sum(category => category.Spent);
}

/// <summary>Financial values and the selected Budget group detail.</summary>
public sealed record BudgetReport(
    BudgetAnalysisResult Analysis,
    string? SelectedGroup,
    string? SelectedCategory,
    BudgetGroupDetail? GroupDetail,
    IReadOnlyList<FinancialTransaction> Transactions);

public sealed partial class Workspace
{
    /// <summary>Calculates the selected month's Budget page from visible rows.</summary>
    public BudgetReport Budget(BudgetReportRequest? request = null)
    {
        request ??= new BudgetReportRequest();
        BudgetRequest budget = request.Budget ?? DefaultBudgetRequest();
        budget.Validate();
        BudgetAnalysisResult analysis = BudgetAnalysisCalculator.Build(
            _snapshot.Budgets,
            _snapshot.Transactions,
            budget);
        string? group = analysis.Groups.Any(entry => string.Equals(entry.Entity, request.Group, StringComparison.Ordinal))
            ? request.Group
            : analysis.Groups.FirstOrDefault()?.Entity;
        BudgetGroupDetail? detail = group is not null && analysis.GroupDetails.TryGetValue(group, out BudgetGroupDetail? value)
            ? value
            : null;
        string? category = detail is not null && detail.Categories.Any(entry =>
            string.Equals(entry.Entity, request.Category, StringComparison.Ordinal))
            ? request.Category
            : null;
        IReadOnlyList<FinancialTransaction> transactions = detail is null
            ? []
            : detail.Transactions
                .Where(transaction => category is null || string.Equals(
                    transaction.Category, category, StringComparison.Ordinal))
                .ToArray();
        return new BudgetReport(analysis, group, category, detail, transactions);
    }

    /// <summary>Calculates the older broad category budget view without a selected group.</summary>
    public BudgetOverviewReport BudgetOverview(int? lookbackMonths = null)
    {
        int lookback = lookbackMonths ?? _settings.Lookback.DefaultMonths;
        if (lookback <= 0)
            throw new ArgumentOutOfRangeException(nameof(lookbackMonths));
        if (_snapshot.LatestDate is not DateOnly latest)
            return new BudgetOverviewReport([], []);

        YearMonth end = YearMonth.From(latest);
        YearMonth start = end.AddMonths(-Math.Min(lookback - 1, MonthsBefore(end)));
        BudgetEntry[] planned = _snapshot.Budgets
            .Where(entry => entry.Kind == TransactionKind.Expense && !entry.IsHidden
                && entry.Month.CompareTo(start) >= 0 && entry.Month.CompareTo(end) <= 0)
            .ToArray();
        FinancialTransaction[] actual = _snapshot.Transactions
            .Where(transaction => transaction.Kind == TransactionKind.Expense && !transaction.IsHidden
                && transaction.Month.CompareTo(start) >= 0 && transaction.Month.CompareTo(end) <= 0)
            .ToArray();
        BudgetOverviewCategory[] categories = planned.Select(entry => entry.Category)
            .Concat(actual.Select(transaction => transaction.Category))
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .Select(category => new BudgetOverviewCategory(
                category,
                planned.Where(entry => entry.Category == category).Sum(entry => entry.Amount),
                -actual.Where(transaction => transaction.Category == category).Sum(transaction => transaction.Amount)))
            .ToArray();
        int historyMonths = _settings.Budget.HistoryMonths;
        if (historyMonths <= 0)
            throw new InvalidOperationException("Budget history must be positive.");
        YearMonth historyStart = end.AddMonths(-Math.Min(historyMonths - 1, MonthsBefore(end)));
        BudgetOverviewMonth[] history = YearMonth.InclusiveRange(historyStart, end)
            .Select(month => new BudgetOverviewMonth(
                month,
                _snapshot.Budgets.Where(entry => entry.Kind == TransactionKind.Expense && !entry.IsHidden
                    && entry.Month == month).Sum(entry => entry.Amount),
                -_snapshot.Transactions.Where(transaction => transaction.Kind == TransactionKind.Expense
                    && !transaction.IsHidden && transaction.Month == month).Sum(transaction => transaction.Amount)))
            .ToArray();
        return new BudgetOverviewReport(categories, history);
    }

    private BudgetRequest DefaultBudgetRequest()
    {
        YearMonth month = _snapshot.Transactions
            .Where(transaction => !transaction.IsHidden)
            .Select(transaction => transaction.Month)
            .Concat(_snapshot.Budgets.Where(entry => !entry.IsHidden).Select(entry => entry.Month))
            .DefaultIfEmpty(new YearMonth(2000, 1))
            .Max();
        string[] groups = _snapshot.Budgets
            .Where(entry => !entry.IsHidden && entry.Kind == TransactionKind.Expense
                && entry.Month == month && entry.Amount > 0m)
            .Select(entry => entry.Group)
            .Where(group => !string.IsNullOrWhiteSpace(group))
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        return new BudgetRequest(
            month,
            groups,
            SpendingAdjustments.Default(_settings.Thresholds.Expense),
            _settings.Budget.HistoryMonths,
            AsOfDate);
    }

    private static int MonthsBefore(YearMonth month) => (month.Year - 1) * 12 + month.Month - 1;
}
