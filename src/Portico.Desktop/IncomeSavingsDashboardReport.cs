using System.Globalization;
using Portico.Application;
using Portico.Finance;
using static Portico.Desktop.DashboardReportText;

namespace Portico.Desktop;

public sealed partial record DashboardPageReport
{
    /// <summary>Sections shown by the Income and savings renderer.</summary>
    public IncomeSavingsPageView? IncomeSavingsView { get; init; }
}

/// <summary>Data regions shown by the Income and savings page.</summary>
public sealed record IncomeSavingsPageView(
    IReadOnlyList<ReportMetric> SummaryMetrics,
    IReadOnlyList<ReportSeries> CashFlowSeries,
    IReadOnlyList<ReportSeries> SavingsRateSeries,
    int PositiveSurplusMonths,
    int MonthCount,
    int ExcludedCount,
    decimal ExcludedIncome,
    decimal ExcludedSpending,
    IReadOnlyList<string> DetailMonths,
    string DetailMonth,
    IReadOnlyList<ReportMetric> DetailMetrics,
    IReadOnlyList<ReportTableRow> IncludedCategories,
    IReadOnlyList<ReportTableRow> IncludedTransactions,
    IReadOnlyList<ReportTableRow> ExcludedTransactions,
    IReadOnlyList<ReportTableRow> MonthlyTotals,
    decimal TargetRate,
    bool HasLedgerRows,
    bool HasIncludedRows,
    string? EmptyMessage = null);

/// <summary>Turns one semantic Income report into existing desktop widgets.</summary>
public static class IncomeSavingsDashboardReport
{
    public static DashboardPageReport Build(IncomeReport report, int lookbackMonths)
    {
        ArgumentNullException.ThrowIfNull(report);
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(lookbackMonths);
        IncomeSavingsAnalysisResult analysis = report.Analysis;
        IncomeSavingsAdjustments adjustments = report.Adjustments;
        IReadOnlyList<ReportMetric> summary = Summary(report, lookbackMonths);
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
        ReportMetric[] detail = report.Detail is IncomeSavingsMonth month
            ?
            [
                Metric("Income", month.Income),
                Metric("Spending", month.NetExpenses),
                new("Net cash flow", month.Surplus, Money(month.Surplus), month.Surplus >= 0m ? "positive" : "negative"),
                new("Savings rate", month.SavingsRatePercent, Percent(month.SavingsRatePercent),
                    month.SavingsRatePercent >= adjustments.TargetRate ? "positive" : null)
            ]
            : [];
        ReportTableRow[] categories = report.Categories
            .OrderBy(row => row.Kind == TransactionKind.Expense ? "Expense" : "Income", StringComparer.Ordinal)
            .ThenByDescending(row => decimal.Abs(row.Amount))
            .ThenBy(row => row.Category, StringComparer.Ordinal)
            .Select(row => new ReportTableRow(
                [row.Kind == TransactionKind.Income ? "Income" : "Expense", row.Category, Money(row.Amount)]))
            .ToArray();
        ReportTableRow[] included = TransactionRows(report.IncludedTransactions, false);
        ReportTableRow[] excluded = TransactionRows(report.ExcludedTransactions, true);
        ReportTableRow[] totals = analysis.CurrentMonthly.Select(month => new ReportTableRow(
            [month.Month.ToString(), Money(month.Income), Money(month.NetExpenses), Money(month.Surplus), Percent(month.SavingsRatePercent)],
            month.Surplus > 0m ? "positive" : month.Surplus < 0m ? "negative" : null)).ToArray();
        bool hasIncluded = analysis.CurrentLedger.Any(entry => entry.Included);
        string? empty = !analysis.Period.HasMonths
            ? "No categorized income or expense transactions are available."
            : hasIncluded ? null
            : analysis.CurrentLedger.Count == 0
                ? "No categorized income or expense transactions fall in this period."
                : "All transactions in this period are excluded from this calculation.";
        var view = new IncomeSavingsPageView(
            summary, cashFlow, savingsRate, analysis.CurrentSummary.PositiveSurplusMonths,
            analysis.CurrentSummary.Months, report.ExcludedCount, report.ExcludedIncome, report.ExcludedSpending,
            analysis.Period.CurrentMonths.Reverse().Select(value => value.ToString()).ToArray(),
            report.DetailMonth?.ToString() ?? string.Empty, detail, categories, included, excluded, totals,
            adjustments.TargetRate, analysis.CurrentLedger.Count > 0, hasIncluded, empty);
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["income.summary"] = Metrics(summary.ToArray()),
            ["income.cash_flow"] = new([], cashFlow, [], [], empty),
            ["income.savings_rate"] = new([], savingsRate, [], [], empty),
            ["income.detail"] = Metrics(detail),
            ["income.included_categories"] = new([], [], ["Type", "Category", "Amount"], categories,
                categories.Length == 0 ? "No included transactions for this month." : null),
            ["income.included_transactions"] = new([], [], ["Date", "Transaction", "Group", "Category", "Amount"], included,
                included.Length == 0 ? "No included transactions for this month." : null),
            ["income.excluded_transactions"] = new([], [], ["Date", "Transaction", "Group", "Category", "Amount", "Reason"], excluded,
                excluded.Length == 0 ? "No excluded transactions for this month." : null),
            ["income.monthly_totals"] = new([], [], ["Month", "Income", "Spending", "Surplus", "Savings rate"], totals,
                totals.Length == 0 ? "No monthly totals are available." : null)
        };
        return new DashboardPageReport(DashboardPageId.IncomeSavings, widgets) { IncomeSavingsView = view };
    }

    private static ReportMetric[] Summary(IncomeReport report, int months)
    {
        IncomePeriodComparison values = report.Comparison;
        static ReportMetric Change(string label, decimal value, decimal? change, int months, bool inverse)
            => new(label, value, Money(value), change is null or 0m ? null
                    : (change < 0m) == inverse ? "positive" : "negative",
                change is null ? null : $"{SignedMoney(change.Value)} vs previous {months} months", change);
        decimal? rateChange = values.SavingsRateChange;
        return
        [
            Change("Avg monthly income", values.Income, values.IncomeChange, months, false),
            Change("Avg monthly spending", values.NetExpenses, values.NetExpensesChange, months, true),
            Change("Avg monthly surplus", values.Surplus, values.SurplusChange, months, false),
            new("Savings rate", values.SavingsRatePercent, Percent(values.SavingsRatePercent),
                rateChange is not null ? rateChange > 0m ? "positive" : rateChange < 0m ? "negative" : null
                    : values.SavingsRatePercent >= report.Adjustments.TargetRate ? "positive" : null,
                rateChange is null ? null : $"{rateChange.Value:+0.0;-0.0;0.0} pts vs previous {months} months",
                rateChange)
        ];
    }

    private static ReportTableRow[] TransactionRows(IEnumerable<IncomeSavingsLedgerEntry> entries, bool includeReason)
        => entries.OrderByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .Select(entry => new ReportTableRow(includeReason
                ? [Date(entry.Transaction.Date), entry.Transaction.Description, Group(entry.Transaction),
                    Category(entry.Transaction), Money(entry.Transaction.Amount), Exclusions(entry.Exclusions)]
                : [Date(entry.Transaction.Date), entry.Transaction.Description, Group(entry.Transaction),
                    Category(entry.Transaction), Money(entry.Transaction.Amount)]))
            .ToArray();
}
