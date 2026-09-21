using System.Numerics;
using Portico.App;
using Portico.CaptureHost;
using Portico.Dashboard;
using Roci.Input;
using Roci.TestUtilities;
using Roci.Ui;
using Roci.Ui.Charts;
using Roci.Ui.Input;
using Roci.Ui.Rendering;

namespace Portico.App.Tests;

public sealed class PorticoDashboardNavigationTests
{
    private static readonly NavigationExpectation[] ExpectedPages =
    [
        new(DashboardPageId.Home, DashboardNavigationGroup.Standalone, 1, "Home", "Accounts and net worth", DashboardNavigationIcon.Home, "H"),
        new(DashboardPageId.IncomeSavings, DashboardNavigationGroup.Analyze, 2, "Income and savings", "Income and savings", DashboardNavigationIcon.Savings, "$"),
        new(DashboardPageId.Merchants, DashboardNavigationGroup.Analyze, 3, "Spending by merchant", "Spending by merchant", DashboardNavigationIcon.Storefront, "M"),
        new(DashboardPageId.Spending, DashboardNavigationGroup.Analyze, 4, "Spending by category", "Spending by category", DashboardNavigationIcon.Category, "C"),
        new(DashboardPageId.YearOverYear, DashboardNavigationGroup.Analyze, 5, "Year over year", "Year over year", DashboardNavigationIcon.CompareArrows, "Y"),
        new(DashboardPageId.Subscriptions, DashboardNavigationGroup.Analyze, 6, "Subscriptions", "Subscriptions", DashboardNavigationIcon.Subscriptions, "S"),
        new(DashboardPageId.TopTransactions, DashboardNavigationGroup.Analyze, 7, "Transactions", "Transactions", DashboardNavigationIcon.ReceiptLong, "T"),
        new(DashboardPageId.Budget, DashboardNavigationGroup.Plan, 8, "Budget", "Budget", DashboardNavigationIcon.AccountBalanceWallet, "B"),
        new(DashboardPageId.FinancialIndependence, DashboardNavigationGroup.Plan, 9, "Financial independence", "Financial independence", DashboardNavigationIcon.Monitoring, "F"),
        new(DashboardPageId.DataHealth, DashboardNavigationGroup.Maintain, 10, "Data health", "Data health", DashboardNavigationIcon.HealthAndSafety, "+")
    ];

