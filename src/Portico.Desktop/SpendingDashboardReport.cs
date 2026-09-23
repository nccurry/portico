using System.Globalization;
using Portico.Application;
using Portico.Finance;
using static Portico.Desktop.DashboardReportText;

namespace Portico.Desktop;

/// <summary>Turns one semantic Spending report into existing desktop widgets.</summary>
public static class SpendingDashboardReport
{
    public static DashboardPageReport Build(SpendingReport report, int lookbackMonths, SpendingComparison comparison)
    {
        ArgumentNullException.ThrowIfNull(report);
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(lookbackMonths);
        if (!Enum.IsDefined(comparison))
            throw new ArgumentOutOfRangeException(nameof(comparison));
        SpendingAnalysisResult analysis = report.Analysis;
        string comparisonLabel = comparison == SpendingComparison.PreviousPeriod
            ? $"previous {lookbackMonths} months" : "same months last year";
        SpendingOverviewEntry[] ranked = report.Ranked.ToArray();
        SpendingOverviewEntry[] trended = report.Trended.ToArray();
        ReportMetric[] summary =
        [
            Metric("Total spending", analysis.Summary.TotalSpending),
            Metric("Average monthly", analysis.Summary.AverageMonthlySpending),
            new($"Change vs {comparisonLabel}", analysis.Summary.Change, SignedMoney(analysis.Summary.Change),
                Tone(analysis.Summary.Change), Percent(analysis.Summary.ChangePercent), analysis.Summary.Change),
            new("Excluded", report.ExcludedCount, report.ExcludedCount.ToString(CultureInfo.InvariantCulture),
                Detail: $"{Money(report.ExcludedSpending)} net spending"),
            new("Included rows", analysis.CurrentLedger.Count(entry => entry.Included),
                analysis.CurrentLedger.Count(entry => entry.Included).ToString(CultureInfo.InvariantCulture))
        ];
        ReportSeries[] trend = trended.Select(entry => Series(
            Slug(entry.Entity), entry.Entity,
            analysis.Period.CurrentMonths.Select((month, index) => Point(month.Start, entry.MonthlyTrend[index])))).ToArray();
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["spending.summary"] = new(summary, [], [], [],
                analysis.Period.HasMonths ? null : "No expense transactions are available.")
            { DateGuide = report.LatestExpenseDate },
            ["spending.trend"] = Chart(trend),
            ["spending.ranking"] = Chart(Series("ranking", "Spending",
                ranked.Select(entry => Point(entry.Entity, entry.Spending)))),
            ["spending.monthly"] = Chart(trend),
            ["spending.categories"] = Chart(Series("categories", "Spending",
                analysis.Overview.Select(entry => Point(entry.Entity, entry.Spending)))),
            ["spending.overview"] = Overview(analysis.Overview, analysis.Period.CurrentMonths,
                report.Breakdown, comparisonLabel),
            ["spending.detail_summary"] = DetailSummary(report.DetailSummary, comparisonLabel),
            ["spending.detail_history"] = report.SelectedEntity is null
                ? Chart([])
                : Chart(
                    Series("current", "Current period", report.History.Select(row => Point(row.CurrentMonth.Start, row.Current))),
                    Series("comparison", comparisonLabel, report.History.Select(row => Point(row.CurrentMonth.Start, row.Comparison)))),
            ["spending.detail_categories"] = Categories(report, comparisonLabel),
            ["spending.detail_merchants"] = Merchants(report.Merchants),
            ["spending.detail_transactions"] = Transactions(report.CurrentDetail),
            ["spending.excluded"] = Excluded(report.Analysis.CurrentLedger)
        };
        return new DashboardPageReport(DashboardPageId.Spending, widgets);
    }

    private static DashboardWidgetReport Overview(
        IReadOnlyList<SpendingOverviewEntry> overview,
        IReadOnlyList<YearMonth> months,
        SpendingBreakdown breakdown,
        string comparisonLabel)
    {
        IReadOnlyList<string> columns = breakdown == SpendingBreakdown.Category
            ? ["Category", "Group", "Spending", "Share", "Average", comparisonLabel, "Change", "Change %", "Transactions", "Monthly trend"]
            : ["Group", "Spending", "Share", "Average", comparisonLabel, "Change", "Change %", "Transactions", "Monthly trend"];
        ReportTableRow[] rows = overview.Select(entry =>
        {
            var values = new List<string> { entry.Entity };
            if (breakdown == SpendingBreakdown.Category)
                values.Add(entry.Group);
            values.AddRange([
                Money(entry.Spending), Percent(entry.SharePercent), Money(entry.AverageMonthlySpending),
                Money(entry.ComparisonSpending), SignedMoney(entry.Change), Percent(entry.ChangePercent),
                entry.TransactionCount.ToString(CultureInfo.InvariantCulture), string.Empty
            ]);
            return new ReportTableRow(values, Tone(entry.Change));
        }).ToArray();
        return new([], overview.Select((entry, index) => Series(
                $"overview-{index}", entry.Entity,
                months.Select((month, monthIndex) => Point(month.Start, entry.MonthlyTrend[monthIndex])))).ToArray(),
            columns, rows, rows.Length == 0 ? "No spending matches these controls." : null);
    }

    private static DashboardWidgetReport DetailSummary(SpendingDetailSummary summary, string comparisonLabel)
        => Metrics(
            Metric("Spending", summary.Spending),
            Metric("Average monthly", summary.AverageMonthlySpending),
            new("Share of view", summary.SharePercent, Percent(summary.SharePercent)),
            new($"Change vs {comparisonLabel}", summary.Change, SignedMoney(summary.Change), Tone(summary.Change),
                Percent(summary.ChangePercent), summary.Change));

    private static DashboardWidgetReport Categories(SpendingReport report, string comparisonLabel)
    {
        if (report.Breakdown != SpendingBreakdown.Group)
            return new([], [], ["Category", "Spending"], [], "Categories are part of the selected category.");
        ReportTableRow[] rows = report.Categories.Select(row => new ReportTableRow(
            [row.Category, Money(row.Spending), Percent(row.SharePercent), Money(row.AverageMonthlySpending),
                Money(row.ComparisonSpending), SignedMoney(row.Change), Percent(row.ChangePercent),
                row.Transactions.ToString(CultureInfo.InvariantCulture)], Tone(row.Change))).ToArray();
        return new([], [], ["Category", "Spending", "Share", "Average", comparisonLabel, "Change", "Change %", "Transactions"],
            rows, rows.Length == 0 ? "No category detail matches this selection." : null);
    }

    private static DashboardWidgetReport Merchants(IReadOnlyList<SpendingMerchantTotal> merchants)
    {
        ReportTableRow[] rows = merchants.Select(row => new ReportTableRow(
            [row.Merchant, Money(row.Spending), Percent(row.SharePercent), row.Transactions.ToString(CultureInfo.InvariantCulture),
                Money(row.AverageTransaction), Date(row.LastTransaction)])).ToArray();
        return new([], [], ["Merchant", "Spending", "Share", "Transactions", "Average", "Last transaction"],
            rows, rows.Length == 0 ? "No merchant detail matches this selection." : null);
    }

    private static DashboardWidgetReport Transactions(IReadOnlyList<SpendingLedgerEntry> current)
    {
        ReportTableRow[] rows = current.Select(entry => new ReportTableRow(
            [Date(entry.Transaction.Date), entry.Transaction.Description, Category(entry.Transaction), Money(entry.NetSpending)],
            entry.NetSpending < 0m ? "positive" : null)).ToArray();
        return new([], [], ["Date", "Transaction", "Category", "Spending"], rows,
            rows.Length == 0 ? "No transactions match this selection." : null);
    }

    private static DashboardWidgetReport Excluded(IReadOnlyList<SpendingLedgerEntry> ledger)
    {
        ReportTableRow[] rows = ledger.Where(entry => !entry.Included)
            .OrderByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .Select(entry => new ReportTableRow(
                [Date(entry.Transaction.Date), entry.Transaction.Description, Group(entry.Transaction),
                    Category(entry.Transaction), Money(entry.NetSpending), Exclusions(entry.Exclusions)]))
            .ToArray();
        return new([], [], ["Date", "Transaction", "Group", "Category", "Spending", "Reason"], rows,
            rows.Length == 0 ? "No rows are excluded by this view." : null);
    }

    private static string? Tone(decimal change)
        => change > 0m ? "negative" : change < 0m ? "positive" : null;

    private static string Slug(string value)
    {
        var slug = new System.Text.StringBuilder(value.Length);
        foreach (char character in value)
        {
            if (char.IsLetterOrDigit(character))
                slug.Append(char.ToLowerInvariant(character));
            else if (slug.Length > 0 && slug[^1] != '-')
                slug.Append('-');
        }
        return slug.ToString().Trim('-');
    }
}
