using System.Globalization;
using Portico.Finance;

namespace Portico.Dashboard;

/// <summary>Builds typed, display-ready reports for every configuration-defined Portico page.</summary>
public static class DashboardReportBuilder
{
    /// <summary>Builds all page reports from one normalized snapshot and filter state.</summary>
    public static DashboardReport Build(
        PortfolioSnapshot snapshot,
        FinanceSettings settings,
        DashboardFilters filters,
        DateOnly? asOfDate = null)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        ArgumentNullException.ThrowIfNull(settings);
        ArgumentNullException.ThrowIfNull(filters);

        IReadOnlyList<FinancialTransaction> visible = snapshot.Transactions.Where(transaction => !transaction.IsHidden).ToArray();
        DateOnly reportDate = asOfDate ?? snapshot.LatestDate ?? new DateOnly(2000, 1, 1);
        YearMonth? latestMonth = LatestMonth(snapshot);
        (YearMonth? start, YearMonth? end) = Period(latestMonth, filters.LookbackMonths);
        IReadOnlyList<FinancialTransaction> spending = FilterExpenseSet(visible, settings, filters.SpendingSet, start, end);
        IReadOnlyList<FinancialTransaction> yearOverYear = FilterExpenseSet(visible, settings, filters.YearOverYearSet, null, null);
        IncomeExpensePolicy incomePolicy = filters.RegularIncome
            ? IncomeExpensePolicy.From(settings.IncomeSavings)
            : new IncomeExpensePolicy([], []);
        IReadOnlyList<MonthlyCashFlow> cashFlow = CashFlowCalculator.BuildMonthly(visible, incomePolicy, start, end);
        IReadOnlyList<AccountBalance> accounts = PortfolioCalculator.LatestBalances(snapshot.Balances);