    [Fact]
    public void Rail_UsesTheConfiguredPorticoHierarchyOrderLabelsHeadingsAndIcons()
    {
        DashboardSession session = CreateSession();
        var scene = CreateScene(session);

        DashboardPageDefinition[] configured = session.Definition.Pages
            .Where(page => page.Visible)
            .OrderBy(page => page.NavigationOrder)
            .ToArray();

        Assert.Equal(ExpectedPages.Select(page => page.Id), configured.Select(page => page.Id));
        Assert.Equal(ExpectedPages.Select(page => page.Group), configured.Select(page => page.NavigationGroup));
        Assert.Equal(ExpectedPages.Select(page => page.Order), configured.Select(page => page.NavigationOrder));
        Assert.Equal(ExpectedPages.Select(page => page.RailLabel), configured.Select(page => page.RailLabel));
        Assert.Equal(ExpectedPages.Select(page => page.PageHeading), configured.Select(page => page.PageHeading));
        Assert.Equal(ExpectedPages.Select(page => page.Icon), configured.Select(page => page.Icon));

        LayoutNode navigation = FindNode(scene, "NavigationItems");
        Assert.Equal(
        [
            "NavigationItem:Home",
            "NavigationGroup:Analyze",
            "NavigationGroup:Plan",
            "NavigationGroup:Maintain"
        ],
        navigation.Children.Select(node => node.Name));
        Assert.Equal(
            ["NavigationGroupLabel:Analyze", "NavigationItem:IncomeSavings", "NavigationItem:Merchants", "NavigationItem:Spending", "NavigationItem:YearOverYear", "NavigationItem:Subscriptions", "NavigationItem:TopTransactions"],
            FindNode(scene, "NavigationGroup:Analyze").Children.Select(node => node.Name));
        Assert.Equal(
            ["NavigationGroupLabel:Plan", "NavigationItem:Budget", "NavigationItem:FinancialIndependence"],
            FindNode(scene, "NavigationGroup:Plan").Children.Select(node => node.Name));
        Assert.Equal(
            ["NavigationGroupLabel:Maintain", "NavigationItem:DataHealth"],
            FindNode(scene, "NavigationGroup:Maintain").Children.Select(node => node.Name));
        Assert.Equal(["ANALYZE", "PLAN", "MAINTAIN"], GroupLabels(scene));
        Assert.DoesNotContain(
            scene.Stage.Root.GetSelfAndDescendants(),
            node => (node.Name ?? string.Empty).Contains("Placeholder", StringComparison.Ordinal));

        foreach (NavigationExpectation expected in ExpectedPages)
        {
            Assert.Equal(expected.RailLabel, Text(scene, $"NavigationLabel:{expected.Id}"));
            Assert.Equal(expected.IconGlyph, Text(scene, $"NavigationIcon:{expected.Id}"));

            scene.SelectPage(expected.Id);
            scene.Refresh();

            Assert.Equal(expected.PageHeading, Text(scene, "PageTitle"));
            Assert.True(FindNode(scene, $"NavigationItem:{expected.Id}").Active);
            Assert.All(
                ExpectedPages.Where(page => page.Id != expected.Id),
                other => Assert.False(FindNode(scene, $"NavigationItem:{other.Id}").Active));
        }
    }

    [Fact]
    public void Definition_RequiresEveryPageNavigationMetadataWhenAnyPageUsesIt()
    {
        DashboardDefinition configured = PorticoDemoSessionFactory.Create().Definition;
        DashboardPageDefinition[] pages = configured.Pages
            .Select(page => page.Id == DashboardPageId.Budget
                ? page with
                {
                    NavigationGroup = DashboardNavigationGroup.Unspecified,
                    NavigationOrder = 0,
                    RailLabel = null,
                    PageHeading = null,
                    Icon = DashboardNavigationIcon.None
                }
                : page)
            .ToArray();

        IReadOnlyList<string> problems = (configured with { Pages = pages }).Validate();

        Assert.Contains("dashboard page 'Budget' needs a navigation group.", problems);
        Assert.Contains("dashboard page 'Budget' navigation order must be positive.", problems);
        Assert.Contains("dashboard page 'Budget' needs a rail label.", problems);
        Assert.Contains("dashboard page 'Budget' needs a page heading.", problems);
        Assert.Contains("dashboard page 'Budget' needs a navigation icon.", problems);
    }

