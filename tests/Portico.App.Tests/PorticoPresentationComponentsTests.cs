using System.Numerics;
using Portico.Adapters;
using Portico.App;
using Portico.App.Ui.Components;
using Portico.CaptureHost;
using Portico.Dashboard;
using Portico.Finance;
using Roci.Core;
using Roci.Input;
using Roci.TestUtilities;
using Roci.Ui;
using Roci.Ui.Processors;
using Roci.Ui.Widgets;

namespace Portico.App.Tests;

public sealed class PorticoPresentationComponentsTests
{
    [Fact]
    public void Home_UsesTheConfiguredSixOptionTimeFrameAndSectionPanel()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        var scene = new PorticoDashboardScene(new Vector2(1280f, 820f), session);

        SegmentedControlState timeFrame = State<SegmentedControlState>(scene, "Control:Home:time_frame");

        Assert.Equal(["3M", "6M", "1Y", "2Y", "5Y", "All"], timeFrame.Segments
            .Select(segment => segment.GetStateOrDefault<SegmentState>()!.Label));
        Assert.Equal(2, timeFrame.SelectedIndex);
        Assert.Equal("Time frame", Text(scene, "Control:Home:time_frame:Label"));
        Assert.Equal("Section:net_worth", Parent(scene, "Widget:net-worth").Name);
        Assert.DoesNotContain(scene.Stage.Root.GetSelfAndDescendants(), node => node.Name == "Filter:lookback");

        Assert.True(InvokeAccept(timeFrame.Segments[4]));
        scene.Refresh();

