using System.Numerics;
using Portico.Adapters;
using Portico.App;
using Portico.Dashboard;
using Portico.Finance;
using Roci.Core;
using Roci.TestUtilities;
using Roci.Ui;
using Roci.Ui.Charts;

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
        Assert.True(HasNode(scene, "PorticoShell"));
        Assert.True(HasNode(scene, "NavigationRail"));
        Assert.True(HasNode(scene, "MainColumn"));
        Assert.True(HasNode(scene, "PageHeader"));
        Assert.True(HasNode(scene, "PageBody"));
        Assert.False(HasNode(scene, "TopBar"));
        Assert.False(HasNode(scene, "PorticoDrawerOverlay"));

        scene.SelectPage(DashboardPageId.Spending);
        scene.SetFilter("lookback", "6");
        scene.Refresh();

        Assert.Equal(DashboardPageId.Spending, session.CurrentPage);
        Assert.Equal(6, session.Filters.LookbackMonths);
        Assert.True(HasNode(scene, "Widget:categories"));
        Assert.True(HasNode(scene, "Chart:categories"));
    }

    [Fact]
    public async Task Scene_RendersLegacyDefinitionWithSafeRailFallbacks()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        PortfolioSnapshot snapshot = await new LocalCsvSnapshotSource(Path.Combine(root, "demo", "data"))
            .LoadAsync(TestContext.Current.CancellationToken);
        DashboardDefinition configured = Definition();
        DashboardDefinition legacy = configured with
        {
            Pages = configured.Pages
                .Select(page => page with
                {
                    NavigationGroup = DashboardNavigationGroup.Unspecified,
                    NavigationOrder = 0,
                    RailLabel = null,
                    PageHeading = null,
                    Icon = DashboardNavigationIcon.None
                })
                .ToArray()
        };

        var scene = new PorticoDashboardScene(
            new Vector2(1280f, 820f),
            new DashboardSession(snapshot, settings, legacy));

        Assert.Equal("Home", Text(scene, "NavigationLabel:Home"));
        Assert.Equal("?", Text(scene, "NavigationIcon:Home"));
        Assert.Equal("Home", Text(scene, "PageTitle"));
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
            if (page.Id == DashboardPageId.Spending)
            {
                Assert.True(HasNode(scene, "SpendingMetricDeck"));
                Assert.True(HasNode(scene, "Section:where_money_went"));
                Assert.True(HasNode(scene, "SpendingOverview"));
                Assert.True(HasNode(scene, "Section:selected_detail"));
                continue;
            }

            if (page.Id == DashboardPageId.IncomeSavings)
            {
                Assert.True(HasNode(scene, "IncomeSavingsControlBar"));
                Assert.True(HasNode(scene, "IncomeSavingsMetricDeck"));
                Assert.True(HasNode(scene, "Section:monthly_cash_flow"));
                Assert.True(HasNode(scene, "Section:month_detail"));
                Assert.True(HasNode(scene, "IncomeSavingsDetailTabs"));
                continue;
            }

            if (page.Id == DashboardPageId.YearOverYear)
            {
                Assert.True(HasNode(scene, "YearOverYearControlBar"));
                Assert.True(HasNode(scene, "Control:YearOverYear:View"));
                Assert.Contains(
                    scene.Stage.Root.GetSelfAndDescendants(),
                    node => node.Name?.StartsWith("YearOverYearComparison:", StringComparison.Ordinal) == true);
                continue;
            }

            if (page.Id == DashboardPageId.Subscriptions)
            {
                Assert.True(HasNode(scene, "SubscriptionsControlBar"));
                Assert.True(HasNode(scene, "SubscriptionsMetricDeck"));
                Assert.True(HasNode(scene, "Section:subscription_inventory"));
                Assert.True(HasNode(scene, "Section:subscription_lifecycle"));
                Assert.True(HasNode(scene, "Chart:lifecycle"));
                continue;
            }

            if (page.Id == DashboardPageId.Merchants)
            {
                Assert.True(HasNode(scene, "MerchantsControlBar"));
                Assert.True(HasNode(scene, "MerchantsMetricDeck"));
                Assert.True(HasNode(scene, "Section:merchant_rankings"));
                Assert.True(HasNode(scene, "Section:merchant_detail"));
                continue;
            }

            if (page.Id == DashboardPageId.TopTransactions)
            {
                Assert.True(HasNode(scene, "TransactionsControlBar"));
                Assert.True(HasNode(scene, "TransactionsMetricDeck"));
                Assert.True(HasNode(scene, "Chart:history"));
                Assert.True(HasNode(scene, "Section:transactions_table"));
                continue;
            }

            if (page.Id == DashboardPageId.Budget)
            {
                Assert.True(HasNode(scene, "BudgetControlBar"));
                Assert.True(HasNode(scene, "BudgetMetricDeck"));
                Assert.True(HasNode(scene, "Section:daily_budget_pace"));
                Assert.True(HasNode(scene, "Section:plan_comparison"));
                Assert.True(HasNode(scene, "Section:budget_group_detail"));
                Assert.True(HasNode(scene, "Year-to-date position"));
                continue;
            }

            if (page.Id == DashboardPageId.FinancialIndependence)
            {
                Assert.True(HasNode(scene, "FinancialIndependenceControlBar"));
                Assert.True(HasNode(scene, "Section:fi_scenario"));
                Assert.True(HasNode(scene, "FinancialIndependenceMetricDeck"));
                Assert.True(HasNode(scene, "Section:fi_projection"));
                Assert.True(HasNode(scene, "FinancialIndependenceFundingSplit"));
                Assert.True(HasNode(scene, "FinancialIndependenceSourceDetailsTabs"));
                continue;
            }

            if (page.Id == DashboardPageId.DataHealth)
            {
                Assert.True(HasNode(scene, "DataHealthControlBar"));
                Assert.True(HasNode(scene, "DataHealthMetricDeck"));
                Assert.True(HasNode(scene, "Section:health_checks"));
                Assert.True(HasNode(scene, "Section:health_detail"));
                continue;
            }

            Assert.All(page.Widgets, widget => Assert.True(HasNode(scene, $"Widget:{widget.Id}")));
        }

        scene.SelectPage(DashboardPageId.Subscriptions);
        scene.Refresh();
        Assert.True(HasNode(scene, "Chart:lifecycle"));
        ChartState subscriptions = GetChartState(scene, "Chart:lifecycle");
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
        ChartHeatmapSeries heatmap = Assert.Single(sensitivity.Series) switch
        {
            ChartHeatmapSeries value => value,
            _ => throw new Xunit.Sdk.XunitException("Expected the sensitivity chart to use a heatmap series.")
        };
        Assert.Equal(new Color(214, 105, 104), heatmap.Style.LowColor!.Value);
        Assert.Equal(new Color(93, 189, 174), heatmap.Style.HighColor!.Value);
        Assert.Equal(2f, heatmap.Style.CellGap);
    }

    [Fact]
    public async Task Scene_UsesTheAppOwnedDarkSkinAndNamedShellStyles()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        PortfolioSnapshot snapshot = await new LocalCsvSnapshotSource(Path.Combine(root, "demo", "data"))
            .LoadAsync(TestContext.Current.CancellationToken);
        var scene = new PorticoDashboardScene(new Vector2(1280f, 820f), new DashboardSession(snapshot, settings, Definition()));

        UiSkin skin = scene.Stage.Root.GetSkinOrDefault()
            ?? throw new Xunit.Sdk.XunitException("Expected the Portico scene to own a skin.");

        Assert.Equal("Portico Dark", skin.Name);
        Assert.Contains("portico-rail", skin.Panel.Styles.Keys);
        Assert.Contains("portico-main", skin.Panel.Styles.Keys);
        Assert.Contains("portico-raised", skin.Panel.Styles.Keys);
        Assert.Contains("portico-navigation-group", skin.Panel.Styles.Keys);
        Assert.Contains("portico-positive", skin.Panel.Styles.Keys);
        Assert.Contains("portico-negative", skin.Panel.Styles.Keys);
        Assert.Contains("portico-neutral", skin.Panel.Styles.Keys);
        Assert.Contains("portico-warning", skin.Panel.Styles.Keys);
        Assert.Contains("portico-loading", skin.Panel.Styles.Keys);
        Assert.Contains("portico-hidden", skin.Panel.Styles.Keys);
        Assert.Contains("portico-primary", skin.Button.Styles.Keys);
        Assert.Contains("portico-secondary", skin.Button.Styles.Keys);
        Assert.Contains("portico-quiet", skin.Button.Styles.Keys);
        Assert.Contains("portico-danger", skin.Button.Styles.Keys);
        Assert.Contains("portico-selected", skin.Button.Styles.Keys);
        Assert.Contains("portico-navigation", skin.Button.Styles.Keys);
        Assert.Contains("portico-navigation-selected", skin.Button.Styles.Keys);
        Assert.True(skin.Button.Styles["portico-navigation"].States.ContainsKey(UiSkinState.Hovered));
        Assert.True(skin.Button.Styles["portico-navigation"].States.ContainsKey(UiSkinState.Focused));
        Assert.Equal(new Color(16, 22, 30), FindNode(scene, "PorticoShell").VisualStyle.BackgroundColor);
        Assert.Equal(new Color(20, 30, 40), FindNode(scene, "NavigationRail").VisualStyle.BackgroundColor);
        Assert.Equal(new Color(31, 44, 57), FindNode(scene, "Widget:net-worth").VisualStyle.BackgroundColor);
        Assert.Equal(new Color(31, 44, 57), FindNode(scene, "Chart:net-worth").VisualStyle.BackgroundColor);
    }

    [Theory]
    [InlineData(1500, 1000)]
    [InlineData(1024, 720)]
    public async Task Scene_ShellKeepsTheRailHeaderAndBodyInsideTheViewport(int width, int height)
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        PortfolioSnapshot snapshot = await new LocalCsvSnapshotSource(Path.Combine(root, "demo", "data"))
            .LoadAsync(TestContext.Current.CancellationToken);
        var scene = new PorticoDashboardScene(new Vector2(width, height), new DashboardSession(snapshot, settings, Definition()));
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        LayoutNode shell = FindNode(scene, "PorticoShell");
        LayoutNode rail = FindNode(scene, "NavigationRail");
        LayoutNode main = FindNode(scene, "MainColumn");
        LayoutNode header = FindNode(scene, "PageHeader");
        LayoutNode body = FindNode(scene, "PageBody");

        Assert.Equal(new Vector2(width, height), shell.BoxModel.ComputedSize);
        Assert.Equal(232f, rail.BoxModel.ComputedSize.X);
        Assert.Equal((float)height, rail.BoxModel.ComputedSize.Y);
        Assert.Equal(0f, rail.ComputedPosition.X);
        Assert.Equal(0f, rail.ComputedPosition.Y);
        Assert.Equal(rail.ComputedPosition.X + rail.BoxModel.ComputedSize.X, main.ComputedPosition.X);
        Assert.Equal((float)height, main.BoxModel.ComputedSize.Y);
        AssertWithin(shell, rail);
        AssertWithin(shell, main);
        AssertWithin(main, header);
        AssertWithin(main, body);
        Assert.True(header.ComputedPosition.Y + header.BoxModel.ComputedSize.Y <= body.ComputedPosition.Y);
        Assert.NotNull(body.ScrollConfig);
        Assert.True(body.ScrollConfig!.Value.EnableVertical);
        Assert.False(body.ScrollConfig!.Value.EnableHorizontal);
        Assert.Null(rail.ScrollConfig);
    }

    [Fact]
    public async Task Scene_NarrowDesktopWrapsTwoCardRowInsteadOfClippingIt()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        PortfolioSnapshot snapshot = await new LocalCsvSnapshotSource(Path.Combine(root, "demo", "data"))
            .LoadAsync(TestContext.Current.CancellationToken);
        var scene = new PorticoDashboardScene(new Vector2(1024f, 720f), new DashboardSession(snapshot, settings, Definition()));
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        LayoutNode overview = FindNode(scene, "Widget:overview");
        LayoutNode safety = FindNode(scene, "Widget:safety");
        LayoutNode body = FindNode(scene, "PageBody");

        Assert.True(safety.ComputedPosition.Y > overview.ComputedPosition.Y);
        Assert.Equal(155f, overview.BoxModel.ComputedSize.Y);
        Assert.Equal(155f, safety.BoxModel.ComputedSize.Y);
        AssertWithinScrollContent(body, overview);
        AssertWithinScrollContent(body, safety);
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
                        new DashboardWidgetDefinition("overview", "Overview", DashboardWidgetKind.Metric, "home.overview"),
                        new DashboardWidgetDefinition("safety", "Safety", DashboardWidgetKind.Metric, "home.safety")
                    ],
                    NavigationGroup: DashboardNavigationGroup.Standalone,
                    NavigationOrder: 1,
                    RailLabel: "Home",
                    PageHeading: "Accounts and net worth",
                    Icon: DashboardNavigationIcon.Home),
                new DashboardPageDefinition(
                    DashboardPageId.Spending,
                    "Spending",
                    "Where money went.",
                    [
                        new DashboardFilterDefinition("lookback", "Lookback", DashboardFilterKind.Select, "lookback", "3", ["3", "6", "12", "24"]),
                        new DashboardFilterDefinition("spending", "View", DashboardFilterKind.Select, "spending", "all", ["all", "discretionary"])
                    ],
                    [new DashboardWidgetDefinition("categories", "Categories", DashboardWidgetKind.BarChart, "spending.categories", 2)],
                    NavigationGroup: DashboardNavigationGroup.Analyze,
                    NavigationOrder: 2,
                    RailLabel: "Spending by category",
                    PageHeading: "Spending by category",
                    Icon: DashboardNavigationIcon.Category)
            ]);

    private static bool HasNode(PorticoDashboardScene scene, string name)
        => scene.Stage.Root.GetSelfAndDescendants().Any(node => node.Name == name);

    private static string Text(PorticoDashboardScene scene, string name)
        => FindNode(scene, name).TextNodeState?.RawText
            ?? throw new Xunit.Sdk.XunitException($"Expected text node '{name}'.");

    private static LayoutNode FindNode(PorticoDashboardScene scene, string name)
    {
        return scene.Stage.Root.GetSelfAndDescendants().Single(node => node.Name == name);
    }

    private static ChartState GetChartState(PorticoDashboardScene scene, string name)
    {
        return scene.Stage.Root.GetSelfAndDescendants()
            .Single(node => node.Name == name)
            .GetStateOrDefault<ChartState>()
            ?? throw new Xunit.Sdk.XunitException($"Expected chart state for '{name}'.");
    }

    private static void AssertWithin(LayoutNode parent, LayoutNode child)
    {
        float parentRight = parent.ComputedPosition.X + parent.BoxModel.ComputedSize.X;
        float parentBottom = parent.ComputedPosition.Y + parent.BoxModel.ComputedSize.Y;
        float childRight = child.ComputedPosition.X + child.BoxModel.ComputedSize.X;
        float childBottom = child.ComputedPosition.Y + child.BoxModel.ComputedSize.Y;

        string bounds = $"Parent '{parent.Name}' at {parent.ComputedPosition} size {parent.BoxModel.ComputedSize}; child '{child.Name}' at {child.ComputedPosition} size {child.BoxModel.ComputedSize}.";
        Assert.True(child.ComputedPosition.X >= parent.ComputedPosition.X, bounds);
        Assert.True(child.ComputedPosition.Y >= parent.ComputedPosition.Y, bounds);
        Assert.True(childRight <= parentRight, bounds);
        Assert.True(childBottom <= parentBottom, bounds);
    }

    private static void AssertWithinScrollContent(LayoutNode scrollContainer, LayoutNode child)
    {
        ScrollState scroll = scrollContainer.ScrollState
            ?? throw new Xunit.Sdk.XunitException($"Expected '{scrollContainer.Name}' to have scroll state.");
        Rectangle content = scrollContainer.BoxModel.ContentBounds(scrollContainer.ComputedPosition);
        float contentRight = content.X + scroll.ContentSize.X;
        float contentBottom = content.Y + scroll.ContentSize.Y;
        float childRight = child.ComputedPosition.X + child.BoxModel.ComputedSize.X;
        float childBottom = child.ComputedPosition.Y + child.BoxModel.ComputedSize.Y;
        string bounds = $"Scroll container '{scrollContainer.Name}' content begins at {content.Position} with size {scroll.ContentSize}; child '{child.Name}' at {child.ComputedPosition} size {child.BoxModel.ComputedSize}.";

        Assert.True(child.ComputedPosition.X >= content.X, bounds);
        Assert.True(child.ComputedPosition.Y >= content.Y, bounds);
        Assert.True(childRight <= contentRight, bounds);
        Assert.True(childBottom <= contentBottom, bounds);
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
