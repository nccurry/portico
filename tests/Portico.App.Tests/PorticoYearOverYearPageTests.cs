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

public sealed class PorticoYearOverYearPageTests
{
    [Theory]
    [InlineData(1500f, 1000f)]
    [InlineData(1024f, 720f)]
    public void YearOverYear_PresetViewRendersSelectedMultiCardComparisonsAtBothDesktopSizes(float width, float height)
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.YearOverYear);
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        Update(scene);

        YearOverYearPageView view = Assert.IsType<YearOverYearPageView>(
            session.Report.Page(DashboardPageId.YearOverYear).YearOverYearView);
        Assert.Equal("Year over year", Text(scene, "PageTitle"));
        Assert.StartsWith("Latest data ", Text(scene, "YearOverYearLatestData"), StringComparison.Ordinal);
        Assert.Equal(YearOverYearViewMode.Preset, session.Presentation.YearOverYear.ViewMode);
        Assert.NotEmpty(session.Presentation.YearOverYear.PresetCategories);
        Assert.True(view.Comparisons.Count > 1);
        Assert.Equal(view.Comparisons.Count, ComparisonCards(scene).Count());
        Assert.Equal("View", Text(scene, "Control:YearOverYear:view:Label"));
        Assert.Equal("Choose categories", Text(scene, "Control:YearOverYear:preset_categories:Label"));
        Assert.Equal(
            ["All spending", "Utilities", "Discretionary", "Single category", "Single group"],
            State<SegmentedControlState>(scene, "Control:YearOverYear:View").Segments
                .Select(segment => segment.GetStateOrDefault<SegmentState>()!.Label));

        YearOverYearComparisonView first = view.Comparisons[0];
        ChartState chart = State<ChartState>(scene, $"YearOverYearChart:{first.Entity}");
        Assert.True(chart.XAxis is ChartDateAxisConfig);
        Assert.Equal(ChartLegendPlacement.Top, chart.Legend);
        if (chart.Series[0] is not ChartLineSeries current)
            throw new Xunit.Sdk.XunitException("Expected the current year to render as a line series.");
        Assert.Equal(4f, current.Style.LineWidth);
        Assert.Equal(new Color(93, 189, 174), current.Style.Color);
        Assert.All(
            chart.Series.Skip(1),
            series => Assert.True(
                series is ChartLineSeries { Style.Color: Color color }
                && color != current.Style.Color,
                "Expected prior years to render as distinct gray lines."));
        Assert.Equal(280f, Find(scene, $"YearOverYearChart:{first.Entity}").BoxModel.ComputedSize.Y);

        LayoutNode body = Find(scene, "PageBody");
        AssertWithinScrollContent(body, Find(scene, "YearOverYearControlBar"));
        Assert.All(ComparisonCards(scene), card => AssertWithinScrollContent(body, card));
    }

    [Fact]
    public void YearOverYear_PresetPickerAndSingleEntityViewsUpdateTheTypedComparison()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.YearOverYear);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        int initialCards = session.Report.Page(DashboardPageId.YearOverYear).YearOverYearView!.Comparisons.Count;
        string removedCategory = session.Presentation.YearOverYear.PresetCategories.Order(StringComparer.Ordinal).First();
        PorticoMultiSelectState<string> picker = scene.MultiSelectState(DashboardPageId.YearOverYear, "preset_categories")
            ?? throw new Xunit.Sdk.XunitException("Expected the Year-over-year preset picker state.");
        Assert.True(InvokeAccept(Find(scene, "Control:YearOverYear:PresetCategories")));
        Assert.True(picker.IsOpen);
        Assert.True(InvokeAccept(Find(scene, $"MultiSelectCheckbox:Control:YearOverYear:PresetCategories:{removedCategory}")));
        scene.Refresh();
        Assert.DoesNotContain(removedCategory, session.Presentation.YearOverYear.PresetCategories);
        Assert.Equal(initialCards - 1, session.Report.Page(DashboardPageId.YearOverYear).YearOverYearView!.Comparisons.Count);

        SegmentedControlState viewControl = State<SegmentedControlState>(scene, "Control:YearOverYear:View");
        Assert.True(InvokeAccept(viewControl.Segments[3]));
        scene.Refresh();
        Assert.Equal(YearOverYearViewMode.SingleCategory, session.Presentation.YearOverYear.ViewMode);
        Assert.NotNull(Find(scene, "Control:YearOverYear:SingleCategory"));
        ChooseOtherDropdownOption(scene, "Control:YearOverYear:SingleCategory");
        scene.Refresh();
        Assert.Single(session.Report.Page(DashboardPageId.YearOverYear).YearOverYearView!.Comparisons);
        Update(scene);
        Assert.Equal(470f, Find(scene, $"YearOverYearChart:{session.Presentation.YearOverYear.SingleCategory}").BoxModel.ComputedSize.Y);

        viewControl = State<SegmentedControlState>(scene, "Control:YearOverYear:View");
        Assert.True(InvokeAccept(viewControl.Segments[4]));
        scene.Refresh();
        Assert.Equal(YearOverYearViewMode.SingleGroup, session.Presentation.YearOverYear.ViewMode);
        Assert.NotNull(Find(scene, "Control:YearOverYear:SingleGroup"));
        ChooseOtherDropdownOption(scene, "Control:YearOverYear:SingleGroup");
        scene.Refresh();
        YearOverYearComparisonView comparison = Assert.Single(
            session.Report.Page(DashboardPageId.YearOverYear).YearOverYearView!.Comparisons);
        Assert.Equal(session.Presentation.YearOverYear.SingleGroup, comparison.Entity);

        CollapsibleState details = State<CollapsibleState>(scene, "Details");
        Assert.False(details.IsExpanded);
        Assert.True(InvokeClick(details.HeaderNode!));
        Assert.True(session.Presentation.YearOverYear.ExpandedDetails.Contains(comparison.Entity));
        Assert.True(details.IsExpanded);
    }

    [Fact]
    public void YearOverYear_WhenThereIsNoPreviousEntityHistoryShowsNotAvailableInTheCard()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        DashboardDefinition definition = TomlConfigurationLoader.LoadDashboard(Path.Combine(root, "dashboard.toml"));
        var snapshot = new PortfolioSnapshot(
        [
            new FinancialTransaction(
                "coverage",
                new DateOnly(2024, 1, 15),
                "Salary",
                "Income",
                "Checking",
                "Salary",
                1_000m,
                TransactionKind.Income),
            new FinancialTransaction(
                "current-food",
                new DateOnly(2025, 6, 15),
                "Food",
                "Living",
                "Checking",
                "Market",
                -100m,
                TransactionKind.Expense)
        ], [], []);
        var session = new DashboardSession(snapshot, settings, definition, PorticoDemoSessionFactory.CaptureDate);
        session.SelectPage(DashboardPageId.YearOverYear);
        session.SetControlValue(DashboardPageId.YearOverYear, "view", "single_category");
        session.SetControlValue(DashboardPageId.YearOverYear, "single_category", "Food");
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        YearOverYearComparisonView comparison = Assert.Single(
            session.Report.Page(DashboardPageId.YearOverYear).YearOverYearView!.Comparisons);
        ReportMetric previous = comparison.Metrics.Single(metric => metric.Label == "Previous year");
        Assert.Null(previous.Value);
        Assert.Equal("Not available", previous.Display);
        Assert.Contains(
            scene.Stage.Root.GetSelfAndDescendants(),
            node => string.Equals(node.TextNodeState?.RawText, "Not available", StringComparison.Ordinal));
    }

    private static void ChooseOtherDropdownOption(PorticoDashboardScene scene, string name)
    {
        LayoutNode dropdown = Find(scene, name);
        DropdownState state = dropdown.GetStateOrDefault<DropdownState>()
            ?? throw new Xunit.Sdk.XunitException($"Expected dropdown state on '{name}'.");
        int index = state.Options.Count > 1 && state.SelectedIndex == 0 ? 1 : 0;
        DropdownProcessor.SetSelected(dropdown, state, index, invokeCallback: true);
    }

    private static void Update(PorticoDashboardScene scene)
    {
        var input = new UiInput { DeltaSeconds = 1f / 60f };
        scene.Stage.Update(new MockTextMeasurer(), ref input);
    }

    private static IEnumerable<LayoutNode> Named(PorticoDashboardScene scene, string prefix)
        => scene.Stage.Root.GetSelfAndDescendants()
            .Where(node => node.Name?.StartsWith(prefix, StringComparison.Ordinal) == true);

    private static IEnumerable<LayoutNode> ComparisonCards(PorticoDashboardScene scene)
        => Named(scene, "YearOverYearComparison:")
            .Where(node => node.Name!.Count(character => character == ':') == 1);

    private static LayoutNode Find(PorticoDashboardScene scene, string name)
        => scene.Stage.Root.GetSelfAndDescendants().Single(node => string.Equals(node.Name, name, StringComparison.Ordinal));

    private static T State<T>(PorticoDashboardScene scene, string name)
        where T : class
        => scene.Stage.Root.GetSelfAndDescendants()
            .Where(node => string.Equals(node.Name, name, StringComparison.Ordinal))
            .Select(node => node.GetStateOrDefault<T>())
            .OfType<T>()
            .SingleOrDefault()
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

        throw new DirectoryNotFoundException("Could not find the Portico repository root.");
    }
}
