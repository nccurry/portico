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
        var presentation = new DashboardPresentationState();
        presentation.InitializeIncomeSavings(settings);
        return Build(snapshot, settings, filters, presentation, asOfDate);
    }

    /// <summary>Builds all page reports with the selected page-local presentation state.</summary>
    public static DashboardReport Build(
        PortfolioSnapshot snapshot,
        FinanceSettings settings,
        DashboardFilters filters,
        DashboardPresentationState presentation,
        DateOnly? asOfDate = null)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        ArgumentNullException.ThrowIfNull(settings);
        ArgumentNullException.ThrowIfNull(filters);
        ArgumentNullException.ThrowIfNull(presentation);

        IReadOnlyList<FinancialTransaction> visible = snapshot.Transactions.Where(transaction => !transaction.IsHidden).ToArray();
        DateOnly reportDate = asOfDate ?? snapshot.LatestDate ?? new DateOnly(2000, 1, 1);
        DateOnly dataHealthDate = snapshot.LatestDate ?? reportDate;
        YearMonth? latestMonth = LatestMonth(snapshot);
        (YearMonth? start, YearMonth? end) = Period(latestMonth, filters.LookbackMonths);
        IReadOnlyList<FinancialTransaction> spending = FilterExpenseSet(visible, settings, filters.SpendingSet, start, end);
        IncomeExpensePolicy incomePolicy = filters.RegularIncome
            ? IncomeExpensePolicy.From(settings.IncomeSavings)
            : new IncomeExpensePolicy([], []);
        IReadOnlyList<MonthlyCashFlow> cashFlow = CashFlowCalculator.BuildMonthly(visible, incomePolicy, start, end);
        IReadOnlyList<AccountBalance> accounts = PortfolioCalculator.LatestBalances(snapshot.Balances);

        var pages = new Dictionary<DashboardPageId, DashboardPageReport>
        {
            [DashboardPageId.Home] = Home(snapshot, cashFlow, settings, filters.HomeTimeFrame, reportDate),
            [DashboardPageId.IncomeSavings] = Income(visible, filters, presentation.IncomeSavings),
            [DashboardPageId.Spending] = Spending(visible, settings, filters, presentation.Spending),
            [DashboardPageId.YearOverYear] = YearOverYear(visible, settings, filters, presentation.YearOverYear),
            [DashboardPageId.Subscriptions] = Subscriptions(
                visible,
                settings,
                filters,
                presentation.Subscriptions,
                reportDate),
            [DashboardPageId.Merchants] = Merchants(visible, settings, filters, presentation.Merchants),
            [DashboardPageId.Budget] = filters.Budget is { } budgetRequest
                ? BudgetPage(snapshot.Budgets, visible, budgetRequest, presentation.Budget, reportDate)
                : Budget(snapshot.Budgets, visible, start, end, settings.Budget.HistoryMonths),
            [DashboardPageId.TopTransactions] = TopTransactions(visible, settings, filters, presentation.Transactions),
            [DashboardPageId.FinancialIndependence] = filters.FinancialIndependenceSource is not null
                || filters.FinancialIndependenceScenario is not null
                ? FinancialIndependencePage(
                    visible,
                    accounts,
                    settings,
                    filters.FinancialIndependenceSource
                        ?? FinancialIndependenceSourceAnalysisCalculator.DefaultFilters(accounts, settings),
                    filters.FinancialIndependenceScenario,
                    reportDate)
                : FinancialIndependence(visible, accounts, settings, latestMonth, reportDate),
            [DashboardPageId.DataHealth] = filters.DataHealth is { } dataHealth
                ? DataHealthPage(snapshot, dataHealth, presentation.DataHealth.SelectedCheckId, dataHealthDate)
                : DataHealth(snapshot, settings.DataHealth, settings.Thresholds, reportDate)
        };
        return new DashboardReport(pages);
    }

    /// <summary>Gets the report ids that a dashboard TOML file can refer to.</summary>
    public static IReadOnlySet<string> SupportedWidgetReports { get; } = new HashSet<string>(StringComparer.Ordinal)
    {
        "home.net_worth", "home.overview", "home.attribution", "home.accounts", "home.inventory", "home.safety",
        "income.summary", "income.cash_flow", "income.savings_rate", "income.detail", "income.included_categories",
        "income.included_transactions", "income.excluded_transactions", "income.monthly_totals",
        "spending.monthly", "spending.categories",
        "spending.summary", "spending.trend", "spending.ranking", "spending.overview", "spending.detail_summary", "spending.detail_history",
        "spending.detail_categories", "spending.detail_merchants", "spending.detail_transactions", "spending.excluded",
        "yoy.comparison", "yoy.totals",
        "subscriptions.active", "subscriptions.monthly", "subscriptions.summary", "subscriptions.lifecycle", "subscriptions.history_spend", "subscriptions.history_active", "subscriptions.candidates", "subscriptions.inactive", "subscriptions.detail_charge_history", "subscriptions.detail_charges", "subscriptions.detail_monthly_totals",
        "merchants.ranking", "merchants.history", "merchants.summary", "merchants.overview", "merchants.detail_summary", "merchants.detail_history", "merchants.detail_categories", "merchants.detail_accounts", "merchants.detail_descriptions", "merchants.detail_transactions", "merchants.excluded",
        "budget.summary", "budget.pace", "budget.comparison", "budget.performance", "budget.group_summary", "budget.history", "budget.categories", "budget.category_table", "budget.transactions", "budget.ytd_summary", "budget.ytd_table", "budget.table",
        "top.expenses", "top.incomes", "top.table", "transactions.summary", "transactions.history", "transactions.breakdown", "transactions.table",
        "fi.summary", "fi.projection", "fi.funding", "fi.sensitivity", "fi.source_accounts", "fi.source_spending", "fi.source_transactions",
        "health.summary", "health.queue", "health.detail", "health.findings"
    };

    private static DashboardPageReport Home(
        PortfolioSnapshot snapshot,
        IReadOnlyList<MonthlyCashFlow> cashFlow,
        FinanceSettings settings,
        HomeTimeFrame timeFrame,
        DateOnly reportDate)
    {
        HomeReportRange? range = HomeReportRange.Create(snapshot.Balances, timeFrame);
        IReadOnlyList<NetWorthPoint> history = BuildHomeHistory(snapshot.Balances, range);
        IReadOnlyList<AccountBalance> accounts = range is null
            ? []
            : PortfolioCalculator.LatestBalances(snapshot.Balances, range.End);
        IReadOnlyList<AccountBalance> openingAccounts = range is null
            ? []
            : PortfolioCalculator.LatestBalances(snapshot.Balances, range.Start);
        IReadOnlyList<ReportMetric> accountGroups = BuildHomeAccountGroups(accounts, openingAccounts, range);
        IReadOnlyList<ReportTableRow> inventory = BuildHomeAccountInventory(accounts, openingAccounts, range);
        NetWorthPoint? opening = history.FirstOrDefault();
        NetWorthPoint? current = history.LastOrDefault();
        CashFlowSummary flow = CashFlowCalculator.Summarize(cashFlow);
        FinancialSafetySummary safety = FinancialSafetyCalculator.Summarize(
            snapshot.Transactions,
            snapshot.Balances,
            settings.FinancialSafety,
            settings.FinancialIndependence,
            reportDate);
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["home.net_worth"] = history.Count == 0
                ? EmptyHomeReport()
                : Chart(
                    Series("net-worth", "Net worth", history.Select(point => Point(point.Date, point.NetWorth))),
                    Series("assets", "Assets", history.Select(point => Point(point.Date, point.Assets))),
                    Series("liabilities", "Liabilities", history.Select(point => Point(point.Date, point.Liabilities)))) with
                {
                    Metrics = HomeNetWorthMetrics(opening, current, range)
                },
            ["home.overview"] = Metrics(
                Metric("Net worth", accounts.Sum(account => account.SignedBalance)),
                Metric("Cash flow", flow.Surplus, flow.Surplus >= 0m ? "positive" : "negative"),
                Metric("Savings rate", flow.SavingsRatePercent, FormatPercent(flow.SavingsRatePercent)),
                Metric("Accounts", accounts.Count, accounts.Count.ToString(CultureInfo.InvariantCulture))),
            ["home.attribution"] = accountGroups.Count == 0
                ? EmptyHomeReport()
                : Chart(
                    Series(
                        "groups",
                        "Net-worth movement",
                        accountGroups
                            .OrderBy(group => group.Change ?? 0m)
                            .ThenBy(group => group.Label, StringComparer.Ordinal)
                            .Select(group => Point(group.Label, group.Change ?? 0m)))),
            ["home.accounts"] = new DashboardWidgetReport(
                accountGroups,
                [],
                [],
                [],
                accountGroups.Count == 0 ? "No mapped balance groups are available." : null),
            ["home.inventory"] = new DashboardWidgetReport(
                [],
                [],
                ["Group", "Account", "Balance", "Change"],
                inventory,
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

    private static DashboardPageReport Income(
        IReadOnlyList<FinancialTransaction> transactions,
        DashboardFilters filters,
        IncomeSavingsPresentationState presentation)
    {
        IncomeSavingsAdjustments adjustments = presentation.Adjustments(filters.RegularIncome);
        IncomeSavingsAnalysisResult analysis = IncomeSavingsAnalysisCalculator.Build(
            transactions,
            filters.EffectiveIncomeLookbackMonths,
            adjustments);
        IReadOnlyList<ReportMetric> summary = IncomeSummaryMetrics(
            analysis.CurrentSummary,
            analysis.PreviousSummary,
            analysis.HasFullPreviousPeriod,
            filters.EffectiveIncomeLookbackMonths,
            adjustments.TargetRate);
        IReadOnlyList<ReportSeries> cashFlow =
        [
            Series("income", "Income", analysis.CurrentMonthly.Select(month => Point(month.Month.Start, month.Income))),
            Series("spending", "Spending", analysis.CurrentMonthly.Select(month => Point(month.Month.Start, -month.NetExpenses))),
            Series("surplus", "Surplus", analysis.CurrentMonthly.Select(month => Point(month.Month.Start, month.Surplus)))
        ];
        IReadOnlyList<ReportSeries> savingsRate =
        [
            Series("savings-rate", "Savings rate", analysis.CurrentMonthly.Select(month => Point(month.Month.Start, month.SavingsRatePercent ?? 0m))),
            Series("target", "Target", analysis.CurrentMonthly.Select(month => Point(month.Month.Start, adjustments.TargetRate)))
        ];
        IReadOnlyList<string> detailMonths = analysis.Period.CurrentMonths
            .Reverse()
            .Select(month => month.ToString())
            .ToArray();
        string detailMonth = detailMonths.Contains(presentation.DetailMonth, StringComparer.Ordinal)
            ? presentation.DetailMonth
            : detailMonths.FirstOrDefault() ?? string.Empty;
        YearMonth? selectedMonth = analysis.Period.CurrentMonths
            .Where(month => string.Equals(month.ToString(), detailMonth, StringComparison.Ordinal))
            .Select(month => (YearMonth?)month)
            .FirstOrDefault();
        IReadOnlyList<IncomeSavingsLedgerEntry> selectedEntries = selectedMonth is YearMonth month
            ? analysis.CurrentLedger.Where(entry => entry.Transaction.Month == month).ToArray()
            : [];
        IReadOnlyList<IncomeSavingsLedgerEntry> includedEntries = selectedEntries.Where(entry => entry.Included).ToArray();
        IReadOnlyList<IncomeSavingsLedgerEntry> excludedEntries = selectedEntries.Where(entry => !entry.Included).ToArray();
        IncomeSavingsMonth? detail = selectedMonth is YearMonth selected
            ? analysis.CurrentMonthly.FirstOrDefault(value => value.Month == selected)
            : null;
        IReadOnlyList<ReportMetric> detailMetrics = detail is null
            ? []
            :
            [
                Metric("Income", detail.Income),
                Metric("Spending", detail.NetExpenses),
                Metric("Net cash flow", detail.Surplus, tone: detail.Surplus >= 0m ? "positive" : "negative"),
                new ReportMetric("Savings rate", detail.SavingsRatePercent, FormatPercent(detail.SavingsRatePercent),
                    detail.SavingsRatePercent >= adjustments.TargetRate ? "positive" : null)
            ];
        IReadOnlyList<ReportTableRow> categories = IncomeCategoryRows(includedEntries);
        IReadOnlyList<ReportTableRow> includedTransactions = IncomeTransactionRows(includedEntries, includeReason: false);
        IReadOnlyList<ReportTableRow> excludedTransactions = IncomeTransactionRows(excludedEntries, includeReason: true);
        IReadOnlyList<ReportTableRow> totals = analysis.CurrentMonthly.Select(month => new ReportTableRow(
        [
            month.Month.ToString(),
            FormatMoney(month.Income),
            FormatMoney(month.NetExpenses),
            FormatMoney(month.Surplus),
            FormatPercent(month.SavingsRatePercent)
        ],
        month.Surplus > 0m ? "positive" : month.Surplus < 0m ? "negative" : null)).ToArray();
        int excludedCount = analysis.CurrentLedger.Count(entry => !entry.Included);
        decimal excludedIncome = analysis.CurrentLedger
            .Where(entry => !entry.Included && entry.Transaction.Kind == TransactionKind.Income)
            .Sum(entry => entry.Transaction.Amount);
        decimal excludedSpending = analysis.CurrentLedger
            .Where(entry => !entry.Included && entry.Transaction.Kind == TransactionKind.Expense)
            .Sum(entry => -entry.Transaction.Amount);
        bool hasIncludedRows = analysis.CurrentLedger.Any(entry => entry.Included);
        string? emptyMessage = analysis.Period.HasMonths
            ? hasIncludedRows
                ? null
                : analysis.CurrentLedger.Count == 0
                    ? "No categorized income or expense transactions fall in this period."
                    : "All transactions in this period are excluded from this calculation."
            : "No categorized income or expense transactions are available.";
        var view = new IncomeSavingsPageView(
            summary,
            cashFlow,
            savingsRate,
            analysis.CurrentSummary.PositiveSurplusMonths,
            analysis.CurrentSummary.Months,
            excludedCount,
            excludedIncome,
            excludedSpending,
            detailMonths,
            detailMonth,
            detailMetrics,
            categories,
            includedTransactions,
            excludedTransactions,
            totals,
            adjustments.TargetRate,
            analysis.CurrentLedger.Count > 0,
            hasIncludedRows,
            emptyMessage);
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["income.summary"] = Metrics(summary.ToArray()),
            ["income.cash_flow"] = new DashboardWidgetReport([], cashFlow, [], [], emptyMessage),
            ["income.savings_rate"] = new DashboardWidgetReport([], savingsRate, [], [], emptyMessage),
            ["income.detail"] = Metrics(detailMetrics.ToArray()),
            ["income.included_categories"] = new DashboardWidgetReport(
                [], [], ["Type", "Category", "Amount"], categories,
                categories.Count == 0 ? "No included transactions for this month." : null),
            ["income.included_transactions"] = new DashboardWidgetReport(
                [], [], ["Date", "Transaction", "Group", "Category", "Amount"], includedTransactions,
                includedTransactions.Count == 0 ? "No included transactions for this month." : null),
            ["income.excluded_transactions"] = new DashboardWidgetReport(
                [], [], ["Date", "Transaction", "Group", "Category", "Amount", "Reason"], excludedTransactions,
                excludedTransactions.Count == 0 ? "No excluded transactions for this month." : null),
            ["income.monthly_totals"] = new DashboardWidgetReport(
                [], [], ["Month", "Income", "Spending", "Surplus", "Savings rate"], totals,
                totals.Count == 0 ? "No monthly totals are available." : null)
        };
        return new DashboardPageReport(DashboardPageId.IncomeSavings, widgets) { IncomeSavingsView = view };
    }

    private static IReadOnlyList<ReportMetric> IncomeSummaryMetrics(
        CashFlowSummary current,
        CashFlowSummary previous,
        bool hasPrevious,
        int months,
        decimal targetRate)
    {
        decimal currentIncome = Average(current.Income, current.Months);
        decimal currentSpending = Average(current.NetExpenses, current.Months);
        decimal currentSurplus = Average(current.Surplus, current.Months);
        decimal previousIncome = Average(previous.Income, previous.Months);
        decimal previousSpending = Average(previous.NetExpenses, previous.Months);
        decimal previousSurplus = Average(previous.Surplus, previous.Months);
        return
        [
            IncomeMetric("Avg monthly income", currentIncome, previousIncome, hasPrevious, months, false),
            IncomeMetric("Avg monthly spending", currentSpending, previousSpending, hasPrevious, months, true),
            IncomeMetric("Avg monthly surplus", currentSurplus, previousSurplus, hasPrevious, months, false),
            IncomeRateMetric(current.SavingsRatePercent, previous.SavingsRatePercent, hasPrevious, months, targetRate)
        ];
    }

    private static ReportMetric IncomeMetric(
        string label,
        decimal current,
        decimal previous,
        bool hasPrevious,
        int months,
        bool inverseTone)
    {
        decimal? change = hasPrevious ? current - previous : null;
        string? tone = change is null || change == 0m
            ? null
            : inverseTone
                ? change < 0m ? "positive" : "negative"
                : change > 0m ? "positive" : "negative";
        return new ReportMetric(
            label,
            current,
            FormatMoney(current),
            tone,
            change is null ? null : $"{FormatSignedMoney(change.Value)} vs previous {months} months",
            change);
    }

    private static ReportMetric IncomeRateMetric(
        decimal? current,
        decimal? previous,
        bool hasPrevious,
        int months,
        decimal targetRate)
    {
        decimal? change = hasPrevious && current is not null && previous is not null
            ? current.Value - previous.Value
            : null;
        string? tone = change is not null
            ? change > 0m ? "positive" : change < 0m ? "negative" : null
            : current >= targetRate ? "positive" : null;
        return new ReportMetric(
            "Savings rate",
            current,
            FormatPercent(current),
            tone,
            change is null ? null : $"{change.Value:+0.0;-0.0;0.0} pts vs previous {months} months",
            change);
    }

    private static IReadOnlyList<ReportTableRow> IncomeCategoryRows(IEnumerable<IncomeSavingsLedgerEntry> entries)
        => entries
            .GroupBy(entry => new
            {
                Type = entry.Transaction.Kind == TransactionKind.Income ? "Income" : "Expense",
                Category = string.IsNullOrWhiteSpace(entry.Transaction.Category) ? "Unknown" : entry.Transaction.Category
            })
            .OrderBy(group => group.Key.Type, StringComparer.Ordinal)
            .ThenByDescending(group => decimal.Abs(group.Sum(entry => entry.Transaction.Amount)))
            .ThenBy(group => group.Key.Category, StringComparer.Ordinal)
            .Select(group => new ReportTableRow(
            [
                group.Key.Type,
                group.Key.Category,
                FormatMoney(group.Key.Type == "Income"
                    ? group.Sum(entry => entry.Transaction.Amount)
                    : -group.Sum(entry => entry.Transaction.Amount))
            ]))
            .ToArray();

    private static IReadOnlyList<ReportTableRow> IncomeTransactionRows(
        IEnumerable<IncomeSavingsLedgerEntry> entries,
        bool includeReason)
        => entries
            .OrderByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .Select(entry => new ReportTableRow(includeReason
                ?
                [
                    FormatDate(entry.Transaction.Date),
                    entry.Transaction.Description,
                    IncomeGroup(entry.Transaction),
                    IncomeCategory(entry.Transaction),
                    FormatMoney(entry.Transaction.Amount),
                    entry.ExclusionReason
                ]
                :
                [
                    FormatDate(entry.Transaction.Date),
                    entry.Transaction.Description,
                    IncomeGroup(entry.Transaction),
                    IncomeCategory(entry.Transaction),
                    FormatMoney(entry.Transaction.Amount)
                ]))
            .ToArray();

    private static decimal Average(decimal value, int months)
        => months == 0 ? 0m : value / months;

    private static string IncomeGroup(FinancialTransaction transaction)
        => string.IsNullOrWhiteSpace(transaction.Group) ? "Unknown" : transaction.Group;

    private static string IncomeCategory(FinancialTransaction transaction)
        => string.IsNullOrWhiteSpace(transaction.Category) ? "Unknown" : transaction.Category;

    private static DashboardPageReport Spending(
        IReadOnlyList<FinancialTransaction> transactions,
        FinanceSettings settings,
        DashboardFilters filters,
        SpendingPresentationState presentation)
    {
        SpendingAnalysisResult analysis = SpendingAnalysisCalculator.Build(
            transactions.Where(transaction => transaction.Kind == TransactionKind.Expense),
            settings,
            filters.SpendingSet,
            filters.LookbackMonths,
            filters.SpendingComparison,
            filters.SpendingBreakdown,
            filters.SpendingAdjustments ?? SpendingAdjustments.Default(settings.Thresholds.Expense));
        SpendingOverviewEntry? selected = SelectedSpendingEntry(analysis.Overview, presentation, filters.SpendingBreakdown);
        (YearMonth? detailMonth, YearMonth? comparisonMonth) = SpendingDetailMonths(analysis.Period, presentation.DetailMonth);
        IReadOnlyList<SpendingLedgerEntry> selectedCurrent = SpendingDetailLedger(
            analysis.CurrentLedger,
            filters.SpendingBreakdown,
            selected?.Entity,
            detailMonth);
        IReadOnlyList<SpendingLedgerEntry> selectedComparison = SpendingDetailLedger(
            analysis.ComparisonLedger,
            filters.SpendingBreakdown,
            selected?.Entity,
            comparisonMonth);
        IReadOnlyList<SpendingOverviewEntry> ranked = analysis.Overview
            .Where(entry => entry.Spending > 0m)
            .Take(10)
            .ToArray();
        IReadOnlyList<SpendingOverviewEntry> trended = ranked.Take(5).ToArray();
        string comparisonLabel = filters.SpendingComparison == SpendingComparison.PreviousPeriod
            ? $"previous {filters.LookbackMonths} months"
            : "same months last year";
        DateOnly? latestExpenseDate = transactions
            .Where(transaction => transaction.Kind == TransactionKind.Expense)
            .Select(transaction => (DateOnly?)transaction.Date)
            .Max();
        decimal excludedSpending = analysis.CurrentLedger
            .Where(entry => !entry.Included)
            .Sum(entry => entry.NetSpending);
        IReadOnlyList<ReportMetric> summary =
        [
            new ReportMetric(
                "Total spending",
                analysis.Summary.TotalSpending,
                FormatMoney(analysis.Summary.TotalSpending),
                null),
            new ReportMetric(
                "Average monthly",
                analysis.Summary.AverageMonthlySpending,
                FormatMoney(analysis.Summary.AverageMonthlySpending),
                null),
            new ReportMetric(
                $"Change vs {comparisonLabel}",
                analysis.Summary.Change,
                FormatSignedMoney(analysis.Summary.Change),
                analysis.Summary.Change > 0m ? "negative" : analysis.Summary.Change < 0m ? "positive" : null,
                FormatPercent(analysis.Summary.ChangePercent),
                analysis.Summary.Change),
            new ReportMetric(
                "Excluded",
                analysis.CurrentLedger.Count(entry => !entry.Included),
                analysis.CurrentLedger.Count(entry => !entry.Included).ToString(CultureInfo.InvariantCulture),
                null,
                $"{FormatMoney(excludedSpending)} net spending"),
            new ReportMetric(
                "Included rows",
                analysis.CurrentLedger.Count(entry => entry.Included),
                analysis.CurrentLedger.Count(entry => entry.Included).ToString(CultureInfo.InvariantCulture))
        ];
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["spending.summary"] = new DashboardWidgetReport(
                summary,
                [],
                [],
                [],
                analysis.Period.HasMonths ? null : "No expense transactions are available.")
            {
                DateGuide = latestExpenseDate
            },
            ["spending.trend"] = Chart(trended.Select(entry => Series(
                Slug(entry.Entity),
                entry.Entity,
                analysis.Period.CurrentMonths.Select((month, index) => Point(month.Start, entry.MonthlyTrend[index])))).ToArray()),
            ["spending.ranking"] = Chart(Series(
                "ranking",
                "Spending",
                ranked.Select(entry => Point(entry.Entity, entry.Spending)))),
            // Keep the earlier generic dashboard report ids available for a smaller custom definition.
            ["spending.monthly"] = Chart(trended.Select(entry => Series(
                Slug(entry.Entity),
                entry.Entity,
                analysis.Period.CurrentMonths.Select((month, index) => Point(month.Start, entry.MonthlyTrend[index])))).ToArray()),
            ["spending.categories"] = Chart(Series(
                "categories",
                "Spending",
                analysis.Overview.Select(entry => Point(entry.Entity, entry.Spending)))),
            ["spending.overview"] = SpendingOverviewReport(
                analysis.Overview,
                analysis.Period.CurrentMonths,
                filters.SpendingBreakdown,
                comparisonLabel),
            ["spending.detail_summary"] = SpendingDetailSummary(
                selectedCurrent,
                selectedComparison,
                analysis.Summary.TotalSpending,
                detailMonth is null ? analysis.Period.CurrentMonths.Count : 1,
                comparisonLabel),
            ["spending.detail_history"] = selected is null
                ? Chart([])
                : Chart(Series(
                    "current",
                    "Current period",
                    SpendingAnalysisCalculator.EntityHistory(analysis, filters.SpendingBreakdown, selected.Entity)
                        .Select(row => Point(row.CurrentMonth.Start, row.Current))),
                    Series(
                        "comparison",
                        comparisonLabel,
                        SpendingAnalysisCalculator.EntityHistory(analysis, filters.SpendingBreakdown, selected.Entity)
                            .Select(row => Point(row.CurrentMonth.Start, row.Comparison)))),
            ["spending.detail_categories"] = SpendingDetailCategories(
                selectedCurrent,
                selectedComparison,
                filters.SpendingBreakdown,
                detailMonth is null ? analysis.Period.CurrentMonths.Count : 1,
                comparisonLabel),
            ["spending.detail_merchants"] = SpendingDetailMerchants(selectedCurrent, settings.MerchantAliases),
            ["spending.detail_transactions"] = SpendingDetailTransactions(selectedCurrent),
            ["spending.excluded"] = SpendingExcludedRows(analysis.CurrentLedger)
        };
        return new DashboardPageReport(DashboardPageId.Spending, widgets);
    }

    private static SpendingOverviewEntry? SelectedSpendingEntry(
        IReadOnlyList<SpendingOverviewEntry> overview,
        SpendingPresentationState presentation,
        SpendingBreakdown breakdown)
    {
        string? requested = presentation.SelectedEntity(breakdown);
        return overview.FirstOrDefault(entry => string.Equals(entry.Entity, requested, StringComparison.Ordinal))
            ?? overview.FirstOrDefault();
    }

    private static (YearMonth? DetailMonth, YearMonth? ComparisonMonth) SpendingDetailMonths(
        SpendingPeriod period,
        string configuredMonth)
    {
        if (!YearMonth.TryParse(configuredMonth, out YearMonth detailMonth))
            return (null, null);

        int index = -1;
        for (int candidate = 0; candidate < period.CurrentMonths.Count; candidate++)
        {
            if (period.CurrentMonths[candidate] == detailMonth)
            {
                index = candidate;
                break;
            }
        }
        return index < 0 ? (null, null) : (detailMonth, period.ComparisonMonths[index]);
    }

    private static IReadOnlyList<SpendingLedgerEntry> SpendingDetailLedger(
        IReadOnlyList<SpendingLedgerEntry> ledger,
        SpendingBreakdown breakdown,
        string? entity,
        YearMonth? month)
    {
        if (string.IsNullOrWhiteSpace(entity))
            return [];

        return ledger
            .Where(entry => entry.Included
                && (month is null || entry.Transaction.Month == month.Value)
                && string.Equals(
                    breakdown == SpendingBreakdown.Group
                        ? SpendingGroup(entry.Transaction)
                        : SpendingCategory(entry.Transaction),
                    entity,
                    StringComparison.Ordinal))
            .ToArray();
    }

    private static DashboardWidgetReport SpendingOverviewReport(
        IReadOnlyList<SpendingOverviewEntry> overview,
        IReadOnlyList<YearMonth> months,
        SpendingBreakdown breakdown,
        string comparisonLabel)
    {
        IReadOnlyList<string> columns = breakdown == SpendingBreakdown.Category
            ? ["Category", "Group", "Spending", "Share", "Average", comparisonLabel, "Change", "Change %", "Transactions", "Monthly trend"]
            : ["Group", "Spending", "Share", "Average", comparisonLabel, "Change", "Change %", "Transactions", "Monthly trend"];
        IReadOnlyList<ReportTableRow> rows = overview.Select(entry =>
        {
            var values = new List<string> { entry.Entity };
            if (breakdown == SpendingBreakdown.Category)
                values.Add(entry.Group);
            values.Add(FormatMoney(entry.Spending));
            values.Add(FormatPercent(entry.SharePercent));
            values.Add(FormatMoney(entry.AverageMonthlySpending));
            values.Add(FormatMoney(entry.ComparisonSpending));
            values.Add(FormatSignedMoney(entry.Change));
            values.Add(FormatPercent(entry.ChangePercent));
            values.Add(entry.TransactionCount.ToString(CultureInfo.InvariantCulture));
            values.Add(string.Empty);
            return new ReportTableRow(
                values,
                entry.Change > 0m ? "negative" : entry.Change < 0m ? "positive" : null);
        }).ToArray();
        return new DashboardWidgetReport(
            [],
            overview.Select((entry, index) => Series(
                $"overview-{index}",
                entry.Entity,
                months.Select((month, monthIndex) => Point(month.Start, entry.MonthlyTrend[monthIndex])))).ToArray(),
            columns,
            rows,
            rows.Count == 0 ? "No spending matches these controls." : null);
    }

    private static DashboardWidgetReport SpendingDetailSummary(
        IReadOnlyList<SpendingLedgerEntry> current,
        IReadOnlyList<SpendingLedgerEntry> comparison,
        decimal viewTotal,
        int monthCount,
        string comparisonLabel)
    {
        decimal spending = current.Sum(entry => entry.NetSpending);
        decimal compared = comparison.Sum(entry => entry.NetSpending);
        decimal change = spending - compared;
        decimal? changePercent = compared == 0m ? null : change / decimal.Abs(compared) * 100m;
        return Metrics(
            new ReportMetric("Spending", spending, FormatMoney(spending)),
            new ReportMetric("Average monthly", monthCount == 0 ? 0m : spending / monthCount, FormatMoney(monthCount == 0 ? 0m : spending / monthCount)),
            new ReportMetric("Share of view", viewTotal == 0m ? 0m : spending / viewTotal * 100m, FormatPercent(viewTotal == 0m ? 0m : spending / viewTotal * 100m)),
            new ReportMetric(
                $"Change vs {comparisonLabel}",
                change,
                FormatSignedMoney(change),
                change > 0m ? "negative" : change < 0m ? "positive" : null,
                FormatPercent(changePercent),
                change));
    }

    private static DashboardWidgetReport SpendingDetailCategories(
        IReadOnlyList<SpendingLedgerEntry> current,
        IReadOnlyList<SpendingLedgerEntry> comparison,
        SpendingBreakdown breakdown,
        int monthCount,
        string comparisonLabel)
    {
        if (breakdown != SpendingBreakdown.Group)
            return new DashboardWidgetReport([], [], ["Category", "Spending"], [], "Categories are part of the selected category.");

        Dictionary<string, (decimal Spending, int Count)> currentTotals = current
            .GroupBy(entry => SpendingCategory(entry.Transaction), StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => (group.Sum(entry => entry.NetSpending), group.Count()), StringComparer.Ordinal);
        Dictionary<string, decimal> comparisonTotals = comparison
            .GroupBy(entry => SpendingCategory(entry.Transaction), StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Sum(entry => entry.NetSpending), StringComparer.Ordinal);
        IReadOnlyList<ReportTableRow> rows = currentTotals.Keys
            .Union(comparisonTotals.Keys, StringComparer.Ordinal)
            .Select(category =>
            {
                (decimal Spending, int Count) currentValue = currentTotals.GetValueOrDefault(category);
                decimal spending = currentValue.Spending;
                decimal compare = comparisonTotals.GetValueOrDefault(category);
                decimal change = spending - compare;
                decimal total = currentTotals.Values.Sum(value => value.Spending);
                return new
                {
                    Category = category,
                    Spending = spending,
                    Share = total == 0m ? 0m : spending / total * 100m,
                    Average = monthCount == 0 ? 0m : spending / monthCount,
                    Compare = compare,
                    Change = change,
                    ChangePercent = compare == 0m ? (decimal?)null : change / decimal.Abs(compare) * 100m,
                    Count = currentValue.Count
                };
            })
            .OrderByDescending(row => row.Spending)
            .ThenBy(row => row.Category, StringComparer.Ordinal)
            .Select(row => new ReportTableRow(
                [
                    row.Category,
                    FormatMoney(row.Spending),
                    FormatPercent(row.Share),
                    FormatMoney(row.Average),
                    FormatMoney(row.Compare),
                    FormatSignedMoney(row.Change),
                    FormatPercent(row.ChangePercent),
                    row.Count.ToString(CultureInfo.InvariantCulture)
                ],
                row.Change > 0m ? "negative" : row.Change < 0m ? "positive" : null))
            .ToArray();
        return new DashboardWidgetReport(
            [],
            [],
            ["Category", "Spending", "Share", "Average", comparisonLabel, "Change", "Change %", "Transactions"],
            rows,
            rows.Count == 0 ? "No category detail matches this selection." : null);
    }

    private static DashboardWidgetReport SpendingDetailMerchants(
        IReadOnlyList<SpendingLedgerEntry> current,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases)
    {
        IReadOnlyList<ReportTableRow> rows = SpendingAnalysisCalculator.Merchants(current, aliases)
            .Select(item => new ReportTableRow(
                [
                    item.Merchant,
                    FormatMoney(item.Spending),
                    FormatPercent(item.SharePercent),
                    item.Transactions.ToString(CultureInfo.InvariantCulture),
                    FormatMoney(item.AverageTransaction),
                    FormatDate(item.LastTransaction)
                ]))
            .ToArray();
        return new DashboardWidgetReport(
            [],
            [],
            ["Merchant", "Spending", "Share", "Transactions", "Average", "Last transaction"],
            rows,
            rows.Count == 0 ? "No merchant detail matches this selection." : null);
    }

    private static DashboardWidgetReport SpendingDetailTransactions(IReadOnlyList<SpendingLedgerEntry> current)
    {
        IReadOnlyList<ReportTableRow> rows = current
            .OrderByDescending(entry => decimal.Abs(entry.NetSpending))
            .ThenByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .Select(entry => new ReportTableRow(
                [
                    FormatDate(entry.Transaction.Date),
                    entry.Transaction.Description,
                    SpendingCategory(entry.Transaction),
                    FormatMoney(entry.NetSpending)
                ],
                entry.NetSpending < 0m ? "positive" : null))
            .ToArray();
        return new DashboardWidgetReport(
            [],
            [],
            ["Date", "Transaction", "Category", "Spending"],
            rows,
            rows.Count == 0 ? "No transactions match this selection." : null);
    }

    private static DashboardWidgetReport SpendingExcludedRows(IReadOnlyList<SpendingLedgerEntry> ledger)
    {
        IReadOnlyList<ReportTableRow> rows = ledger
            .Where(entry => !entry.Included)
            .OrderByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .Select(entry => new ReportTableRow(
                [
                    FormatDate(entry.Transaction.Date),
                    entry.Transaction.Description,
                    SpendingGroup(entry.Transaction),
                    SpendingCategory(entry.Transaction),
                    FormatMoney(entry.NetSpending),
                    entry.ExclusionReason
                ]))
            .ToArray();
        return new DashboardWidgetReport(
            [],
            [],
            ["Date", "Transaction", "Group", "Category", "Spending", "Reason"],
            rows,
            rows.Count == 0 ? "No rows are excluded by this view." : null);
    }

    private static string SpendingGroup(FinancialTransaction transaction)
        => string.IsNullOrWhiteSpace(transaction.Group) ? "Unknown" : transaction.Group;

    private static string SpendingCategory(FinancialTransaction transaction)
        => string.IsNullOrWhiteSpace(transaction.Category) ? "Unknown" : transaction.Category;

    private static DashboardPageReport YearOverYear(
        IReadOnlyList<FinancialTransaction> transactions,
        FinanceSettings settings,
        DashboardFilters filters,
        YearOverYearPresentationState presentation)
    {
        IReadOnlyList<string> presetCategories = YearOverYearAnalysisCalculator.PresetCategories(
            transactions,
            settings,
            filters.YearOverYearSet);
        IReadOnlyList<string> categories = YearOverYearAnalysisCalculator.Entities(
            transactions,
            YearOverYearDimension.Category);
        IReadOnlyList<string> groups = YearOverYearAnalysisCalculator.Entities(
            transactions,
            YearOverYearDimension.Group);
        IReadOnlyList<YearOverYearComparisonView> comparisons = BuildYearOverYearComparisons(
            transactions,
            settings,
            filters.YearOverYearSet,
            presentation,
            presetCategories);
        string? emptyMessage = YearOverYearEmptyMessage(presentation, presetCategories, categories, groups, comparisons);
        string? latestCaption = transactions.Count == 0
            ? null
            : $"Latest data {transactions.Max(transaction => transaction.Date).ToString("MMM dd, yyyy", CultureInfo.InvariantCulture)} · includes {transactions.Max(transaction => transaction.Date).ToString("MMM yyyy", CultureInfo.InvariantCulture)} to date";
        var view = new YearOverYearPageView(
            latestCaption,
            presetCategories,
            categories,
            groups,
            comparisons,
            emptyMessage);
        YearOverYearComparisonView? first = comparisons.FirstOrDefault();
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["yoy.comparison"] = first is null
                ? Chart([])
                : new DashboardWidgetReport(first.Metrics, first.Series, [], [], emptyMessage),
            ["yoy.totals"] = first is null
                ? Chart([])
                : new DashboardWidgetReport([], [], first.TotalColumns, first.TotalRows, emptyMessage)
        };
        return new DashboardPageReport(DashboardPageId.YearOverYear, widgets) { YearOverYearView = view };
    }

    private static IReadOnlyList<YearOverYearComparisonView> BuildYearOverYearComparisons(
        IReadOnlyList<FinancialTransaction> transactions,
        FinanceSettings settings,
        string presetSetKey,
        YearOverYearPresentationState presentation,
        IReadOnlyList<string> presetCategories)
    {
        IEnumerable<(YearOverYearDimension Dimension, string Entity, string? SetKey)> requested = presentation.ViewMode switch
        {
            YearOverYearViewMode.Preset => presetCategories
                .Where(presentation.PresetCategories.Contains)
                .Select(category => (YearOverYearDimension.Category, category, (string?)presetSetKey)),
            YearOverYearViewMode.SingleCategory when !string.IsNullOrWhiteSpace(presentation.SingleCategory) =>
                [(YearOverYearDimension.Category, presentation.SingleCategory!, null)],
            YearOverYearViewMode.SingleGroup when !string.IsNullOrWhiteSpace(presentation.SingleGroup) =>
                [(YearOverYearDimension.Group, presentation.SingleGroup!, null)],
            _ => []
        };
        return requested
            .Select(request => YearOverYearAnalysisCalculator.Build(
                transactions,
                settings,
                request.SetKey,
                request.Dimension,
                request.Entity))
            .Where(comparison => comparison is not null)
            .Select(comparison => YearOverYearComparisonViewFor(comparison!))
            .ToArray();
    }

    private static YearOverYearComparisonView YearOverYearComparisonViewFor(YearOverYearComparison comparison)
    {
        YearOverYearSummary summary = comparison.Summary;
        IReadOnlyList<ReportMetric> metrics =
        [
            Metric(summary.CurrentYear.ToString(CultureInfo.InvariantCulture), summary.CurrentTotal),
            new ReportMetric(
                summary.PreviousYear?.ToString(CultureInfo.InvariantCulture) ?? "Previous year",
                summary.PreviousTotal,
                summary.PreviousTotal is null ? "Not available" : FormatMoney(summary.PreviousTotal.Value)),
            new ReportMetric(
                "Change",
                summary.Change,
                summary.Change is null ? "Not available" : FormatSignedMoney(summary.Change.Value),
                summary.Change is null ? null : summary.Change.Value < 0m ? "positive" : summary.Change.Value > 0m ? "negative" : null,
                summary.ChangePercent is null ? null : FormatSignedPercent(summary.ChangePercent.Value),
                summary.Change)
        ];
        IReadOnlyList<ReportSeries> series = comparison.History
            .GroupBy(point => point.Year)
            .OrderByDescending(group => group.Key)
            .Select(group => Series(
                group.Key.ToString(CultureInfo.InvariantCulture),
                group.Key.ToString(CultureInfo.InvariantCulture),
                group.Select(point => Point(new DateOnly(point.Year, point.Month, 1), point.Spending))))
            .ToArray();
        IReadOnlyList<ReportTableRow> totals = comparison.Totals
            .OrderByDescending(total => total.Year)
            .Select(total => new ReportTableRow(
            [
                total.Year.ToString(CultureInfo.InvariantCulture),
                FormatMoney(total.SpendingThroughMonth),
                total.Change is null ? "Not available" : FormatSignedMoney(total.Change.Value),
                total.ChangePercent is null ? "Not available" : FormatSignedPercent(total.ChangePercent.Value)
            ],
            total.Change is null ? null : total.Change.Value < 0m ? "positive" : total.Change.Value > 0m ? "negative" : null))
            .ToArray();
        IReadOnlyList<ReportTableRow> transactions = comparison.Transactions
            .Select(transaction => new ReportTableRow(
            [
                FormatDate(transaction.Date),
                transaction.Description,
                SpendingGroup(transaction),
                SpendingCategory(transaction),
                transaction.Account,
                FormatMoney(-transaction.Amount)
            ]))
            .ToArray();
        return new YearOverYearComparisonView(
            comparison.Entity,
            comparison.Summary.ThroughMonth is > 0 and <= 12
                ? new DateOnly(2000, comparison.Summary.ThroughMonth, 1).ToString("MMMM", CultureInfo.InvariantCulture)
                : string.Empty,
            metrics,
            series,
            ["Year", $"Spending through {new DateOnly(2000, comparison.Summary.ThroughMonth, 1).ToString("MMMM", CultureInfo.InvariantCulture)}", "Change from prior year", "Change %"],
            totals,
            ["Date", "Description", "Group", "Category", "Account", "Spending"],
            transactions);
    }

    private static string? YearOverYearEmptyMessage(
        YearOverYearPresentationState presentation,
        IReadOnlyList<string> presetCategories,
        IReadOnlyList<string> categories,
        IReadOnlyList<string> groups,
        IReadOnlyList<YearOverYearComparisonView> comparisons)
    {
        if (comparisons.Count > 0)
            return null;
        return presentation.ViewMode switch
        {
            YearOverYearViewMode.Preset when presetCategories.Count == 0 => "No expense transactions are available.",
            YearOverYearViewMode.Preset => "Choose at least one category to compare.",
            YearOverYearViewMode.SingleCategory when categories.Count == 0 => "No expense category data is available.",
            YearOverYearViewMode.SingleGroup when groups.Count == 0 => "No expense group data is available.",
            _ => "No spending history is available for this selection."
        };
    }

    private static DashboardPageReport Subscriptions(
        IReadOnlyList<FinancialTransaction> transactions,
        FinanceSettings settings,
        DashboardFilters filters,
        SubscriptionsPresentationState presentation,
        DateOnly reportDate)
    {
        IReadOnlyList<string> categories = filters.SubscriptionCategories ?? settings.Subscriptions.KnownCategories;
        IReadOnlyList<string> exclusions = filters.SubscriptionDiscoveryExclusions ?? settings.Subscriptions.DefaultExcludeCategories;
        int confidence = filters.SubscriptionMinimumConfidence is >= 70 and <= 100
            ? filters.SubscriptionMinimumConfidence
            : settings.Subscriptions.MinimumConfidence;
        SubscriptionAnalysisResult analysis = SubscriptionAnalysisCalculator.Build(
            transactions,
            settings.Subscriptions,
            settings.MerchantAliases,
            categories,
            exclusions,
            confidence);
        string? selectedMerchant = SelectedSubscriptionMerchant(analysis, presentation.SelectedMerchant);
        bool selectedCandidate = selectedMerchant is not null
            && analysis.Candidates.Any(entry => string.Equals(entry.Merchant, selectedMerchant, StringComparison.Ordinal));
        IReadOnlyList<SubscriptionChargeEntry> selectedCharges = selectedMerchant is null
            ? []
            : SubscriptionAnalysisCalculator.ChargesFor(analysis, selectedMerchant, selectedCandidate);
        int? ageDays = analysis.LatestDataDate is DateOnly latest
            ? Math.Max(0, reportDate.DayNumber - latest.DayNumber)
            : null;
        IReadOnlyList<ReportMetric> summaryMetrics =
        [
            Metric("Active subscriptions", analysis.Summary.ActiveCount, analysis.Summary.ActiveCount.ToString(CultureInfo.InvariantCulture)),
            Metric("Estimated monthly run rate", analysis.Summary.MonthlyRunRate),
            Metric("Spent in the last 12 months", analysis.Summary.TrailingTwelveMonthSpend),
            new ReportMetric(
                "12-month change",
                analysis.Summary.AnnualChangePercent,
                analysis.Summary.AnnualChangePercent is null ? "Not available" : FormatSignedPercent(analysis.Summary.AnnualChangePercent.Value),
                analysis.Summary.AnnualChangePercent is null ? null : analysis.Summary.AnnualChangePercent > 0m ? "negative" : "positive",
                analysis.Summary.AnnualChangePercent is null ? null : FormatSignedMoney(analysis.Summary.TrailingTwelveMonthSpend - analysis.Summary.PriorTwelveMonthSpend))
        ];
        IReadOnlyList<ReportSeries> spendHistory =
        [
            Series("actual", "Actual spend", analysis.History.Select(entry => Point(entry.Month.Start, entry.ActualSpend))),
            Series("average", "3-month average", analysis.History.Select(entry => Point(entry.Month.Start, entry.RollingAverage)))
        ];
        IReadOnlyList<ReportSeries> activeHistory =
        [
            Series("active", "Active merchants", analysis.History.Select(entry => Point(entry.Month.Start, entry.ActiveMerchants)))
        ];
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["subscriptions.summary"] = new DashboardWidgetReport(summaryMetrics, [], [], []),
            ["subscriptions.active"] = SubscriptionInventoryReport(
                analysis.Active,
                "No active subscriptions are present in the selected categories.",
                summaryMetrics,
                analysis.Lifecycles,
                analysis.LatestDataDate),
            ["subscriptions.lifecycle"] = new DashboardWidgetReport(
                [],
                [],
                [],
                [],
                analysis.Lifecycles.Count == 0 ? "No subscription lifecycles overlap this history range." : null)
            {
                TimelineRanges = analysis.Lifecycles.Select(entry => new ReportTimelineRange(
                    entry.Merchant,
                    entry.EpisodeStart,
                    entry.DisplayEnd,
                    FormatOptionalMoney(entry.MonthlyRunRate))).ToArray(),
                DateGuide = analysis.LatestDataDate
            },
            ["subscriptions.monthly"] = Chart(Series("subscriptions", "Subscription spending", analysis.History.Select(entry => Point(entry.Month.Start, entry.ActualSpend)))),
            ["subscriptions.history_spend"] = Chart(spendHistory),
            ["subscriptions.history_active"] = Chart(activeHistory),
            ["subscriptions.candidates"] = SubscriptionInventoryReport(
                analysis.Candidates,
                "No strong uncategorized subscription candidates were found."),
            ["subscriptions.inactive"] = SubscriptionInventoryReport(
                analysis.Inactive,
                "No inactive subscriptions are present in the selected categories."),
            ["subscriptions.detail_charge_history"] = Chart(
                Series(
                    "charges",
                    "Charge amount",
                    selectedCharges
                        .OrderBy(entry => entry.Transaction.Date)
                        .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
                        .Select(entry => Point(entry.Transaction.Date, entry.Amount)))),
            ["subscriptions.detail_charges"] = SubscriptionChargesReport(selectedCharges),
            ["subscriptions.detail_monthly_totals"] = SubscriptionMonthlyTotalsReport(selectedCharges)
        };
        string? caption = analysis.LatestDataDate is DateOnly date
            ? $"Transaction history through {date.ToString("MMMM d, yyyy", CultureInfo.InvariantCulture)}."
            : null;
        return new DashboardPageReport(DashboardPageId.Subscriptions, widgets)
        {
            SubscriptionsView = new SubscriptionsPageView(
                caption,
                ageDays,
                ageDays is int days && days > settings.Subscriptions.StaleAfterDays,
                analysis,
                selectedMerchant,
                selectedCandidate,
                selectedCharges,
                transactions.Count == 0 ? "No transactions are available. Refresh the spreadsheet data to build a subscription inventory." : null)
        };
    }

    private static DashboardPageReport Merchants(
        IReadOnlyList<FinancialTransaction> transactions,
        FinanceSettings settings,
        DashboardFilters filters,
        MerchantsPresentationState presentation)
    {
        string setKey = filters.MerchantSet ?? filters.SpendingSet;
        SpendingAdjustments adjustments = filters.MerchantAdjustments
            ?? SpendingAdjustments.Default(settings.Thresholds.Expense);
        MerchantAnalysisResult analysis = MerchantAnalysisCalculator.Build(
            transactions,
            settings,
            setKey,
            filters.EffectiveMerchantLookbackMonths,
            filters.MerchantComparison,
            adjustments);
        string? selectedMerchant = analysis.Overview.Any(entry => string.Equals(entry.Merchant, presentation.SelectedMerchant, StringComparison.Ordinal))
            ? presentation.SelectedMerchant
            : analysis.Overview.FirstOrDefault()?.Merchant;
        YearMonth? detailMonth = YearMonth.TryParse(presentation.DetailMonth, out YearMonth parsedMonth)
            ? parsedMonth
            : null;
        IReadOnlyList<MerchantHistoryEntry> selectedHistory = selectedMerchant is null
            ? []
            : MerchantAnalysisCalculator.History(analysis, selectedMerchant, settings.MerchantAliases);
        IReadOnlyList<MerchantDetailBreakdownEntry> selectedCategories = selectedMerchant is null
            ? []
            : MerchantAnalysisCalculator.Breakdown(analysis.CurrentLedger, selectedMerchant, "Category", settings.MerchantAliases);
        IReadOnlyList<MerchantDetailBreakdownEntry> selectedAccounts = selectedMerchant is null
            ? []
            : MerchantAnalysisCalculator.Breakdown(analysis.CurrentLedger, selectedMerchant, "Account", settings.MerchantAliases);
        IReadOnlyList<MerchantDescriptionEntry> selectedDescriptions = selectedMerchant is null
            ? []
            : MerchantAnalysisCalculator.Descriptions(analysis.CurrentLedger, selectedMerchant, settings.MerchantAliases);
        IReadOnlyList<SpendingLedgerEntry> selectedTransactions = selectedMerchant is null
            ? []
            : MerchantAnalysisCalculator.Transactions(analysis.CurrentLedger, selectedMerchant, detailMonth, settings.MerchantAliases);
        MerchantOverviewEntry? detail = analysis.Overview.FirstOrDefault(entry => string.Equals(entry.Merchant, selectedMerchant, StringComparison.Ordinal));
        IReadOnlyList<ReportMetric> summary =
        [
            Metric("Total spending", analysis.Summary.TotalSpending),
            Metric("Average monthly", analysis.Summary.AverageMonthlySpending),
            Metric("Merchants", analysis.Summary.MerchantCount, analysis.Summary.MerchantCount.ToString(CultureInfo.InvariantCulture)),
            Metric("At repeat merchants", analysis.Summary.RepeatSpendingSharePercent, FormatPercent(analysis.Summary.RepeatSpendingSharePercent))
        ];
        IReadOnlyList<ReportSeries> history = selectedMerchant is null
            ? []
            :
            [
                Series("current", "Current period", selectedHistory.Select(entry => Point(entry.CurrentMonth.Start, entry.CurrentSpending))),
                Series("comparison", "Comparison", selectedHistory.Select(entry => Point(entry.CurrentMonth.Start, entry.ComparisonSpending)))
            ];
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["merchants.summary"] = new DashboardWidgetReport(summary, [], [], []),
            ["merchants.ranking"] = Chart(Series("merchants", "Spending", analysis.Overview.Take(12).Select(entry => Point(entry.Merchant, entry.Spending)))),
            ["merchants.overview"] = MerchantOverviewReport(analysis.Overview),
            ["merchants.history"] = Chart(history),
            ["merchants.detail_summary"] = MerchantDetailSummary(detail, filters.MerchantComparison),
            ["merchants.detail_history"] = Chart(history),
            ["merchants.detail_categories"] = MerchantBreakdownReport("Category", selectedCategories),
            ["merchants.detail_accounts"] = MerchantBreakdownReport("Account", selectedAccounts),
            ["merchants.detail_descriptions"] = MerchantDescriptionsReport(selectedDescriptions),
            ["merchants.detail_transactions"] = MerchantTransactionsReport(selectedTransactions),
            ["merchants.excluded"] = MerchantExcludedReport(analysis.CurrentLedger)
        };
        DateOnly? latest = transactions.Where(transaction => transaction.Kind == TransactionKind.Expense).Select(transaction => (DateOnly?)transaction.Date).Max();
        return new DashboardPageReport(DashboardPageId.Merchants, widgets)
        {
            MerchantsView = new MerchantsPageView(
                latest is DateOnly date ? $"Spending through {date.ToString("MMMM d, yyyy", CultureInfo.InvariantCulture)}" : null,
                analysis,
                selectedMerchant,
                detailMonth?.ToString() ?? "all",
                selectedHistory,
                selectedCategories,
                selectedAccounts,
                selectedDescriptions,
                selectedTransactions,
                analysis.Overview.Count == 0 ? "No spending is included in this view. Adjust the filters to continue." : null)
        };
    }

    private static string? SelectedSubscriptionMerchant(SubscriptionAnalysisResult analysis, string? selected)
    {
        if (!string.IsNullOrWhiteSpace(selected)
            && analysis.Active.Concat(analysis.Candidates).Concat(analysis.Inactive)
                .Any(entry => string.Equals(entry.Merchant, selected, StringComparison.Ordinal)))
        {
            return selected;
        }

        return analysis.Active.FirstOrDefault()?.Merchant
            ?? analysis.Candidates.FirstOrDefault()?.Merchant
            ?? analysis.Inactive.FirstOrDefault()?.Merchant;
    }

    private static DashboardWidgetReport SubscriptionInventoryReport(
        IReadOnlyList<SubscriptionInventoryEntry> entries,
        string emptyMessage,
        IReadOnlyList<ReportMetric>? metrics = null,
        IReadOnlyList<SubscriptionLifecycleEntry>? lifecycles = null,
        DateOnly? dateGuide = null)
    {
        var report = new DashboardWidgetReport(
            metrics ?? [],
            [],
            ["Merchant", "Status", "Cadence", "Est. monthly", "Last charge"],
            entries.Select(entry => new ReportTableRow([
                entry.Merchant,
                entry.Source == "Detected" ? $"Detected ({entry.Confidence}%)" : entry.Status,
                entry.Cadence,
                FormatOptionalMoney(entry.MonthlyRunRate),
                FormatDate(entry.LastDate)
            ], string.Equals(entry.Status, "Active", StringComparison.Ordinal) ? "positive" : null)).ToArray(),
            entries.Count == 0 ? emptyMessage : null);
        if (lifecycles is null)
            return report;

        return report with
        {
            TimelineRanges = lifecycles.Select(entry => new ReportTimelineRange(
                entry.Merchant,
                entry.EpisodeStart,
                entry.DisplayEnd,
                FormatOptionalMoney(entry.MonthlyRunRate))).ToArray(),
            DateGuide = dateGuide
        };
    }

    private static DashboardWidgetReport SubscriptionChargesReport(IReadOnlyList<SubscriptionChargeEntry> charges)
        => new(
            [],
            [],
            ["Date", "Description", "Category", "Account", "Amount"],
            charges.Select(entry => new ReportTableRow([
                FormatDate(entry.Transaction.Date),
                entry.Transaction.Description,
                entry.Transaction.Category,
                entry.Transaction.Account,
                FormatMoney(entry.Amount)
            ])).ToArray(),
            charges.Count == 0 ? "No subscription charges are available for this merchant." : null);

    private static DashboardWidgetReport SubscriptionMonthlyTotalsReport(IReadOnlyList<SubscriptionChargeEntry> charges)
        => new(
            [],
            [],
            ["Month", "Actual spend"],
            charges
                .GroupBy(entry => entry.Transaction.Month)
                .OrderByDescending(group => group.Key)
                .Select(group => new ReportTableRow([
                    group.Key.Start.ToString("MMM yyyy", CultureInfo.InvariantCulture),
                    FormatMoney(group.Sum(entry => entry.Amount))
                ]))
                .ToArray(),
            charges.Count == 0 ? "No monthly totals are available." : null);

    private static DashboardWidgetReport MerchantOverviewReport(IReadOnlyList<MerchantOverviewEntry> entries)
        => new(
            [],
            [],
            ["Merchant", "Spending", "Share", "Average monthly", "Change", "Transactions", "Category"],
            entries.Select(entry => new ReportTableRow([
                entry.Merchant,
                FormatMoney(entry.Spending),
                FormatPercent(entry.SharePercent),
                FormatMoney(entry.AverageMonthlySpending),
                FormatSignedMoney(entry.Change),
                entry.TransactionCount.ToString(CultureInfo.InvariantCulture),
                entry.PrimaryCategory
            ], entry.Change > 0m ? "negative" : entry.Change < 0m ? "positive" : null)).ToArray(),
            entries.Count == 0 ? "No spending is included in this view. Adjust the filters to continue." : null);

    private static DashboardWidgetReport MerchantDetailSummary(MerchantOverviewEntry? entry, SpendingComparison comparison)
    {
        if (entry is null)
            return new DashboardWidgetReport([], [], [], [], "Select a merchant to inspect its detail.");

        string comparisonLabel = comparison == SpendingComparison.PreviousPeriod ? "previous period" : "last year";
        return new DashboardWidgetReport(
            [
                Metric("Spending", entry.Spending),
                new ReportMetric(
                    $"Change vs {comparisonLabel}",
                    entry.Change,
                    FormatSignedMoney(entry.Change),
                    entry.Change > 0m ? "negative" : entry.Change < 0m ? "positive" : null,
                    FormatPercent(entry.ChangePercent)),
                Metric("Transactions", entry.TransactionCount, entry.TransactionCount.ToString(CultureInfo.InvariantCulture)),
                Metric("Average purchase", entry.AverageTransaction)
            ],
            [],
            [],
            []);
    }

    private static DashboardWidgetReport MerchantBreakdownReport(string label, IReadOnlyList<MerchantDetailBreakdownEntry> entries)
        => new(
            [],
            [],
            [label, "Spending", "Share", "Transactions"],
            entries.Select(entry => new ReportTableRow([
                entry.Entity,
                FormatMoney(entry.Spending),
                FormatPercent(entry.SharePercent),
                entry.Transactions.ToString(CultureInfo.InvariantCulture)
            ])).ToArray(),
            entries.Count == 0 ? $"No {label.ToLowerInvariant()} detail is available." : null);

    private static DashboardWidgetReport MerchantDescriptionsReport(IReadOnlyList<MerchantDescriptionEntry> entries)
        => new(
            [],
            [],
            ["Description", "Spending", "Transactions", "Last transaction"],
            entries.Select(entry => new ReportTableRow([
                entry.Description,
                FormatMoney(entry.Spending),
                entry.Transactions.ToString(CultureInfo.InvariantCulture),
                FormatDate(entry.LastTransaction)
            ])).ToArray(),
            entries.Count == 0 ? "No descriptions are available." : null);

    private static DashboardWidgetReport MerchantTransactionsReport(IReadOnlyList<SpendingLedgerEntry> entries)
        => new(
            [],
            [],
            ["Date", "Description", "Category", "Group", "Account", "Spending"],
            entries.Select(entry => new ReportTableRow([
                FormatDate(entry.Transaction.Date),
                entry.Transaction.Description,
                entry.Transaction.Category,
                entry.Transaction.Group,
                entry.Transaction.Account,
                FormatMoney(entry.NetSpending)
            ])).ToArray(),
            entries.Count == 0 ? "No transactions are available for this merchant." : null);

    private static DashboardWidgetReport MerchantExcludedReport(IReadOnlyList<SpendingLedgerEntry> entries)
    {
        SpendingLedgerEntry[] excluded = entries.Where(entry => !entry.Included).ToArray();
        return new DashboardWidgetReport(
            [],
            [],
            ["Date", "Description", "Category", "Group", "Spending", "Reason"],
            excluded.Select(entry => new ReportTableRow([
                FormatDate(entry.Transaction.Date),
                entry.Transaction.Description,
                entry.Transaction.Category,
                entry.Transaction.Group,
                FormatMoney(entry.NetSpending),
                entry.ExclusionReason
            ], "negative")).ToArray(),
            excluded.Length == 0 ? "No current-period rows are excluded." : null);
    }

    private static DashboardWidgetReport TransactionsTableReport(IReadOnlyList<TransactionExplorerEntry> entries)
        => new(
            [],
            [],
            ["Date", "Description", "Merchant", "Type", "Group", "Category", "Account", "Amount", "Occurrences", "Flags"],
            entries.Select(entry => new ReportTableRow([
                FormatDate(entry.Transaction.Date),
                entry.Transaction.Description,
                entry.Merchant,
                TransactionKindLabel(entry.Transaction.Kind),
                entry.Transaction.Group,
                entry.Transaction.Category,
                entry.Transaction.Account,
                FormatSignedMoney(entry.Transaction.Amount),
                entry.Occurrences.ToString(CultureInfo.InvariantCulture),
                TransactionFlags(entry)
            ], entry.Transaction.Amount < 0m ? "negative" : entry.Transaction.Amount > 0m ? "positive" : null)).ToArray(),
            entries.Count == 0 ? "No transactions match this view." : null);

    private static string TransactionFlags(TransactionExplorerEntry entry)
    {
        var values = new List<string>();
        if (entry.IsOneOff)
            values.Add("One-off");
        if (entry.IsUnusual)
            values.Add("Unusual amount");
        if (entry.IsReversal)
            values.Add("Refund / reversal");
        return string.Join(", ", values);
    }

    private static string TransactionKindLabel(TransactionKind kind)
        => kind switch
        {
            TransactionKind.Income => "Income",
            TransactionKind.Expense => "Expense",
            TransactionKind.Transfer => "Transfer",
            _ => "Unknown"
        };

    private static DashboardPageReport BudgetPage(
        IReadOnlyList<BudgetEntry> budgets,
        IReadOnlyList<FinancialTransaction> transactions,
        BudgetRequest request,
        BudgetPresentationState presentation,
        DateOnly reportDate)
    {
        BudgetAnalysisResult analysis = BudgetAnalysisCalculator.Build(budgets, transactions, request);
        string? selectedGroup = analysis.Groups.Any(entry => string.Equals(
                entry.Entity,
                presentation.SelectedGroup,
                StringComparison.Ordinal))
            ? presentation.SelectedGroup
            : analysis.Groups.FirstOrDefault()?.Entity;
        BudgetGroupDetail? detail = selectedGroup is not null
            && analysis.GroupDetails.TryGetValue(selectedGroup, out BudgetGroupDetail? value)
            ? value
            : null;
        string category = detail is not null
            && (presentation.TransactionCategory == "all"
                || detail.Categories.Any(entry => string.Equals(
                    entry.Entity,
                    presentation.TransactionCategory,
                    StringComparison.Ordinal)))
            ? presentation.TransactionCategory
            : "all";
        IReadOnlyList<FinancialTransaction> visibleTransactions = detail is null
            ? []
            : detail.Transactions
                .Where(transaction => category == "all" || string.Equals(
                    transaction.Category,
                    category,
                    StringComparison.Ordinal))
                .ToArray();
        DashboardWidgetReport summary = new(
            BudgetSummaryMetrics(analysis),
            [],
            [],
            [],
            analysis.EmptyMessage);
        DashboardWidgetReport comparison = Chart(
            Series("budget", "Budget", analysis.Groups.Select(entry => Point(entry.Entity, entry.Budget))),
            Series("actual", "Spent", analysis.Groups.Select(entry => Point(entry.Entity, entry.Spent))));
        DashboardWidgetReport pace = Chart(
            Series("actual", "Actual cumulative", analysis.DailyPace.Select(entry => Point(entry.Date, entry.ActualCumulative))),
            Series("ideal", "Ideal pace", analysis.DailyPace.Select(entry => Point(entry.Date, entry.IdealCumulative))));
        DashboardWidgetReport performance = BudgetPerformanceTable(analysis.Groups, analysis.MonthProgress, "Group");
        DashboardWidgetReport groupSummary = detail is null
            ? new DashboardWidgetReport([], [], [], [], analysis.EmptyMessage ?? "Select a budget group to inspect it.")
            : Metrics(
                Metric("Spent", detail.Performance.Spent),
                Metric("Budget", detail.Performance.Budget),
                Metric("Typical month", detail.Performance.TypicalSpending),
                Metric("Outside the plan", detail.Performance.OutsidePlan));
        DashboardWidgetReport history = detail is null
            ? new DashboardWidgetReport([], [], [], [], "Select a budget group to see its history.")
            : Chart(
                Series("budget", "Budget", detail.History.Select(entry => Point(entry.Month.Start, entry.Budget))),
                Series("spent", "Spent", detail.History.Select(entry => Point(entry.Month.Start, entry.Spent))));
        DashboardWidgetReport categories = detail is null
            ? new DashboardWidgetReport([], [], [], [], "Select a budget group to see its category drivers.")
            : Chart(
                Series("budget", "Budget", detail.Categories.Select(entry => Point(entry.Entity, entry.Budget))),
                Series("spent", "Spent", detail.Categories.Select(entry => Point(entry.Entity, entry.Spent))));
        DashboardWidgetReport categoryTable = detail is null
            ? new DashboardWidgetReport([], [], [], [], "Select a budget group to see its category drivers.")
            : BudgetPerformanceTable(detail.Categories, analysis.MonthProgress, "Category");
        DashboardWidgetReport transactionTable = new(
            [],
            [],
            ["Date", "Category", "Description", "Account", "Net spending"],
            visibleTransactions.Select(transaction => new ReportTableRow([
                FormatDate(transaction.Date),
                transaction.Category,
                transaction.Description,
                transaction.Account,
                FormatMoney(-transaction.Amount)
            ])).ToArray(),
            detail is null ? "Select a budget group to inspect its transactions." : "No transactions match this category selection.");
        decimal ytdBudget = analysis.YearToDate.Sum(entry => entry.Budget);
        decimal ytdSpent = analysis.YearToDate.Sum(entry => entry.Spent);
        DashboardWidgetReport ytdSummary = Metrics(
            Metric("YTD spending", ytdSpent),
            Metric("YTD budget", ytdBudget),
            Metric("YTD remaining", ytdBudget - ytdSpent),
            new ReportMetric(
                "YTD used",
                ytdBudget > 0m ? ytdSpent / ytdBudget * 100m : null,
                FormatPercent(ytdBudget > 0m ? ytdSpent / ytdBudget * 100m : null),
                ytdSpent > ytdBudget && ytdBudget > 0m ? "negative" : null));
        DashboardWidgetReport ytdTable = BudgetPerformanceTable(analysis.YearToDate, 1m, "Group");
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["budget.summary"] = summary,
            ["budget.pace"] = pace,
            ["budget.comparison"] = comparison,
            ["budget.performance"] = performance,
            ["budget.group_summary"] = groupSummary,
            ["budget.history"] = history,
            ["budget.categories"] = categories,
            ["budget.category_table"] = categoryTable,
            ["budget.transactions"] = transactionTable,
            ["budget.ytd_summary"] = ytdSummary,
            ["budget.ytd_table"] = ytdTable,
            // Keep older direct report consumers working while the new page uses the source-shaped IDs.
            ["budget.table"] = performance
        };
        return new DashboardPageReport(DashboardPageId.Budget, widgets)
        {
            BudgetView = new BudgetPageView(
                transactions.Count == 0 ? null : $"Spending through {FormatDate(reportDate)}",
                analysis,
                selectedGroup,
                category,
                visibleTransactions,
                analysis.EmptyMessage)
        };
    }

    private static DashboardWidgetReport BudgetPerformanceTable(
        IReadOnlyList<BudgetPerformanceEntry> entries,
        decimal monthProgress,
        string entityLabel)
        => new(
            [],
            [],
            [entityLabel, "Status", "Budget", "Spent", "Remaining", "Used", "Vs typical", "Outside plan"],
            entries.Select(entry => new ReportTableRow([
                entry.Entity,
                BudgetStatus(entry, monthProgress),
                FormatMoney(entry.Budget),
                FormatMoney(entry.Spent),
                FormatMoney(entry.Remaining),
                FormatPercent(entry.PercentUsed),
                FormatSignedMoney(entry.VersusTypical),
                FormatMoney(entry.OutsidePlan)
            ], BudgetTone(entry, monthProgress))).ToArray(),
            entries.Count == 0 ? "No budget data is available for this selection." : null);

    private static IReadOnlyList<ReportMetric> BudgetSummaryMetrics(BudgetAnalysisResult analysis)
    {
        BudgetSummary summary = analysis.Summary;
        decimal paceDelta = summary.PercentUsed - analysis.MonthProgress * 100m;
        int within = analysis.Groups.Count(entry => entry.Budget > 0m && entry.Spent <= entry.Budget);
        int budgeted = analysis.Groups.Count(entry => entry.Budget > 0m);
        int outside = analysis.Groups.Count(entry => entry.OutsidePlan > 0m);
        return
        [
            new ReportMetric(
                "Spending",
                summary.Spent,
                FormatMoney(summary.Spent),
                summary.VersusTypical > 0m ? "negative" : null,
                summary.TypicalSpending > 0m ? $"{FormatSignedMoney(summary.VersusTypical)} vs typical" : null),
            new ReportMetric("Remaining", summary.Remaining, FormatMoney(summary.Remaining), summary.Remaining < 0m ? "negative" : null, $"{FormatMoney(summary.Budget)} budget"),
            new ReportMetric(
                "Budget used",
                summary.PercentUsed,
                FormatPercent(summary.PercentUsed),
                summary.PercentUsed > 100m ? "negative" : null,
                analysis.MonthProgress < 1m
                    ? $"{paceDelta:+0.0;-0.0;0.0} pts vs month elapsed"
                    : $"{within} of {budgeted} groups within budget"),
            new ReportMetric("Outside the plan", summary.OutsidePlan, FormatMoney(summary.OutsidePlan), summary.OutsidePlan > 0m ? "negative" : null, $"{outside} unbudgeted categories")
        ];
    }

    private static string BudgetStatus(BudgetPerformanceEntry entry, decimal monthProgress)
    {
        if (entry.Budget <= 0m && entry.Spent > 0m)
            return "Outside plan";
        if (entry.Budget > 0m && entry.Spent > entry.Budget)
            return "Over budget";
        if (entry.Budget > 0m && monthProgress < 1m && entry.PercentUsed > monthProgress * 100m + 10m)
            return "Ahead of pace";
        return "On pace";
    }

    private static string? BudgetTone(BudgetPerformanceEntry entry, decimal monthProgress)
        => BudgetStatus(entry, monthProgress) switch
        {
            "Over budget" or "Outside plan" => "negative",
            "Ahead of pace" => "warning",
            _ => null
        };

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
        FinanceSettings settings,
        DashboardFilters filters,
        TransactionsPresentationState presentation)
    {
        TransactionExplorerFilters request = filters.TransactionExplorer ?? TransactionExplorerFilters.Default;
        TransactionExplorerAnalysisResult analysis = TransactionExplorerAnalysisCalculator.Build(
            transactions,
            settings.MerchantAliases,
            request);
        IReadOnlyList<ReportMetric> summary =
        [
            Metric("Transactions", analysis.Summary.TransactionCount, analysis.Summary.TransactionCount.ToString(CultureInfo.InvariantCulture)),
            Metric("Money out", analysis.Summary.Outflow),
            Metric("Money in", analysis.Summary.Inflow),
            new ReportMetric(
                "Net amount",
                analysis.Summary.NetAmount,
                FormatSignedMoney(analysis.Summary.NetAmount),
                analysis.Summary.NetAmount > 0m ? "positive" : analysis.Summary.NetAmount < 0m ? "negative" : null)
        ];
        IReadOnlyList<ReportSeries> history = analysis.Results
            .GroupBy(entry => entry.Transaction.Kind)
            .OrderBy(group => group.Key)
            .Select(group => Series(
                group.Key.ToString().ToLowerInvariant(),
                TransactionKindLabel(group.Key),
                group.Select(entry => Point(entry.Transaction.Date, entry.Transaction.Amount, entry.Transaction.Description))))
            .ToArray();
        IReadOnlyList<ReportSeries> breakdown =
        [
            Series("magnitude", "Total magnitude", analysis.Breakdown.Take(12).Select(entry => Point(entry.Entity, entry.Magnitude)))
        ];
        DashboardWidgetReport table = TransactionsTableReport(analysis.Results);
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["transactions.summary"] = new DashboardWidgetReport(summary, [], [], []),
            ["transactions.history"] = Chart(history),
            ["transactions.breakdown"] = Chart(breakdown),
            ["transactions.table"] = table,
            ["top.expenses"] = Chart(history.Where(series => string.Equals(series.Id, "expense", StringComparison.Ordinal)).ToArray()),
            ["top.incomes"] = Chart(history.Where(series => string.Equals(series.Id, "income", StringComparison.Ordinal)).ToArray()),
            ["top.table"] = table
        };
        return new DashboardPageReport(DashboardPageId.TopTransactions, widgets)
        {
            TransactionsView = new TransactionsPageView(
                analysis.EndDate is DateOnly date ? $"Latest transaction {date.ToString("MMM d, yyyy", CultureInfo.InvariantCulture)}" : null,
                analysis,
                analysis.Results.Count == 0 ? "No transactions match this view." : null)
        };
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

    private static DashboardPageReport FinancialIndependencePage(
        IReadOnlyList<FinancialTransaction> transactions,
        IReadOnlyList<AccountBalance> accounts,
        FinanceSettings settings,
        FinancialIndependenceSourceFilters sourceFilters,
        FinancialIndependenceScenario? selectedScenario,
        DateOnly reportDate)
    {
        FinancialIndependenceSourceAnalysis source = FinancialIndependenceSourceAnalysisCalculator.Build(
            accounts,
            transactions,
            sourceFilters);
        FinancialIndependenceScenario scenario = selectedScenario
            ?? FinancialIndependenceSourceAnalysisCalculator.DefaultScenario(source, settings.FinancialIndependence);
        scenario.Validate();
        FinancialIndependenceSummary summary = FinancialIndependenceCalculator.Summarize(
            scenario.Assets,
            scenario.AnnualSpending,
            scenario.ExpectedReturnRate,
            scenario.AnnualIncome,
            scenario.WithdrawalRate);
        IReadOnlyList<PortfolioProjectionPoint> projection = FinancialIndependenceCalculator.Project(
            scenario.Assets,
            scenario.AnnualSpending,
            scenario.ExpectedReturnRate,
            scenario.ProjectionYears,
            scenario.AnnualIncome);
        decimal[] spendingChanges = [-20m, -10m, 0m, 10m, 20m];
        decimal[] returns = [0m, 3m, 5m, scenario.ExpectedReturnRate, 9m];
        IReadOnlyList<RunwaySensitivityCell> sensitivity = FinancialIndependenceCalculator.BuildSensitivity(
            scenario.Assets,
            scenario.AnnualSpending,
            scenario.AnnualIncome,
            spendingChanges,
            returns.Distinct().Order().ToArray());
        string runway = summary.RunwayYears is null ? "Sustainable" : $"{summary.RunwayYears:0.0} years";
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["fi.summary"] = Metrics(
                new ReportMetric("Runway", summary.RunwayYears, runway, summary.RunwayYears is null ? "positive" : null, summary.RunwayYears is null ? "Portfolio does not deplete" : "Until portfolio reaches $0"),
                new ReportMetric("Annual gap", summary.AnnualSurplus, FormatSignedMoney(summary.AnnualSurplus), summary.AnnualSurplus >= 0m ? "positive" : "negative", summary.AnnualSurplus >= 0m ? "Annual surplus" : "Annual shortfall"),
                new ReportMetric("Net portfolio spending", summary.NetAnnualSpending, FormatMoney(summary.NetAnnualSpending), null, $"{FormatMoney(summary.SustainableSpending)} supported at withdrawal rate"),
                new ReportMetric("FI target", summary.FinancialIndependenceTarget, FormatMoney(summary.FinancialIndependenceTarget), summary.FundingGap >= 0m ? "positive" : "negative", summary.FundingGap >= 0m ? $"{FormatMoney(summary.FundingGap)} above target" : $"{FormatMoney(-summary.FundingGap)} still needed")),
            ["fi.projection"] = Chart(Series("portfolio", "Projected portfolio", projection.Select(point => Point(new DateOnly(reportDate.Year + point.Year, 1, 1), point.Balance)))),
            ["fi.funding"] = Chart(
                Series("investment-return", "Investment return", [Point("Annual funding", summary.AnnualReturn)]),
                Series("earned-income", "Earned income", [Point("Annual funding", summary.AnnualIncome)]),
                Series("spending", "Spending", [Point("Annual funding", -summary.AnnualSpending)])),
            ["fi.sensitivity"] = SensitivityReport(sensitivity, scenario.AnnualSpending),
            ["fi.source_accounts"] = new DashboardWidgetReport(
                [],
                [],
                ["Group", "Account", "Balance"],
                source.Accounts.Select(account => new ReportTableRow([account.Group, account.Account, FormatMoney(account.SignedBalance)])).ToArray(),
                source.Accounts.Count == 0 ? "No portfolio accounts are selected." : null),
            ["fi.source_spending"] = Chart(Series("spending", "Spending", source.MonthlySpending.Select(entry => Point(entry.Month.Start, entry.Spending)))),
            ["fi.source_transactions"] = new DashboardWidgetReport(
                [],
                [],
                ["Date", "Description", "Group", "Category", "Account", "Spending"],
                source.Expenses.Select(transaction => new ReportTableRow([
                    FormatDate(transaction.Date),
                    transaction.Description,
                    transaction.Group,
                    transaction.Category,
                    transaction.Account,
                    FormatMoney(-transaction.Amount)
                ])).ToArray(),
                source.Expenses.Count == 0 ? "No expense rows are included in this source range." : null)
        };
        return new DashboardPageReport(DashboardPageId.FinancialIndependence, widgets)
        {
            FinancialIndependenceView = new FinancialIndependencePageView(
                transactions.Count == 0 ? null : $"Transactions through {FormatDate(reportDate)}",
                source,
                scenario,
                summary,
                projection,
                sensitivity,
                transactions.Count == 0 && accounts.Count == 0 ? "Transaction and balance history are required for this analysis." : null)
        };
    }

    private static DashboardWidgetReport SensitivityReport(
        IReadOnlyList<RunwaySensitivityCell> sensitivity,
        decimal baselineSpending)
        => new(
            [],
            sensitivity
                .GroupBy(cell => cell.ReturnRate)
                .OrderBy(group => group.Key)
                .Select(group => Series(
                    $"return-{group.Key:0.##}",
                    $"{group.Key:0.##}% return",
                    group.Select(cell => Point(SpendingChangeLabel(cell.AnnualSpending, baselineSpending), cell.RunwayYears ?? 100m))))
                .ToArray(),
            ["Spending change", "Return", "Runway"],
            sensitivity.Select(cell => new ReportTableRow([
                SpendingChangeLabel(cell.AnnualSpending, baselineSpending),
                $"{cell.ReturnRate:0.##}%",
                cell.RunwayYears is null ? "Sustainable" : $"{cell.RunwayYears:0.0} years"
            ])).ToArray(),
            "A sustainable scenario is shown without a finite runway.")
        {
            HeatmapCells = sensitivity
                .Select(cell => new ReportHeatmapCell(
                    SpendingChangeLabel(cell.AnnualSpending, baselineSpending),
                    $"{cell.ReturnRate:0.##}% return",
                    cell.RunwayYears ?? 100m,
                    cell.RunwayYears is null ? "Sustainable" : $"{cell.RunwayYears:0.0} years"))
                .ToArray()
        };

    private static string SpendingChangeLabel(decimal spending, decimal baseline)
    {
        if (baseline == 0m)
            return "Baseline";
        decimal change = (spending / baseline - 1m) * 100m;
        return change == 0m ? "Baseline" : $"{change:+0;-0;0}%";
    }

    private static DashboardPageReport DataHealthPage(
        PortfolioSnapshot snapshot,
        DataHealthCheckOptions options,
        string selectedCheckId,
        DateOnly asOfDate)
    {
        DataHealthAnalysisResult analysis = DataHealthAnalysisCalculator.Build(
            snapshot.Transactions,
            snapshot.Balances,
            options,
            asOfDate);
        DataHealthCheckResult selected = analysis.Checks.FirstOrDefault(check => string.Equals(
                check.Id,
                selectedCheckId,
                StringComparison.Ordinal))
            ?? analysis.Checks[0];
        int transactionCount = snapshot.Transactions.Count(transaction => options.IncludeInactive || !transaction.IsHidden);
        DashboardWidgetReport queue = new(
            [],
            [],
            ["Status", "Check", "Findings", "Financial scope", "Next step"],
            analysis.Checks.Select(check => new ReportTableRow([
                check.Status,
                check.Name,
                check.FindingCount.ToString(CultureInfo.InvariantCulture),
                check.FindingCount == 0 ? "—" : FormatMoney(check.FinancialScope),
                check.Action
            ], HealthTone(check.Status))).ToArray());
        DashboardWidgetReport detail = DataHealthDetailReport(selected);
        string? emptyMessage = snapshot.Transactions.Count == 0 && snapshot.Balances.Count == 0
            ? "No transaction or balance data is available."
            : null;
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["health.summary"] = Metrics(
                new ReportMetric(
                    "Needs attention",
                    analysis.NeedsAttention,
                    analysis.NeedsAttention.ToString(CultureInfo.InvariantCulture),
                    analysis.NeedsAttention == 0 ? "positive" : "negative"),
                new ReportMetric(
                    "Review items",
                    analysis.ReviewItems,
                    analysis.ReviewItems.ToString(CultureInfo.InvariantCulture),
                    analysis.ReviewItems == 0 ? "positive" : "warning"),
                new ReportMetric(
                    "Transactions through",
                    analysis.LatestTransactionDate?.DayNumber,
                    FormatDateOrNoData(analysis.LatestTransactionDate),
                    null,
                    $"{transactionCount.ToString(CultureInfo.InvariantCulture)} rows"),
                new ReportMetric(
                    "Balances through",
                    analysis.LatestBalanceDate?.DayNumber,
                    FormatDateOrNoData(analysis.LatestBalanceDate),
                    null,
                    $"{analysis.AccountCount.ToString(CultureInfo.InvariantCulture)} accounts")),
            ["health.queue"] = queue,
            ["health.detail"] = detail,
            ["health.findings"] = queue
        };
        return new DashboardPageReport(DashboardPageId.DataHealth, widgets)
        {
            DataHealthView = new DataHealthPageView(
                "Review source freshness, mapping gaps, and suspicious records.",
                analysis,
                selected.Id,
                selected,
                emptyMessage)
        };
    }

    private static DashboardWidgetReport DataHealthDetailReport(DataHealthCheckResult check)
    {
        if (check.Id == "duplicates")
        {
            return new DashboardWidgetReport(
                [],
                [],
                ["Date 1", "Date 2", "Days apart", "Amount", "Account 1", "Account 2", "Description 1", "Description 2"],
                check.DuplicatePairs.Select(pair => new ReportTableRow([
                    FormatDate(pair.First.Date),
                    FormatDate(pair.Second.Date),
                    pair.DaysApart.ToString(CultureInfo.InvariantCulture),
                    FormatMoney(decimal.Abs(pair.First.Amount)),
                    pair.First.Account,
                    pair.Second.Account,
                    pair.First.Description,
                    pair.Second.Description
                ], "warning")).ToArray(),
                check.FindingCount == 0 ? "No findings for this check." : null);
        }

        if (check.Id is "account_mapping" or "stale_accounts")
        {
            string finalColumn = check.Id == "stale_accounts" ? "Days stale" : "Missing fields";
            return new DashboardWidgetReport(
                [],
                [],
                ["Latest date", "Account", "Group", "Balance", finalColumn],
                check.Records.Select(record => new ReportTableRow([
                    FormatDateOrNoData(record.Date),
                    record.Account,
                    record.Group,
                    record.Amount is null ? "—" : FormatMoney(record.Amount.Value),
                    record.Details
                ], HealthTone(check.Status))).ToArray(),
                check.FindingCount == 0 ? "No findings for this check." : null);
        }

        string detailsColumn = check.Id switch
        {
            "incomplete" => "Missing fields",
            "reversals" => "Review reason",
            _ => "Details"
        };
        return new DashboardWidgetReport(
            [],
            [],
            ["Date", "Description", "Account", "Category", "Group", "Amount", detailsColumn],
            check.Records.Select(record => new ReportTableRow([
                FormatDateOrNoData(record.Date),
                record.Description,
                record.Account,
                record.Category,
                record.Group,
                record.Amount is null ? "—" : FormatMoney(record.Amount.Value),
                record.Details
            ], HealthTone(check.Status))).ToArray(),
            check.FindingCount == 0 ? "No findings for this check." : null);
    }

    private static string HealthTone(string status)
        => status switch
        {
            "Needs attention" => "negative",
            "Review" => "warning",
            _ => "positive"
        };

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

    private static IReadOnlyList<NetWorthPoint> BuildHomeHistory(
        IReadOnlyList<BalanceObservation> observations,
        HomeReportRange? range)
    {
        if (range is null)
            return [];

        var dates = new SortedSet<DateOnly>
        {
            range.Start,
            range.End
        };
        int daysUntilSunday = ((int)DayOfWeek.Sunday - (int)range.Start.DayOfWeek + 7) % 7;
        for (DateOnly date = range.Start.AddDays(daysUntilSunday); date <= range.End; date = date.AddDays(7))
            dates.Add(date);

        return dates.Select(date => NetWorthAt(observations, date)).ToArray();
    }

    private static NetWorthPoint NetWorthAt(
        IReadOnlyList<BalanceObservation> observations,
        DateOnly date)
    {
        IReadOnlyList<AccountBalance> accounts = PortfolioCalculator.LatestBalances(observations, date);
        decimal assets = accounts
            .Where(account => account.AccountClass == AccountClass.Asset)
            .Sum(account => account.SignedBalance);
        decimal liabilities = accounts
            .Where(account => account.AccountClass == AccountClass.Liability)
            .Sum(account => account.SignedBalance);
        return new NetWorthPoint(date, assets, liabilities, assets + liabilities);
    }

    private static IReadOnlyList<ReportMetric> HomeNetWorthMetrics(
        NetWorthPoint? opening,
        NetWorthPoint? current,
        HomeReportRange? range)
    {
        if (opening is null || current is null || range is null)
            return [];

        string period = HomePeriodLabel(range);
        return
        [
            ChangeMetric("Net worth", current.NetWorth, opening.NetWorth, period),
            ChangeMetric("Assets", current.Assets, opening.Assets, period),
            LiabilityMetric(current.Liabilities, opening.Liabilities, period)
        ];
    }

    private static IReadOnlyList<ReportMetric> BuildHomeAccountGroups(
        IReadOnlyList<AccountBalance> accounts,
        IReadOnlyList<AccountBalance> openingAccounts,
        HomeReportRange? range)
    {
        if (range is null)
            return [];

        var opening = openingAccounts.ToDictionary(
            account => AccountKey(account),
            account => account,
            StringComparer.Ordinal);
        string period = HomePeriodLabel(range);
        return accounts
            .Where(account => !string.IsNullOrWhiteSpace(account.Group))
            .GroupBy(account => account.Group, StringComparer.Ordinal)
            .OrderByDescending(group => decimal.Abs(group.Sum(account => account.SignedBalance)))
            .ThenBy(group => group.Key, StringComparer.Ordinal)
            .Select(group =>
            {
                AccountBalance[] current = group.ToArray();
                decimal currentBalance = current.Sum(account => account.SignedBalance);
                decimal openingBalance = current
                    .Where(account => opening.TryGetValue(AccountKey(account), out _))
                    .Sum(account => opening[AccountKey(account)].SignedBalance);
                bool liabilityOnly = current.All(account => account.AccountClass == AccountClass.Liability);
                decimal displayBalance = liabilityOnly ? decimal.Abs(currentBalance) : currentBalance;
                decimal displayChange = liabilityOnly
                    ? -(currentBalance - openingBalance)
                    : currentBalance - openingBalance;
                decimal netWorthContribution = currentBalance - openingBalance;
                string? tone = displayChange == 0m
                    ? null
                    : liabilityOnly
                        ? displayChange < 0m ? "positive" : "negative"
                        : displayChange > 0m ? "positive" : "negative";
                return new ReportMetric(
                    group.Key,
                    displayBalance,
                    FormatMoney(displayBalance),
                    tone,
                    $"{FormatSignedMoney(displayChange)} {period}",
                    netWorthContribution);
            })
            .ToArray();
    }

    private static IReadOnlyList<ReportTableRow> BuildHomeAccountInventory(
        IReadOnlyList<AccountBalance> accounts,
        IReadOnlyList<AccountBalance> openingAccounts,
        HomeReportRange? range)
    {
        if (range is null)
            return [];

        var opening = openingAccounts.ToDictionary(
            account => AccountKey(account),
            account => account,
            StringComparer.Ordinal);
        AccountBalance[] groupedAccounts = accounts
            .Where(account => !string.IsNullOrWhiteSpace(account.Group))
            .ToArray();
        var liabilityGroups = groupedAccounts
            .GroupBy(account => account.Group, StringComparer.Ordinal)
            .Where(group => group.All(account => account.AccountClass == AccountClass.Liability))
            .Select(group => group.Key)
            .ToHashSet(StringComparer.Ordinal);
        return groupedAccounts
            .OrderBy(account => account.Group, StringComparer.Ordinal)
            .ThenByDescending(account => decimal.Abs(account.SignedBalance))
            .ThenBy(account => account.Account, StringComparer.Ordinal)
            .ThenBy(account => account.AccountId, StringComparer.Ordinal)
            .Select(account =>
            {
                decimal openingBalance = opening.TryGetValue(AccountKey(account), out AccountBalance? value)
                    ? value.SignedBalance
                    : 0m;
                bool liability = liabilityGroups.Contains(account.Group);
                decimal displayBalance = liability ? decimal.Abs(account.SignedBalance) : account.SignedBalance;
                decimal displayChange = liability
                    ? -(account.SignedBalance - openingBalance)
                    : account.SignedBalance - openingBalance;
                string? tone = displayChange == 0m
                    ? null
                    : liability
                        ? displayChange < 0m ? "positive" : "negative"
                        : displayChange > 0m ? "positive" : "negative";
                return new ReportTableRow(
                    [
                        account.Group,
                        account.Account,
                        FormatMoney(displayBalance),
                        FormatSignedMoney(displayChange)
                    ],
                    tone);
            })
            .ToArray();
    }

    private static ReportMetric ChangeMetric(
        string label,
        decimal current,
        decimal opening,
        string period)
    {
        decimal change = current - opening;
        return new ReportMetric(
            label,
            current,
            FormatMoney(current),
            change > 0m ? "positive" : change < 0m ? "negative" : null,
            $"{FormatSignedMoney(change)} {period}",
            change);
    }

    private static ReportMetric LiabilityMetric(decimal current, decimal opening, string period)
    {
        decimal magnitude = decimal.Abs(current);
        decimal change = magnitude - decimal.Abs(opening);
        return new ReportMetric(
            "Liabilities",
            magnitude,
            FormatMoney(magnitude),
            change < 0m ? "positive" : change > 0m ? "negative" : null,
            $"{FormatSignedMoney(change)} {period}",
            change);
    }

    private static string HomePeriodLabel(HomeReportRange range)
        // Home.py keeps the configured label when weekly sampling moves the first point by at most one week.
        => range.TimeFrame == HomeTimeFrame.All || range.Start > range.RequestedStart.AddDays(7)
            ? $"since {range.Start:MMM yyyy}"
            : $"over {HomeReportRange.Label(range.TimeFrame)}";

    private static string AccountKey(AccountBalance account)
        => account.AccountId;

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

    private static DashboardWidgetReport Metrics(params ReportMetric[] metrics)
        => new(metrics, [], [], []);

    private static DashboardWidgetReport Chart(params ReportSeries[] series)
        => Chart((IReadOnlyList<ReportSeries>)series);

    private static DashboardWidgetReport Chart(IReadOnlyList<ReportSeries> series)
        => new([], series, [], [], series.Count == 0 ? "No data is available for this selection." : null);

    private static DashboardWidgetReport EmptyHomeReport()
        => new([], [], [], [], "No visible account balances are available.");

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

    private static string FormatOptionalMoney(decimal? value)
        => value is null ? "Pending" : FormatMoney(value.Value);

    private static string FormatSignedMoney(decimal value)
        => value == 0m
            ? FormatMoney(value)
            : $"{(value > 0m ? "+" : "-")}{FormatMoney(decimal.Abs(value))}";

    private static string FormatPercent(decimal? value)
        => value is null ? "—" : $"{value:0.0}%";

    private static string FormatSignedPercent(decimal value)
        => $"{value:+0.0;-0.0;0.0}%";

    private static string FormatCoverage(decimal? months, int targetMonths)
        => months is null ? "No expense baseline" : $"{months:0.0} / {targetMonths} months";

    private static string FormatDate(DateOnly value)
        => value.ToString("MMM d, yyyy", CultureInfo.GetCultureInfo("en-US"));

    private static string FormatDateOrNoData(DateOnly? value)
        => value is null ? "No data" : FormatDate(value.Value);

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

}
