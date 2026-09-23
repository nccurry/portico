using Portico.Finance;

namespace Portico.Application.Tests;

public sealed class IncomeReportTests
{
    [Fact]
    public async Task Income_UsesVisibleRowsAndMatchesFinanceTotals()
    {
        FinancialTransaction[] rows =
        [
            ReportWorkspaceFixture.Transaction("salary", 2026, 3, 2, "Work", "Salary", 1000m, TransactionKind.Income),
            ReportWorkspaceFixture.Transaction("groceries", 2026, 3, 3, "Needs", "Food", -200m),
            ReportWorkspaceFixture.Transaction("gift", 2026, 3, 4, "Other", "Gift", 50m, TransactionKind.Income),
            ReportWorkspaceFixture.Transaction("hidden", 2026, 3, 5, "Needs", "Food", -500m, hidden: true),
            ReportWorkspaceFixture.Transaction("older", 2026, 2, 1, "Needs", "Food", -40m)
        ];
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(rows, [], []));

        IncomeReport report = workspace.Income(new IncomeReportRequest(LookbackMonths: 1));
        IncomeSavingsAnalysisResult direct = IncomeSavingsAnalysisCalculator.Build(
            rows.Where(row => !row.IsHidden), 1,
            IncomeSavingsAdjustments.Default(ReportWorkspaceFixture.Settings(), regular: true));

        Assert.Equal(new YearMonth(2026, 3), report.DetailMonth);
        Assert.Equal(direct.CurrentSummary, report.Analysis.CurrentSummary);
        Assert.Equal(1000m, report.Detail!.Income);
        Assert.Equal(200m, report.Detail.NetExpenses);
        Assert.Equal(800m, report.Detail.Surplus);
        Assert.Equal(1000m, report.Comparison.Income);
        Assert.Equal(200m, report.Comparison.NetExpenses);
        Assert.Equal(800m, report.Comparison.Surplus);
        Assert.Equal(1000m, report.Comparison.IncomeChange);
        Assert.Equal(["groceries", "salary"], report.IncludedTransactions.Select(row => row.Transaction.Id));
        Assert.Equal(["gift"], report.ExcludedTransactions.Select(row => row.Transaction.Id));
        Assert.Equal(1, report.ExcludedCount);
        Assert.Equal(50m, report.ExcludedIncome);
        Assert.Equal(0m, report.ExcludedSpending);
        Assert.Equal([TransactionKind.Expense, TransactionKind.Income], report.Categories.Select(row => row.Kind));
        Assert.Equal([200m, 1000m], report.Categories.Select(row => row.Amount));
    }

    [Fact]
    public async Task Income_SelectsRequestedMonthOrFallsBackToLatest()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
        [
            ReportWorkspaceFixture.Transaction("feb", 2026, 2, 1, "Needs", "Food", -20m),
            ReportWorkspaceFixture.Transaction("mar", 2026, 3, 1, "Needs", "Food", -30m)
        ], [], []));

        IncomeReport selected = workspace.Income(new IncomeReportRequest(DetailMonth: new YearMonth(2026, 2)));
        IncomeReport fallback = workspace.Income(new IncomeReportRequest(DetailMonth: new YearMonth(2025, 1)));

        Assert.Equal(new YearMonth(2026, 2), selected.DetailMonth);
        Assert.Equal(["feb"], selected.IncludedTransactions.Select(row => row.Transaction.Id));
        Assert.Equal(new YearMonth(2026, 3), fallback.DetailMonth);
        Assert.Equal(["mar"], fallback.IncludedTransactions.Select(row => row.Transaction.Id));
    }

    [Fact]
    public async Task Income_ActualViewIncludesRowsExcludedByRegularView()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
            [ReportWorkspaceFixture.Transaction("gift", 2026, 3, 1, "Other", "Gift", 50m, TransactionKind.Income)],
            [], []));

        IncomeReport regular = workspace.Income(new IncomeReportRequest(LookbackMonths: 1));
        IncomeReport actual = workspace.Income(new IncomeReportRequest(LookbackMonths: 1, RegularIncome: false));

        Assert.Equal(0m, regular.Detail!.Income);
        Assert.Equal(50m, actual.Detail!.Income);
        Assert.Equal(["gift"], actual.IncludedTransactions.Select(row => row.Transaction.Id));
    }

    [Fact]
    public async Task Income_EmptyRowsAndInvalidLookback()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot([], [], []));

        IncomeReport report = workspace.Income();

        Assert.Null(report.DetailMonth);
        Assert.Null(report.Detail);
        Assert.Empty(report.Categories);
        Assert.Empty(report.IncludedTransactions);
        Assert.Empty(report.ExcludedTransactions);
        Assert.Throws<ArgumentOutOfRangeException>(() => workspace.Income(new IncomeReportRequest(LookbackMonths: 0)));
    }

    [Fact]
    public async Task Income_NearLastCalendarMonthIsSelectable()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot(
            [ReportWorkspaceFixture.Transaction("last", 9999, 11, 30, "Work", "Salary", 10m, TransactionKind.Income)],
            [], []));

        IncomeReport report = workspace.Income(new IncomeReportRequest(LookbackMonths: 1,
            DetailMonth: new YearMonth(9999, 11)));

        Assert.Equal(new YearMonth(9999, 11), report.DetailMonth);
        Assert.Equal(10m, report.Detail!.Income);
    }
}
