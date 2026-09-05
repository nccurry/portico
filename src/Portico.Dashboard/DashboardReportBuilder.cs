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
        "home.net_worth", "home.overview", "home.attribution", "home.accounts", "home.inventory", "home.safety",
        "income.summary", "income.cash_flow", "income.savings_rate", "income.detail", "income.included_categories",
        "income.included_transactions", "income.excluded_transactions", "income.monthly_totals",
        "spending.monthly", "spending.categories",
        "spending.summary", "spending.trend", "spending.ranking", "spending.overview", "spending.detail_summary", "spending.detail_history",
        "spending.detail_categories", "spending.detail_merchants", "spending.detail_transactions", "spending.excluded",
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
