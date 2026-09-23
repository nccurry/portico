using Portico.Application;
using Portico.Finance;
using static Portico.Desktop.PlanHealthFormat;

namespace Portico.Desktop;

public sealed partial record DashboardPageReport
{
    public FinancialIndependencePageView? FinancialIndependenceView { get; init; }
}

/// <summary>Financial Independence detail used by the existing desktop page.</summary>
public sealed record FinancialIndependencePageView(
    string? LatestDataCaption,
    FinancialIndependenceSourceAnalysis Source,
    FinancialIndependenceScenario Scenario,
    FinancialIndependenceSummary Summary,
    IReadOnlyList<PortfolioProjectionPoint> Projection,
    IReadOnlyList<RunwaySensitivityCell> Sensitivity,
    string? EmptyMessage = null);

/// <summary>Turns semantic Financial Independence values into desktop widgets.</summary>
public static class FinancialIndependenceDashboardMapper
{
    public static DashboardPageReport Build(FinancialIndependenceReport report, DateOnly reportDate)
    {
        ArgumentNullException.ThrowIfNull(report);
        FinancialIndependenceSummary summary = report.Summary;
        FinancialIndependenceSourceAnalysis source = report.Source;
        FinancialIndependenceScenario scenario = report.Scenario;
        string runway = summary.RunwayYears is null ? "Sustainable" : $"{summary.RunwayYears:0.0} years";
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["fi.summary"] = Metrics(
                new ReportMetric("Runway", summary.RunwayYears, runway,
                    summary.RunwayYears is null ? "positive" : null,
                    summary.RunwayYears is null ? "Portfolio does not deplete" : "Until portfolio reaches $0"),
                new ReportMetric("Annual gap", summary.AnnualSurplus, SignedMoney(summary.AnnualSurplus),
                    summary.AnnualSurplus >= 0m ? "positive" : "negative",
                    summary.AnnualSurplus >= 0m ? "Annual surplus" : "Annual shortfall"),
                new ReportMetric("Net portfolio spending", summary.NetAnnualSpending, Money(summary.NetAnnualSpending),
                    null, $"{Money(summary.SustainableSpending)} supported at withdrawal rate"),
                new ReportMetric("FI target", summary.FinancialIndependenceTarget, Money(summary.FinancialIndependenceTarget),
                    summary.FundingGap >= 0m ? "positive" : "negative",
                    summary.FundingGap >= 0m ? $"{Money(summary.FundingGap)} above target"
                        : $"{Money(-summary.FundingGap)} still needed")),
            ["fi.projection"] = Chart(Series("portfolio", "Projected portfolio",
                report.Projection.Select(point => ProjectionPoint(reportDate, point)))),
            ["fi.funding"] = Chart(
                Series("investment-return", "Investment return", [Point("Annual funding", summary.AnnualReturn)]),
                Series("earned-income", "Earned income", [Point("Annual funding", summary.AnnualIncome)]),
                Series("spending", "Spending", [Point("Annual funding", -summary.AnnualSpending)])),
            ["fi.sensitivity"] = SensitivityReport(report.Sensitivity, scenario.AnnualSpending),
            ["fi.source_accounts"] = new([], [], ["Group", "Account", "Balance"],
                source.Accounts.Select(account => new ReportTableRow([
                    account.Group, account.Account, Money(account.SignedBalance)
                ])).ToArray(),
                source.Accounts.Count == 0 ? "No portfolio accounts are selected." : null),
            ["fi.source_spending"] = Chart(Series("spending", "Spending",
                source.MonthlySpending.Select(entry => Point(entry.Month.Start, entry.Spending)))),
            ["fi.source_transactions"] = new([], [],
                ["Date", "Description", "Group", "Category", "Account", "Spending"],
                source.Expenses.Select(transaction => new ReportTableRow([
                    Date(transaction.Date), transaction.Description, transaction.Group,
                    transaction.Category, transaction.Account, Money(-transaction.Amount)
                ])).ToArray(),
                source.Expenses.Count == 0 ? "No expense rows are included in this source range." : null)
        };
        return new DashboardPageReport(DashboardPageId.FinancialIndependence, widgets)
        {
            FinancialIndependenceView = new FinancialIndependencePageView(
                report.LatestTransactionDate is null ? null : $"Transactions through {Date(reportDate)}",
                source, scenario, summary, report.Projection, report.Sensitivity,
                report.LatestTransactionDate is null && report.LatestBalanceDate is null
                    ? "Transaction and balance history are required for this analysis." : null)
        };
    }

    private static DashboardWidgetReport SensitivityReport(
        IReadOnlyList<RunwaySensitivityCell> sensitivity, decimal baselineSpending)
        => new([], sensitivity
                .GroupBy(cell => cell.ReturnRate)
                .OrderBy(group => group.Key)
                .Select(group => Series($"return-{group.Key:0.##}", $"{group.Key:0.##}% return",
                    group.Select(cell => Point(SpendingChangeLabel(cell.AnnualSpending, baselineSpending),
                        cell.RunwayYears ?? 100m))))
                .ToArray(),
            ["Spending change", "Return", "Runway"],
            sensitivity.Select(cell => new ReportTableRow([
                SpendingChangeLabel(cell.AnnualSpending, baselineSpending),
                $"{cell.ReturnRate:0.##}%",
                cell.RunwayYears is null ? "Sustainable" : $"{cell.RunwayYears:0.0} years"
            ])).ToArray(),
            "A sustainable scenario is shown without a finite runway.")
        {
            HeatmapCells = sensitivity.Select(cell => new ReportHeatmapCell(
                SpendingChangeLabel(cell.AnnualSpending, baselineSpending),
                $"{cell.ReturnRate:0.##}% return",
                cell.RunwayYears ?? 100m,
                cell.RunwayYears is null ? "Sustainable" : $"{cell.RunwayYears:0.0} years")).ToArray()
        };

    private static ReportPoint ProjectionPoint(DateOnly reportDate, PortfolioProjectionPoint point)
        => point.Year <= 9999 - reportDate.Year
            ? Point(new DateOnly(reportDate.Year + point.Year, 1, 1), point.Balance)
            : new ReportPoint(null, $"Year {point.Year}", point.Year, point.Balance);

    private static string SpendingChangeLabel(decimal spending, decimal baseline)
    {
        if (baseline == 0m)
            return "Baseline";
        decimal change = (spending / baseline - 1m) * 100m;
        return change == 0m ? "Baseline" : $"{change:+0;-0;0}%";
    }
}
