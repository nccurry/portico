using System.Globalization;
using Portico.Application;
using Portico.Finance;
using static Portico.Desktop.ExploreDashboardFormatting;

namespace Portico.Desktop;

/// <summary>Page data that the subscription renderer uses beyond individual widgets.</summary>
public sealed record SubscriptionsPageView(
    string? LatestDataCaption,
    int? DataAgeDays,
    bool DataIsStale,
    SubscriptionAnalysisResult Analysis,
    string? SelectedMerchant,
    bool SelectedMerchantIsCandidate,
    IReadOnlyList<SubscriptionChargeEntry> SelectedCharges,
    string? EmptyMessage = null);

public sealed partial record DashboardPageReport
{
    public SubscriptionsPageView? SubscriptionsView { get; init; }
}

/// <summary>Turns subscription analysis into the configured desktop widgets.</summary>
public static class SubscriptionsDashboardReport
{
    public static DashboardPageReport Build(SubscriptionsReport report)
    {
        ArgumentNullException.ThrowIfNull(report);
        SubscriptionAnalysisResult analysis = report.Analysis;
        ReportMetric[] summary =
        [
            Metric("Active subscriptions", analysis.Summary.ActiveCount,
                analysis.Summary.ActiveCount.ToString(CultureInfo.InvariantCulture)),
            Metric("Estimated monthly run rate", analysis.Summary.MonthlyRunRate),
            Metric("Spent in the last 12 months", analysis.Summary.TrailingTwelveMonthSpend),
            new ReportMetric(
                "12-month change",
                analysis.Summary.AnnualChangePercent,
                analysis.Summary.AnnualChangePercent is null ? "Not available" : SignedPercent(analysis.Summary.AnnualChangePercent.Value),
                analysis.Summary.AnnualChangePercent is null ? null : analysis.Summary.AnnualChangePercent > 0m ? "negative" : "positive",
                analysis.Summary.AnnualChangePercent is null ? null : SignedMoney(
                    analysis.Summary.TrailingTwelveMonthSpend - analysis.Summary.PriorTwelveMonthSpend))
        ];
        ReportSeries[] spendHistory =
        [
            Series("actual", "Actual spend", analysis.History.Select(entry => Point(entry.Month.Start, entry.ActualSpend))),
            Series("average", "3-month average", analysis.History.Select(entry => Point(entry.Month.Start, entry.RollingAverage)))
        ];
        ReportTimelineRange[] lifecycles = analysis.Lifecycles.Select(entry => new ReportTimelineRange(
            entry.Merchant, entry.EpisodeStart, entry.DisplayEnd, OptionalMoney(entry.MonthlyRunRate))).ToArray();
        SubscriptionChargeEntry[] selectedCharges = report.SelectedCharges.ToArray();
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["subscriptions.summary"] = new(summary, [], [], []),
            ["subscriptions.active"] = Inventory(analysis.Active,
                "No active subscriptions are present in the selected categories.", summary, lifecycles, analysis.LatestDataDate),
            ["subscriptions.lifecycle"] = new([], [], [], [],
                lifecycles.Length == 0 ? "No subscription lifecycles overlap this history range." : null)
            {
                TimelineRanges = lifecycles,
                DateGuide = analysis.LatestDataDate
            },
            ["subscriptions.monthly"] = Chart(Series("subscriptions", "Subscription spending",
                analysis.History.Select(entry => Point(entry.Month.Start, entry.ActualSpend)))),
            ["subscriptions.history_spend"] = Chart(spendHistory),
            ["subscriptions.history_active"] = Chart(Series("active", "Active merchants",
                analysis.History.Select(entry => Point(entry.Month.Start, entry.ActiveMerchants)))),
            ["subscriptions.candidates"] = Inventory(analysis.Candidates,
                "No strong uncategorized subscription candidates were found."),
            ["subscriptions.inactive"] = Inventory(analysis.Inactive,
                "No inactive subscriptions are present in the selected categories."),
            ["subscriptions.detail_charge_history"] = Chart(Series("charges", "Charge amount",
                selectedCharges.OrderBy(entry => entry.Transaction.Date)
                    .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
                    .Select(entry => Point(entry.Transaction.Date, entry.Amount)))),
            ["subscriptions.detail_charges"] = Charges(selectedCharges),
            ["subscriptions.detail_monthly_totals"] = MonthlyTotals(selectedCharges)
        };
        string? caption = analysis.LatestDataDate is DateOnly date
            ? $"Transaction history through {date.ToString("MMMM d, yyyy", CultureInfo.InvariantCulture)}."
            : null;
        return new DashboardPageReport(DashboardPageId.Subscriptions, widgets)
        {
            SubscriptionsView = new(caption, report.DataAgeDays, report.DataIsStale, analysis,
                report.SelectedMerchant, report.SelectedMerchantIsCandidate, selectedCharges,
                analysis.LatestDataDate is null
                    ? "No transactions are available. Refresh the spreadsheet data to build a subscription inventory."
                    : null)
        };
    }

    private static DashboardWidgetReport Inventory(
        IReadOnlyList<SubscriptionInventoryEntry> entries,
        string emptyMessage,
        IReadOnlyList<ReportMetric>? metrics = null,
        IReadOnlyList<ReportTimelineRange>? lifecycles = null,
        DateOnly? dateGuide = null)
        => new(metrics ?? [], [], ["Merchant", "Status", "Cadence", "Est. monthly", "Last charge"],
            entries.Select(entry => new ReportTableRow(
                [entry.Merchant,
                    entry.Source == "Detected" ? $"Detected ({entry.Confidence}%)" : entry.Status,
                    entry.Cadence, OptionalMoney(entry.MonthlyRunRate), Date(entry.LastDate)],
                entry.Status == "Active" ? "positive" : null)).ToArray(),
            entries.Count == 0 ? emptyMessage : null)
        {
            TimelineRanges = lifecycles ?? [],
            DateGuide = dateGuide
        };

    private static DashboardWidgetReport Charges(IReadOnlyList<SubscriptionChargeEntry> entries)
        => new([], [], ["Date", "Description", "Category", "Account", "Amount"],
            entries.Select(entry => new ReportTableRow(
                [Date(entry.Transaction.Date), entry.Transaction.Description,
                    entry.Transaction.Category, entry.Transaction.Account, Money(entry.Amount)])).ToArray(),
            entries.Count == 0 ? "No subscription charges are available for this merchant." : null);

    private static DashboardWidgetReport MonthlyTotals(IReadOnlyList<SubscriptionChargeEntry> entries)
        => new([], [], ["Month", "Actual spend"],
            entries.GroupBy(entry => entry.Transaction.Month).OrderByDescending(group => group.Key)
                .Select(group => new ReportTableRow(
                    [group.Key.Start.ToString("MMM yyyy", CultureInfo.InvariantCulture), Money(group.Sum(entry => entry.Amount))]))
                .ToArray(),
            entries.Count == 0 ? "No monthly totals are available." : null);
}
