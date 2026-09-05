namespace Portico.Finance;

/// <summary>Describes the month, groups, and adjustments used by a Budget page view.</summary>
public sealed record BudgetRequest(
    YearMonth SelectedMonth,
    IReadOnlyList<string> Groups,
    SpendingAdjustments Adjustments,
    int HistoryMonths,
    DateOnly ThroughDate)
{
    /// <summary>Checks that the request has values that can produce a stable report.</summary>
    public void Validate()
    {
        ArgumentNullException.ThrowIfNull(Groups);
        ArgumentNullException.ThrowIfNull(Adjustments);
        if (HistoryMonths is < 1 or > 120)
            throw new ArgumentOutOfRangeException(nameof(HistoryMonths));
    }
}

/// <summary>Describes a budget total for one group or category in one month.</summary>
public sealed record BudgetHistoryEntry(
    YearMonth Month,
    string Entity,
    decimal Budget,
    decimal TrackedSpent,
    decimal OutsidePlan)
{
    /// <summary>Gets all spending, including unbudgeted categories.</summary>
    public decimal Spent => TrackedSpent + OutsidePlan;
}

/// <summary>Describes one current budget group or category against its recent history.</summary>
public sealed record BudgetPerformanceEntry(
    string Entity,
    decimal Budget,
    decimal TrackedSpent,
    decimal OutsidePlan,
    decimal Spent,
    decimal Remaining,
    decimal? PercentUsed,
    decimal TypicalSpending,
    decimal VersusTypical,
    decimal BudgetVariance,
    int MonthsWithinBudget,
    int MonthsBudgeted,
    decimal? SuccessRate,
    IReadOnlyList<decimal> Trend);

/// <summary>Describes a cumulative daily spending and budget-pace point.</summary>
public sealed record BudgetDailyPaceEntry(DateOnly Date, decimal ActualCumulative, decimal IdealCumulative);

/// <summary>Describes the selected month's total budget position.</summary>
public sealed record BudgetSummary(
    decimal Budget,
    decimal TrackedSpent,
    decimal OutsidePlan,
    decimal Spent,
    decimal Remaining,
    decimal PercentUsed,
    decimal TypicalSpending,
    decimal VersusTypical);

/// <summary>Contains the drill-down data for one selected budget group.</summary>
public sealed record BudgetGroupDetail(
    BudgetPerformanceEntry Performance,
    IReadOnlyList<BudgetHistoryEntry> History,
    IReadOnlyList<BudgetPerformanceEntry> Categories,
    IReadOnlyList<FinancialTransaction> Transactions);

/// <summary>Contains all source-shaped Budget data for a selected month and group set.</summary>
public sealed record BudgetAnalysisResult(
    BudgetRequest Request,
    decimal MonthProgress,
    BudgetSummary Summary,
    IReadOnlyList<BudgetPerformanceEntry> Groups,
    IReadOnlyDictionary<string, BudgetGroupDetail> GroupDetails,
    IReadOnlyList<BudgetDailyPaceEntry> DailyPace,
    IReadOnlyList<BudgetPerformanceEntry> YearToDate,
    string? EmptyMessage = null);

