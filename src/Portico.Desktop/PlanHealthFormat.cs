using System.Globalization;

namespace Portico.Desktop;

internal static class PlanHealthFormat
{
    private static readonly CultureInfo Us = CultureInfo.GetCultureInfo("en-US");

    public static string Money(decimal value) => value.ToString("C0", Us);

    public static string SignedMoney(decimal value)
        => value == 0m ? Money(value) : $"{(value > 0m ? "+" : "-")}{Money(decimal.Abs(value))}";

    public static string Percent(decimal? value) => value is null ? "—" : $"{value:0.0}%";

    public static string Date(DateOnly value) => value.ToString("MMM d, yyyy", Us);

    public static string DateOrNoData(DateOnly? value) => value is null ? "No data" : Date(value.Value);

    public static DashboardWidgetReport Metrics(params ReportMetric[] metrics) => new(metrics, [], [], []);

    public static DashboardWidgetReport Chart(params ReportSeries[] series)
        => new([], series, [], [], series.Length == 0 ? "No data is available for this selection." : null);

    public static ReportSeries Series(string id, string label, IEnumerable<ReportPoint> points)
        => new(id, label, points.ToArray());

    public static ReportPoint Point(DateOnly date, decimal value) => new(date, null, date.DayNumber, value);

    public static ReportPoint Point(string category, decimal value) => new(null, category, 0m, value);

    public static ReportMetric Metric(string label, decimal? value, string? tone = null)
        => new(label, value, value is null ? "—" : Money(value.Value), tone);
}
