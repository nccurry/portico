using System.Numerics;
using Portico.Adapters;
using Portico.App;
using Portico.Dashboard;
using Portico.Finance;
using Roci.Ui;
using Roci.Ui.Processors;

namespace Portico.App.Tests;

public sealed class PorticoDashboardSceneTests
{
    [Fact]
    public async Task Scene_BuildsConfiguredWidgetsAndAppliesNavigationAndFilters()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        PortfolioSnapshot snapshot = await new LocalCsvSnapshotSource(Path.Combine(root, "demo", "data"))
            .LoadAsync(TestContext.Current.CancellationToken);
        var session = new DashboardSession(snapshot, settings, Definition());
        var scene = new PorticoDashboardScene(new Vector2(1280f, 820f), session);

        Assert.True(HasNode(scene, "Widget:net-worth"));
        Assert.True(HasNode(scene, "Chart:net-worth"));
        Assert.False(scene.IsDrawerOpen);

        scene.ToggleDrawer();
        scene.Refresh();

        Assert.True(scene.IsDrawerOpen);
        Assert.True(HasNode(scene, "PorticoDrawerOverlay"));
        Assert.True(HasNode(scene, "DrawerPage:Spending"));
        Assert.True(HasNode(scene, "DrawerCurrentPage:Home"));

        scene.SelectPage(DashboardPageId.Spending);
        scene.SetFilter("lookback", "6");
        scene.Refresh();

        Assert.False(scene.IsDrawerOpen);
        Assert.Equal(DashboardPageId.Spending, session.CurrentPage);
        Assert.Equal(6, session.Filters.LookbackMonths);
        Assert.True(HasNode(scene, "Widget:categories"));
        Assert.True(HasNode(scene, "Chart:categories"));

        scene.ToggleDrawer();
        scene.Refresh();

        Assert.True(HasNode(scene, "DrawerCurrentPage:Spending"));
        Assert.False(HasNode(scene, "DrawerCurrentPage:Home"));
    }

    [Fact]
    public async Task Scene_BuildsEveryVisiblePageFromTheCheckedInDashboard()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        DashboardDefinition definition = TomlConfigurationLoader.LoadDashboard(Path.Combine(root, "dashboard.toml"));
        PortfolioSnapshot snapshot = await new LocalCsvSnapshotSource(Path.Combine(root, "demo", "data"))
            .LoadAsync(TestContext.Current.CancellationToken);
        var session = new DashboardSession(snapshot, settings, definition, new DateOnly(2026, 8, 1));
        var scene = new PorticoDashboardScene(new Vector2(1280f, 820f), session);

        foreach (DashboardPageDefinition page in definition.Pages.Where(page => page.Visible))
        {
            scene.SelectPage(page.Id);
            scene.Refresh();

            Assert.Equal(page.Id, session.CurrentPage);
            Assert.All(page.Widgets, widget => Assert.True(HasNode(scene, $"Widget:{widget.Id}")));
        }

        scene.SelectPage(DashboardPageId.Subscriptions);
        scene.Refresh();
        Assert.True(HasNode(scene, "Chart:active"));
        ChartState subscriptions = GetChartState(scene, "Chart:active");
        Assert.True(Assert.Single(subscriptions.Series) is ChartTimelineSeries);
        Assert.True(Assert.Single(subscriptions.Guides) is ChartDateReferenceLine);

        scene.SelectPage(DashboardPageId.IncomeSavings);
        scene.Refresh();
        ChartState cashFlow = GetChartState(scene, "Chart:cash-flow");
        Assert.Contains(cashFlow.Series, series => series is ChartBarSeries);
        Assert.Contains(cashFlow.Series, series => series is ChartLineSeries);

        scene.SelectPage(DashboardPageId.FinancialIndependence);
        scene.Refresh();
        Assert.True(HasNode(scene, "Chart:sensitivity"));
        ChartState sensitivity = GetChartState(scene, "Chart:sensitivity");
        Assert.True(Assert.Single(sensitivity.Series) is ChartHeatmapSeries);
    }

    [Fact]
    public async Task Scene_DismissesTheDrawerWhenTheMenuReceivesCancel()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        PortfolioSnapshot snapshot = await new LocalCsvSnapshotSource(Path.Combine(root, "demo", "data"))
            .LoadAsync(TestContext.Current.CancellationToken);
        var scene = new PorticoDashboardScene(new Vector2(1280f, 820f), new DashboardSession(snapshot, settings, Definition()));

        scene.ToggleDrawer();
        scene.Refresh();
        LayoutNode firstPage = scene.Stage.Root.GetSelfAndDescendants().Single(node => node.Name == "DrawerPage:Home");
        SelectionProcessor.UpdateDetailed(scene.Stage.Root, new SelectionInput { FocusedNode = firstPage });
        SelectionProcessor.UpdateDetailed(scene.Stage.Root, new SelectionInput { CancelPressed = true });

        Assert.False(scene.IsDrawerOpen);
    }

    private static DashboardDefinition Definition()
        => new(
            1,
            "Portico",
            [
                new DashboardPageDefinition(
                    DashboardPageId.Home,
                    "Home",
                    "Overview",
                    [new DashboardFilterDefinition("lookback", "Lookback", DashboardFilterKind.Select, "lookback", "3", ["3", "6", "12", "24"])],
                    [
                        new DashboardWidgetDefinition("net-worth", "Net worth", DashboardWidgetKind.AreaChart, "home.net_worth", 2),
                        new DashboardWidgetDefinition("overview", "Overview", DashboardWidgetKind.Metric, "home.overview")
                    ]),
                new DashboardPageDefinition(
                    DashboardPageId.Spending,
                    "Spending",
                    "Where money went.",
                    [
                        new DashboardFilterDefinition("lookback", "Lookback", DashboardFilterKind.Select, "lookback", "3", ["3", "6", "12", "24"]),
                        new DashboardFilterDefinition("spending", "View", DashboardFilterKind.Select, "spending", "all", ["all", "discretionary"])
                    ],
                    [new DashboardWidgetDefinition("categories", "Categories", DashboardWidgetKind.BarChart, "spending.categories", 2)])
            ]);

    private static bool HasNode(PorticoDashboardScene scene, string name)
        => scene.Stage.Root.GetSelfAndDescendants().Any(node => node.Name == name);

    private static ChartState GetChartState(PorticoDashboardScene scene, string name)
    {
        return scene.Stage.Root.GetSelfAndDescendants()
            .Single(node => node.Name == name)
            .GetStateOrDefault<ChartState>()
            ?? throw new Xunit.Sdk.XunitException($"Expected chart state for '{name}'.");
    }

    private static string FindRepositoryRoot()
    {
        string[] startingPoints = [Directory.GetCurrentDirectory(), AppContext.BaseDirectory];
        foreach (string start in startingPoints)
        {
            var current = new DirectoryInfo(start);
            while (current is not null)
            {
                if (File.Exists(Path.Combine(current.FullName, "portico-demo.toml")))
                    return current.FullName;
                current = current.Parent;
            }
        }

        throw new InvalidOperationException("Could not find the Portico repository root.");
    }
}
