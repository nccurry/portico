using Portico.Application;
using Portico.Desktop;
using Portico.Finance;

namespace Portico.Desktop.Tests;

public sealed class PlanHealthDashboardMapperTests
{
    [Fact]
    public async Task BudgetPreservesAllWidgetIdsAndSelectedGroupRows()
    {
        var date = new DateOnly(2026, 3, 10);
        Workspace workspace = await MapperWorkspaceFixture.Open(new PortfolioSnapshot(
            [
                MapperWorkspaceFixture.Transaction("food", date, "Needs", "Food", -60m),
                MapperWorkspaceFixture.Transaction("rent", date, "Housing", "Rent", -200m)
            ], [],
            [MapperWorkspaceFixture.Budget("Needs", "Food", 100m),
                MapperWorkspaceFixture.Budget("Housing", "Rent", 300m)]), date);

        DashboardPageReport needs = BudgetDashboardMapper.Build(
            workspace.Budget(new BudgetReportRequest(Group: "Needs")), workspace.AsOfDate, workspace.HasVisibleTransactions);
        DashboardPageReport housing = BudgetDashboardMapper.Build(
            workspace.Budget(new BudgetReportRequest(Group: "Housing")), workspace.AsOfDate, workspace.HasVisibleTransactions);

        Assert.Equal(12, needs.Widgets.Count);
        Assert.Equal("Spending through Mar 10, 2026", needs.BudgetView?.LatestDataCaption);
        Assert.Equal("Needs", needs.BudgetView?.SelectedGroup);
        Assert.Equal("Food", Assert.Single(needs.Widgets["budget.transactions"].Rows).Values[1]);
        Assert.Equal("Rent", Assert.Single(housing.Widgets["budget.transactions"].Rows).Values[1]);
        Assert.Equal(260m, needs.Widgets["budget.summary"].Metrics.Single(metric => metric.Label == "Spending").Value);
        Assert.Same(needs.Widgets["budget.performance"], needs.Widgets["budget.table"]);
    }

    [Fact]
    public async Task BudgetCaptionUsesAnyVisibleTransactionNotOnlyTheSelectedGroup()
    {
        var date = new DateOnly(2026, 3, 10);
        Workspace workspace = await MapperWorkspaceFixture.Open(new PortfolioSnapshot(
            [
                MapperWorkspaceFixture.Transaction("other", date, "Housing", "Rent", -200m),
                MapperWorkspaceFixture.Transaction("hidden", date, "Needs", "Food", -50m, hidden: true)
            ], [], [MapperWorkspaceFixture.Budget("Needs", "Food", 100m)]), date);
        BudgetReport report = workspace.Budget(new BudgetReportRequest(Group: "Needs"));

        Assert.Empty(report.Transactions);
        Assert.True(workspace.HasVisibleTransactions);
        Assert.Equal("Spending through Mar 10, 2026", BudgetDashboardMapper.Build(
            report, workspace.AsOfDate, workspace.HasVisibleTransactions).BudgetView?.LatestDataCaption);

        Workspace hiddenOnly = await MapperWorkspaceFixture.Open(new PortfolioSnapshot(
            [MapperWorkspaceFixture.Transaction("hidden", date, "Needs", "Food", -50m, hidden: true)], [],
            [MapperWorkspaceFixture.Budget("Needs", "Food", 100m)]), date);
        Assert.False(hiddenOnly.HasVisibleTransactions);
        Assert.Null(BudgetDashboardMapper.Build(hiddenOnly.Budget(), hiddenOnly.AsOfDate,
            hiddenOnly.HasVisibleTransactions).BudgetView?.LatestDataCaption);
    }

    [Fact]
    public async Task BudgetMapsTypedEmptyReasonToExistingPageCopy()
    {
        Workspace workspace = await MapperWorkspaceFixture.Open(new PortfolioSnapshot([], [], []));

        DashboardPageReport page = BudgetDashboardMapper.Build(
            workspace.Budget(), workspace.AsOfDate, workspace.HasVisibleTransactions);

        Assert.Equal(BudgetEmptyReason.NoGroupsSelected, page.BudgetView?.Analysis.EmptyReason);
        Assert.Equal("Select at least one budget group.", page.BudgetView?.EmptyMessage);
        Assert.Equal("Select at least one budget group.", page.Widgets["budget.summary"].EmptyMessage);
    }