        Assert.Equal(HomeTimeFrame.FiveYears, session.Filters.HomeTimeFrame);
        Assert.Equal(4, State<SegmentedControlState>(scene, "Control:Home:time_frame").SelectedIndex);
    }

    [Theory]
    [InlineData(1500f, 1000f)]
    [InlineData(1024f, 720f)]
    public void Home_TimeFrameSegmentsFillTheConfiguredFullWidthControl(float width, float height)
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        LayoutNode group = FindNode(scene, "Control:Home:time_frame:Group");
        LayoutNode control = FindNode(scene, "Control:Home:time_frame");
        LayoutNode[] segments = State<SegmentedControlState>(scene, "Control:Home:time_frame").Segments.ToArray();
        float expectedSegmentWidth = control.BoxModel.ComputedSize.X / segments.Length;

        Assert.Equal(group.BoxModel.ComputedSize.X, control.BoxModel.ComputedSize.X);
        Assert.All(segments, segment => Assert.Equal(expectedSegmentWidth, segment.BoxModel.ComputedSize.X));
        Assert.Equal(control.ComputedPosition.X, segments[0].ComputedPosition.X);
        Assert.Equal(
            control.ComputedPosition.X + control.BoxModel.ComputedSize.X,
            segments[^1].ComputedPosition.X + segments[^1].BoxModel.ComputedSize.X);
    }

    [Fact]
    public void Home_BuildsTheSourceReadingOrderAndRetainsReportAndDetailState()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        var scene = new PorticoDashboardScene(new Vector2(1280f, 820f), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        Assert.Equal("Net worth history", Text(scene, "WidgetTitle:net-worth"));
        Assert.Equal("What changed", Text(scene, "WidgetTitle:what-changed"));
        Assert.Equal("Account groups", Text(scene, "Section:account_groups:Title"));
        Assert.Equal("Financial safety", Text(scene, "WidgetTitle:safety"));
        Assert.Equal("Net worth", Text(scene, "MetricLabel:net-worth:Net worth"));
        Assert.Equal("Assets", Text(scene, "MetricLabel:net-worth:Assets"));
        Assert.Equal("Liabilities", Text(scene, "MetricLabel:net-worth:Liabilities"));
        Assert.Contains("over 1Y", Text(scene, "MetricDetail:net-worth:Net worth"), StringComparison.Ordinal);

        ChartState changesChart = State<ChartState>(scene, "Chart:what-changed");
        ChartBarSeries changeBars = Assert.Single(changesChart.Series) switch
        {
            ChartBarSeries value => value,
            _ => throw new Xunit.Sdk.XunitException("Expected What changed to use a bar series.")
        };
        Assert.Equal(ChartBarOrientation.Horizontal, changeBars.Orientation);
        Assert.True(changesChart.XAxis is ChartLinearAxisConfig { Title: "Net-worth movement ($)" });
        Assert.True(changesChart.YAxis is ChartCategoryAxisConfig { Title: null });

        Assert.True(FindNode(scene, "Section:net_worth").ComputedPosition.Y
            < FindNode(scene, "Section:what_changed").ComputedPosition.Y);
        Assert.True(FindNode(scene, "Section:what_changed").ComputedPosition.Y
            < FindNode(scene, "Widget:accounts").ComputedPosition.Y);
        Assert.True(FindNode(scene, "Widget:accounts").ComputedPosition.Y
            < FindNode(scene, "Section:financial_safety").ComputedPosition.Y);

        SegmentedControlState timeFrame = State<SegmentedControlState>(scene, "Control:Home:time_frame");
        Assert.True(InvokeAccept(timeFrame.Segments[4]));
        scene.Refresh();
        Assert.Equal(HomeTimeFrame.FiveYears, session.Filters.HomeTimeFrame);
        Assert.Equal(4, State<SegmentedControlState>(scene, "Control:Home:time_frame").SelectedIndex);

        CollapsibleState savingsDetails = State<CollapsibleState>(scene, "Account details: Savings (3)");
        Assert.False(savingsDetails.IsExpanded);
        Assert.True(InvokeClick(savingsDetails.HeaderNode!));
        Assert.True(session.Presentation.IsHomeAccountGroupExpanded("Savings"));
        Assert.True(savingsDetails.IsExpanded);

        scene.ToggleHideValues();
        scene.Refresh();
        Assert.Equal("Hidden", Text(scene, "MetricValue:net-worth:Net worth"));
        Assert.Equal(4, State<SegmentedControlState>(scene, "Control:Home:time_frame").SelectedIndex);

        scene.SelectPage(DashboardPageId.Spending);
        scene.Refresh();
        scene.SelectPage(DashboardPageId.Home);
        scene.Refresh();

        Assert.True(scene.DisplayState.HideValues);
        Assert.Equal(HomeTimeFrame.FiveYears, session.Filters.HomeTimeFrame);
        Assert.Equal(4, State<SegmentedControlState>(scene, "Control:Home:time_frame").SelectedIndex);
        Assert.True(State<CollapsibleState>(scene, "Account details: Savings (3)").IsExpanded);
        Assert.Equal("Hidden", Text(scene, "MetricValue:net-worth:Net worth"));
    }

    [Fact]
    public void Home_NarrowLayoutKeepsTheSourceSectionsInsideScrollableContent()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        var scene = new PorticoDashboardScene(new Vector2(1024f, 720f), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        LayoutNode body = FindNode(scene, "PageBody");
        LayoutNode netWorth = FindNode(scene, "Widget:net-worth");
        LayoutNode changes = FindNode(scene, "Widget:what-changed");
        LayoutNode accounts = FindNode(scene, "Widget:accounts");
        LayoutNode safety = FindNode(scene, "Widget:safety");

        Assert.True(changes.ComputedPosition.Y > netWorth.ComputedPosition.Y);
        Assert.True(accounts.ComputedPosition.Y > changes.ComputedPosition.Y);
        Assert.True(safety.ComputedPosition.Y > accounts.ComputedPosition.Y);
        AssertWithinScrollContent(body, netWorth);
        AssertWithinScrollContent(body, changes);
        AssertWithinScrollContent(body, accounts);
        AssertWithinScrollContent(body, safety);
    }

    [Fact]
    public void Home_WithoutVisibleBalancesStopsAtTheSourceEmptyState()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        DashboardDefinition definition = TomlConfigurationLoader.LoadDashboard(Path.Combine(root, "dashboard.toml"));
        var session = new DashboardSession(new PortfolioSnapshot([], [], []), settings, definition, PorticoDemoSessionFactory.CaptureDate);
        var scene = new PorticoDashboardScene(new Vector2(1280f, 820f), session);

        Assert.Equal("No balance history is available yet.", Text(scene, "Empty:home-balance-history:Title"));
        Assert.Equal(
            "Refresh after your spreadsheet has account balances.",
            Text(scene, "Empty:home-balance-history:Message"));
        Assert.DoesNotContain(scene.Stage.Root.GetSelfAndDescendants(), node => node.Name == "Widget:safety");
        Assert.DoesNotContain(scene.Stage.Root.GetSelfAndDescendants(), node => node.Name == "Widget:accounts");
    }

    [Fact]
    public void Home_WithOnlyUnmappedBalancesSkipsAttributionAndShowsTheMappedGroupsState()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        DashboardDefinition definition = TomlConfigurationLoader.LoadDashboard(Path.Combine(root, "dashboard.toml"));
        var snapshot = new PortfolioSnapshot(
            [],
            [new BalanceObservation(
                "unmapped",
                "Unmapped",
                " ",
                new DateOnly(2026, 3, 1),
                new TimeOnly(8, 0),
                90m,
                AccountClass.Asset,
                false)],
            []);
        var session = new DashboardSession(snapshot, settings, definition, PorticoDemoSessionFactory.CaptureDate);
        var scene = new PorticoDashboardScene(new Vector2(1280f, 820f), session);

        Assert.DoesNotContain(scene.Stage.Root.GetSelfAndDescendants(), node => node.Name == "Widget:what-changed");
        Assert.Equal("Account groups", Text(scene, "Section:account_groups:Title"));
        Assert.Equal("No mapped balance groups are available.", Text(scene, "Empty:accounts:Message"));
    }

    [Fact]
    public void IncomeControls_UseTheSourceControlsAndKeepDetailSelectionAfterRebuild()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.IncomeSavings);
        var scene = new PorticoDashboardScene(new Vector2(1024f, 720f), session);
        var input = new UiInput { DeltaSeconds = 1f / 60f };
        scene.Stage.Update(new MockTextMeasurer(), ref input);

        LayoutNode timeFrame = FindNode(scene, "Control:IncomeSavings:lookback:Group");
        LayoutNode calculation = FindNode(scene, "Control:IncomeSavings:calculation:Group");
        LayoutNode adjust = FindNode(scene, "Control:IncomeSavings:adjust_calculation:Group");
        LayoutNode detailTabs = FindNode(scene, "IncomeSavingsDetailTabs");
        LayoutNode controlBar = FindNode(scene, "IncomeSavingsControlBar");
        LayoutNode body = FindNode(scene, "PageBody");
        Assert.True(calculation.ComputedPosition.Y >= timeFrame.ComputedPosition.Y);
        Assert.InRange(adjust.BoxModel.ComputedSize.X, 1f, 280f);
        Assert.True(detailTabs.ComputedPosition.Y > controlBar.ComputedPosition.Y);
        AssertWithinScrollContent(body, controlBar);
        AssertWithinScrollContent(body, detailTabs);

        SegmentedControlState tabs = State<SegmentedControlState>(scene, "IncomeSavingsDetailTabs");
        Assert.Equal(["Included", "Excluded"], tabs.Segments.Select(segment => segment.GetStateOrDefault<SegmentState>()!.Label.Split(' ')[0]));
        Assert.Equal(0, tabs.SelectedIndex);
        Assert.True(InvokeAccept(tabs.Segments[1]));
        scene.Refresh();

        Assert.Equal("Excluded", session.Presentation.IncomeSavings.DetailTab);
        Assert.Equal(1, State<SegmentedControlState>(scene, "IncomeSavingsDetailTabs").SelectedIndex);
    }

    [Fact]
    public void MultiSelect_OpensTogglesClearsDismissesAndRetainsStateAcrossRebuild()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.IncomeSavings);
        var scene = new PorticoDashboardScene(new Vector2(1280f, 820f), session);
        PorticoMultiSelectState<string> state = scene.MultiSelectState(DashboardPageId.IncomeSavings, "exclude_income_categories")
            ?? throw new Xunit.Sdk.XunitException("Expected the configured multi-select state.");

        LayoutNode trigger = FindNode(scene, "Control:IncomeSavings:exclude_income_categories");
        Assert.True(InvokeAccept(trigger));
        Assert.True(state.IsOpen);
        LayoutNode salary = FindNode(scene, "MultiSelectCheckbox:Control:IncomeSavings:exclude_income_categories:Salary");

        Assert.True(InvokeAccept(salary));
        scene.Refresh();

        Assert.Contains("Salary", session.Presentation.IncomeSavings.ExcludedIncomeCategories);
        Assert.True(state.IsOpen);
        Assert.Same(state, scene.MultiSelectState(DashboardPageId.IncomeSavings, "exclude_income_categories"));
        Assert.Equal("Salary", Text(scene, "Control:IncomeSavings:exclude_income_categories:Summary"));

        LayoutNode clear = FindNode(scene, "MultiSelectClear:Control:IncomeSavings:exclude_income_categories");
        Assert.True(InvokeAccept(clear));
        scene.Refresh();
        Assert.Empty(session.Presentation.IncomeSavings.ExcludedIncomeCategories);
        Assert.Equal("All", Text(scene, "Control:IncomeSavings:exclude_income_categories:Summary"));

        var cancelInput = new UiCommandInput((int)InputCommands.Cancel, Pressed: true, Down: true, Released: false);
        var cancel = new UiInput
        {
            Commands = [cancelInput],
            DeltaSeconds = 1f / 60f
        };
        var cancelConfig = new UiCommandConfig();
        cancelConfig.Cancel((int)InputCommands.Cancel);
        var cancelFrame = new UiCommandFrame([cancelInput], cancelConfig);
        PopoverProcessor.Update(scene.Stage.Root, in cancel, in cancelFrame);

        Assert.False(state.IsOpen);
    }

    [Fact]
    public void MultiSelectState_OnlyNotifiesForRealSelectionChangesAndKeepsSearchState()
    {
        var state = new PorticoMultiSelectState<string>(["Salary"]);
        var notifications = new List<IReadOnlySet<string>>();

        Assert.False(state.SetSelected("Salary", true, notifications.Add));
        Assert.True(state.SetSelected("Bonus", true, notifications.Add));
        Assert.False(state.SetSelected("Bonus", true, notifications.Add));
        Assert.True(state.Clear(notifications.Add));
        Assert.False(state.Clear(notifications.Add));
        Assert.True(state.SetOpen(true));
        Assert.True(state.SetSearchText(" bonus "));

        Assert.Equal(2, notifications.Count);
        Assert.Equal(["Bonus", "Salary"], notifications[0].Order());
        Assert.Empty(notifications[1]);
        Assert.True(state.IsOpen);
        Assert.Equal("bonus", state.SearchText);
        Assert.True(state.Matches("Annual bonus"));
        Assert.False(state.Matches("Salary"));
    }

    [Fact]
    public void MultiSelectState_CanSynchronizeItsOwnSelectionWithoutClearingIt()
    {
        var state = new PorticoMultiSelectState<string>(["Salary"]);

        state.ReplaceSelection(state.SelectedValues);

        Assert.Equal(["Salary"], state.SelectedValues);
    }

    [Fact]
    public void LocalPanels_PlaceHeaderActionsAndExposeEmptyAndErrorStates()
    {
        var stage = new UiStage(new Vector2(600f, 400f));
        int retries = 0;
        stage.Ui.RootPanel()
            .SectionPanel(
                "Section:test",
                "Test section",
                "Helper text",
                actions => actions.Button("Section:test:Action")
                    .Text("Action").End()
                .EndButton())
                .Text("Body", "Section:test:Body")
            .End()
            .EndSectionPanel()
            .EmptyPanel("Nothing here", "Change the filters and try again.", "Empty:test")
            .ErrorPanel("Could not load", "The source check failed.", "Error:test", () => retries++)
            .ErrorPanel("Refresh unavailable", "No retry is available.", "Error:no-retry")
        .EndRootPanel();

        LayoutNode header = FindNode(stage, "Section:test:Header");
        Assert.Equal(["Section:test:Heading", "Section:test:Action"], header.Children.Select(child => child.Name));
        Assert.Equal("Nothing here", Text(stage, "Empty:test:Title"));
        Assert.Equal("The source check failed.", Text(stage, "Error:test:Message"));
        Assert.True(InvokeAccept(FindNode(stage, "Error:test:Retry")));
        Assert.Equal(1, retries);
        Assert.DoesNotContain(stage.Root.GetSelfAndDescendants(), node => node.Name == "Error:no-retry:Retry");
    }

    private static string FindRepositoryRoot()
    {
        string[] startingPoints = [Directory.GetCurrentDirectory(), AppContext.BaseDirectory];
        foreach (string start in startingPoints)
        {
            var current = new DirectoryInfo(start);
            while (current is not null)
            {
                if (File.Exists(Path.Combine(current.FullName, "portico-demo.toml"))
                    && File.Exists(Path.Combine(current.FullName, "dashboard.toml")))
                {
                    return current.FullName;
                }

                current = current.Parent;
            }
        }

        throw new InvalidOperationException("Could not find the Portico repository root.");
    }

    private static LayoutNode FindNode(PorticoDashboardScene scene, string name)
        => FindNode(scene.Stage, name);

    private static LayoutNode FindNode(UiStage stage, string name)
        => stage.Root.GetSelfAndDescendants().Single(node => string.Equals(node.Name, name, StringComparison.Ordinal));

    private static LayoutNode Parent(PorticoDashboardScene scene, string name)
        => FindNode(scene, name).Parent
            ?? throw new Xunit.Sdk.XunitException($"Expected node '{name}' to have a parent.");

    private static T State<T>(PorticoDashboardScene scene, string name)
        where T : class
        => scene.Stage.Root.GetSelfAndDescendants()
            .Where(node => string.Equals(node.Name, name, StringComparison.Ordinal))
            .Select(node => node.GetStateOrDefault<T>())
            .OfType<T>()
            .SingleOrDefault()
            ?? throw new Xunit.Sdk.XunitException($"Expected state '{typeof(T).Name}' on '{name}'.");

    private static string Text(PorticoDashboardScene scene, string name) => Text(scene.Stage, name);

    private static string Text(UiStage stage, string name)
        => FindNode(stage, name).TextNodeState?.RawText
            ?? throw new Xunit.Sdk.XunitException($"Expected text node '{name}'.");

    private static void AssertWithinScrollContent(LayoutNode scrollContainer, LayoutNode child)
    {
        ScrollState scroll = scrollContainer.ScrollState
            ?? throw new Xunit.Sdk.XunitException($"Expected '{scrollContainer.Name}' to have scroll state.");
        Rectangle content = scrollContainer.BoxModel.ContentBounds(scrollContainer.ComputedPosition);
        float contentRight = content.X + scroll.ContentSize.X;
        float contentBottom = content.Y + scroll.ContentSize.Y;
        float childRight = child.ComputedPosition.X + child.BoxModel.ComputedSize.X;
        float childBottom = child.ComputedPosition.Y + child.BoxModel.ComputedSize.Y;

        Assert.True(child.ComputedPosition.X >= content.X);
        Assert.True(child.ComputedPosition.Y >= content.Y);
        Assert.True(childRight <= contentRight);
        Assert.True(childBottom <= contentBottom);
    }

    private static bool InvokeAccept(LayoutNode node)
        => InvokeCommand(node, (int)InputCommands.Accept);

    private static bool InvokeClick(LayoutNode node)
        => InvokeCommand(node, (int)InputCommands.ClickLeft);

    private static bool InvokeCommand(LayoutNode node, int command)
    {
        UiCommandHandler? handler = node.Interaction?.CommandHandlers?
            .FirstOrDefault(candidate => candidate.Handles(command));
        return handler is not null && handler.Callback(node, command);
    }
}