        var pages = new Dictionary<DashboardPageId, DashboardPageReport>
        {
            [DashboardPageId.Home] = Home(snapshot, cashFlow, accounts, settings, reportDate),
            [DashboardPageId.IncomeSavings] = Income(cashFlow, settings.IncomeSavings.TargetRate),
            [DashboardPageId.Spending] = Spending(spending),
            [DashboardPageId.YearOverYear] = YearOverYear(yearOverYear),
            [DashboardPageId.Subscriptions] = Subscriptions(
                visible,
                settings.Subscriptions,
                settings.MerchantAliases,
                latestMonth,
                reportDate),
            [DashboardPageId.Merchants] = Merchants(spending, settings.MerchantAliases),
            [DashboardPageId.Budget] = Budget(snapshot.Budgets, visible, start, end, settings.Budget.HistoryMonths),
            [DashboardPageId.TopTransactions] = TopTransactions(visible, settings.Thresholds, start, end),
            [DashboardPageId.FinancialIndependence] = FinancialIndependence(visible, accounts, settings, latestMonth, reportDate),
            [DashboardPageId.DataHealth] = DataHealth(snapshot, settings.DataHealth, settings.Thresholds, reportDate)
        };
        return new DashboardReport(pages);
    }

    /// <summary>Gets the report ids that a dashboard TOML file can refer to.</summary>
    public static IReadOnlySet<string> SupportedWidgetReports { get; } = new HashSet<string>(StringComparer.Ordinal)
    {
        "home.net_worth", "home.overview", "home.accounts", "home.inventory", "home.safety",
        "income.cash_flow", "income.savings_rate",
        "spending.monthly", "spending.categories",
        "yoy.comparison", "yoy.totals",
        "subscriptions.active", "subscriptions.monthly",
        "merchants.ranking", "merchants.history",
        "budget.comparison", "budget.history", "budget.table",
        "top.expenses", "top.incomes", "top.table",
        "fi.summary", "fi.projection", "fi.sensitivity",
        "health.summary", "health.findings"
    };

    private static DashboardPageReport Home(
        PortfolioSnapshot snapshot,
        IReadOnlyList<MonthlyCashFlow> cashFlow,
        IReadOnlyList<AccountBalance> accounts,
        FinanceSettings settings,
        DateOnly reportDate)
    {
        IReadOnlyList<NetWorthPoint> history = PortfolioCalculator.BuildNetWorthHistory(snapshot.Balances);
        decimal netWorth = accounts.Sum(account => account.SignedBalance);
        CashFlowSummary flow = CashFlowCalculator.Summarize(cashFlow);
        FinancialSafetySummary safety = FinancialSafetyCalculator.Summarize(
            snapshot.Transactions,
            snapshot.Balances,
            settings.FinancialSafety,
            settings.FinancialIndependence,
            reportDate);
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["home.net_worth"] = Chart(
                Series("net-worth", "Net worth", history.Select(point => Point(point.Date, point.NetWorth))),
                Series("assets", "Assets", history.Select(point => Point(point.Date, point.Assets))),
                Series("liabilities", "Liabilities", history.Select(point => Point(point.Date, point.Liabilities)))),
            ["home.overview"] = Metrics(
                Metric("Net worth", netWorth),
                Metric("Cash flow", flow.Surplus, flow.Surplus >= 0m ? "positive" : "negative"),
                Metric("Savings rate", flow.SavingsRatePercent, FormatPercent(flow.SavingsRatePercent)),
                Metric("Accounts", accounts.Count, accounts.Count.ToString(CultureInfo.InvariantCulture))),
            ["home.accounts"] = Chart(
                Series("accounts", "Latest balance", accounts
                    .GroupBy(account => account.Group, StringComparer.Ordinal)
                    .OrderBy(group => group.Key, StringComparer.Ordinal)
                    .Select(group => Point(group.Key, group.Sum(account => account.SignedBalance))))),
            ["home.inventory"] = new DashboardWidgetReport(
                [],
                [],
                ["Group", "Account", "Balance"],
                accounts.Select(account => new ReportTableRow([
                    account.Group,
                    account.Account,
                    FormatMoney(account.SignedBalance)
                ], account.SignedBalance < 0m ? "negative" : null)).ToArray(),
                accounts.Count == 0 ? "No visible account balances are available." : null),
            ["home.safety"] = Metrics(
                Metric(
                    "Emergency fund",
                    safety.EmergencyFundMonthsCovered,
                    FormatCoverage(safety.EmergencyFundMonthsCovered, safety.EmergencyFundTargetMonths),
                    safety.EmergencyFundMonthsCovered >= safety.EmergencyFundTargetMonths ? "positive" : null),
                Metric(
                    "Debt paid down",
                    safety.DebtProgressPercent,
                    FormatPercent(safety.DebtProgressPercent),
                    safety.DebtProgressPercent >= 0m ? "positive" : "negative"),
                Metric(
                    "FI funding",
                    safety.FinancialIndependenceProgressPercent,
                    FormatPercent(safety.FinancialIndependenceProgressPercent),
                    safety.FinancialIndependenceProgressPercent >= 100m ? "positive" : null))
        };
        return new DashboardPageReport(DashboardPageId.Home, widgets);
    }

    private static DashboardPageReport Income(IReadOnlyList<MonthlyCashFlow> monthly, decimal targetRate)
    {
        CashFlowSummary summary = CashFlowCalculator.Summarize(monthly);
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["income.cash_flow"] = Chart(
                Series("income", "Income", monthly.Select(value => Point(value.Month.Start, value.Income))),
                Series("spending", "Spending", monthly.Select(value => Point(value.Month.Start, value.NetExpenses))),
                Series("surplus", "Surplus", monthly.Select(value => Point(value.Month.Start, value.Surplus)))),
            ["income.savings_rate"] = Chart(
                Series("savings-rate", "Savings rate", monthly.Select(value => Point(value.Month.Start, value.SavingsRatePercent ?? 0m))),
                Series("target", "Target", monthly.Select(value => Point(value.Month.Start, targetRate))))
        };
        widgets["income.cash_flow"] = widgets["income.cash_flow"] with
        {
            Metrics = [
                Metric("Income", summary.Income),
                Metric("Spending", summary.NetExpenses),
                Metric("Surplus", summary.Surplus, summary.Surplus >= 0m ? "positive" : "negative")
            ]
        };
        return new DashboardPageReport(DashboardPageId.IncomeSavings, widgets);
    }

    private static DashboardPageReport Spending(IReadOnlyList<FinancialTransaction> transactions)
    {
        IReadOnlyList<SpendingItem> categories = CashFlowCalculator.AggregateSpending(transactions, transaction => transaction.Category);
        var monthly = transactions
            .GroupBy(transaction => new { transaction.Month, transaction.Category })
            .OrderBy(group => group.Key.Month)
            .ThenBy(group => group.Key.Category, StringComparer.Ordinal)
            .ToArray();
        IReadOnlyList<ReportSeries> monthlySeries = monthly
            .GroupBy(group => group.Key.Category, StringComparer.Ordinal)
            .OrderByDescending(group => group.Sum(month => -month.Sum(transaction => transaction.Amount)))
            .Take(8)
            .Select(group => Series(
                Slug(group.Key),
                group.Key,
                group.Select(value => Point(value.Key.Month.Start, -value.Sum(transaction => transaction.Amount)))))
            .ToArray();
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["spending.monthly"] = Chart(monthlySeries),
            ["spending.categories"] = Chart(Series("categories", "Spending", categories.Select(item => Point(item.Entity, item.Spending))))
        };
        return new DashboardPageReport(DashboardPageId.Spending, widgets);
    }

    private static DashboardPageReport YearOverYear(IReadOnlyList<FinancialTransaction> transactions)
    {
        IReadOnlyList<ReportSeries> comparison = transactions
            .GroupBy(transaction => transaction.Date.Year)
            .OrderBy(group => group.Key)
            .Select(group => Series(
                group.Key.ToString(CultureInfo.InvariantCulture),
                group.Key.ToString(CultureInfo.InvariantCulture),
                Enumerable.Range(1, 12).Select(month => Point(
                    new DateOnly(group.Key, month, 1),
                    -group.Where(transaction => transaction.Date.Month == month).Sum(transaction => transaction.Amount)))))
            .ToArray();
        IReadOnlyList<ReportPoint> totals = transactions
            .GroupBy(transaction => transaction.Date.Year)
            .OrderBy(group => group.Key)
            .Select(group => Point(group.Key.ToString(CultureInfo.InvariantCulture), -group.Sum(transaction => transaction.Amount)))
            .ToArray();
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["yoy.comparison"] = Chart(comparison),
            ["yoy.totals"] = Chart(Series("year-totals", "Spending", totals))
        };
        return new DashboardPageReport(DashboardPageId.YearOverYear, widgets);
    }

    private static DashboardPageReport Subscriptions(
        IReadOnlyList<FinancialTransaction> transactions,
        SubscriptionSettings settings,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases,
        YearMonth? latestMonth,
        DateOnly reportDate)
    {
        IReadOnlyList<SubscriptionItem> subscriptions = FindSubscriptions(transactions, settings, aliases);
        IReadOnlyList<FinancialTransaction> selected = transactions
            .Where(transaction => transaction.Kind == TransactionKind.Expense
                && subscriptions.Any(item => string.Equals(item.Merchant, Merchant(transaction, aliases), StringComparison.Ordinal)))
            .ToArray();
        int? dataAgeDays = transactions.Count == 0
            ? null
            : Math.Max(0, reportDate.DayNumber - transactions.Max(transaction => transaction.Date).DayNumber);
        IReadOnlyList<ReportPoint> monthly = ByMonth(selected, latestMonth is null ? null : latestMonth.Value.AddMonths(-11), latestMonth)
            .Select(value => Point(value.Month.Start, value.Value))
            .ToArray();
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["subscriptions.active"] = new DashboardWidgetReport(
                [
                    Metric("Active subscriptions", subscriptions.Count, subscriptions.Count.ToString(CultureInfo.InvariantCulture)),
                    Metric(
                        "Data age",
                        dataAgeDays,
                        dataAgeDays is null ? "No transaction data" : $"{dataAgeDays.Value} days old",
                        dataAgeDays > settings.StaleAfterDays ? "negative" : null)
                ],
                [],
                ["Merchant", "Source", "First seen", "Last seen", "Monthly run rate"],
                subscriptions.Select(item => new ReportTableRow([
                    item.Merchant,
                    item.Confidence is int confidence ? $"Detected ({confidence}%)" : item.Source,
                    FormatDate(item.FirstDate),
                    FormatDate(item.LastDate),
                    FormatMoney(item.MonthlyRunRate)
                ])).ToArray(),
                subscriptions.Count == 0 ? "No recurring subscription candidates were found." : null)
            {
                TimelineRanges = subscriptions
                    .Select(item => new ReportTimelineRange(
                        item.Merchant,
                        item.FirstDate,
                        item.LastDate,
                        FormatMoney(item.MonthlyRunRate)))
                    .ToArray(),
                DateGuide = reportDate
            },
            ["subscriptions.monthly"] = Chart(Series("subscriptions", "Subscription spending", monthly))
        };
        return new DashboardPageReport(DashboardPageId.Subscriptions, widgets);
    }

    private static DashboardPageReport Merchants(
        IReadOnlyList<FinancialTransaction> transactions,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        IReadOnlyList<SpendingItem> ranked = CashFlowCalculator.AggregateSpending(
            transactions,
            transaction => Merchant(transaction, aliases));
        string[] selected = ranked.Take(6).Select(item => item.Entity).ToArray();
        IReadOnlyList<ReportSeries> history = selected.Select(merchant => Series(
            Slug(merchant),
            merchant,
            ByMonth(transactions.Where(transaction => string.Equals(Merchant(transaction, aliases), merchant, StringComparison.Ordinal)), null, null)
                .Select(value => Point(value.Month.Start, value.Value)))).ToArray();
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["merchants.ranking"] = Chart(Series("merchants", "Spending", ranked.Select(item => Point(item.Entity, item.Spending)))),
            ["merchants.history"] = Chart(history)
        };
        return new DashboardPageReport(DashboardPageId.Merchants, widgets);
    }

    private static DashboardPageReport Budget(
        IReadOnlyList<BudgetEntry> budgets,
        IReadOnlyList<FinancialTransaction> spending,
        YearMonth? start,
        YearMonth? end,
        int historyMonths)
    {
        if (end is null)
            return new DashboardPageReport(DashboardPageId.Budget, EmptyBudget());

        IReadOnlyList<BudgetEntry> planned = budgets
            .Where(entry => entry.Kind == TransactionKind.Expense
                && !entry.IsHidden
                && IsInside(entry.Month, start, end))
            .OrderBy(entry => entry.Category, StringComparer.Ordinal)
            .ToArray();
        IReadOnlyDictionary<string, decimal> actual = spending
            .Where(transaction => transaction.Kind == TransactionKind.Expense && IsInside(transaction.Month, start, end))
            .GroupBy(transaction => transaction.Category, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => -group.Sum(transaction => transaction.Amount), StringComparer.Ordinal);
        string[] categories = planned.Select(entry => entry.Category)
            .Concat(actual.Keys)
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        var rows = new List<ReportTableRow>(categories.Length);
        var budgetPoints = new List<ReportPoint>(categories.Length);
        var actualPoints = new List<ReportPoint>(categories.Length);
        foreach (string category in categories)
        {
            decimal budget = planned.Where(entry => entry.Category == category).Sum(entry => entry.Amount);
            actual.TryGetValue(category, out decimal spent);
            budgetPoints.Add(Point(category, budget));
            actualPoints.Add(Point(category, spent));
            rows.Add(new ReportTableRow([
                category,
                FormatMoney(budget),
                FormatMoney(spent),
                FormatMoney(budget - spent)
            ], spent > budget && budget > 0m ? "negative" : null));
        }

        YearMonth historyStart = end.Value.AddMonths(1 - historyMonths);
        IReadOnlyList<YearMonth> historyMonthsRange = YearMonth.InclusiveRange(historyStart, end.Value);
        IReadOnlyList<ReportPoint> budgetHistory = historyMonthsRange
            .Select(month => Point(
                month.Start,
                budgets.Where(entry => entry.Kind == TransactionKind.Expense && !entry.IsHidden && entry.Month == month)
                    .Sum(entry => entry.Amount)))
            .ToArray();
        IReadOnlyList<ReportPoint> actualHistory = historyMonthsRange
            .Select(month => Point(
                month.Start,
                -spending.Where(transaction => transaction.Kind == TransactionKind.Expense && transaction.Month == month)
                    .Sum(transaction => transaction.Amount)))
            .ToArray();

        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["budget.comparison"] = Chart(Series("budget", "Budget", budgetPoints), Series("actual", "Actual", actualPoints)),
            ["budget.history"] = Chart(
                Series("budget", "Budget", budgetHistory),
                Series("actual", "Actual", actualHistory)),
            ["budget.table"] = new DashboardWidgetReport(
                [Metric("Budgeted", budgetPoints.Sum(point => point.Y)), Metric("Actual", actualPoints.Sum(point => point.Y))],
                [],
                ["Category", "Budget", "Actual", "Remaining"],
                rows,
                rows.Count == 0 ? "No budget entries or spending are available for this period." : null)
        };
        return new DashboardPageReport(DashboardPageId.Budget, widgets);
    }

    private static DashboardPageReport TopTransactions(
        IReadOnlyList<FinancialTransaction> transactions,
        ThresholdSettings thresholds,
        YearMonth? start,
        YearMonth? end)
    {
        IReadOnlyList<FinancialTransaction> inPeriod = transactions.Where(transaction => IsInside(transaction.Month, start, end)).ToArray();
        IReadOnlyList<FinancialTransaction> expenses = inPeriod
            .Where(transaction => transaction.Kind == TransactionKind.Expense && -transaction.Amount >= thresholds.Expense)
            .OrderBy(transaction => transaction.Date)
            .ThenBy(transaction => transaction.Id, StringComparer.Ordinal)
            .ToArray();
        IReadOnlyList<FinancialTransaction> incomes = inPeriod
            .Where(transaction => transaction.Kind == TransactionKind.Income && transaction.Amount >= thresholds.Income)
            .OrderBy(transaction => transaction.Date)
            .ThenBy(transaction => transaction.Id, StringComparer.Ordinal)
            .ToArray();
        IReadOnlyList<FinancialTransaction> top = inPeriod
            .Where(transaction => transaction.Kind is TransactionKind.Expense or TransactionKind.Income)
            .OrderByDescending(transaction => decimal.Abs(transaction.Amount))
            .ThenByDescending(transaction => transaction.Date)
            .ThenBy(transaction => transaction.Id, StringComparer.Ordinal)
            .Take(30)
            .ToArray();
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["top.expenses"] = Chart(Series("expenses", "Large expense", expenses.Select(transaction => Point(
                transaction.Date,
                -transaction.Amount,
                transaction.Description)))),
            ["top.incomes"] = Chart(Series("incomes", "Large income", incomes.Select(transaction => Point(
                transaction.Date,
                transaction.Amount,
                transaction.Description)))),
            ["top.table"] = new DashboardWidgetReport(
                [
                    Metric("Large expenses", expenses.Count, expenses.Count.ToString(CultureInfo.InvariantCulture)),
                    Metric("Large income", incomes.Count, incomes.Count.ToString(CultureInfo.InvariantCulture))
                ],
                [],
                ["Date", "Description", "Category", "Amount"],
                top.Select(transaction => new ReportTableRow([
                    FormatDate(transaction.Date),
                    transaction.Description,
                    transaction.Category,
                    FormatMoney(transaction.Amount)
                ], transaction.Kind == TransactionKind.Expense ? "negative" : "positive")).ToArray(),
                top.Count == 0 ? "No income or expense transactions are available." : null)
        };
        return new DashboardPageReport(DashboardPageId.TopTransactions, widgets);
    }

    private static DashboardPageReport FinancialIndependence(
        IReadOnlyList<FinancialTransaction> transactions,
        IReadOnlyList<AccountBalance> accounts,
        FinanceSettings settings,
        YearMonth? latestMonth,
        DateOnly asOfDate)
    {
        (YearMonth? start, YearMonth? end) = Period(latestMonth, settings.FinancialIndependence.SpendingLookbackMonths);
        decimal months = start is null || end is null ? 0m : settings.FinancialIndependence.SpendingLookbackMonths;
        decimal annualSpending = months == 0m
            ? 0m
            : -transactions
                .Where(transaction => transaction.Kind == TransactionKind.Expense && IsInside(transaction.Month, start, end))
                .Sum(transaction => transaction.Amount) / months * 12m;
        decimal annualIncome = months == 0m
            ? 0m
            : transactions
                .Where(transaction => transaction.Kind == TransactionKind.Income && IsInside(transaction.Month, start, end))
                .Sum(transaction => transaction.Amount) / months * 12m;
        decimal portfolio = accounts
            .Where(account => IsIncluded(account, settings.FinancialIndependence))
            .Sum(account => account.SignedBalance);
        FinancialIndependenceSummary summary = FinancialIndependenceCalculator.Summarize(
            portfolio,
            annualSpending,
            settings.FinancialIndependence.ExpectedReturnRate,
            annualIncome,
            settings.FinancialIndependence.WithdrawalRate);
        IReadOnlyList<PortfolioProjectionPoint> projection = FinancialIndependenceCalculator.Project(
            portfolio,
            annualSpending,
            settings.FinancialIndependence.ExpectedReturnRate,
            settings.FinancialIndependence.ProjectionYears,
            annualIncome);
        decimal[] spendingChanges = [-20m, -10m, 0m, 10m, 20m];
        decimal[] returns = (new decimal[] { 0m, 3m, 5m, settings.FinancialIndependence.ExpectedReturnRate, 9m })
            .Distinct()
            .Order()
            .ToArray();
        IReadOnlyList<RunwaySensitivityCell> sensitivity = FinancialIndependenceCalculator.BuildSensitivity(
            portfolio,
            annualSpending,
            annualIncome,
            spendingChanges,
            returns);
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["fi.summary"] = Metrics(
                Metric("Portfolio", portfolio),
                Metric("FI target", summary.FinancialIndependenceTarget),
                Metric("Funding gap", summary.FundingGap, summary.FundingGap >= 0m ? "positive" : "negative"),
                Metric("Runway", summary.RunwayYears, summary.RunwayYears is null ? "Sustainable" : $"{summary.RunwayYears:0.0} years")),
            ["fi.projection"] = Chart(Series("portfolio", "Projected portfolio", projection.Select(point => Point(
                new DateOnly(asOfDate.Year + point.Year, 1, 1), point.Balance)))),
            ["fi.sensitivity"] = new DashboardWidgetReport(
                [],
                sensitivity.GroupBy(cell => cell.ReturnRate).Select(group => Series(
                    $"return-{group.Key:0.##}",
                    $"{group.Key:0.##}% return",
                    group.Select(cell => Point($"{(cell.AnnualSpending / (annualSpending == 0m ? 1m : annualSpending) - 1m) * 100m:+0;-0;0}%", cell.RunwayYears ?? 999m)))).ToArray(),
                ["Spending change", "Return", "Runway"],
                sensitivity.Select(cell => new ReportTableRow([
                    FormatMoney(cell.AnnualSpending),
                    $"{cell.ReturnRate:0.##}%",
                    cell.RunwayYears is null ? "Sustainable" : $"{cell.RunwayYears:0.0} years"
                ])).ToArray(),
                "A sustainable scenario is shown without a finite runway.")
            {
                HeatmapCells = sensitivity
                    .Select(cell => new ReportHeatmapCell(
                        $"{(cell.AnnualSpending / (annualSpending == 0m ? 1m : annualSpending) - 1m) * 100m:+0;-0;0}%",
                        $"{cell.ReturnRate:0.##}% return",
                        cell.RunwayYears ?? 100m,
                        cell.RunwayYears is null ? "Sustainable" : $"{cell.RunwayYears:0.0} years"))
                    .ToArray()
            }
        };
        return new DashboardPageReport(DashboardPageId.FinancialIndependence, widgets);
    }

    private static DashboardPageReport DataHealth(
        PortfolioSnapshot snapshot,
        DataHealthSettings settings,
        ThresholdSettings thresholds,
        DateOnly asOfDate)
    {
        IReadOnlyList<FinancialTransaction> uncategorized = snapshot.Transactions
            .Where(transaction => transaction.Kind == TransactionKind.Unknown || transaction.Group == "Uncategorized")
            .ToArray();
        IReadOnlyList<BalanceObservation> stale = snapshot.Balances
            .GroupBy(balance => balance.AccountId, StringComparer.Ordinal)
            .Select(group => group.OrderByDescending(balance => balance.Date).ThenByDescending(balance => balance.Time).First())
            .Where(balance => asOfDate.DayNumber - balance.Date.DayNumber > settings.StaleAccountDays)
            .ToArray();
        IReadOnlyList<DuplicatePair> duplicates = FindDuplicatePairs(snapshot.Transactions, thresholds, settings);
        var rows = new List<ReportTableRow>();
        rows.AddRange(uncategorized.Select(transaction => new ReportTableRow([
            "Uncategorized", FormatDate(transaction.Date), transaction.Description, transaction.Category
        ], "negative")));
        rows.AddRange(stale.Select(balance => new ReportTableRow([
            "Stale account", FormatDate(balance.Date), balance.Account, $"{asOfDate.DayNumber - balance.Date.DayNumber} days old"
        ], "negative")));
        rows.AddRange(duplicates.Select(pair => new ReportTableRow([
            "Possible duplicate", FormatDate(pair.First.Date), pair.First.Description, $"{pair.DaysApart} days apart"
        ], "negative")));
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["health.summary"] = Metrics(
                Metric("Uncategorized", uncategorized.Count, uncategorized.Count.ToString(CultureInfo.InvariantCulture), uncategorized.Count == 0 ? "positive" : "negative"),
                Metric("Stale accounts", stale.Count, stale.Count.ToString(CultureInfo.InvariantCulture), stale.Count == 0 ? "positive" : "negative"),
                Metric("Possible duplicates", duplicates.Count, duplicates.Count.ToString(CultureInfo.InvariantCulture), duplicates.Count == 0 ? "positive" : "negative")),
            ["health.findings"] = new DashboardWidgetReport(
                [], [], ["Finding", "Date", "Details", "Status"], rows,
                rows.Count == 0 ? "No data health findings." : null)
        };
        return new DashboardPageReport(DashboardPageId.DataHealth, widgets);
    }

    private static IReadOnlyDictionary<string, DashboardWidgetReport> EmptyBudget()
        => new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["budget.comparison"] = new DashboardWidgetReport([], [], [], [], "No dated budget data is available for this period."),
            ["budget.history"] = new DashboardWidgetReport([], [], [], [], "No dated budget data is available for this period."),
            ["budget.table"] = new DashboardWidgetReport([], [], ["Category", "Budget", "Actual", "Remaining"], [], "No dated budget data is available for this period.")
        };

    private static IReadOnlyList<FinancialTransaction> FilterExpenseSet(
        IReadOnlyList<FinancialTransaction> transactions,
        FinanceSettings settings,
        string setKey,
        YearMonth? start,
        YearMonth? end)
        => TransactionSetMatcher.Select(transactions, setKey, settings.TransactionSets, settings.MerchantAliases)
            .Where(transaction => transaction.Kind == TransactionKind.Expense && IsInside(transaction.Month, start, end))
            .ToArray();

    private static IReadOnlyList<SubscriptionItem> FindSubscriptions(
        IReadOnlyList<FinancialTransaction> transactions,
        SubscriptionSettings settings,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        FinancialTransaction[] expenses = transactions
            .Where(transaction => transaction.Kind == TransactionKind.Expense)
            .ToArray();
        var results = new List<SubscriptionItem>();
        var knownMerchants = new HashSet<string>(StringComparer.Ordinal);

        foreach (IGrouping<string, FinancialTransaction> group in expenses
                     .Where(transaction => settings.KnownCategories.Contains(transaction.Category, StringComparer.Ordinal))
                     .GroupBy(transaction => Merchant(transaction, aliases), StringComparer.Ordinal))
        {
            FinancialTransaction[] values = group.OrderBy(transaction => transaction.Date).ToArray();
            knownMerchants.Add(group.Key);
            results.Add(CreateSubscription(group.Key, values, "Configured", null));
        }

        foreach (IGrouping<string, FinancialTransaction> group in expenses
                     .Where(transaction => !settings.KnownCategories.Contains(transaction.Category, StringComparer.Ordinal)
                         && !settings.DefaultExcludeCategories.Contains(transaction.Category, StringComparer.Ordinal)
                         && !settings.DetectionExcludedCategories.Contains(transaction.Category, StringComparer.Ordinal))
                     .GroupBy(transaction => Merchant(transaction, aliases), StringComparer.Ordinal))
        {
            if (knownMerchants.Contains(group.Key))
                continue;

            FinancialTransaction[] values = group.OrderBy(transaction => transaction.Date).ToArray();
            int confidence = SubscriptionConfidence(values);
            if (confidence < settings.MinimumConfidence)
                continue;

            results.Add(CreateSubscription(group.Key, values, "Detected", confidence));
        }

        return results
            .OrderByDescending(item => item.MonthlyRunRate)
            .ThenBy(item => item.Merchant, StringComparer.Ordinal)
            .ToArray();
    }

    private static SubscriptionItem CreateSubscription(
        string merchant,
        IReadOnlyList<FinancialTransaction> values,
        string source,
        int? confidence)
    {
        decimal months = decimal.Max(1m, MonthsBetween(values[0].Month, values[^1].Month) + 1m);
        return new SubscriptionItem(
            merchant,
            values[0].Date,
            values[^1].Date,
            -values.Sum(transaction => transaction.Amount) / months,
            source,
            confidence);
    }

    private static int SubscriptionConfidence(IReadOnlyList<FinancialTransaction> values)
    {
        int uniqueMonths = values.Select(transaction => transaction.Month).Distinct().Count();
        if (values.Count < 3 || uniqueMonths < 3 || values.Count > uniqueMonths * 1.25m)
            return 0;

        decimal[] intervals = values
            .Zip(values.Skip(1), (first, second) => (decimal)(second.Date.DayNumber - first.Date.DayNumber))
            .ToArray();
        decimal cadence = Median(intervals);
        decimal tolerance = decimal.Max(7m, cadence * 0.25m);
        decimal regularity = intervals.Count(interval => decimal.Abs(interval - cadence) <= tolerance) / (decimal)intervals.Length;
        decimal medianAmount = Median(values.Select(transaction => decimal.Abs(transaction.Amount)));
        decimal meanDeviation = values.Average(transaction => decimal.Abs(decimal.Abs(transaction.Amount) - medianAmount));
        decimal amountStability = medianAmount == 0m
            ? 0m
            : decimal.Max(0m, 1m - meanDeviation / (medianAmount * 0.5m));
        decimal confidence = regularity * 50m
            + decimal.Min(values.Count / 6m, 1m) * 15m
            + decimal.Min(uniqueMonths / 6m, 1m) * 15m
            + amountStability * 20m;
        return decimal.ToInt32(decimal.Round(confidence, 0, MidpointRounding.AwayFromZero));
    }

    private static decimal Median(IEnumerable<decimal> values)
    {
        decimal[] ordered = values.Order().ToArray();
        if (ordered.Length == 0)
            return 0m;

        int middle = ordered.Length / 2;
        return ordered.Length % 2 == 0
            ? (ordered[middle - 1] + ordered[middle]) / 2m
            : ordered[middle];
    }

    private static IReadOnlyList<MonthlyValue> ByMonth(
        IEnumerable<FinancialTransaction> transactions,
        YearMonth? start,
        YearMonth? end)
        => transactions
            .Where(transaction => transaction.Kind == TransactionKind.Expense && IsInside(transaction.Month, start, end))
            .GroupBy(transaction => transaction.Month)
            .OrderBy(group => group.Key)
            .Select(group => new MonthlyValue(group.Key, -group.Sum(transaction => transaction.Amount)))
            .ToArray();

    private static bool IsIncluded(AccountBalance account, FinancialIndependenceSettings settings)
    {
        if (settings.IncludedGroups.Count == 0 && settings.IncludedAccountPatterns.Count == 0)
            return account.AccountClass == AccountClass.Asset;
        return settings.IncludedGroups.Contains(account.Group, StringComparer.Ordinal)
            || settings.IncludedAccountPatterns.Any(pattern => account.Account.Contains(pattern, StringComparison.OrdinalIgnoreCase));
    }

    private static IReadOnlyList<DuplicatePair> FindDuplicatePairs(
        IEnumerable<FinancialTransaction> transactions,
        ThresholdSettings thresholds,
        DataHealthSettings settings)
    {
        FinancialTransaction[] candidates = transactions
            .Where(transaction => !transaction.IsHidden && decimal.Abs(transaction.Amount) >= thresholds.DuplicateMinimum)
            .OrderBy(transaction => transaction.Amount)
            .ThenBy(transaction => transaction.Date)
            .ToArray();
        var pairs = new List<DuplicatePair>();
        foreach (IGrouping<decimal, FinancialTransaction> amountGroup in candidates.GroupBy(transaction => transaction.Amount))
        {
            FinancialTransaction[] values = amountGroup.OrderBy(transaction => transaction.Date).ToArray();
            for (int firstIndex = 0; firstIndex < values.Length; firstIndex++)
            {
                FinancialTransaction first = values[firstIndex];
                for (int secondIndex = firstIndex + 1; secondIndex < values.Length; secondIndex++)
                {
                    FinancialTransaction second = values[secondIndex];
                    int daysApart = second.Date.DayNumber - first.Date.DayNumber;
                    if (daysApart > thresholds.DuplicateDays)
                        break;
                    if (settings.DuplicateRequireSameAccount
                        && !string.Equals(first.Account, second.Account, StringComparison.Ordinal))
                    {
                        continue;
                    }
                    if (settings.DuplicateRequireSameCategory
                        && !string.Equals(first.Category, second.Category, StringComparison.Ordinal))
                    {
                        continue;
                    }
                    if (settings.DuplicateRequireSameDescription
                        && !string.Equals(first.Description.Trim(), second.Description.Trim(), StringComparison.OrdinalIgnoreCase))
                    {
                        continue;
                    }

                    pairs.Add(new DuplicatePair(first, second, daysApart));
                }
            }
        }

        return pairs;
    }

    private static (YearMonth? Start, YearMonth? End) Period(YearMonth? latest, int months)
    {
        if (latest is null || months <= 0)
            return (null, null);
        return (latest.Value.AddMonths(1 - months), latest);
    }

    private static YearMonth? LatestMonth(PortfolioSnapshot snapshot)
        => snapshot.LatestDate is DateOnly date ? YearMonth.From(date) : null;

    private static bool IsInside(YearMonth month, YearMonth? start, YearMonth? end)
        => start is null || (month.CompareTo(start.Value) >= 0 && month.CompareTo(end!.Value) <= 0);

    private static int MonthsBetween(YearMonth start, YearMonth end)
        => (end.Year - start.Year) * 12 + end.Month - start.Month;

    private static string Merchant(FinancialTransaction transaction, IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
        => TransactionSetMatcher.NormalizeMerchant(transaction.Description, aliases);

    private static DashboardWidgetReport Metrics(params ReportMetric[] metrics)
        => new(metrics, [], [], []);

    private static DashboardWidgetReport Chart(params ReportSeries[] series)
        => Chart((IReadOnlyList<ReportSeries>)series);

    private static DashboardWidgetReport Chart(IReadOnlyList<ReportSeries> series)
        => new([], series, [], [], series.Count == 0 ? "No data is available for this selection." : null);

    private static ReportSeries Series(string id, string label, IEnumerable<ReportPoint> points)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(id);
        ArgumentException.ThrowIfNullOrWhiteSpace(label);
        ArgumentNullException.ThrowIfNull(points);
        return new ReportSeries(id, label, points.ToArray());
    }

    private static ReportPoint Point(DateOnly date, decimal value, string? label = null)
        => new(date, null, date.DayNumber, value, label);

    private static ReportPoint Point(string category, decimal value, string? label = null)
        => new(null, category, 0m, value, label);

    private static ReportMetric Metric(string label, decimal? value, string? display = null, string? tone = null)
        => new(label, value, display ?? (value is null ? "—" : FormatMoney(value.Value)), tone);

    private static string FormatMoney(decimal value)
        => value.ToString("C0", CultureInfo.GetCultureInfo("en-US"));

    private static string FormatPercent(decimal? value)
        => value is null ? "—" : $"{value:0.0}%";

    private static string FormatCoverage(decimal? months, int targetMonths)
        => months is null ? "No expense baseline" : $"{months:0.0} / {targetMonths} months";

    private static string FormatDate(DateOnly value)
        => value.ToString("MMM d, yyyy", CultureInfo.GetCultureInfo("en-US"));

    private static string Slug(string value)
    {
        var builder = new System.Text.StringBuilder(value.Length);
        foreach (char character in value)
        {
            if (char.IsLetterOrDigit(character))
                builder.Append(char.ToLowerInvariant(character));
            else if (builder.Length > 0 && builder[^1] != '-')
                builder.Append('-');
        }

        return builder.ToString().Trim('-');
    }

    private sealed record MonthlyValue(YearMonth Month, decimal Value);

    private sealed record DuplicatePair(FinancialTransaction First, FinancialTransaction Second, int DaysApart);

    private sealed record SubscriptionItem(
        string Merchant,
        DateOnly FirstDate,
        DateOnly LastDate,
        decimal MonthlyRunRate,
        string Source,
        int? Confidence);
}
