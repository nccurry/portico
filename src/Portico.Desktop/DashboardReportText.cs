using System.Globalization;
using Portico.Finance;

namespace Portico.Desktop;

/// <summary>Formats report values and typed exclusion reasons for desktop pages.</summary>
internal static class DashboardReportText
{
    private static readonly CultureInfo Culture = CultureInfo.GetCultureInfo("en-US");

    public static string Money(decimal value) => value.ToString("C0", Culture);

    public static string SignedMoney(decimal value)
        => value == 0m ? Money(value) : $"{(value > 0m ? "+" : "-")}{Money(decimal.Abs(value))}";

    public static string Percent(decimal? value) => value is null ? "—" : $"{value:0.0}%";

    public static string SignedPercent(decimal value) => $"{value:+0.0;-0.0;0.0}%";

    public static string Date(DateOnly value) => value.ToString("MMM d, yyyy", Culture);

    public static string Group(FinancialTransaction transaction)
        => string.IsNullOrWhiteSpace(transaction.Group) ? "Unknown" : transaction.Group;

    public static string Category(FinancialTransaction transaction)
        => string.IsNullOrWhiteSpace(transaction.Category) ? "Unknown" : transaction.Category;

    public static ReportPoint Point(DateOnly date, decimal value) => new(date, null, date.DayNumber, value);

    public static ReportPoint Point(string category, decimal value) => new(null, category, 0m, value);

    public static ReportSeries Series(string id, string label, IEnumerable<ReportPoint> points)
        => new(id, label, points.ToArray());

    public static DashboardWidgetReport Chart(params ReportSeries[] series)
        => new([], series, [], [], series.Length == 0 ? "No data is available for this selection." : null);

    public static DashboardWidgetReport Metrics(params ReportMetric[] metrics) => new(metrics, [], [], []);

    public static ReportMetric Metric(string label, decimal value)
        => new(label, value, Money(value));

    public static string Exclusions(IEnumerable<LedgerExclusion> exclusions)
        => string.Join("; ", exclusions.Select(Exclusion));

    private static string Exclusion(LedgerExclusion exclusion)
        => exclusion.Reason switch
        {
            LedgerExclusionReason.TransferGroup => "Transfer group",
            LedgerExclusionReason.OutsideConfiguredSet => $"Outside configured set: {exclusion.Value}",
            LedgerExclusionReason.OutsideIncludedDescriptions => "Outside included groups/categories/transactions",
            LedgerExclusionReason.ExcludedIncomeCategory => $"Excluded income category: {exclusion.Value}",
            LedgerExclusionReason.ExcludedExpenseGroup => $"Excluded group: {exclusion.Value}",
            LedgerExclusionReason.ExcludedExpenseCategory => $"Excluded expense category: {exclusion.Value}",
            LedgerExclusionReason.ExcludedCategory => $"Excluded category: {exclusion.Value}",
            LedgerExclusionReason.ExcludedDescription => $"Excluded transaction like: {exclusion.Value}",
            LedgerExclusionReason.IncomeOverLimit => $"Income over {RequiredLimit(exclusion)}",
            LedgerExclusionReason.ExpenseOverLimit => $"Expense over {RequiredLimit(exclusion)}",
            _ => throw new ArgumentOutOfRangeException(nameof(exclusion))
        };

    private static string RequiredLimit(LedgerExclusion exclusion)
        => exclusion.Limit is decimal value ? Money(value)
            : throw new ArgumentException("An exclusion limit is required.", nameof(exclusion));
}