/// <summary>Builds plan-versus-actual Budget analysis without any UI dependency.</summary>
public static class BudgetAnalysisCalculator
{
    /// <summary>Builds summary, pace, group detail, and year-to-date values for one budget request.</summary>
    public static BudgetAnalysisResult Build(
        IEnumerable<BudgetEntry> budgets,
        IEnumerable<FinancialTransaction> transactions,
        BudgetRequest request)
    {
        ArgumentNullException.ThrowIfNull(budgets);
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(request);
        request.Validate();

        BudgetEntry[] budgetRows = budgets
            .Where(entry => !entry.IsHidden && entry.Kind == TransactionKind.Expense)
            .ToArray();
        FinancialTransaction[] expenseRows = transactions
            .Where(transaction => !transaction.IsHidden && transaction.Kind == TransactionKind.Expense)
            .ToArray();
        string[] selectedGroups = request.Groups
            .Where(group => !string.IsNullOrWhiteSpace(group))
            .Select(group => group.Trim())
            .Where(group => !Contains(request.Adjustments.ExcludedGroups, group))
            .Distinct(StringComparer.Ordinal)
            .ToArray();

        if (selectedGroups.Length == 0)
            return Empty(request, "Select at least one budget group.");

        YearMonth historyStart = HistoryStart(
            budgetRows,
            expenseRows,
            selectedGroups,
            request.SelectedMonth,
            request.HistoryMonths);
        IReadOnlyList<YearMonth> historyMonths = YearMonth.InclusiveRange(historyStart, request.SelectedMonth);
        IReadOnlyList<BudgetHistoryEntry> groupHistory = BuildHistory(
            budgetRows,
            expenseRows,
            historyMonths,
            selectedGroups,
            BudgetDimension.Group,
            request.Adjustments,
            onlyCurrentEntities: false);
        IReadOnlyList<BudgetPerformanceEntry> groups = BuildPerformance(groupHistory, request.SelectedMonth)
            .OrderByDescending(entry => entry.Spent)
            .ThenBy(entry => entry.Entity, StringComparer.Ordinal)
            .ToArray();
        if (groups.Count == 0)
            return Empty(request, "No budget or spending data is available for this selection.");

        BudgetSummary summary = Summarize(groupHistory, request.SelectedMonth);
        var details = new Dictionary<string, BudgetGroupDetail>(StringComparer.Ordinal);
        foreach (BudgetPerformanceEntry group in groups)
        {
            string selectedGroup = group.Entity;
            IReadOnlyList<BudgetHistoryEntry> history = groupHistory
                .Where(entry => string.Equals(entry.Entity, selectedGroup, StringComparison.Ordinal))
                .ToArray();
            IReadOnlyList<BudgetHistoryEntry> categories = BuildHistory(
                budgetRows,
                expenseRows,
                historyMonths,
                [selectedGroup],
                BudgetDimension.Category,
                request.Adjustments,
                onlyCurrentEntities: true);
            FinancialTransaction[] groupTransactions = FilterTransactions(
                    expenseRows,
                    request.SelectedMonth,
                    request.SelectedMonth,
                    [selectedGroup],
                    request.Adjustments)
                .OrderByDescending(transaction => -transaction.Amount)
                .ThenByDescending(transaction => transaction.Date)
                .ThenBy(transaction => transaction.Id, StringComparer.Ordinal)
                .ToArray();
            details[selectedGroup] = new BudgetGroupDetail(
                group,
                history,
                BuildPerformance(categories, request.SelectedMonth),
                groupTransactions);
        }

        return new BudgetAnalysisResult(
            request,
            MonthProgress(request.SelectedMonth, request.ThroughDate),
            summary,
            groups,
            details,
            BuildDailyPace(budgetRows, expenseRows, request, selectedGroups),
            BuildYearToDate(budgetRows, expenseRows, request, selectedGroups),
            null);
    }

    private static BudgetAnalysisResult Empty(BudgetRequest request, string message)
        => new(
            request,
            MonthProgress(request.SelectedMonth, request.ThroughDate),
            new BudgetSummary(0m, 0m, 0m, 0m, 0m, 0m, 0m, 0m),
            [],
            new Dictionary<string, BudgetGroupDetail>(StringComparer.Ordinal),
            [],
            [],
            message);

    private static YearMonth HistoryStart(
        IReadOnlyList<BudgetEntry> budgets,
        IReadOnlyList<FinancialTransaction> transactions,
        IReadOnlyList<string> groups,
        YearMonth selectedMonth,
        int historyMonths)
    {
        YearMonth requestedStart = selectedMonth.AddMonths(-historyMonths);
        YearMonth[] observed = budgets
            .Where(entry => Contains(groups, entry.Group) && entry.Month.CompareTo(selectedMonth) <= 0)
            .Select(entry => entry.Month)
            .Concat(transactions
                .Where(transaction => Contains(groups, transaction.Group)
                    && transaction.Month.CompareTo(selectedMonth) <= 0)
                .Select(transaction => transaction.Month))
            .ToArray();
        if (observed.Length == 0)
            return selectedMonth;

        YearMonth earliest = observed.Min();
        return earliest.CompareTo(requestedStart) > 0 ? earliest : requestedStart;
    }

