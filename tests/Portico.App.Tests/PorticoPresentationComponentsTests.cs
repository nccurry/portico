using System.Numerics;
using Portico.App;
using Portico.App.Ui.Components;
using Portico.CaptureHost;
using Portico.Dashboard;
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

        Assert.Equal(HomeTimeFrame.FiveYears, session.Presentation.Home.TimeFrame);
        Assert.Equal(4, State<SegmentedControlState>(scene, "Control:Home:time_frame").SelectedIndex);
    }

    [Fact]
    public void IncomeControls_WrapAtNarrowDesktopWidthAndKeepNativeTabSelectionAfterRebuild()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.IncomeSavings);
        var scene = new PorticoDashboardScene(new Vector2(1024f, 720f), session);
        var input = new UiInput { DeltaSeconds = 1f / 60f };
        scene.Stage.Update(new MockTextMeasurer(), ref input);

        LayoutNode view = FindNode(scene, "Control:IncomeSavings:income_view:Group");
        LayoutNode categories = FindNode(scene, "Control:IncomeSavings:exclude_income_categories:Group");
        LayoutNode detail = FindNode(scene, "Control:IncomeSavings:detail_tab:Group");
        LayoutNode detailLabel = FindNode(scene, "Control:IncomeSavings:detail_tab:Label");
        LayoutNode tabPanelNode = FindNode(scene, "Control:IncomeSavings:detail_tab");
        LayoutNode controlBar = FindNode(scene, "ControlBar");
        Assert.True(categories.ComputedPosition.X > view.ComputedPosition.X);
        Assert.True(detail.ComputedPosition.Y > categories.ComputedPosition.Y);
        Assert.True(detail.ComputedPosition.Y + detail.BoxModel.ComputedSize.Y <= controlBar.ComputedPosition.Y + controlBar.BoxModel.ComputedSize.Y);
        Assert.True(detailLabel.ComputedPosition.Y < tabPanelNode.ComputedPosition.Y);
        Assert.Single(scene.Stage.Root.GetSelfAndDescendants(), node => node.Name == "Control:IncomeSavings:exclude_income_categories:Label");

        TabPanelState tabs = State<TabPanelState>(scene, "Control:IncomeSavings:detail_tab");
        Assert.Equal(["Included", "Excluded"], tabs.Tabs.Select(tab => tab.Label));
        Assert.Equal(0, tabs.ActiveIndex);
        Assert.True(InvokeAccept(tabs.Tabs[1].HeaderNode));
        scene.Refresh();

        Assert.Equal("Excluded", session.Presentation.IncomeSavings.DetailTab);
        Assert.Equal(1, State<TabPanelState>(scene, "Control:IncomeSavings:detail_tab").ActiveIndex);
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

    private static LayoutNode FindNode(PorticoDashboardScene scene, string name)
        => FindNode(scene.Stage, name);

    private static LayoutNode FindNode(UiStage stage, string name)
        => stage.Root.GetSelfAndDescendants().Single(node => string.Equals(node.Name, name, StringComparison.Ordinal));

    private static LayoutNode Parent(PorticoDashboardScene scene, string name)
        => FindNode(scene, name).Parent
            ?? throw new Xunit.Sdk.XunitException($"Expected node '{name}' to have a parent.");

    private static T State<T>(PorticoDashboardScene scene, string name)
        where T : class
        => FindNode(scene, name).GetStateOrDefault<T>()
            ?? throw new Xunit.Sdk.XunitException($"Expected state '{typeof(T).Name}' on '{name}'.");

    private static string Text(PorticoDashboardScene scene, string name) => Text(scene.Stage, name);

    private static string Text(UiStage stage, string name)
        => FindNode(stage, name).TextNodeState?.RawText
            ?? throw new Xunit.Sdk.XunitException($"Expected text node '{name}'.");

    private static bool InvokeAccept(LayoutNode node)
    {
        int command = (int)InputCommands.Accept;
        UiCommandHandler? handler = node.Interaction?.CommandHandlers?
            .FirstOrDefault(candidate => candidate.Handles(command));
        return handler is not null && handler.Callback(node, command);
    }
}