    [Fact]
    public void Rail_ActivatesPagesFromPointerAndKeyboardAndRetainsLogicalFocusAfterRebuild()
    {
        DashboardSession session = CreateSession();
        var scene = CreateScene(session);
        scene.Stage.SetCommandConfig(UiInputMap.Default().CreateCommandConfig());
        var measurer = new MockTextMeasurer();
        scene.Stage.RefreshLayout(measurer);

        LayoutNode spending = FindNode(scene, "NavigationItem:Spending");
        var pointerInput = new UiInput
        {
            CursorPosition = CenterOf(spending),
            CursorMoved = true,
            Commands = [new UiCommandInput((int)InputCommands.ClickLeft, Pressed: true, Down: true, Released: false)],
            DeltaSeconds = 1f / 60f
        };

        scene.Update(ref pointerInput, measurer, UiRenderScaleOptions.Default, 1f);
        scene.Refresh();

        Assert.Equal(DashboardPageId.Spending, session.CurrentPage);
        Assert.Equal("Spending by category", Text(scene, "PageTitle"));
        Assert.Equal("NavigationItem:Spending", FocusProcessor.GetFocusedNodeOrDefault(scene.Stage.Root)?.Name);

        LayoutNode home = FindNode(scene, "NavigationItem:Home");
        FocusProcessor.SetFocus(scene.Stage.Root, home);
        var downInput = new UiInput
        {
            Commands = [new UiCommandInput((int)InputCommands.Down, Pressed: true, Down: true, Released: false)],
            DeltaSeconds = 1f / 60f
        };

        scene.Update(ref downInput, measurer, UiRenderScaleOptions.Default, 1f);

        Assert.Equal("NavigationItem:IncomeSavings", FocusProcessor.GetFocusedNodeOrDefault(scene.Stage.Root)?.Name);

        var selectIncomeInput = new UiInput
        {
            Commands = [new UiCommandInput((int)InputCommands.Accept, Pressed: true, Down: true, Released: false)],
            DeltaSeconds = 1f / 60f
        };

        scene.Update(ref selectIncomeInput, measurer, UiRenderScaleOptions.Default, 1f);
        scene.Refresh();

        Assert.Equal(DashboardPageId.IncomeSavings, session.CurrentPage);
        Assert.Equal("Income and savings", Text(scene, "PageTitle"));
        Assert.Equal("NavigationItem:IncomeSavings", FocusProcessor.GetFocusedNodeOrDefault(scene.Stage.Root)?.Name);

        LayoutNode health = FindNode(scene, "NavigationItem:DataHealth");
        FocusProcessor.SetFocus(scene.Stage.Root, health);
        var keyboardInput = new UiInput
        {
            Commands = [new UiCommandInput((int)InputCommands.Accept, Pressed: true, Down: true, Released: false)],
            DeltaSeconds = 1f / 60f
        };

        scene.Update(ref keyboardInput, measurer, UiRenderScaleOptions.Default, 1f);
        scene.Refresh();

        Assert.Equal(DashboardPageId.DataHealth, session.CurrentPage);
        Assert.Equal("Data health", Text(scene, "PageTitle"));
        Assert.Equal("NavigationItem:DataHealth", FocusProcessor.GetFocusedNodeOrDefault(scene.Stage.Root)?.Name);
    }

    [Fact]
    public void Navigation_AwayAndBackKeepsTheCurrentReportAndConfiguredFilters()
    {
        DashboardSession session = CreateSession();
        DashboardReport report = session.Report;
        DashboardFilters filters = session.Filters;
        var scene = CreateScene(session);

        scene.SelectPage(DashboardPageId.Spending);
        scene.Refresh();
        scene.SelectPage(DashboardPageId.Home);
        scene.Refresh();

        Assert.Equal(DashboardPageId.Home, session.CurrentPage);
        Assert.Same(report, session.Report);
        Assert.Equal(filters, session.Filters);
        Assert.Equal("Accounts and net worth", Text(scene, "PageTitle"));
    }

    [Fact]
    public void NavigationLoop_ChangesOneControlOnEveryPageAndRetainsItAfterReturn()
    {
        DashboardSession session = CreateSession();
        var scene = CreateScene(session);
        var controls = new Dictionary<DashboardPageId, string>
        {
            [DashboardPageId.Home] = "time_frame",
            [DashboardPageId.IncomeSavings] = "lookback",
            [DashboardPageId.Merchants] = "lookback",
            [DashboardPageId.Spending] = "lookback",
            [DashboardPageId.YearOverYear] = "view",
            [DashboardPageId.Subscriptions] = "history_lookback",
            [DashboardPageId.TopTransactions] = "lookback",
            [DashboardPageId.Budget] = "month",
            [DashboardPageId.FinancialIndependence] = "spending_lookback",
            [DashboardPageId.DataHealth] = "selected_check"
        };

        foreach (DashboardPageDefinition page in session.Definition.Pages.Where(page => page.Visible))
        {
            string controlId = controls[page.Id];
            scene.SelectPage(page.Id);
            scene.Refresh();

            string current = session.ControlValue(page.Id, controlId);
            string changed = session.ControlOptions(page.Id, controlId)
                .First(value => !string.Equals(value, current, StringComparison.Ordinal));
            session.SetControlValue(page.Id, controlId, changed);
            scene.Refresh();

            Assert.Equal(changed, session.ControlValue(page.Id, controlId));

            DashboardPageId otherPage = page.Id == DashboardPageId.Home
                ? DashboardPageId.IncomeSavings
                : DashboardPageId.Home;
            scene.SelectPage(otherPage);
            scene.Refresh();
            scene.SelectPage(page.Id);
            scene.Refresh();

            Assert.Equal(page.PageHeading, Text(scene, "PageTitle"));
            Assert.Equal(changed, session.ControlValue(page.Id, controlId));
        }
    }

