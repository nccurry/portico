using Portico.Finance;

namespace Portico.Application.Tests;

public sealed class BudgetReportTests
{
    [Fact]
    public async Task Budget_DefaultSelectionMatchesFinanceAndSkipsHiddenRows()
    {
        BudgetEntry[] budgets =
        [
            ReportWorkspaceFixture.Budget(2026, 3, "Needs", "Food", 300m),
            ReportWorkspaceFixture.Budget(2026, 3, "Housing", "Rent", 1000m),
            ReportWorkspaceFixture.Budget(2026, 3, "Hidden", "Secret", 9000m, hidden: true)
        ];
        FinancialTransaction[] rows =
        [
            ReportWorkspaceFixture.Transaction("food", 2026, 3, 4, "Needs", "Food", -100m),
            ReportWorkspaceFixture.Transaction("rent", 2026, 3, 5, "Housing", "Rent", -800m),
            ReportWorkspaceFixture.Transaction("hidden", 2026, 3, 6, "Needs", "Food", -999m, hidden: true)
        ];
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(rows, [], budgets));

        BudgetReport report = workspace.Budget();
        BudgetAnalysisResult direct = BudgetAnalysisCalculator.Build(budgets, rows, report.Analysis.Request);

        Assert.Equal(new YearMonth(2026, 3), report.Analysis.Request.SelectedMonth);
        Assert.Equal(["Housing", "Needs"], report.Analysis.Request.Groups);
        Assert.Equal(direct.Summary, report.Analysis.Summary);
        Assert.Equal(1300m, report.Analysis.Summary.Budget);
        Assert.Equal(900m, report.Analysis.Summary.Spent);
        Assert.Equal("Housing", report.SelectedGroup);
        Assert.Null(report.SelectedCategory);
        Assert.Equal(["rent"], report.Transactions.Select(row => row.Id));
    }

    [Fact]
    public async Task Budget_SelectedGroupAndCategoryFallBackWhenUnavailable()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
        [
            ReportWorkspaceFixture.Transaction("food", 2026, 3, 1, "Needs", "Food", -60m),
            ReportWorkspaceFixture.Transaction("fuel", 2026, 3, 2, "Needs", "Fuel", -40m)
        ], [],
        [
            ReportWorkspaceFixture.Budget(2026, 3, "Needs", "Food", 100m),
            ReportWorkspaceFixture.Budget(2026, 3, "Needs", "Fuel", 50m)
        ]));

        BudgetReport selected = workspace.Budget(new BudgetReportRequest(Group: "Needs", Category: "Fuel"));
        BudgetReport fallback = workspace.Budget(new BudgetReportRequest(Group: "missing", Category: "missing"));

        Assert.Equal("Fuel", selected.SelectedCategory);
        Assert.Equal(["fuel"], selected.Transactions.Select(row => row.Id));
        Assert.Equal("Needs", fallback.SelectedGroup);
        Assert.Null(fallback.SelectedCategory);
        Assert.Equal(["food", "fuel"], fallback.Transactions.Select(row => row.Id));
    }

    [Fact]
    public async Task Budget_ExplicitMonthAndThroughDateControlPace()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
        [
            ReportWorkspaceFixture.Transaction("feb", 2026, 2, 10, "Needs", "Food", -25m),
            ReportWorkspaceFixture.Transaction("mar", 2026, 3, 1, "Needs", "Food", -50m)
        ], [],
        [
            ReportWorkspaceFixture.Budget(2026, 2, "Needs", "Food", 100m),
            ReportWorkspaceFixture.Budget(2026, 3, "Needs", "Food", 100m)
        ]));
        var selected = new BudgetRequest(new YearMonth(2026, 2), ["Needs"],
            SpendingAdjustments.Default(100m), 2, new DateOnly(2026, 2, 15));

        BudgetReport report = workspace.Budget(new BudgetReportRequest(selected));

        Assert.Equal(25m, report.Analysis.Summary.Spent);
        Assert.Equal(15, report.Analysis.DailyPace.Count);
        Assert.Equal(new DateOnly(2026, 2, 15), report.Analysis.DailyPace[^1].Date);
        Assert.Equal(15m / 28m, report.Analysis.MonthProgress);
        Assert.Equal(["feb"], report.Transactions.Select(row => row.Id));
    }

    [Fact]
    public async Task Budget_EmptyRowsAndInvalidHistory()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot([], [], []));

        BudgetReport report = workspace.Budget();

        Assert.Empty(report.Analysis.Groups);
        Assert.Null(report.SelectedGroup);
        Assert.Empty(report.Transactions);
        Assert.Empty(workspace.BudgetOverview().Categories);
        Assert.Empty(workspace.BudgetOverview().History);
        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.Budget(new BudgetReportRequest(
            new BudgetRequest(new YearMonth(2026, 3), ["Needs"], SpendingAdjustments.Default(100m), 0,
                new DateOnly(2026, 3, 1)))));
    }

    [Fact]
    public async Task BudgetOverview_PreservesBroadCategoryPathAndCalendarHistory()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
        [
            ReportWorkspaceFixture.Transaction("food", 2026, 3, 1, "Needs", "Food", -50m),
            ReportWorkspaceFixture.Transaction("rent", 2026, 3, 2, "Housing", "Rent", -200m),
            ReportWorkspaceFixture.Transaction("old", 2026, 2, 1, "Needs", "Food", -10m),
            ReportWorkspaceFixture.Transaction("hidden", 2026, 3, 3, "Needs", "Food", -999m, hidden: true)
        ], [],
        [
            ReportWorkspaceFixture.Budget(2026, 3, "Needs", "Food", 100m),
            ReportWorkspaceFixture.Budget(2026, 3, "Housing", "Rent", 300m)
        ]));

        BudgetOverviewReport report = workspace.BudgetOverview(lookbackMonths: 1);

        Assert.Equal(["Food", "Rent"], report.Categories.Select(row => row.Category));
        Assert.Equal([50m, 200m], report.Categories.Select(row => row.Spent));
        Assert.Equal(400m, report.Budget);
        Assert.Equal(250m, report.Spent);
        Assert.Equal([new YearMonth(2026, 1), new YearMonth(2026, 2), new YearMonth(2026, 3)],
            report.History.Select(row => row.Month));
        Assert.Equal(10m, report.History[1].Spent);
        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.BudgetOverview(0));
    }

    [Fact]
    public async Task BudgetOverview_ClipsLookbackAtFirstCalendarMonth()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
            [ReportWorkspaceFixture.Transaction("first", 1, 1, 1, "Needs", "Food", -5m)],
            [],
            [ReportWorkspaceFixture.Budget(1, 1, "Needs", "Food", 10m)]));

        BudgetOverviewReport report = workspace.BudgetOverview(lookbackMonths: 12);

        Assert.Equal(5m, Assert.Single(report.Categories).Spent);
        Assert.Equal(new YearMonth(1, 1), Assert.Single(report.History).Month);
    }
}
