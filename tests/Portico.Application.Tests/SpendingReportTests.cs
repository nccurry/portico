using Portico.Finance;

namespace Portico.Application.Tests;

public sealed class SpendingReportTests
{
    [Fact]
    public async Task Spending_UsesVisibleExpensesAndMatchesFinanceSummary()
    {
        FinancialTransaction[] rows =
        [
            ReportWorkspaceFixture.Transaction("feb", 2026, 2, 2, "Needs", "Food", -50m),
            ReportWorkspaceFixture.Transaction("mar-food", 2026, 3, 4, "Needs", "Food", -100m),
            ReportWorkspaceFixture.Transaction("mar-rent", 2026, 3, 5, "Needs", "Rent", -200m),
            ReportWorkspaceFixture.Transaction("hidden", 2026, 3, 6, "Needs", "Food", -999m, hidden: true),
            ReportWorkspaceFixture.Transaction("salary", 2026, 3, 7, "Work", "Salary", 1000m, TransactionKind.Income)
        ];
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(rows, [], []));
        var request = new SpendingReportRequest(LookbackMonths: 1, DetailMonth: new YearMonth(2026, 3));

        SpendingReport report = workspace.Spending(request);
        SpendingAnalysisResult direct = SpendingAnalysisCalculator.Build(
            rows.Where(row => !row.IsHidden), ReportWorkspaceFixture.Settings(), "all", 1,
            SpendingComparison.PreviousPeriod, SpendingBreakdown.Category,
            SpendingAdjustments.Default(100m));

        Assert.Equal(direct.Summary, report.Analysis.Summary);
        Assert.Equal(300m, report.Analysis.Summary.TotalSpending);
        Assert.Equal(new DateOnly(2026, 3, 5), report.LatestExpenseDate);
        Assert.Equal("Rent", report.SelectedEntity!.Entity);
        Assert.Equal(new YearMonth(2026, 3), report.DetailMonth);
        Assert.Equal(new YearMonth(2026, 2), report.ComparisonMonth);
        Assert.Equal(["mar-rent"], report.CurrentDetail.Select(row => row.Transaction.Id));
        Assert.Empty(report.ComparisonDetail);
        Assert.Equal(200m, Assert.Single(report.Merchants).Spending);
        Assert.Equal(200m, report.DetailSummary.Spending);
        Assert.Equal(200m / 300m * 100m, report.DetailSummary.SharePercent);
        Assert.Equal(0, report.ExcludedCount);
    }

    [Fact]
    public async Task Spending_SelectionFallsBackAndUnselectedMonthMeansAll()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
        [
            ReportWorkspaceFixture.Transaction("feb", 2026, 2, 1, "Needs", "Food", -40m),
            ReportWorkspaceFixture.Transaction("mar", 2026, 3, 1, "Needs", "Food", -60m)
        ], [], []));

        SpendingReport report = workspace.Spending(new SpendingReportRequest(
            LookbackMonths: 2,
            Entity: "missing",
            DetailMonth: new YearMonth(2025, 1)));

        Assert.Equal("Food", report.SelectedEntity!.Entity);
        Assert.Null(report.DetailMonth);
        Assert.Null(report.ComparisonMonth);
        Assert.Equal(["mar", "feb"], report.CurrentDetail.Select(row => row.Transaction.Id));
        Assert.Equal(2, report.History.Count);
        Assert.Equal(100m, report.History.Sum(row => row.Current));
    }

    [Fact]
    public async Task Spending_EmptyRowsAndInvalidChoices()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot([], [], []));

        SpendingReport report = workspace.Spending();

        Assert.Null(report.SelectedEntity);
        Assert.Empty(report.CurrentDetail);
        Assert.Empty(report.History);
        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.Spending(
            new SpendingReportRequest(LookbackMonths: 0)));
        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.Spending(
            new SpendingReportRequest(Comparison: (SpendingComparison)99)));
        Assert.Throws<ArgumentException>(() => workspace.Spending(
            new SpendingReportRequest(TransactionSet: "missing")));
    }

    [Fact]
    public async Task Spending_ExcludedRowsDoNotBecomeDetailOrOverview()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
        [
            ReportWorkspaceFixture.Transaction("visible", 2026, 3, 1, "Needs", "Food", -20m),
            ReportWorkspaceFixture.Transaction("hidden", 2026, 3, 2, "Needs", "Food", -99m, hidden: true)
        ], [], []));
        var adjustments = new SpendingAdjustments(["Needs"], [], [], [], false, 100m);

        SpendingReport report = workspace.Spending(new SpendingReportRequest(
            LookbackMonths: 1, Adjustments: adjustments));

        Assert.Equal(1, report.ExcludedCount);
        Assert.Equal(20m, report.ExcludedSpending);
        Assert.Null(report.SelectedEntity);
        Assert.Empty(report.CurrentDetail);
        Assert.Empty(report.Analysis.Overview);
    }

    [Fact]
    public async Task Spending_BlankCategoryUsesSameEntityAsFinance()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
            [ReportWorkspaceFixture.Transaction("blank", 2026, 3, 1, "Needs", "", -15m)], [], []));

        SpendingReport report = workspace.Spending(new SpendingReportRequest(LookbackMonths: 1));

        Assert.Equal("Unknown", report.SelectedEntity!.Entity);
        Assert.Equal(["blank"], report.CurrentDetail.Select(row => row.Transaction.Id));
    }

    [Fact]
    public async Task Spending_GroupDetailCalculatesCategoryComparisonAndStableOrder()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
        [
            ReportWorkspaceFixture.Transaction("prior-food", 2026, 2, 2, "Needs", "Food", -30m),
            ReportWorkspaceFixture.Transaction("current-fuel", 2026, 3, 3, "Needs", "Fuel", -20m),
            ReportWorkspaceFixture.Transaction("current-food", 2026, 3, 4, "Needs", "Food", -50m)
        ], [], []));

        SpendingReport report = workspace.Spending(new SpendingReportRequest(
            LookbackMonths: 1,
            Breakdown: SpendingBreakdown.Group,
            Entity: "Needs",
            DetailMonth: new YearMonth(2026, 3)));

        Assert.Equal(70m, report.DetailSummary.Spending);
        Assert.Equal(30m, report.DetailSummary.ComparisonSpending);
        Assert.Equal(40m, report.DetailSummary.Change);
        Assert.Equal(["Food", "Fuel"], report.Categories.Select(row => row.Category));
        Assert.Equal([50m, 20m], report.Categories.Select(row => row.Spending));
        Assert.Equal(30m, report.Categories[0].ComparisonSpending);
        Assert.Equal(20m, report.Categories[0].Change);
        Assert.Equal(1, report.Categories[0].Transactions);
    }
}
