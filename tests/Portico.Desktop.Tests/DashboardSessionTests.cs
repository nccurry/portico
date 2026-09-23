using Portico.Application;
using Portico.Configuration;
using Portico.Finance;

namespace Portico.Desktop.Tests;

public sealed class DashboardSessionTests
{
    [Fact]
    public async Task FirstOpenBuildsEveryConfiguredPageFromWorkspaceReports()
    {
        (Workspace workspace, DashboardDefinition definition) = await Open();

        var session = new DashboardSession(workspace, definition);

        Assert.Equal(DashboardPageId.Home, session.CurrentPage);
        Assert.Equal(10, session.Report.Pages.Count);
        foreach (DashboardPageDefinition page in definition.Pages)
        {
            DashboardPageReport report = session.Report.Page(page.Id);
            foreach (DashboardWidgetDefinition widget in page.Widgets)
                Assert.Contains(widget.Report, report.Widgets.Keys);
        }
    }

    [Fact]
    public async Task ConfiguredControlsChangeTypedRequestsAndKeepAllPagesAvailable()
    {
        (Workspace workspace, DashboardDefinition definition) = await Open();
        var session = new DashboardSession(workspace, definition);

        session.SetControlValue(DashboardPageId.Home, "time_frame", "3m");
        session.SetControlValue(DashboardPageId.Spending, "comparison", "last_year");
        session.SetControlValue(DashboardPageId.IncomeSavings, "calculation", "actual");
        session.SelectPage(DashboardPageId.DataHealth);

        Assert.Equal(HomePeriod.ThreeMonths, session.Filters.HomeTimeFrame);
        Assert.Equal(SpendingComparison.LastYear, session.Filters.SpendingComparison);
        Assert.False(session.Filters.RegularIncome);
        Assert.Equal(DashboardPageId.DataHealth, session.CurrentPage);
        Assert.Equal(10, session.Report.Pages.Count);
    }

    [Fact]
    public async Task InvalidControlValueDoesNotChangeTheSession()
    {
        (Workspace workspace, DashboardDefinition definition) = await Open();
        var session = new DashboardSession(workspace, definition);
        DashboardReport report = session.Report;

        Assert.Throws<ArgumentException>(() => session.SetControlValue(
            DashboardPageId.Home, "time_frame", "private-account-token"));

        Assert.Same(report, session.Report);
        Assert.Equal(HomePeriod.OneYear, session.Filters.HomeTimeFrame);
    }

    [Fact]
    public async Task SpendingChoiceRebuildsFromTheSelectedTransactionSet()
    {
        var snapshot = new PortfolioSnapshot(
            [
                MapperWorkspaceFixture.Transaction("bill", new DateOnly(2026, 3, 1), "Bills", "Electric", -100m),
                MapperWorkspaceFixture.Transaction("fun", new DateOnly(2026, 3, 2), "Entertainment", "Movie", -50m)
            ],
            [MapperWorkspaceFixture.Balance("cash", new DateOnly(2026, 3, 2), 500m)],
            [MapperWorkspaceFixture.Budget("Bills", "Electric", 100m)]);
        (Workspace workspace, DashboardDefinition definition) = await Open(snapshot);
        var session = new DashboardSession(workspace, definition);

        Assert.Equal(50m, SpendingTotal(session));

        session.SetControlValue(DashboardPageId.Spending, "spending_view", "all");

        Assert.Equal(150m, SpendingTotal(session));
        Assert.Equal("all", session.Filters.SpendingSet);
    }

    [Fact]
    public async Task InvalidDirectFilterDoesNotKeepBrokenScenarioState()
    {
        (Workspace workspace, DashboardDefinition definition) = await Open();
        var session = new DashboardSession(workspace, definition);
        DashboardReport report = session.Report;
        FinancialIndependenceScenario? scenario = session.Filters.FinancialIndependenceScenario;

        Assert.Throws<ArgumentOutOfRangeException>(() => session.SetFilter("fi_assets", "-1"));

        Assert.Equal(scenario, session.Filters.FinancialIndependenceScenario);
        Assert.Same(report, session.Report);
    }

    private static decimal? SpendingTotal(DashboardSession session)
        => Assert.Single(session.Report.Page(DashboardPageId.Spending)
            .Widgets["spending.summary"].Metrics, metric => metric.Label == "Total spending").Value;

    private static async Task<(Workspace Workspace, DashboardDefinition Definition)> Open(PortfolioSnapshot? snapshot = null)
    {
        string root = FindRepositoryRoot();
        var application = new PorticoApplication(
            new TomlConfigurationReader(Path.GetTempPath()),
            new EmptyPortfolioReader(snapshot ?? new PortfolioSnapshot([], [], [])));
        OpenWorkspaceOutcome opened = await application.OpenWorkspaceAsync(
            new ConfigurationSelection(Path.Combine(root, "portico.toml")),
            cancellationToken: TestContext.Current.CancellationToken);
        Workspace workspace = opened switch
        {
            WorkspaceOpened value => value.GetWorkspace(),
            _ => throw new InvalidOperationException("Expected the checked-in configuration to open.")
        };
        DashboardReadOutcome read = DashboardConfigurationReader.Read(
            Path.Combine(root, "dashboard.toml"), workspace.ReportChoices);
        DashboardDefinition definition = read switch
        {
            DashboardReadSuccess value => value.Definition,
            _ => throw new InvalidOperationException("Expected the checked-in dashboard to load.")
        };
        return (workspace, definition);
    }

    private static string FindRepositoryRoot()
    {
        for (DirectoryInfo? directory = new(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            if (File.Exists(Path.Combine(directory.FullName, "dashboard.toml")))
                return directory.FullName;
        }

        throw new InvalidOperationException("The dashboard fixture was not found.");
    }

    private sealed class EmptyPortfolioReader(PortfolioSnapshot snapshot) : IPortfolioReader
    {
        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
            => Task.FromResult<PortfolioReadOutcome>(new PortfolioReadSuccess(snapshot));
    }
}