    private static IReadOnlyList<BudgetHistoryEntry> BuildHistory(
        IReadOnlyList<BudgetEntry> budgets,
        IReadOnlyList<FinancialTransaction> transactions,
        IReadOnlyList<YearMonth> months,
        IReadOnlyList<string> groups,
        BudgetDimension dimension,
        SpendingAdjustments adjustments,
        bool onlyCurrentEntities)
    {
        if (groups.Count == 0 || months.Count == 0)
            return [];

        BudgetEntry[] planned = budgets
            .Where(entry => Contains(groups, entry.Group)
                && Contains(months, entry.Month)
                && !Contains(adjustments.ExcludedCategories, entry.Category))
            .ToArray();
        FinancialTransaction[] actual = FilterTransactions(
            transactions,
            months[0],
            months[^1],
            groups,
            adjustments);
        var tracked = planned
            .Where(entry => entry.Amount > 0m)
            .Select(entry => new BudgetCategoryKey(entry.Month, entry.Group, entry.Category))
            .ToHashSet();
        string[] entities = Entities(planned, actual, groups, months[^1], dimension, onlyCurrentEntities);
        if (entities.Length == 0)
            return [];

        var rows = new List<BudgetHistoryEntry>(months.Count * entities.Length);
        foreach (YearMonth month in months)
        {
            foreach (string entity in entities)
            {
                BudgetEntry[] entityBudgets = planned
                    .Where(entry => entry.Month == month && Entity(entry.Group, entry.Category, dimension) == entity)
                    .ToArray();
                FinancialTransaction[] entityTransactions = actual
                    .Where(transaction => transaction.Month == month && Entity(transaction.Group, transaction.Category, dimension) == entity)
                    .ToArray();
                decimal trackedSpent = entityTransactions
                    .Where(transaction => tracked.Contains(new BudgetCategoryKey(transaction.Month, transaction.Group, transaction.Category)))
                    .Sum(transaction => -transaction.Amount);
                decimal outsidePlan = entityTransactions
                    .Where(transaction => !tracked.Contains(new BudgetCategoryKey(transaction.Month, transaction.Group, transaction.Category)))
                    .Sum(transaction => -transaction.Amount);
                rows.Add(new BudgetHistoryEntry(
                    month,
                    entity,
                    entityBudgets.Sum(entry => entry.Amount),
                    trackedSpent,
                    outsidePlan));
            }
        }

        return rows;
    }

    private static string[] Entities(
        IReadOnlyList<BudgetEntry> budgets,
        IReadOnlyList<FinancialTransaction> transactions,
        IReadOnlyList<string> groups,
        YearMonth selectedMonth,
        BudgetDimension dimension,
        bool onlyCurrentEntities)
    {
        if (dimension == BudgetDimension.Group)
            return groups.ToArray();

        IEnumerable<BudgetEntry> budgetValues = onlyCurrentEntities
            ? budgets.Where(entry => entry.Month == selectedMonth)
            : budgets;
        IEnumerable<FinancialTransaction> transactionValues = onlyCurrentEntities
            ? transactions.Where(transaction => transaction.Month == selectedMonth)
            : transactions;
        return budgetValues.Select(entry => entry.Category)
            .Concat(transactionValues.Select(transaction => transaction.Category))
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Distinct(StringComparer.Ordinal)
            .OrderBy(value => value, StringComparer.Ordinal)
            .ToArray();
    }

    private static IReadOnlyList<BudgetPerformanceEntry> BuildPerformance(
        IReadOnlyList<BudgetHistoryEntry> history,
        YearMonth selectedMonth)
    {
        if (history.Count == 0)
            return [];

        return history
            .Where(entry => entry.Month == selectedMonth)
            .Select(current =>
            {
                BudgetHistoryEntry[] prior = history
                    .Where(entry => entry.Month.CompareTo(selectedMonth) < 0
                        && string.Equals(entry.Entity, current.Entity, StringComparison.Ordinal))
                    .OrderBy(entry => entry.Month)
                    .ToArray();
                BudgetHistoryEntry[] budgeted = prior.Where(entry => entry.Budget > 0m).ToArray();
                decimal? percentUsed = current.Budget > 0m ? current.Spent / current.Budget * 100m : null;
                decimal typical = Median(prior.Select(entry => entry.Spent));
                return new BudgetPerformanceEntry(
                    current.Entity,
                    current.Budget,
                    current.TrackedSpent,
                    current.OutsidePlan,
                    current.Spent,
                    current.Budget - current.Spent,
                    percentUsed,
                    typical,
                    current.Spent - typical,
                    current.Spent - current.Budget,
                    budgeted.Count(entry => entry.Spent <= entry.Budget),
                    budgeted.Length,
                    budgeted.Length == 0 ? null : budgeted.Count(entry => entry.Spent <= entry.Budget) / (decimal)budgeted.Length * 100m,
                    [.. prior.Select(entry => entry.Spent), current.Spent]);
            })
            .ToArray();
    }

    private static BudgetSummary Summarize(IReadOnlyList<BudgetHistoryEntry> history, YearMonth selectedMonth)
    {
        BudgetHistoryEntry[] current = history.Where(entry => entry.Month == selectedMonth).ToArray();
        decimal budget = current.Sum(entry => entry.Budget);
        decimal tracked = current.Sum(entry => entry.TrackedSpent);
        decimal outside = current.Sum(entry => entry.OutsidePlan);
        decimal spent = tracked + outside;
        decimal typical = Median(history
            .Where(entry => entry.Month.CompareTo(selectedMonth) < 0)
            .GroupBy(entry => entry.Month)
            .Select(group => group.Sum(entry => entry.Spent)));
        return new BudgetSummary(
            budget,
            tracked,
            outside,
            spent,
            budget - spent,
            budget > 0m ? spent / budget * 100m : 0m,
            typical,
            spent - typical);
    }

