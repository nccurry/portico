using System.Numerics;
using Portico.App;
using Portico.CaptureHost;
using Portico.Dashboard;
using Roci.Launch;
using Roci.TestUtilities;
using Roci.Testing;
using Roci.Ui;

namespace Portico.App.Tests;

public sealed class PorticoCaptureCatalogTests
{
    [Fact]
    public void CaptureCatalog_AllCurrentPagesHaveBothRequiredSizes()
    {
        IReadOnlyList<CaptureCase> cases = PorticoCaptureCatalog.CaptureCatalog.CaptureCases;

        Assert.Equal(28, cases.Count);
        Assert.Equal(
        [
            "budget",
            "budget-refresh-failed",
            "data-health",
            "data-health-refresh-unavailable",
            "financial-independence",
            "home",
            "home-hidden",
            "income-savings",
            "merchants",
            "spending",
            "spending-loading",
            "subscriptions",
            "top-transactions",
            "year-over-year"
        ],
        cases.Select(capture => capture.ScenarioId).Distinct().Order(StringComparer.Ordinal));

        foreach (CaptureCase capture in cases)
        {
            Assert.Equal(PorticoCaptureCatalog.DemoLaunchState, capture.LaunchStateId);
            Assert.Equal(PorticoCaptureCatalog.CaptureFrame, capture.CaptureFrame);
            Assert.Null(capture.GoldenPath);
            Assert.Equal(capture.CaptureSize, capture.Verification.ExpectedSize);
            Assert.Equal(4, capture.Verification.MinimumUniqueColors);
        }

        Assert.Equal(
            14,
            cases.Count(capture => capture.CaptureSize == new CaptureSize(1500, 1000)));
        Assert.Equal(
            14,
            cases.Count(capture => capture.CaptureSize == new CaptureSize(1024, 720)));

        DashboardPageId[] configuredPages = PorticoDemoSessionFactory.Create()
            .Definition.Pages
            .Where(page => page.Visible)
            .Select(page => page.Id)
            .Order()
            .ToArray();
        DashboardPageId[] capturedPages = cases
            .Select(SelectedPageFor)
            .Distinct()
            .Order()
            .ToArray();

        Assert.Equal(configuredPages, capturedPages);
        foreach (DashboardPageId page in configuredPages)
        {
            Assert.Equal(
                2,
                cases.Count(capture => string.Equals(capture.ScenarioId, NormalScenarioFor(page), StringComparison.Ordinal)));
        }
    }

    [Fact]
    public void RunCatalog_NormalCaptureArgumentsResolveTheNamedPageAndRequestedSize()
    {
        GameRunOptionsParseResult parsed = GameRunOptionsParser.Parse(
        [
            "--start-state", "demo",
            "--scenario", "spending",
            "--capture-size", "1500x1000",
            "--capture-frame", "8",
            "--capture", "artifacts/captures/spending.png"
        ],
        GameRunFeatures.Automation | GameRunFeatures.Capture);

        Assert.True(parsed.TryGetOptions(out GameRunOptions? options));
        Assert.NotNull(options);
        GameRunValidationResult validation = PorticoCaptureCatalog.RunCatalog.Validate(options);
        Assert.True(validation.TryGetContext(out GameRunContext? context));
        Assert.NotNull(context);
        Assert.Equal("spending", context.ScenarioId);
        Assert.Equal(new CaptureSize(1500, 1000), context.OriginalOptions.CaptureSize);
    }

    [Theory]
    [InlineData("home", DashboardPageId.Home, 12, "discretionary", "utilities", true)]
    [InlineData("spending", DashboardPageId.Spending, 3, "all", "utilities", true)]
    [InlineData("income-savings", DashboardPageId.IncomeSavings, 12, "discretionary", "utilities", false)]
    [InlineData("year-over-year", DashboardPageId.YearOverYear, 12, "discretionary", "all", true)]
    [InlineData("subscriptions", DashboardPageId.Subscriptions, 12, "discretionary", "utilities", true)]
    [InlineData("merchants", DashboardPageId.Merchants, 3, "all", "utilities", true)]
    [InlineData("budget", DashboardPageId.Budget, 3, "discretionary", "utilities", true)]
    [InlineData("top-transactions", DashboardPageId.TopTransactions, 3, "discretionary", "utilities", true)]
    [InlineData("financial-independence", DashboardPageId.FinancialIndependence, 12, "discretionary", "utilities", true)]
    [InlineData("data-health", DashboardPageId.DataHealth, 12, "discretionary", "utilities", true)]
    public void CreateSession_NamedScenarioSelectsTheExpectedPageAndControlState(
        string scenario,
        DashboardPageId page,
        int lookbackMonths,
        string spendingSet,
        string yearOverYearSet,
        bool regularIncome)
    {
        GameRunContext context = PorticoCaptureCatalog.RunCatalog.CreateContext(new GameRunOptions
        {
            StartStateId = PorticoCaptureCatalog.DemoLaunchState,
            ScenarioId = scenario
        });

        DashboardSession session = PorticoCaptureCatalog.CreateSession(context);

        Assert.Equal(page, session.CurrentPage);
        Assert.Equal(lookbackMonths, session.Filters.LookbackMonths);
        Assert.Equal(spendingSet, session.Filters.SpendingSet);
        Assert.Equal(yearOverYearSet, session.Filters.YearOverYearSet);
        Assert.Equal(regularIncome, session.Filters.RegularIncome);
    }

