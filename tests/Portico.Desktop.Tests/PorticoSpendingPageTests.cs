using System.Numerics;
using Portico.Configuration;
using Portico.Desktop;
using Portico.Desktop.Ui.Components;
using Portico.CaptureHost;
using Portico.Desktop;
using Portico.Finance;
using Roci.Core;
using Roci.Input;
using Roci.TestUtilities;
using Roci.Ui;
using Roci.Ui.Charts;
using Roci.Ui.Widgets;

namespace Portico.Desktop.Tests;

public sealed class PorticoSpendingPageTests
{
    [Theory]
    [InlineData(1500f, 1000f)]
    [InlineData(1024f, 720f)]
    public void Spending_RendersTheSourceRegionsAndHorizontalRankingAtBothDesktopSizes(float width, float height)
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.Spending);
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        Assert.Equal("Spending by category", Text(scene, "PageTitle"));
        Assert.StartsWith("Spending through ", Text(scene, "SpendingPageCaption"), StringComparison.Ordinal);
        Assert.Equal("Time frame", Text(scene, "Control:Spending:lookback:Label"));
        Assert.Null(FindOrDefault(scene, "Control:Spending:adjust_view:Label"));

        LayoutNode controlBar = Find(scene, "SpendingControlBar");
        LayoutNode timeFrameLabel = Find(scene, "Control:Spending:lookback:Label");
        LayoutNode timeFrameControl = Find(scene, "Control:Spending:SpendingTimeFrame");
        Assert.Equal(Color.Transparent, controlBar.VisualStyle.BackgroundColor);
        Assert.True(timeFrameLabel.ComputedPosition.Y + timeFrameLabel.BoxModel.ComputedSize.Y <= timeFrameControl.ComputedPosition.Y);
        LayoutNode adjustView = Find(scene, "Control:Spending:AdjustView");
        Assert.InRange(adjustView.BoxModel.ComputedSize.X, 300f, 340f);
        LayoutNode breakdownLabel = Find(scene, "SpendingBreakdownControl:Label");
        LayoutNode breakdownControl = Find(scene, "Control:Spending:Breakdown");
        Assert.True(breakdownLabel.ComputedPosition.Y + breakdownLabel.BoxModel.ComputedSize.Y <= breakdownControl.ComputedPosition.Y);

        SegmentedControlState timeFrame = State<SegmentedControlState>(scene, "Control:Spending:SpendingTimeFrame");
        Assert.Equal(["3M", "6M", "1Y", "2Y"], timeFrame.Segments.Select(segment => segment.GetStateOrDefault<SegmentState>()!.Label));
        Assert.NotNull(FindOrDefault(scene, "SpendingMetric:Total spending"));
        Assert.NotNull(FindOrDefault(scene, "SpendingMetric:Average monthly"));
        Assert.NotNull(FindOrDefault(scene, "SpendingMetric:Change vs previous 12 months"));

        ChartState ranking = State<ChartState>(scene, "Chart:ranking");
        ChartBarSeries bars = Assert.Single(ranking.Series) switch
        {
            ChartBarSeries value => value,
            _ => throw new Xunit.Sdk.XunitException("Expected the Spending ranking to use a bar series.")
        };
        Assert.Equal(ChartBarOrientation.Horizontal, bars.Orientation);
        Assert.True(ranking.XAxis is ChartLinearAxisConfig);
        Assert.True(ranking.YAxis is ChartCategoryAxisConfig);
        Assert.True(ranking.XAxis is ChartLinearAxisConfig { Title: "Spending ($)" });
        Assert.True(ranking.YAxis is ChartCategoryAxisConfig { Title: null });
        ChartState trend = State<ChartState>(scene, "Chart:trend");
        Assert.True(trend.XAxis is ChartDateAxisConfig { Title: null });
        Assert.True(trend.YAxis is ChartLinearAxisConfig { Title: "Spending ($)" });
        Assert.Equal("Monthly trend · top 5", Text(scene, "WidgetTitle:trend"));
        int rankedCount = bars.Values.Length;
        Assert.Equal($"Top {rankedCount} categories by spending", Text(scene, "WidgetTitle:ranking"));
        Assert.NotNull(FindOrDefault(scene, "SpendingOverview:Header:Monthly trend"));
        Assert.NotNull(FindOrDefault(scene, "SpendingOverview:Header:Transactions"));
        DashboardWidgetReport overview = session.Report.Page(DashboardPageId.Spending).Widgets["spending.overview"];
        ReportTableRow firstOverviewRow = overview.Rows[0];
        LayoutNode firstOverviewHeader = Find(scene, $"SpendingOverview:Header:{overview.Columns[0]}");
        LayoutNode firstOverviewCell = scene.Stage.Root.GetSelfAndDescendants()
            .First(node => string.Equals(
                node.Name,
                $"SpendingOverviewRow:{firstOverviewRow.Values[0]}:{firstOverviewRow.Values[0]}",
                StringComparison.Ordinal));
        Assert.InRange(
            MathF.Abs(firstOverviewHeader.ComputedPosition.X - firstOverviewCell.ComputedPosition.X),
            0f,
            12f);
        Assert.NotNull(FindOrDefault(scene, "Section:selected_detail"));
        Assert.NotNull(FindOrDefault(scene, "SpendingDetailMetric:Spending"));
        Assert.NotNull(FindOrDefault(scene, "SpendingDetailMetric:Average monthly"));
        Assert.NotNull(FindOrDefault(scene, "SpendingDetailMetric:Share of view"));

        LayoutNode body = Find(scene, "PageBody");
        ScrollState pageScroll = body.ScrollState
            ?? throw new Xunit.Sdk.XunitException("Expected the Spending page body to scroll.");
        Assert.Equal(Vector2.Zero, pageScroll.ScrollOffset);
        AssertWithinScrollContent(body, Find(scene, "Section:where_money_went"));
        AssertWithinScrollContent(body, Find(scene, "Section:selected_detail"));
    }

    [Fact]
    public void Spending_KeyboardAndPointerControlsUpdateTheTypedReportAndResetAdjustments()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.Spending);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        SegmentedControlState timeFrame = State<SegmentedControlState>(scene, "Control:Spending:SpendingTimeFrame");
        Assert.True(InvokeAccept(timeFrame.Segments[0]));
        scene.Refresh();
        Assert.Equal(3, session.Filters.LookbackMonths);

        SegmentedControlState comparison = State<SegmentedControlState>(scene, "Control:Spending:SpendingComparison");
        Assert.True(InvokeAccept(comparison.Segments[1]));
        scene.Refresh();
        Assert.Equal(SpendingComparison.LastYear, session.Filters.SpendingComparison);

        Assert.True(InvokeClick(Find(scene, "Control:Spending:AdjustView")));
        scene.Refresh();
        Assert.True(session.Presentation.Spending.AdjustViewOpen);
        Assert.Equal("Adjust view", Text(scene, "SpendingAdjustPopover:Title"));

        string group = session.ControlOptions(DashboardPageId.Spending, "exclude_groups")[0];
        PorticoMultiSelectState<string> groups = scene.MultiSelectState(DashboardPageId.Spending, "exclude_groups")
            ?? throw new Xunit.Sdk.XunitException("Expected the Spending group multi-select state.");
        Assert.True(InvokeAccept(Find(scene, "Control:Spending:exclude_groups")));
        Assert.True(groups.IsOpen);
        Assert.True(InvokeAccept(Find(scene, $"MultiSelectCheckbox:Control:Spending:exclude_groups:{group}")));
        scene.Refresh();
        Assert.Contains(group, session.ControlValues(DashboardPageId.Spending, "exclude_groups"));
        Assert.True(session.Filters.SpendingAdjustments!.IsModified);
        Assert.Equal("Adjust view · modified", Text(scene, "Control:Spending:AdjustView:Text"));
        scene.Stage.RefreshLayout(new MockTextMeasurer());
        LayoutNode exclusionBadge = Find(scene, "SpendingExclusionBadge");
        LayoutNode moneyPanel = Find(scene, "Section:where_money_went");
        float badgeBottom = exclusionBadge.ComputedPosition.Y + exclusionBadge.BoxModel.ComputedSize.Y;
        float badgeGap = moneyPanel.ComputedPosition.Y - badgeBottom;
        Assert.True(
            badgeGap >= 8f,
            $"Expected a readable gap below the exclusion badge, but it was {badgeGap:0.##} pixels.");

        TextInputState includedTerms = State<TextInputState>(scene, "Control:Spending:include_transaction_names:Input");
        includedTerms.Text = "market";
        includedTerms.OnTextChanged!(includedTerms.Text);
        Assert.True(InvokeAccept(Find(scene, "Control:Spending:include_transaction_names:Add")));
        scene.Refresh();
        Assert.Contains("market", session.ControlValues(DashboardPageId.Spending, "include_transaction_names"));

        Assert.True(InvokeAccept(Find(scene, "Control:Spending:exclude_large_expenses")));
        scene.Refresh();
        Assert.True(session.Filters.SpendingAdjustments!.ExcludeLargeExpenses);
        Assert.NotNull(FindOrDefault(scene, "Control:Spending:expense_limit"));

        Assert.True(InvokeAccept(Find(scene, "Control:Spending:ResetAdjustments")));
        scene.Refresh();
        Assert.False(session.Filters.SpendingAdjustments!.IsModified);
        Assert.Empty(session.ControlValues(DashboardPageId.Spending, "exclude_groups"));
        Assert.Empty(session.ControlValues(DashboardPageId.Spending, "include_transaction_names"));
        Assert.False(session.Filters.SpendingAdjustments.ExcludeLargeExpenses);
        Assert.Equal("Adjust view", Text(scene, "Control:Spending:AdjustView:Text"));
    }

    [Fact]
    public void Spending_RetainsSelectionAcrossNavigationMasksValuesAndClearsASelectionThatDisappears()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.Spending);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);
        string selected = session.Report.Page(DashboardPageId.Spending).Widgets["spending.overview"].Rows[0].Values[0];

        Assert.True(InvokeClick(Find(scene, $"SpendingOverviewRow:{selected}")));
        scene.Refresh();
        Assert.Equal(selected, session.Presentation.Spending.SelectedCategory);

        scene.SelectPage(DashboardPageId.Home);
        scene.Refresh();
        scene.SelectPage(DashboardPageId.Spending);
        scene.Refresh();
        Assert.Equal(selected, session.Presentation.Spending.SelectedCategory);

        scene.ToggleHideValues();
        scene.Refresh();
        Assert.True(scene.DisplayState.HideValues);
        Assert.Equal("Hidden", Text(scene, "MetricValue:Spending:Total spending"));

        IReadOnlyList<string> months = session.ControlOptions(DashboardPageId.Spending, "detail_month");
        string oldestVisibleMonth = months[^1];
        session.SetControlValue(DashboardPageId.Spending, "detail_month", oldestVisibleMonth);
        session.SetControlValue(DashboardPageId.Spending, "lookback", "3");
        scene.Refresh();
        Assert.Equal("all", session.Presentation.Spending.DetailMonth);

        session.SetControlValues(DashboardPageId.Spending, "exclude_categories", [selected]);
        scene.Refresh();
        Assert.Null(session.Presentation.Spending.SelectedCategory);
        Assert.DoesNotContain(
            session.Report.Page(DashboardPageId.Spending).Widgets["spending.overview"].Rows,
            row => string.Equals(row.Values[0], selected, StringComparison.Ordinal));
    }

    [Fact]
    public void Spending_StopsAtTheSourceEmptyStateWhenOnlyComparisonRowsRemain()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = DesktopTestSessions.LoadSettings(root);
        DashboardDefinition definition = DesktopTestSessions.LoadDefinition(root);
        var snapshot = new PortfolioSnapshot(
            [
                new FinancialTransaction(
                    "comparison",
                    new DateOnly(2025, 2, 15),
                    "Food",
                    "Living",
                    "Checking",
                    "Market",
                    -40m,
                    TransactionKind.Expense),
                new FinancialTransaction(
                    "current",
                    new DateOnly(2025, 6, 15),
                    "Flight",
                    "Travel",
                    "Checking",
                    "Flight",
                    -100m,
                    TransactionKind.Expense)
            ],
            [],
            []);
        var session = DesktopTestSessions.Create(snapshot, settings, definition);
        session.SelectPage(DashboardPageId.Spending);
        session.SetControlValue(DashboardPageId.Spending, "spending_view", "all");
        session.SetControlValue(DashboardPageId.Spending, "lookback", "3");
        session.SetControlValues(DashboardPageId.Spending, "exclude_groups", ["Travel"]);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        Assert.Equal("No spending is included in this view.", Text(scene, "SpendingNoIncludedRows:Title"));
        Assert.Equal("Adjust the filters to continue.", Text(scene, "SpendingNoIncludedRows:Message"));
        Assert.Null(FindOrDefault(scene, "SpendingMetricDeck"));
        Assert.Null(FindOrDefault(scene, "Section:selected_detail"));
        Assert.Contains(
            scene.Stage.Root.GetSelfAndDescendants(),
            node => string.Equals(node.Name, "Excluded from this view (1)", StringComparison.Ordinal));
    }

    private static LayoutNode Find(PorticoDashboardScene scene, string name)
        => FindOrDefault(scene, name)
            ?? throw new Xunit.Sdk.XunitException(
                $"Expected node '{name}'. Metric nodes: {string.Join(", ", scene.Stage.Root.GetSelfAndDescendants().Where(node => node.Name?.StartsWith("Metric", StringComparison.Ordinal) == true).Select(node => node.Name))}");

    private static LayoutNode? FindOrDefault(PorticoDashboardScene scene, string name)
        => scene.Stage.Root.GetSelfAndDescendants()
            .SingleOrDefault(node => string.Equals(node.Name, name, StringComparison.Ordinal));

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

    private static string FindRepositoryRoot()
    {
        string[] startingPoints = [Directory.GetCurrentDirectory(), AppContext.BaseDirectory];
        foreach (string start in startingPoints)
        {
            var current = new DirectoryInfo(start);
            while (current is not null)
            {
                if (File.Exists(Path.Combine(current.FullName, "portico.toml"))
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