    private static IReadOnlyList<BudgetDailyPaceEntry> BuildDailyPace(
        IReadOnlyList<BudgetEntry> budgets,
        IReadOnlyList<FinancialTransaction> transactions,
        BudgetRequest request,
        IReadOnlyList<string> groups)
    {
        DateOnly monthStart = request.SelectedMonth.Start;
        if (request.ThroughDate < monthStart)
            return [];

        DateOnly end = request.ThroughDate > request.SelectedMonth.End ? request.SelectedMonth.End : request.ThroughDate;
        decimal budget = budgets
            .Where(entry => entry.Month == request.SelectedMonth
                && Contains(groups, entry.Group)
                && !Contains(request.Adjustments.ExcludedCategories, entry.Category))
            .Sum(entry => entry.Amount);
        FinancialTransaction[] values = FilterTransactions(
            transactions,
            request.SelectedMonth,
            request.SelectedMonth,
            groups,
            request.Adjustments);
        var actualByDate = values
            .Where(transaction => transaction.Date >= monthStart && transaction.Date <= end)
            .GroupBy(transaction => transaction.Date)
            .ToDictionary(group => group.Key, group => group.Sum(transaction => -transaction.Amount));
        var result = new List<BudgetDailyPaceEntry>(end.Day);
        decimal actual = 0m;
        for (DateOnly date = monthStart; date <= end; date = date.AddDays(1))
        {
            actual += actualByDate.GetValueOrDefault(date);
            result.Add(new BudgetDailyPaceEntry(
                date,
                actual,
                budget * date.Day / request.SelectedMonth.End.Day));
        }

        return result;
    }

    private static IReadOnlyList<BudgetPerformanceEntry> BuildYearToDate(
        IReadOnlyList<BudgetEntry> budgets,
        IReadOnlyList<FinancialTransaction> transactions,
        BudgetRequest request,
        IReadOnlyList<string> groups)
    {
        IReadOnlyList<YearMonth> months = YearMonth.InclusiveRange(new YearMonth(request.SelectedMonth.Year, 1), request.SelectedMonth);
        BudgetEntry[] planned = budgets
            .Where(entry => Contains(months, entry.Month)
                && Contains(groups, entry.Group)
                && !Contains(request.Adjustments.ExcludedCategories, entry.Category))
            .ToArray();
        FinancialTransaction[] actual = FilterTransactions(transactions, months[0], months[^1], groups, request.Adjustments);
        return groups
            .Select(group =>
            {
                decimal budget = planned.Where(entry => entry.Group == group).Sum(entry => entry.Amount);
                decimal spent = actual.Where(transaction => transaction.Group == group).Sum(transaction => -transaction.Amount);
                return new BudgetPerformanceEntry(
                    group,
                    budget,
                    spent,
                    0m,
                    spent,
                    budget - spent,
                    budget > 0m ? spent / budget * 100m : null,
                    0m,
                    0m,
                    spent - budget,
                    0,
                    0,
                    null,
                    []);
            })
            .OrderByDescending(entry => entry.PercentUsed ?? (entry.Spent > 0m ? decimal.MaxValue : 0m))
            .ThenBy(entry => entry.Entity, StringComparer.Ordinal)
            .ToArray();
    }

    private static FinancialTransaction[] FilterTransactions(
        IEnumerable<FinancialTransaction> transactions,
        YearMonth start,
        YearMonth end,
        IReadOnlyList<string> groups,
        SpendingAdjustments adjustments)
        => transactions
            .Where(transaction => transaction.Month.CompareTo(start) >= 0
                && transaction.Month.CompareTo(end) <= 0
                && Contains(groups, transaction.Group)
                && !Contains(adjustments.ExcludedCategories, transaction.Category)
                && MatchesAdjustments(transaction, adjustments))
            .ToArray();

    private static bool MatchesAdjustments(FinancialTransaction transaction, SpendingAdjustments adjustments)
    {
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

    private static bool Contains<T>(IEnumerable<T> values, T value)
        => values.Contains(value);

    private static string Entity(string group, string category, BudgetDimension dimension)
        => dimension == BudgetDimension.Group ? group : category;

    private static decimal MonthProgress(YearMonth selectedMonth, DateOnly throughDate)
    {
        if (throughDate < selectedMonth.Start)
            return 0m;
        if (throughDate >= selectedMonth.End)
            return 1m;
        return throughDate.Day / (decimal)selectedMonth.End.Day;
    }

    private static decimal Median(IEnumerable<decimal> values)
    {
        decimal[] sorted = values.Order().ToArray();
        if (sorted.Length == 0)
            return 0m;
        int middle = sorted.Length / 2;
        return sorted.Length % 2 == 1 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2m;
    }

    private enum BudgetDimension
    {
        Group,
        Category
    }

    private readonly record struct BudgetCategoryKey(YearMonth Month, string Group, string Category);
}
