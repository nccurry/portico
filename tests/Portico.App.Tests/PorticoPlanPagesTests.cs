using System.Numerics;
using Portico.App;
using Portico.App.Ui.Components;
using Portico.CaptureHost;
using Portico.Dashboard;
using Portico.Finance;
using Roci.Core;
using Roci.Input;
using Roci.TestUtilities;
using Roci.Ui;
using Roci.Ui.Widgets;

namespace Portico.App.Tests;

public sealed class PorticoPlanPagesTests
{
    [Theory]
    [InlineData(1500f, 1000f)]
    [InlineData(1024f, 720f)]
    public void Budget_RendersTheSourceRegionsAtBothDesktopSizes(float width, float height)
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.Budget);
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        BudgetPageView view = Assert.IsType<BudgetPageView>(session.Report.Page(DashboardPageId.Budget).BudgetView);
        Assert.Equal("Budget", Text(scene, "PageTitle"));
        Assert.StartsWith("Spending through ", Text(scene, "BudgetPageCaption"), StringComparison.Ordinal);
        Assert.Null(view.EmptyMessage);
        Assert.NotEmpty(view.Analysis.Groups);
        Assert.NotNull(Find(scene, "BudgetControlBar"));
        Assert.NotNull(Find(scene, "BudgetMetricDeck"));
        Assert.NotNull(Find(scene, "Section:daily_budget_pace"));
        Assert.NotNull(Find(scene, "Chart:pace"));
        Assert.NotNull(Find(scene, "Section:plan_comparison"));
        Assert.NotNull(Find(scene, "Table:budget-performance"));
        Assert.NotNull(Find(scene, "Section:budget_group_detail"));
        Assert.True(FindOrDefault(scene, "Table:budget-transactions") is not null
            || FindOrDefault(scene, "BudgetTransactionsEmpty") is not null);
        Assert.NotNull(State<CollapsibleState>(scene, "Year-to-date position"));

        LayoutNode body = Find(scene, "PageBody");
        AssertWithinScrollContent(body, Find(scene, "BudgetControlBar"));
        AssertWithinScrollContent(body, Find(scene, "Section:daily_budget_pace"));
        AssertWithinScrollContent(body, Find(scene, "Section:plan_comparison"));
        AssertWithinScrollContent(body, Find(scene, "Section:budget_group_detail"));
    }

    [Fact]
    public void Budget_ControlsKeepTheSelectedGroupAndAdjustmentsInSync()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.Budget);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        string originalMonth = session.ControlValue(DashboardPageId.Budget, "month");
        string nextMonth = session.ControlOptions(DashboardPageId.Budget, "month")
            .First(value => !string.Equals(value, originalMonth, StringComparison.Ordinal));
        session.SetControlValue(DashboardPageId.Budget, "month", nextMonth);
        scene.Refresh();
        Assert.Equal(nextMonth, session.Filters.Budget!.SelectedMonth.ToString());

        Assert.True(InvokeClick(Find(scene, "Control:Budget:AdjustView")));
        scene.Refresh();
        Assert.True(session.Presentation.Budget.AdjustViewOpen);
        Assert.Equal("Adjust view", Text(scene, "BudgetAdjustPopover:Title"));

        string excludedGroup = session.ControlOptions(DashboardPageId.Budget, "exclude_groups")[0];
        PorticoMultiSelectState<string> groups = scene.MultiSelectState(DashboardPageId.Budget, "exclude_groups")
            ?? throw new Xunit.Sdk.XunitException("Expected the Budget adjustment picker state.");
        Assert.True(InvokeAccept(Find(scene, "Control:Budget:exclude_groups")));
        Assert.True(groups.IsOpen);
        Assert.True(InvokeAccept(Find(scene, $"MultiSelectCheckbox:Control:Budget:exclude_groups:{excludedGroup}")));
        scene.Refresh();
        Assert.Contains(excludedGroup, session.ControlValues(DashboardPageId.Budget, "exclude_groups"));
        Assert.True(session.Filters.Budget!.Adjustments.IsModified);

        DashboardWidgetReport performance = session.Report.Page(DashboardPageId.Budget).Widgets["budget.performance"];
        Assert.NotEmpty(performance.Rows);
        Assert.True(InvokeAccept(Find(scene, "TableRowSelection:budget-performance:0")));
        scene.Refresh();
        Assert.Equal(performance.Rows[0].Values[0], session.Presentation.Budget.SelectedGroup);

        CollapsibleState yearToDate = State<CollapsibleState>(scene, "Year-to-date position");
        Assert.True(InvokeClick(yearToDate.HeaderNode!));
        scene.Refresh();
        Assert.True(session.Presentation.Budget.YearToDateOpen);
        Assert.NotNull(Find(scene, "BudgetYearToDateContent"));

        Assert.True(InvokeAccept(Find(scene, "Control:Budget:ResetAdjustments")));
        scene.Refresh();
        Assert.False(session.Filters.Budget!.Adjustments.IsModified);
    }

    [Theory]
    [InlineData(1500f, 1000f)]
    [InlineData(1024f, 720f)]
    public void FinancialIndependence_RendersTheSourceRegionsAtBothDesktopSizes(float width, float height)
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.FinancialIndependence);
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        FinancialIndependencePageView view = Assert.IsType<FinancialIndependencePageView>(
            session.Report.Page(DashboardPageId.FinancialIndependence).FinancialIndependenceView);
        Assert.Equal("Financial independence", Text(scene, "PageTitle"));
        Assert.StartsWith("Transactions through ", Text(scene, "FinancialIndependencePageCaption"), StringComparison.Ordinal);
        Assert.Null(view.EmptyMessage);
        Assert.NotNull(Find(scene, "FinancialIndependenceControlBar"));
        Assert.NotNull(Find(scene, "Section:fi_scenario"));
        Assert.NotNull(Find(scene, "FinancialIndependenceMetricDeck"));
        Assert.NotNull(Find(scene, "Section:fi_projection"));
        Assert.NotNull(Find(scene, "Chart:projection"));
        Assert.NotNull(Find(scene, "Chart:funding"));
        Assert.NotNull(Find(scene, "Chart:sensitivity"));
        Assert.NotNull(State<CollapsibleState>(scene, "Source details"));

        LayoutNode body = Find(scene, "PageBody");
        AssertWithinScrollContent(body, Find(scene, "FinancialIndependenceControlBar"));
        AssertWithinScrollContent(body, Find(scene, "Section:fi_scenario"));
        AssertWithinScrollContent(body, Find(scene, "Section:fi_projection"));
    }

    [Fact]
    public void FinancialIndependence_SourceAndScenarioControlsUpdateAndResetTheReport()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.FinancialIndependence);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        FinancialIndependenceScenario initial = session.Filters.FinancialIndependenceScenario!;
        decimal assetsStep = session.Definition.Pages
            .Single(page => page.Id == DashboardPageId.FinancialIndependence)
            .Controls
            .Single(control => control.Id == "assets")
            .Step!.Value;
        decimal adjustedAssets = initial.Assets + assetsStep;
        session.SetControlNumber(DashboardPageId.FinancialIndependence, "assets", adjustedAssets);
        scene.Refresh();
        Assert.Equal(adjustedAssets, session.Filters.FinancialIndependenceScenario!.Assets);
        Assert.Throws<ArgumentOutOfRangeException>(() => session.SetControlNumber(
            DashboardPageId.FinancialIndependence,
            "withdrawal_rate",
            0m));

        Assert.True(InvokeClick(Find(scene, "Control:FinancialIndependence:AdjustSourceData")));
        scene.Refresh();
        Assert.True(session.Presentation.FinancialIndependence.AdjustSourceDataOpen);
        Assert.Equal("Adjust source data", Text(scene, "FinancialIndependenceSourcePopover:Title"));

        string account = session.ControlValues(DashboardPageId.FinancialIndependence, "include_accounts").First();
        PorticoMultiSelectState<string> accounts = scene.MultiSelectState(DashboardPageId.FinancialIndependence, "include_accounts")
            ?? throw new Xunit.Sdk.XunitException("Expected the FI account picker state.");
        Assert.True(InvokeAccept(Find(scene, "Control:FinancialIndependence:include_accounts")));
        Assert.True(accounts.IsOpen);
        Assert.True(InvokeAccept(Find(scene, $"MultiSelectCheckbox:Control:FinancialIndependence:include_accounts:{account}")));
        scene.Refresh();
        Assert.DoesNotContain(account, session.ControlValues(DashboardPageId.FinancialIndependence, "include_accounts"));

        Assert.True(InvokeAccept(Find(scene, "Control:FinancialIndependence:ResetScenario")));
        scene.Refresh();
        Assert.NotEqual(adjustedAssets, session.Filters.FinancialIndependenceScenario!.Assets);

        CollapsibleState details = State<CollapsibleState>(scene, "Source details");
        Assert.True(InvokeClick(details.HeaderNode!));
        scene.Refresh();
        Assert.True(session.Presentation.FinancialIndependence.SourceDetailsOpen);
        session.SetControlValue(DashboardPageId.FinancialIndependence, "source_tab", "Spending");
        scene.Refresh();
        Assert.Equal("Spending", session.Presentation.FinancialIndependence.SourceDetailsTab);
        Assert.NotNull(Find(scene, "FinancialIndependenceSourceSpending"));
    }

    [Fact]
    public void FinancialIndependence_OpenSourcePopoverKeepsTheSharedHeaderAboveTheScrollableBody()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.FinancialIndependence);
        session.SetFinancialIndependenceAdjustSourceDataOpen(true);
        var scene = new PorticoDashboardScene(
            new Vector2(1500f, 1000f),
            session,
            new PorticoDashboardDisplayState(isDemoData: true));
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        LayoutNode banner = Find(scene, "DemoDataBanner");
        LayoutNode header = Find(scene, "PageHeader");
        LayoutNode body = Find(scene, "PageBody");
        float bannerBottom = banner.ComputedPosition.Y + banner.BoxModel.ComputedSize.Y;
        float headerBottom = header.ComputedPosition.Y + header.BoxModel.ComputedSize.Y;

        Assert.True(bannerBottom <= header.ComputedPosition.Y);
        Assert.True(headerBottom <= body.ComputedPosition.Y);
        Assert.NotNull(Find(scene, "FinancialIndependenceSourcePopover"));
    }

    private static LayoutNode Find(PorticoDashboardScene scene, string name)
        => FindOrDefault(scene, name)
            ?? throw new Xunit.Sdk.XunitException($"Expected node '{name}'.");

    private static LayoutNode? FindOrDefault(PorticoDashboardScene scene, string name)
        => scene.Stage.Root.GetSelfAndDescendants()
            .SingleOrDefault(node => string.Equals(node.Name, name, StringComparison.Ordinal))
            ;

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
}
