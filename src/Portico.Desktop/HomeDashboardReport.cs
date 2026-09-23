using System.Globalization;
using Portico.Application;

namespace Portico.Desktop;

/// <summary>Turns semantic Home values into the existing six desktop widgets.</summary>
public static class HomeDashboardReport
{
    private static readonly CultureInfo MoneyCulture = CultureInfo.GetCultureInfo("en-US");

    public static DashboardPageReport Build(HomeReport home, int visibleAccountCount)
    {
        ArgumentNullException.ThrowIfNull(home);
        ArgumentOutOfRangeException.ThrowIfNegative(visibleAccountCount);

        var history = home.NetWorthHistory;
        ReportMetric[] groups = home.Groups.Select(group => GroupMetric(group, home.Window)).ToArray();
        ReportTableRow[] accounts = home.Accounts.Select(account => AccountRow(account, home.Groups)).ToArray();
        var closing = home.Closing;
        var safety = home.Safety;

        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["home.net_worth"] = history.Count == 0
                ? EmptyBalances()
                : Chart(
                    Series("net-worth", "Net worth", history.Select(point => Point(point.Date, point.NetWorth))),
                    Series("assets", "Assets", history.Select(point => Point(point.Date, point.Assets))),
                    Series("liabilities", "Liabilities", history.Select(point => Point(point.Date, point.Liabilities)))) with
                {
                    Metrics = NetWorthMetrics(home)
                },
            ["home.overview"] = Metrics(
                Metric("Net worth", closing?.NetWorth ?? 0m),
                Metric("Cash flow", home.CashFlow.Surplus, tone: home.CashFlow.Surplus >= 0m ? "positive" : "negative"),
                Metric("Savings rate", home.CashFlow.SavingsRatePercent, Percent(home.CashFlow.SavingsRatePercent)),
                Metric("Accounts", visibleAccountCount, visibleAccountCount.ToString(CultureInfo.InvariantCulture))),
            ["home.attribution"] = groups.Length == 0
                ? EmptyBalances()
                : Chart(Series(
                    "groups",
                    "Net-worth movement",
                    groups.OrderBy(group => group.Change ?? 0m)
                        .ThenBy(group => group.Label, StringComparer.Ordinal)
                        .Select(group => Point(group.Label, group.Change ?? 0m)))),
            ["home.accounts"] = new(groups, [], [], [], groups.Length == 0
                ? "No mapped balance groups are available." : null),
            ["home.inventory"] = new([], [], ["Group", "Account", "Balance", "Change"], accounts,
                visibleAccountCount == 0 ? "No visible account balances are available." : null),
            ["home.safety"] = Metrics(
                Metric("Emergency fund", safety.EmergencyFundMonthsCovered,
                    safety.EmergencyFundMonthsCovered is null
                        ? "No expense baseline"
                        : $"{safety.EmergencyFundMonthsCovered:0.0} / {safety.EmergencyFundTargetMonths} months",
                    safety.EmergencyFundMonthsCovered >= safety.EmergencyFundTargetMonths ? "positive" : null),
                Metric("Debt paid down", safety.DebtProgressPercent, Percent(safety.DebtProgressPercent),
                    safety.DebtProgressPercent >= 0m ? "positive" : "negative"),
                Metric("FI funding", safety.FinancialIndependenceProgressPercent,
                    Percent(safety.FinancialIndependenceProgressPercent),
                    safety.FinancialIndependenceProgressPercent >= 100m ? "positive" : null))
        };
        return new DashboardPageReport(DashboardPageId.Home, widgets);
    }

    private static IReadOnlyList<ReportMetric> NetWorthMetrics(HomeReport home)
    {
        var opening = home.Opening;
        var closing = home.Closing;
        HomeBalanceWindow? window = home.Window;
        if (opening is null || closing is null || window is null)
            return [];

        string period = PeriodLabel(window);
        return
        [
            ChangeMetric("Net worth", closing.NetWorth, opening.NetWorth, period),
            ChangeMetric("Assets", closing.Assets, opening.Assets, period),
            LiabilityMetric(closing.Liabilities, opening.Liabilities, period)
        ];
    }

    private static ReportMetric GroupMetric(HomeGroupMovement group, HomeBalanceWindow? window)
    {
        decimal balance = group.LiabilitiesOnly ? decimal.Abs(group.ClosingSignedBalance) : group.ClosingSignedBalance;
        decimal change = group.LiabilitiesOnly ? -group.NetWorthChange : group.NetWorthChange;
        string? tone = change == 0m ? null : group.LiabilitiesOnly
            ? change < 0m ? "positive" : "negative"
            : change > 0m ? "positive" : "negative";
        return new ReportMetric(group.Group, balance, Money(balance), tone,
            $"{SignedMoney(change)} {PeriodLabel(window)}", group.NetWorthChange);
    }

    private static ReportTableRow AccountRow(
        HomeAccountMovement account,
        IReadOnlyList<HomeGroupMovement> groups)
    {
        bool liabilityGroup = groups.First(group => group.Group == account.Group).LiabilitiesOnly;
        decimal balance = liabilityGroup ? decimal.Abs(account.ClosingSignedBalance) : account.ClosingSignedBalance;
        decimal change = liabilityGroup ? -account.NetWorthChange : account.NetWorthChange;
        string? tone = change == 0m ? null : liabilityGroup
            ? change < 0m ? "positive" : "negative"
            : change > 0m ? "positive" : "negative";
        return new ReportTableRow(
            [account.Group, account.Account, Money(balance), SignedMoney(change)],
            tone);
    }

    private static string PeriodLabel(HomeBalanceWindow? window)
    {
        if (window is null)
            return "";
        if (window.Period == HomePeriod.All
            || window.Start.DayNumber - window.RequestedStart.DayNumber > 7)
            return $"since {window.Start:MMM yyyy}";
        string label = window.Period switch
        {
            HomePeriod.ThreeMonths => "3M",
            HomePeriod.SixMonths => "6M",
            HomePeriod.OneYear => "1Y",
            HomePeriod.TwoYears => "2Y",
            HomePeriod.FiveYears => "5Y",
            _ => throw new ArgumentOutOfRangeException(nameof(window))
        };
        return $"over {label}";
    }

    private static ReportMetric ChangeMetric(string label, decimal current, decimal opening, string period)
    {
        decimal change = current - opening;
        return new(label, current, Money(current), change > 0m ? "positive" : change < 0m ? "negative" : null,
            $"{SignedMoney(change)} {period}", change);
    }

    private static ReportMetric LiabilityMetric(decimal current, decimal opening, string period)
    {
        decimal change = decimal.Abs(current) - decimal.Abs(opening);
        return new("Liabilities", decimal.Abs(current), Money(decimal.Abs(current)),
            change < 0m ? "positive" : change > 0m ? "negative" : null,
            $"{SignedMoney(change)} {period}", change);
    }

    private static DashboardWidgetReport Metrics(params ReportMetric[] metrics)
        => new(metrics, [], [], []);

    private static DashboardWidgetReport Chart(params ReportSeries[] series)
        => new([], series, [], [], series.Length == 0 ? "No data is available for this selection." : null);

    private static DashboardWidgetReport EmptyBalances()
        => new([], [], [], [], "No visible account balances are available.");

    private static ReportSeries Series(string id, string label, IEnumerable<ReportPoint> points)
        => new(id, label, points.ToArray());

    private static ReportPoint Point(DateOnly date, decimal value)
        => new(date, null, date.DayNumber, value);

    private static ReportPoint Point(string category, decimal value)
        => new(null, category, 0m, value);

    private static ReportMetric Metric(string label, decimal? value, string? display = null, string? tone = null)
        => new(label, value, display ?? (value is null ? "—" : Money(value.Value)), tone);

    private static string Money(decimal value) => value.ToString("C0", MoneyCulture);

    private static string SignedMoney(decimal value)
        => value == 0m ? Money(value) : $"{(value > 0m ? "+" : "-")}{Money(decimal.Abs(value))}";

    private static string Percent(decimal? value) => value is null ? "—" : $"{value:0.0}%";
}
