using System.Numerics;
using Portico.Desktop.Ui.Components;
using Portico.CaptureHost;
using Portico.Desktop;
using Roci.Core;
using Roci.Input;
using Roci.TestUtilities;
using Roci.Ui;
using Roci.Ui.Charts;
using Roci.Ui.Widgets;

namespace Portico.Desktop.Tests;

public sealed class PorticoIncomeSavingsPageTests
{
    [Theory]
    [InlineData(1500f, 1000f)]
    [InlineData(1024f, 720f)]
    public void IncomeSavings_RendersTheSourceRegionsAtBothDesktopSizes(float width, float height)
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.IncomeSavings);
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        Update(scene);

        Assert.Equal("Income and savings", Text(scene, "PageTitle"));
        Assert.Equal("Time frame", Text(scene, "Control:IncomeSavings:lookback:Label"));
        Assert.Equal("Calculation", Text(scene, "Control:IncomeSavings:calculation:Label"));
        Assert.Equal(
            ["3M", "6M", "1Y", "2Y"],
            State<SegmentedControlState>(scene, "Control:IncomeSavings:TimeFrame").Segments
                .Select(segment => segment.GetStateOrDefault<SegmentState>()!.Label));
        Assert.Equal(
            ["Regular", "Actual"],
            State<SegmentedControlState>(scene, "Control:IncomeSavings:Calculation").Segments
                .Select(segment => segment.GetStateOrDefault<SegmentState>()!.Label));
        Assert.Equal("Adjust calculation", Text(scene, "Control:IncomeSavings:AdjustCalculation:Text"));
        Assert.Equal(4, Named(scene, "IncomeSavingsMetric:").Count());

        ChartState cashFlow = State<ChartState>(scene, "Chart:cash-flow");
        Assert.Contains(cashFlow.Series, series => series is ChartBarSeries);
        Assert.Contains(cashFlow.Series, series => series is ChartLineSeries);
        Assert.NotNull(Find(scene, "Chart:savings-rate"));
        Assert.NotNull(Find(scene, "IncomeSavingsPositiveMonthsBadge"));
        Assert.NotNull(Find(scene, "Section:month_detail"));
        Assert.NotNull(Find(scene, "IncomeSavingsDetailTabs"));
        Assert.Single(
            scene.Stage.Root.GetSelfAndDescendants(),
            node => string.Equals(node.Name, "Monthly totals", StringComparison.Ordinal)
                && node.GetStateOrDefault<CollapsibleState>() is not null);

        LayoutNode body = Find(scene, "PageBody");
        AssertWithinScrollContent(body, Find(scene, "IncomeSavingsControlBar"));
        AssertWithinScrollContent(body, Find(scene, "Section:monthly_cash_flow"));
        AssertWithinScrollContent(body, Find(scene, "Section:month_detail"));
        Assert.InRange(Find(scene, "Control:IncomeSavings:AdjustCalculation").BoxModel.ComputedSize.X, 1f, 220f);
    }

    [Fact]
    public void IncomeSavings_ControlsUpdateTheCalculationAdjustmentsAndDetailTab()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.IncomeSavings);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        SegmentedControlState calculation = State<SegmentedControlState>(scene, "Control:IncomeSavings:Calculation");
        Assert.True(InvokeAccept(calculation.Segments[1]));
        scene.Refresh();
        Assert.False(session.Filters.RegularIncome);
        Assert.Equal("Actual calculation", Text(scene, "IncomeSavingsPageCaption"));

        Assert.True(InvokeClick(Find(scene, "Control:IncomeSavings:AdjustCalculation")));
        scene.Refresh();
        Assert.True(session.Presentation.IncomeSavings.AdjustCalculationOpen);
        Assert.Equal("Adjust calculation", Text(scene, "IncomeSavingsAdjustPopover:Title"));

        string category = session.ControlOptions(DashboardPageId.IncomeSavings, "exclude_income_categories")[0];
        PorticoMultiSelectState<string> categories = scene.MultiSelectState(
            DashboardPageId.IncomeSavings,
            "exclude_income_categories")
            ?? throw new Xunit.Sdk.XunitException("Expected the Income adjustment multi-select state.");
        Assert.True(InvokeAccept(Find(scene, "Control:IncomeSavings:exclude_income_categories")));
        Assert.True(categories.IsOpen);
        Assert.True(InvokeAccept(Find(scene, $"MultiSelectCheckbox:Control:IncomeSavings:exclude_income_categories:{category}")));
        scene.Refresh();

        Assert.Contains(category, session.ControlValues(DashboardPageId.IncomeSavings, "exclude_income_categories"));
        Assert.Contains("modified", Text(scene, "Control:IncomeSavings:AdjustCalculation:Text"), StringComparison.Ordinal);
        Assert.True(InvokeAccept(Find(scene, "Control:IncomeSavings:ResetAdjustments")));
        scene.Refresh();
        Assert.Empty(session.ControlValues(DashboardPageId.IncomeSavings, "exclude_income_categories"));

        SegmentedControlState tabs = State<SegmentedControlState>(scene, "IncomeSavingsDetailTabs");
        Assert.True(InvokeAccept(tabs.Segments[1]));
        scene.Refresh();
        Assert.Equal("Excluded", session.Presentation.IncomeSavings.DetailTab);
        Assert.NotNull(Find(scene, "IncomeSavingsExcludedTransactions"));
    }

    [Fact]
    public void IncomeSavings_KeepsTheExcludedMonthDetailWhenAdjustmentsExcludeEveryRow()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.IncomeSavings);
        session.SetControlValues(
            DashboardPageId.IncomeSavings,
            "exclude_income_categories",
            session.ControlOptions(DashboardPageId.IncomeSavings, "exclude_income_categories"));
        session.SetControlValues(
            DashboardPageId.IncomeSavings,
            "exclude_expense_groups",
            session.ControlOptions(DashboardPageId.IncomeSavings, "exclude_expense_groups"));
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);
        Update(scene);

        Assert.NotNull(Find(scene, "IncomeSavingsCashFlowEmpty"));
        Assert.NotNull(Find(scene, "Section:month_detail"));
        Assert.NotNull(Find(scene, "IncomeSavingsDetailTabs"));
        Assert.Contains(
            scene.Stage.Root.GetSelfAndDescendants(),
            node => string.Equals(node.Name, "Monthly totals", StringComparison.Ordinal)
                && node.GetStateOrDefault<CollapsibleState>() is not null);
    }

    private static void Update(PorticoDashboardScene scene)
    {
        var input = new UiInput { DeltaSeconds = 1f / 60f };
        scene.Stage.Update(new MockTextMeasurer(), ref input);
    }

    private static IEnumerable<LayoutNode> Named(PorticoDashboardScene scene, string prefix)
        => scene.Stage.Root.GetSelfAndDescendants()
            .Where(node => node.Name?.StartsWith(prefix, StringComparison.Ordinal) == true);

    private static LayoutNode Find(PorticoDashboardScene scene, string name)
        => scene.Stage.Root.GetSelfAndDescendants().Single(node => string.Equals(node.Name, name, StringComparison.Ordinal));

    private static T State<T>(PorticoDashboardScene scene, string name)
        where T : class
        => Find(scene, name).GetStateOrDefault<T>()
            ?? throw new Xunit.Sdk.XunitException($"Expected '{typeof(T).Name}' state on '{name}'.");

    private static string Text(PorticoDashboardScene scene, string name)
        => Find(scene, name).TextNodeState?.RawText
            ?? throw new Xunit.Sdk.XunitException($"Expected text node '{name}'.");

    private static bool InvokeAccept(LayoutNode node)
        => Invoke(node, (int)InputCommands.Accept);

    private static bool InvokeClick(LayoutNode node)
        => Invoke(node, (int)InputCommands.ClickLeft);

    private static bool Invoke(LayoutNode node, int command)
    {
        UiCommandHandler? handler = node.Interaction?.CommandHandlers?
            .FirstOrDefault(candidate => candidate.Handles(command));
        return handler is not null && handler.Callback(node, command);
    }

    private static void AssertWithinScrollContent(LayoutNode scrollContainer, LayoutNode child)
    {
        ScrollState scroll = scrollContainer.ScrollState
            ?? throw new Xunit.Sdk.XunitException($"Expected '{scrollContainer.Name}' to scroll.");
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
}