    [Fact]
    public void HideValuesMasksMetricTableAxisAndTooltipPresentationWithoutChangingTheReport()
    {
        DashboardSession session = CreateSession();
        DashboardReport report = session.Report;
        var displayState = new PorticoDashboardDisplayState(isDemoData: true);
        var scene = CreateScene(session, displayState);

        Assert.Contains(
            Texts(scene).Where(item => item.Name.StartsWith("MetricValue:", StringComparison.Ordinal)).Select(item => item.Value),
            value => value.Any(char.IsDigit));

        scene.ToggleHideValues();
        scene.Refresh();

        Assert.True(displayState.HideValues);
        Assert.Same(report, session.Report);
        Assert.Contains("Hidden", Texts(scene).Select(item => item.Value));
        Assert.DoesNotContain(
            Texts(scene).Where(item => item.Name.StartsWith("MetricValue:", StringComparison.Ordinal)).Select(item => item.Value),
            value => value.Any(char.IsDigit));

        ChartState netWorth = Chart(scene, "Chart:net-worth");
        ChartLinearAxisConfig axis = netWorth.YAxis switch
        {
            ChartLinearAxisConfig linear => linear,
            _ => throw new Xunit.Sdk.XunitException("Expected a numeric net-worth axis.")
        };
        Assert.Equal("Hidden", axis.Formatter!(1234d));
        Assert.NotNull(netWorth.Interaction.TooltipFormatter);

        scene.SelectPage(DashboardPageId.TopTransactions);
        scene.Refresh();

        string[] tableValues = Texts(scene)
            .Where(item => item.Name.StartsWith("TableRow:", StringComparison.Ordinal))
            .Select(item => item.Value)
            .ToArray();
        Assert.Contains("Hidden", tableValues);
        Assert.DoesNotContain(tableValues, value => value.Any(char.IsDigit));
    }

    [Fact]
    public void DemoBannerAppearsOnlyForTheDemoHostState()
    {
        var normal = CreateScene(CreateSession());
        var demo = CreateScene(CreateSession(), new PorticoDashboardDisplayState(isDemoData: true));

        Assert.Null(FindNodeOrDefault(normal, "DemoDataBanner"));
        Assert.Null(FindNodeOrDefault(normal, "RailDemoDataState"));
        Assert.NotNull(FindNodeOrDefault(demo, "DemoDataBanner"));
        Assert.NotNull(FindNodeOrDefault(demo, "RailDemoDataState"));
        Assert.Equal("Demo data ready", Text(demo, "RailLoadStatusLabel"));
    }