    [Theory]
    [InlineData("home-hidden", true, PorticoDataLoadStatus.Loaded)]
    [InlineData("spending-loading", false, PorticoDataLoadStatus.Loading)]
    [InlineData("budget-refresh-failed", false, PorticoDataLoadStatus.Failed)]
    [InlineData("data-health-refresh-unavailable", false, PorticoDataLoadStatus.Unavailable)]
    public void CreateDisplayState_SpecialScenarioSuppliesTheExpectedVisualState(
        string scenario,
        bool hideValues,
        PorticoDataLoadStatus status)
    {
        GameRunContext context = PorticoCaptureCatalog.RunCatalog.CreateContext(new GameRunOptions
        {
            StartStateId = PorticoCaptureCatalog.DemoLaunchState,
            ScenarioId = scenario
        });

        PorticoDashboardDisplayState state = PorticoCaptureCatalog.CreateDisplayState(context);

        Assert.True(state.IsDemoData);
        Assert.Equal(hideValues, state.HideValues);
        Assert.Equal(status, state.LoadStatus);
        Assert.True(state.HasLastGoodData);
    }

    [Theory]
    [InlineData(1500, 1000)]
    [InlineData(1024, 720)]
    public void CaptureHostSettings_CaptureSizeSetsTheLogicalDashboardSize(int width, int height)
    {
        GameRunContext context = PorticoCaptureCatalog.RunCatalog.CreateContext(new GameRunOptions
        {
            CaptureSize = new CaptureSize(width, height)
        });

        var settings = PorticoDashboardGame.CreateHostSettings(context);

        Assert.Equal(width, settings.LogicalSize.Width);
        Assert.Equal(height, settings.LogicalSize.Height);
    }

    [Theory]
    [InlineData(1500, 1000)]
    [InlineData(1024, 720)]
    public void Scene_AtCaptureSizeKeepsItsMainRegionsInsideTheViewport(int width, int height)
    {
        GameRunContext context = PorticoCaptureCatalog.RunCatalog.CreateContext(new GameRunOptions
        {
            StartStateId = PorticoCaptureCatalog.DemoLaunchState,
            ScenarioId = "home"
        });
        DashboardSession session = PorticoCaptureCatalog.CreateSession(context);
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        LayoutNode shell = FindNode(scene, "PorticoShell");
        LayoutNode rail = FindNode(scene, "NavigationRail");
        LayoutNode main = FindNode(scene, "MainColumn");
        LayoutNode header = FindNode(scene, "PageHeader");
        LayoutNode body = FindNode(scene, "PageBody");

        Assert.Equal(new Vector2(width, height), shell.BoxModel.ComputedSize);
        Assert.Equal(232f, rail.BoxModel.ComputedSize.X);
        AssertWithin(shell, rail);
        AssertWithin(shell, main);
        AssertWithin(main, header);
        AssertWithin(main, body);
        Assert.True(header.ComputedPosition.Y + header.BoxModel.ComputedSize.Y <= body.ComputedPosition.Y);
    }

    private static LayoutNode FindNode(PorticoDashboardScene scene, string name)
    {
        return scene.Stage.Root.GetSelfAndDescendants().Single(node => node.Name == name);
    }

    private static DashboardPageId SelectedPageFor(CaptureCase captureCase)
    {
        GameRunContext context = PorticoCaptureCatalog.RunCatalog.CreateContext(new GameRunOptions
        {
            StartStateId = captureCase.LaunchStateId,
            ScenarioId = captureCase.ScenarioId
        });
        return PorticoCaptureCatalog.CreateSession(context).CurrentPage;
    }

    private static string NormalScenarioFor(DashboardPageId page)
        => page switch
        {
            DashboardPageId.Home => "home",
            DashboardPageId.IncomeSavings => "income-savings",
            DashboardPageId.Spending => "spending",
            DashboardPageId.YearOverYear => "year-over-year",
            DashboardPageId.Subscriptions => "subscriptions",
            DashboardPageId.Merchants => "merchants",
            DashboardPageId.Budget => "budget",
            DashboardPageId.TopTransactions => "top-transactions",
            DashboardPageId.FinancialIndependence => "financial-independence",
            DashboardPageId.DataHealth => "data-health",
            _ => throw new ArgumentOutOfRangeException(nameof(page), page, null)
        };

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
}