    [Fact]
    public async Task FinancialIndependenceMapsScenarioAndSourceSelection()
    {
        var date = new DateOnly(2026, 3, 10);
        Workspace workspace = await MapperWorkspaceFixture.Open(new PortfolioSnapshot(
            [MapperWorkspaceFixture.Transaction("food", date, "Needs", "Food", -120m)],
            [MapperWorkspaceFixture.Balance("Checking", date, 500m)], []), date);
        FinancialIndependenceReport initial = workspace.FinancialIndependence();
        var changed = new FinancialIndependenceScenario(1000m, 240m, 60m, 3m, 5m, 2);
        FinancialIndependenceReport selected = workspace.FinancialIndependence(
            new FinancialIndependenceReportRequest(Scenario: changed));
        FinancialIndependenceReport noAccounts = workspace.FinancialIndependence(
            new FinancialIndependenceReportRequest(
                Source: new FinancialIndependenceSourceFilters([], 1, SpendingAdjustments.Default(100m))));

        DashboardPageReport firstPage = FinancialIndependenceDashboardMapper.Build(initial, workspace.AsOfDate);
        DashboardPageReport changedPage = FinancialIndependenceDashboardMapper.Build(selected, workspace.AsOfDate);
        DashboardPageReport noAccountsPage = FinancialIndependenceDashboardMapper.Build(noAccounts, workspace.AsOfDate);

        Assert.Equal(7, firstPage.Widgets.Count);
        Assert.Equal("Transactions through Mar 10, 2026", firstPage.FinancialIndependenceView?.LatestDataCaption);
        Assert.Equal(1000m, changedPage.FinancialIndependenceView?.Scenario.Assets);
        Assert.Equal(3, changedPage.Widgets["fi.projection"].Series.Single().Points.Count);
        Assert.Equal(3600m, changedPage.Widgets["fi.summary"].Metrics.Single(metric => metric.Label == "FI target").Value);
        Assert.Equal("Spending", changedPage.Widgets["fi.source_spending"].Series.Single().Label);
        Assert.NotEmpty(firstPage.Widgets["fi.source_accounts"].Rows);
        Assert.Empty(noAccountsPage.Widgets["fi.source_accounts"].Rows);
    }

    [Fact]
    public async Task FinancialIndependenceEmptySourceKeepsEmptyPanelMessageAndWidgets()
    {
        Workspace workspace = await MapperWorkspaceFixture.Open(new PortfolioSnapshot([], [], []));

        DashboardPageReport page = FinancialIndependenceDashboardMapper.Build(
            workspace.FinancialIndependence(), workspace.AsOfDate);

        Assert.Equal(7, page.Widgets.Count);
        Assert.Null(page.FinancialIndependenceView?.LatestDataCaption);
        Assert.Equal("Transaction and balance history are required for this analysis.",
            page.FinancialIndependenceView?.EmptyMessage);
        Assert.Equal("No portfolio accounts are selected.", page.Widgets["fi.source_accounts"].EmptyMessage);
    }

    [Fact]
    public async Task FinancialIndependenceProjectionKeepsValuesAtCalendarMaximum()
    {
        var date = new DateOnly(9999, 12, 31);
        Workspace workspace = await MapperWorkspaceFixture.Open(new PortfolioSnapshot(
            [], [MapperWorkspaceFixture.Balance("Checking", date, 500m)], []), date);

        DashboardPageReport page = FinancialIndependenceDashboardMapper.Build(
            workspace.FinancialIndependence(), workspace.AsOfDate);

        IReadOnlyList<ReportPoint> points = page.Widgets["fi.projection"].Series.Single().Points;
        Assert.Equal(11, points.Count);
        Assert.Equal(new DateOnly(9999, 1, 1), points[0].Date);
        Assert.Equal("Year 10", points[^1].Category);
        Assert.Equal(page.FinancialIndependenceView?.Projection[^1].Balance, points[^1].Y);
    }