    [Fact]
    public void RefreshBoundary_UsesLoadingAndCompletedCheckStatesWithoutReplacingTheHeldReport()
    {
        DashboardSession session = CreateSession();
        DashboardReport report = session.Report;
        var boundary = new PendingRefreshBoundary();
        var scene = CreateScene(session, refreshBoundary: boundary);

        scene.RequestDataRefresh();
        scene.Refresh();

        Assert.Equal(PorticoDataLoadStatus.Loading, scene.DisplayState.LoadStatus);
        Assert.Equal("Refreshing data", Text(scene, "RailLoadStatusLabel"));
        Assert.Equal("Checking the source. Showing the loaded data.", scene.DisplayState.StatusMessage);
        Assert.False(FindNode(scene, "RefreshDataAction").Enabled);
        Assert.NotNull(FindNodeOrDefault(scene, "LoadStatePanel"));

        boundary.Complete(PorticoRefreshResult.SourceChecked());
        scene.Refresh();

        Assert.Equal(PorticoDataLoadStatus.Loaded, scene.DisplayState.LoadStatus);
        Assert.Equal("Source check completed. Showing the loaded data.", scene.DisplayState.StatusMessage);
        Assert.True(scene.DisplayState.HasLastGoodData);
        Assert.Same(report, session.Report);
        Assert.True(FindNode(scene, "RefreshDataAction").Enabled);
    }

    [Fact]
    public void RefreshFailureAndUnavailableKeepNavigationAndLastGoodPageUsable()
    {
        DashboardSession failedSession = CreateSession();
        var failedScene = CreateScene(failedSession, refreshBoundary: new ImmediateRefreshBoundary(PorticoRefreshResult.Failed()));
        failedScene.RequestDataRefresh();
        failedScene.Refresh();

        Assert.Equal(PorticoDataLoadStatus.Failed, failedScene.DisplayState.LoadStatus);
        Assert.True(failedScene.DisplayState.HasLastGoodData);
        Assert.Equal("Refresh failed", Text(failedScene, "RailLoadStatusLabel"));
        failedScene.SelectPage(DashboardPageId.Budget);
        failedScene.Refresh();
        Assert.Equal(DashboardPageId.Budget, failedSession.CurrentPage);
        Assert.Equal("Budget", Text(failedScene, "PageTitle"));

        DashboardSession unavailableSession = CreateSession();
        var unavailableScene = CreateScene(unavailableSession);
        unavailableScene.RequestDataRefresh();
        unavailableScene.Refresh();

        Assert.Equal(PorticoDataLoadStatus.Unavailable, unavailableScene.DisplayState.LoadStatus);
        Assert.True(unavailableScene.DisplayState.HasLastGoodData);
        Assert.Equal("Refresh unavailable", Text(unavailableScene, "RailLoadStatusLabel"));
        unavailableScene.SelectPage(DashboardPageId.DataHealth);
        unavailableScene.Refresh();
        Assert.Equal(DashboardPageId.DataHealth, unavailableSession.CurrentPage);
    }

    [Theory]
    [InlineData(1500, 1000)]
    [InlineData(1024, 720)]
    public void EveryConfiguredPageKeepsTheFixedRailAndScrollableBodyInsideTheViewport(int width, int height)
    {
        DashboardSession session = CreateSession();
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        var measurer = new MockTextMeasurer();

        foreach (DashboardPageDefinition page in session.Definition.Pages.Where(page => page.Visible))
        {
            scene.SelectPage(page.Id);
            scene.Refresh();
            scene.Stage.RefreshLayout(measurer);

            LayoutNode shell = FindNode(scene, "PorticoShell");
            LayoutNode rail = FindNode(scene, "NavigationRail");
            LayoutNode main = FindNode(scene, "MainColumn");
            LayoutNode header = FindNode(scene, "PageHeader");
            LayoutNode body = FindNode(scene, "PageBody");

            Assert.Equal(new Vector2(width, height), shell.BoxModel.ComputedSize);
            Assert.Equal(232f, rail.BoxModel.ComputedSize.X);
            Assert.Equal((float)height, rail.BoxModel.ComputedSize.Y);
            AssertWithin(shell, rail);
            AssertWithin(shell, main);
            AssertWithin(main, header);
            AssertWithin(main, body);
            Assert.NotNull(body.ScrollConfig);
            Assert.True(body.ScrollConfig!.Value.EnableVertical);
            Assert.False(body.ScrollConfig!.Value.EnableHorizontal);
            Assert.Null(rail.ScrollConfig);
        }
    }

