using System.Globalization;
using Portico.Application;
using Portico.Finance;
using static Portico.Desktop.ExploreDashboardFormatting;

namespace Portico.Desktop;

/// <summary>Page data that the merchant renderer uses beyond individual widgets.</summary>
public sealed record MerchantsPageView(
    string? LatestDataCaption,
    MerchantAnalysisResult Analysis,
    string? SelectedMerchant,
    string DetailMonth,
    IReadOnlyList<MerchantHistoryEntry> SelectedHistory,
    IReadOnlyList<MerchantDetailBreakdownEntry> SelectedCategories,
    IReadOnlyList<MerchantDetailBreakdownEntry> SelectedAccounts,
    IReadOnlyList<MerchantDescriptionEntry> SelectedDescriptions,
    IReadOnlyList<SpendingLedgerEntry> SelectedTransactions,
    string? EmptyMessage = null);

public sealed partial record DashboardPageReport
{
    public MerchantsPageView? MerchantsView { get; init; }
}

/// <summary>Turns merchant analysis into the configured desktop widgets.</summary>
public static class MerchantsDashboardReport
{
    public static DashboardPageReport Build(MerchantsReport report, SpendingComparison comparison)
    {
        ArgumentNullException.ThrowIfNull(report);
        MerchantAnalysisResult analysis = report.Analysis;
        MerchantOverviewEntry? selected = analysis.Overview.FirstOrDefault(entry =>
            string.Equals(entry.Merchant, report.SelectedMerchant, StringComparison.Ordinal));
        ReportMetric[] summary =
        [
            Metric("Total spending", analysis.Summary.TotalSpending),
            Metric("Average monthly", analysis.Summary.AverageMonthlySpending),
            Metric("Merchants", analysis.Summary.MerchantCount,
                analysis.Summary.MerchantCount.ToString(CultureInfo.InvariantCulture)),
            Metric("At repeat merchants", analysis.Summary.RepeatSpendingSharePercent,
                Percent(analysis.Summary.RepeatSpendingSharePercent))
        ];
        ReportSeries[] history = report.SelectedMerchant is null ? [] :
        [
            Series("current", "Current period", report.SelectedHistory.Select(entry =>
                Point(entry.CurrentMonth.Start, entry.CurrentSpending))),
            Series("comparison", "Comparison", report.SelectedHistory.Select(entry =>
                Point(entry.CurrentMonth.Start, entry.ComparisonSpending)))
        ];
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["merchants.summary"] = new(summary, [], [], []),
            ["merchants.ranking"] = Chart(Series("merchants", "Spending",
                analysis.Overview.Take(12).Select(entry => Point(entry.Merchant, entry.Spending)))),
            ["merchants.overview"] = Overview(analysis.Overview),
            ["merchants.history"] = Chart(history),
            ["merchants.detail_summary"] = DetailSummary(selected, comparison),
            ["merchants.detail_history"] = Chart(history),
            ["merchants.detail_categories"] = Breakdown("Category", report.SelectedCategories),
            ["merchants.detail_accounts"] = Breakdown("Account", report.SelectedAccounts),
            ["merchants.detail_descriptions"] = Descriptions(report.SelectedDescriptions),
            ["merchants.detail_transactions"] = Transactions(report.SelectedTransactions),
            ["merchants.excluded"] = Excluded(analysis.CurrentLedger)
        };
        string? caption = report.LatestExpenseDate is DateOnly date
            ? $"Spending through {date.ToString("MMMM d, yyyy", CultureInfo.InvariantCulture)}"
            : null;
        return new DashboardPageReport(DashboardPageId.Merchants, widgets)
        {
            MerchantsView = new(caption, analysis, report.SelectedMerchant,
                report.DetailMonth?.ToString() ?? "all", report.SelectedHistory,
                report.SelectedCategories, report.SelectedAccounts, report.SelectedDescriptions,
                report.SelectedTransactions, analysis.Overview.Count == 0
                    ? "No spending is included in this view. Adjust the filters to continue."
                    : null)
        };
    }

    private static DashboardWidgetReport Overview(IReadOnlyList<MerchantOverviewEntry> entries)
        => new([], [], ["Merchant", "Spending", "Share", "Average monthly", "Change", "Transactions", "Category"],
            entries.Select(entry => new ReportTableRow(
                [entry.Merchant, Money(entry.Spending), Percent(entry.SharePercent), Money(entry.AverageMonthlySpending),
                    SignedMoney(entry.Change), entry.TransactionCount.ToString(CultureInfo.InvariantCulture),
                    entry.PrimaryCategory],
                entry.Change > 0m ? "negative" : entry.Change < 0m ? "positive" : null)).ToArray(),
            entries.Count == 0 ? "No spending is included in this view. Adjust the filters to continue." : null);

    private static DashboardWidgetReport DetailSummary(MerchantOverviewEntry? entry, SpendingComparison comparison)
    {
        if (entry is null)
            return new([], [], [], [], "Select a merchant to inspect its detail.");
        string period = comparison == SpendingComparison.PreviousPeriod ? "previous period" : "last year";
        return new(
            [Metric("Spending", entry.Spending),
                new ReportMetric($"Change vs {period}", entry.Change, SignedMoney(entry.Change),
                    entry.Change > 0m ? "negative" : entry.Change < 0m ? "positive" : null,
                    Percent(entry.ChangePercent)),
                Metric("Transactions", entry.TransactionCount,
                    entry.TransactionCount.ToString(CultureInfo.InvariantCulture)),
                Metric("Average purchase", entry.AverageTransaction)],
            [], [], []);
    }

    private static DashboardWidgetReport Breakdown(string label, IReadOnlyList<MerchantDetailBreakdownEntry> entries)
        => new([], [], [label, "Spending", "Share", "Transactions"],
            entries.Select(entry => new ReportTableRow(
                [entry.Entity, Money(entry.Spending), Percent(entry.SharePercent),
                    entry.Transactions.ToString(CultureInfo.InvariantCulture)])).ToArray(),
            entries.Count == 0 ? $"No {label.ToLowerInvariant()} detail is available." : null);

    private static DashboardWidgetReport Descriptions(IReadOnlyList<MerchantDescriptionEntry> entries)
        => new([], [], ["Description", "Spending", "Transactions", "Last transaction"],
            entries.Select(entry => new ReportTableRow(
                [entry.Description, Money(entry.Spending), entry.Transactions.ToString(CultureInfo.InvariantCulture),
                    Date(entry.LastTransaction)])).ToArray(),
            entries.Count == 0 ? "No descriptions are available." : null);

    private static DashboardWidgetReport Transactions(IReadOnlyList<SpendingLedgerEntry> entries)
        => new([], [], ["Date", "Description", "Category", "Group", "Account", "Spending"],
            entries.Select(entry => new ReportTableRow(
                [Date(entry.Transaction.Date), entry.Transaction.Description, entry.Transaction.Category,
                    entry.Transaction.Group, entry.Transaction.Account, Money(entry.NetSpending)])).ToArray(),
            entries.Count == 0 ? "No transactions are available for this merchant." : null);

    private static DashboardWidgetReport Excluded(IReadOnlyList<SpendingLedgerEntry> entries)
    {
        SpendingLedgerEntry[] excluded = entries.Where(entry => !entry.Included).ToArray();
        return new([], [], ["Date", "Description", "Category", "Group", "Spending", "Reason"],
            excluded.Select(entry => new ReportTableRow(
                [Date(entry.Transaction.Date), entry.Transaction.Description, entry.Transaction.Category,
                    entry.Transaction.Group, Money(entry.NetSpending), entry.ExclusionReason], "negative")).ToArray(),
            excluded.Length == 0 ? "No current-period rows are excluded." : null);
    }
}