    [Fact]
    public async Task DataHealthMapsTypedChecksAndChangesSelectedDetail()
    {
        var date = new DateOnly(2026, 3, 10);
        Workspace workspace = await MapperWorkspaceFixture.Open(new PortfolioSnapshot(
            [
                MapperWorkspaceFixture.Transaction("first", date, "Needs", "Food", -20m),
                MapperWorkspaceFixture.Transaction("second", date, "Needs", "Food", -20m)
            ], [], []), date);

        DashboardPageReport first = DataHealthDashboardMapper.Build(workspace.DataHealth());
        DashboardPageReport duplicate = DataHealthDashboardMapper.Build(workspace.DataHealth(
            new DataHealthReportRequest(SelectedCheckId: "duplicates")));

        Assert.Equal(4, first.Widgets.Count);
        Assert.Equal(6, first.DataHealthView?.Analysis.Checks.Count);
        Assert.Equal("Missing classifications", first.DataHealthView?.Analysis.Checks[0].Name);
        Assert.Equal(
            ["Missing classifications", "Missing transaction details", "Account mapping gaps",
                "Stale balance accounts", "Potential duplicate transactions", "Refunds and income reversals"],
            first.DataHealthView?.Analysis.Checks.Select(check => check.Name));
        Assert.Equal("duplicates", duplicate.DataHealthView?.SelectedCheckId);
        Assert.Equal("Potential duplicate transactions", duplicate.DataHealthView?.SelectedCheck.Name);
        Assert.Equal("Review", duplicate.Widgets["health.queue"].Rows[4].Values[0]);
        Assert.Equal("warning", Assert.Single(duplicate.Widgets["health.detail"].Rows).Tone);
        Assert.Equal("Date 1", duplicate.Widgets["health.detail"].Columns[0]);
        Assert.Same(duplicate.Widgets["health.queue"], duplicate.Widgets["health.findings"]);
    }

    [Fact]
    public async Task DataHealthDetailUsesTheExistingWordingForTypedFindings()
    {
        var date = new DateOnly(2026, 3, 10);
        Workspace workspace = await MapperWorkspaceFixture.Open(new PortfolioSnapshot(
        [
            new FinancialTransaction("incomplete", date, "Food", "Living", "", "", -30m, TransactionKind.Expense),
            new FinancialTransaction("refund", date, "Food", "Living", "Checking", "Refund", 15m, TransactionKind.Expense),
            new FinancialTransaction("income-reversal", date, "Pay", "Income", "Checking", "Correction", -10m, TransactionKind.Income)
        ],
        [
            new BalanceObservation("", "Old account", "", new DateOnly(2026, 2, 1), TimeOnly.MinValue,
                100m, AccountClass.Asset, false)
        ], []), date);

        static DashboardWidgetReport Detail(Workspace workspace, string checkId)
            => DataHealthDashboardMapper.Build(workspace.DataHealth(
                new DataHealthReportRequest(SelectedCheckId: checkId))).Widgets["health.detail"];

        Assert.Equal("Account, Description", Assert.Single(Detail(workspace, "incomplete").Rows).Values[^1]);
        Assert.Equal("Account ID, Group", Assert.Single(Detail(workspace, "account_mapping").Rows).Values[^1]);
        Assert.Equal("37 days old", Assert.Single(Detail(workspace, "stale_accounts").Rows).Values[^1]);
        Assert.Equal(["Expense refund", "Income reversal"],
            Detail(workspace, "reversals").Rows.Select(row => row.Values[^1]).Order(StringComparer.Ordinal));
    }

    [Fact]
    public async Task DataHealthEmptySourceKeepsExistingEmptyPanelMessage()
    {
        Workspace workspace = await MapperWorkspaceFixture.Open(new PortfolioSnapshot([], [], []));

        DashboardPageReport page = DataHealthDashboardMapper.Build(workspace.DataHealth());

        Assert.Equal("No transaction or balance data is available.", page.DataHealthView?.EmptyMessage);
        Assert.Equal("No data", page.Widgets["health.summary"].Metrics.Single(metric => metric.Label == "Balances through").Display);
        Assert.Equal("No findings for this check.", page.Widgets["health.detail"].EmptyMessage);
        Assert.All(page.Widgets["health.queue"].Rows, row => Assert.Equal("Passed", row.Values[0]));
    }
}
