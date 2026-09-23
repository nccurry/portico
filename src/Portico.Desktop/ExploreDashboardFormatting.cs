using System.Globalization;

namespace Portico.Desktop;

/// <summary>Formats values shared by the subscription, merchant, and transaction pages.</summary>
internal static class ExploreDashboardFormatting
{
    private static readonly CultureInfo DisplayCulture = CultureInfo.GetCultureInfo("en-US");

    public static DashboardWidgetReport Chart(params ReportSeries[] series)
        => new([], series, [], [], series.Length == 0 ? "No data is available for this selection." : null);

    public static ReportSeries Series(string id, string label, IEnumerable<ReportPoint> points)
        => new(id, label, points.ToArray());

    public static ReportPoint Point(DateOnly date, decimal value, string? label = null)
        => new(date, null, date.DayNumber, value, label);

    public static ReportPoint Point(string category, decimal value)
        => new(null, category, 0m, value);

    public static ReportMetric Metric(string label, decimal? value, string? display = null, string? tone = null)
        => new(label, value, display ?? (value is null ? "—" : Money(value.Value)), tone);

    public static string Money(decimal value) => value.ToString("C0", DisplayCulture);

    public static string OptionalMoney(decimal? value) => value is null ? "Pending" : Money(value.Value);

    public static string SignedMoney(decimal value)
        => value == 0m ? Money(value) : $"{(value > 0m ? "+" : "-")}{Money(decimal.Abs(value))}";

    public static string Percent(decimal? value) => value is null ? "—" : $"{value:0.0}%";

    public static string SignedPercent(decimal value) => $"{value:+0.0;-0.0;0.0}%";

    public static string Date(DateOnly value) => value.ToString("MMM d, yyyy", DisplayCulture);
}