    private static DashboardSession CreateSession() => PorticoDemoSessionFactory.Create();

    private static PorticoDashboardScene CreateScene(
        DashboardSession session,
        PorticoDashboardDisplayState? displayState = null,
        IPorticoRefreshBoundary? refreshBoundary = null)
        => new(new Vector2(1500f, 1000f), session, displayState, refreshBoundary);

    private static LayoutNode FindNode(PorticoDashboardScene scene, string name)
        => FindNodeOrDefault(scene, name)
            ?? throw new Xunit.Sdk.XunitException($"Expected node '{name}'.");

    private static LayoutNode? FindNodeOrDefault(PorticoDashboardScene scene, string name)
        => scene.Stage.Root.GetSelfAndDescendants()
            .FirstOrDefault(node => string.Equals(node.Name, name, StringComparison.Ordinal));

    private static string Text(PorticoDashboardScene scene, string name)
        => FindNode(scene, name).TextNodeState?.RawText
            ?? throw new Xunit.Sdk.XunitException($"Expected text node '{name}'.");

    private static IEnumerable<(string Name, string Value)> Texts(PorticoDashboardScene scene)
        => scene.Stage.Root.GetSelfAndDescendants()
            .Where(node => node.TextNodeState.HasValue)
            .Select(node => (node.Name ?? string.Empty, node.TextNodeState!.Value.RawText));

    private static IReadOnlyList<string> GroupLabels(PorticoDashboardScene scene)
        => Texts(scene)
            .Where(item => item.Name.StartsWith("NavigationGroupLabel:", StringComparison.Ordinal))
            .Select(item => item.Value)
            .ToArray();

    private static ChartState Chart(PorticoDashboardScene scene, string name)
        => FindNode(scene, name).GetStateOrDefault<ChartState>()
            ?? throw new Xunit.Sdk.XunitException($"Expected chart state for '{name}'.");

    private static Vector2 CenterOf(LayoutNode node)
        => node.ComputedPosition + node.BoxModel.ComputedSize / 2f;

    private static void AssertWithin(LayoutNode parent, LayoutNode child)
    {
        float parentRight = parent.ComputedPosition.X + parent.BoxModel.ComputedSize.X;
        float parentBottom = parent.ComputedPosition.Y + parent.BoxModel.ComputedSize.Y;
        float childRight = child.ComputedPosition.X + child.BoxModel.ComputedSize.X;
        float childBottom = child.ComputedPosition.Y + child.BoxModel.ComputedSize.Y;

        Assert.True(child.ComputedPosition.X >= parent.ComputedPosition.X);
        Assert.True(child.ComputedPosition.Y >= parent.ComputedPosition.Y);
        Assert.True(childRight <= parentRight);
        Assert.True(childBottom <= parentBottom);
    }

    private sealed record NavigationExpectation(
        DashboardPageId Id,
        DashboardNavigationGroup Group,
        int Order,
        string RailLabel,
        string PageHeading,
        DashboardNavigationIcon Icon,
        string IconGlyph);

    private sealed class PendingRefreshBoundary : IPorticoRefreshBoundary
    {
        private readonly TaskCompletionSource<PorticoRefreshResult> _completion = new(TaskCreationOptions.RunContinuationsAsynchronously);

        public Task<PorticoRefreshResult> CheckSourceAsync() => _completion.Task;

        public void Complete(PorticoRefreshResult result) => _completion.SetResult(result);
    }

    private sealed class ImmediateRefreshBoundary(PorticoRefreshResult result) : IPorticoRefreshBoundary
    {
        public Task<PorticoRefreshResult> CheckSourceAsync() => Task.FromResult(result);
    }
}
