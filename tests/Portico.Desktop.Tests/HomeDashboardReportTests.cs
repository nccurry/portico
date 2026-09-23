using Portico.Application;
using Portico.Desktop;
using Portico.Finance;

namespace Portico.Desktop.Tests;

public sealed class HomeDashboardReportTests
{
    [Fact]
    public void EmptyHomeKeepsAllSixWidgetsAndTheirExistingEmptyMessages()
    {
        var home = new HomeReport(null, [], [], [], 0, EmptyCashFlow(), EmptySafety());

        DashboardPageReport page = HomeDashboardReport.Build(home);

        Assert.Equal(DashboardPageId.Home, page.PageId);
        Assert.Equal(6, page.Widgets.Count);
        Assert.Equal("No visible account balances are available.", page.Widgets["home.net_worth"].EmptyMessage);
        Assert.Equal("No mapped balance groups are available.", page.Widgets["home.accounts"].EmptyMessage);
        Assert.Equal("No visible account balances are available.", page.Widgets["home.inventory"].EmptyMessage);
        Assert.Equal("0", page.Widgets["home.overview"].Metrics.Single(metric => metric.Label == "Accounts").Display);
    }

    [Fact]
    public void HomeMapsSemanticMovementsWithoutRecalculatingBalances()
    {
        var start = new DateOnly(2026, 1, 1);
        var end = new DateOnly(2026, 1, 31);
        var home = new HomeReport(
            new HomeBalanceWindow(HomePeriod.OneYear, start.AddDays(-365), start, end),
            [new NetWorthPoint(start, 1000m, -400m, 600m), new NetWorthPoint(end, 1200m, -300m, 900m)],
            [new HomeGroupMovement("Debt", -400m, -300m, LiabilitiesOnly: true)],
            [new HomeAccountMovement("a1", "Credit card", "Debt", AccountClass.Liability, -400m, -300m)],
            2,
            new CashFlowSummary(500m, 300m, 200m, 40m, 200m, 1, 1),
            EmptySafety());

        DashboardPageReport page = HomeDashboardReport.Build(home);

        Assert.Equal(3, page.Widgets["home.net_worth"].Series.Count);
        Assert.Equal(900m, page.Widgets["home.overview"].Metrics.Single(metric => metric.Label == "Net worth").Value);
        Assert.Equal("2", page.Widgets["home.overview"].Metrics.Single(metric => metric.Label == "Accounts").Display);
        ReportMetric debt = Assert.Single(page.Widgets["home.accounts"].Metrics);
        Assert.Equal("$300", debt.Display);
        Assert.Equal("-$100", debt.Detail?.Split(' ')[0]);
        Assert.Equal("positive", debt.Tone);
        Assert.Equal(100m, debt.Change);
        ReportTableRow account = Assert.Single(page.Widgets["home.inventory"].Rows);
        Assert.Equal(["Debt", "Credit card", "$300", "-$100"], account.Values);
    }

    private static CashFlowSummary EmptyCashFlow() => new(0m, 0m, 0m, null, 0m, 0, 0);

    private static FinancialSafetySummary EmptySafety()
        => new(0m, 0m, 0m, null, 6, 0m, 0m, 0m, null, null, 0m, 1_000_000m, null);
}
