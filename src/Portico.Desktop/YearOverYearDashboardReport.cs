using System.Globalization;
using Portico.Application;
using Portico.Finance;
using static Portico.Desktop.DashboardReportText;

namespace Portico.Desktop;

public sealed partial record DashboardPageReport
{
    /// <summary>Comparison cards and choices used by the current Year over year renderer.</summary>
    public YearOverYearPageView? YearOverYearView { get; init; }
}

/// <summary>One expandable Year over year comparison card.</summary>
public sealed record YearOverYearComparisonView(
    string Entity,
    string ThroughMonthLabel,
    IReadOnlyList<ReportMetric> Metrics,
    IReadOnlyList<ReportSeries> Series,
    IReadOnlyList<string> TotalColumns,
    IReadOnlyList<ReportTableRow> TotalRows,
    IReadOnlyList<string> TransactionColumns,
    IReadOnlyList<ReportTableRow> TransactionRows);

/// <summary>Choices and comparison cards shown by the Year over year page.</summary>
public sealed record YearOverYearPageView(
    string? LatestDataCaption,
    IReadOnlyList<string> PresetCategories,
    IReadOnlyList<string> Categories,
    IReadOnlyList<string> Groups,
    IReadOnlyList<YearOverYearComparisonView> Comparisons,
    string? EmptyMessage = null);

/// <summary>Turns semantic year-over-year comparisons into desktop cards.</summary>
public static class YearOverYearDashboardReport
{
    public static DashboardPageReport Build(YearOverYearReport report)
    {
        ArgumentNullException.ThrowIfNull(report);
        YearOverYearComparisonView[] comparisons = report.Comparisons.Select(Comparison).ToArray();
        string? empty = report.EmptyReason switch
        {
            null => null,
            YearOverYearEmptyReason.NoPresetCategories => "No expense transactions are available.",
            YearOverYearEmptyReason.NoPresetSelection => "Choose at least one category to compare.",
            YearOverYearEmptyReason.NoCategories => "No expense category data is available.",
            YearOverYearEmptyReason.NoGroups => "No expense group data is available.",
            YearOverYearEmptyReason.NoMatchingHistory => "No spending history is available for this selection.",
            _ => throw new ArgumentOutOfRangeException(nameof(report))
        };
        string? caption = report.LatestTransactionDate is DateOnly latest
            ? $"Latest data {Date(latest)} · includes {latest.ToString("MMM yyyy", CultureInfo.InvariantCulture)} to date"
            : null;
        var view = new YearOverYearPageView(caption, report.PresetCategories, report.Categories,
            report.Groups, comparisons, empty);
        YearOverYearComparisonView? first = comparisons.FirstOrDefault();
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["yoy.comparison"] = first is null
                ? Chart([])
                : new(first.Metrics, first.Series, [], [], empty),
            ["yoy.totals"] = first is null
                ? Chart([])
                : new([], [], first.TotalColumns, first.TotalRows, empty)
        };
        return new DashboardPageReport(DashboardPageId.YearOverYear, widgets) { YearOverYearView = view };
    }

    private static YearOverYearComparisonView Comparison(YearOverYearComparison comparison)
    {
        YearOverYearSummary summary = comparison.Summary;
        string month = summary.ThroughMonth is > 0 and <= 12
            ? new DateOnly(2000, summary.ThroughMonth, 1).ToString("MMMM", CultureInfo.InvariantCulture)
            : string.Empty;
        ReportMetric[] metrics =
        [
            Metric(summary.CurrentYear.ToString(CultureInfo.InvariantCulture), summary.CurrentTotal),
            new(summary.PreviousYear?.ToString(CultureInfo.InvariantCulture) ?? "Previous year",
                summary.PreviousTotal, summary.PreviousTotal is decimal prior ? Money(prior) : "Not available"),
            new("Change", summary.Change,
                summary.Change is decimal change ? SignedMoney(change) : "Not available",
                summary.Change is decimal value ? value < 0m ? "positive" : value > 0m ? "negative" : null : null,
                summary.ChangePercent is decimal percent ? SignedPercent(percent) : null,
                summary.Change)
        ];
        ReportSeries[] series = comparison.History.GroupBy(point => point.Year)
            .OrderByDescending(group => group.Key)
            .Select(group => Series(group.Key.ToString(CultureInfo.InvariantCulture),
                group.Key.ToString(CultureInfo.InvariantCulture),
                group.Select(point => Point(new DateOnly(point.Year, point.Month, 1), point.Spending))))
            .ToArray();
        ReportTableRow[] totals = comparison.Totals.OrderByDescending(total => total.Year)
            .Select(total => new ReportTableRow(
                [total.Year.ToString(CultureInfo.InvariantCulture), Money(total.SpendingThroughMonth),
                    total.Change is decimal change ? SignedMoney(change) : "Not available",
                    total.ChangePercent is decimal percent ? SignedPercent(percent) : "Not available"],
                total.Change is decimal value ? value < 0m ? "positive" : value > 0m ? "negative" : null : null))
            .ToArray();
        ReportTableRow[] transactions = comparison.Transactions.Select(transaction => new ReportTableRow(
            [Date(transaction.Date), transaction.Description, Group(transaction), Category(transaction),
                transaction.Account, Money(-transaction.Amount)])).ToArray();
        return new YearOverYearComparisonView(
            comparison.Entity, month, metrics, series,
            ["Year", $"Spending through {month}", "Change from prior year", "Change %"], totals,
            ["Date", "Description", "Group", "Category", "Account", "Spending"], transactions);
    }
}
