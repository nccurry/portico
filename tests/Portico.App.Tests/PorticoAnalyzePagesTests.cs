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

public sealed class PorticoAnalyzePagesTests
{
    [Theory]
    [InlineData(1500f, 1000f)]
    [InlineData(1024f, 720f)]
    public void Subscriptions_RendersTheSourceRegionsAtBothDesktopSizes(float width, float height)
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.Subscriptions);
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        DashboardControlDefinition settings = session.Definition.Pages
            .Single(page => page.Id == DashboardPageId.Subscriptions)
            .Controls
            .Single(control => control.Id == "subscription_settings");
        SubscriptionsPageView view = Assert.IsType<SubscriptionsPageView>(
            session.Report.Page(DashboardPageId.Subscriptions).SubscriptionsView);
        Assert.Equal(DashboardControlKind.Collapsible, settings.Kind);
        Assert.Equal("Subscriptions", Text(scene, "PageTitle"));
        Assert.StartsWith("Transaction history through ", Text(scene, "SubscriptionsPageCaption"), StringComparison.Ordinal);
        Assert.NotEmpty(view.Analysis.Active);
        Assert.NotNull(Find(scene, "SubscriptionsControlBar"));
        Assert.NotNull(Find(scene, "SubscriptionsMetricDeck"));
        Assert.NotNull(Find(scene, "Section:subscription_inventory"));
        Assert.NotNull(Find(scene, "Section:subscription_lifecycle"));
        Assert.NotNull(Find(scene, "Section:subscription_history"));
        Assert.NotNull(Find(scene, "Chart:lifecycle"));
        Assert.True(State<ChartState>(scene, "Chart:lifecycle").Series.Single() is ChartTimelineSeries);

        LayoutNode body = Find(scene, "PageBody");
        AssertWithinScrollContent(body, Find(scene, "SubscriptionsControlBar"));
        AssertWithinScrollContent(body, Find(scene, "Section:subscription_inventory"));
        AssertWithinScrollContent(body, Find(scene, "Section:subscription_lifecycle"));
        AssertWithinScrollContent(body, Find(scene, "Section:subscription_history"));
    }

    [Fact]
    public void Subscriptions_SettingsControlsChangeTheReportAndSelectedMerchantDetail()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.Subscriptions);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        Assert.True(InvokeClick(Find(scene, "Subscription settings Header")));
        scene.Refresh();
        Assert.True(session.Presentation.Subscriptions.SettingsOpen);
        Assert.NotNull(Find(scene, "SubscriptionSettingsContent"));
        Assert.NotNull(State<SliderState>(scene, "Control:Subscriptions:minimum_confidence"));

        string removedCategory = session.ControlValues(DashboardPageId.Subscriptions, "subscription_categories")
            .Order(StringComparer.Ordinal)
            .First();
        PorticoMultiSelectState<string> categories = scene.MultiSelectState(
            DashboardPageId.Subscriptions,
            "subscription_categories")
            ?? throw new Xunit.Sdk.XunitException("Expected the subscription category picker state.");
        Assert.True(InvokeAccept(Find(scene, "Control:Subscriptions:subscription_categories")));
        Assert.True(categories.IsOpen);
        Assert.True(InvokeAccept(Find(scene, $"MultiSelectCheckbox:Control:Subscriptions:subscription_categories:{removedCategory}")));
        scene.Refresh();
        Assert.DoesNotContain(removedCategory, session.ControlValues(DashboardPageId.Subscriptions, "subscription_categories"));

        DashboardWidgetReport inventory = session.Report.Page(DashboardPageId.Subscriptions).Widgets["subscriptions.active"];
        Assert.NotEmpty(inventory.Rows);
        string selectedMerchant = inventory.Rows[0].Values[0];
        Assert.True(InvokeClick(Find(scene, "TableRowSelection:subscriptions-active:0")));
        scene.Refresh();
        Assert.Equal(selectedMerchant, session.Presentation.Subscriptions.SelectedMerchant);
        Assert.Equal(selectedMerchant, Text(scene, "Section:subscription_detail:Title"));
        Assert.NotEmpty(State<ChartState>(scene, "Chart:detail-charge-history").Series);

        SegmentedControlState lifecycleScope = State<SegmentedControlState>(scene, "Control:Subscriptions:TimelineScope");
        Assert.True(InvokeAccept(lifecycleScope.Segments[1]));
        scene.Refresh();
        Assert.Equal("all", session.Presentation.Subscriptions.TimelineScope);

        session.SetControlValue(DashboardPageId.Subscriptions, "history_lookback", "3m");
        scene.Refresh();
        Assert.Equal("3m", session.Presentation.Subscriptions.HistoryLookback);
    }

    [Theory]
    [InlineData(1500f, 1000f)]
    [InlineData(1024f, 720f)]
    public void Merchants_RendersTheSourceRegionsAtBothDesktopSizes(float width, float height)
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.Merchants);
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        MerchantsPageView view = Assert.IsType<MerchantsPageView>(session.Report.Page(DashboardPageId.Merchants).MerchantsView);
        Assert.Equal("Spending by merchant", Text(scene, "PageTitle"));
        Assert.StartsWith("Spending through ", Text(scene, "MerchantsPageCaption"), StringComparison.Ordinal);
        Assert.NotEmpty(view.Analysis.Overview);
        Assert.NotNull(Find(scene, "MerchantsControlBar"));
        Assert.NotNull(Find(scene, "MerchantsMetricDeck"));
        Assert.NotNull(Find(scene, "Section:merchant_rankings"));
        LayoutNode rankingPane = Find(scene, "MerchantsRankingPane");
        LayoutNode overviewPane = Find(scene, "MerchantsOverviewPane");
        LayoutNode merchantTable = Find(scene, "Table:merchant-overview");
        LayoutNode tableHeader = Find(scene, "TableHeader:merchant-overview");
        LayoutNode firstRow = Find(scene, "TableRowSelection:merchant-overview:0");
        Assert.Equal(merchantTable.BoxModel.ComputedSize.X, tableHeader.BoxModel.ComputedSize.X);
        Assert.Equal(merchantTable.BoxModel.ComputedSize.X, firstRow.BoxModel.ComputedSize.X);
        Assert.Single(
            firstRow.GetSelfAndDescendants(),
            node => node.Name == "TableRowSelection:merchant-overview:0:Cell:0");
        if (width == 1500f)
        {
            Assert.Equal(rankingPane.ComputedPosition.Y, overviewPane.ComputedPosition.Y);
            Assert.True(overviewPane.ComputedPosition.X > rankingPane.ComputedPosition.X);
            Assert.True(
                merchantTable.ComputedPosition.X >= overviewPane.ComputedPosition.X,
                $"Expected table X {merchantTable.ComputedPosition.X} to stay in overview pane X {overviewPane.ComputedPosition.X}.");
        }
        Assert.NotNull(Find(scene, "Section:merchant_detail"));
        Assert.NotNull(Find(scene, "MerchantDetailTabs"));
        Assert.True(State<ChartState>(scene, "Chart:detail-history").Series.Count > 0);

        LayoutNode body = Find(scene, "PageBody");
        AssertWithinScrollContent(body, Find(scene, "MerchantsControlBar"));
        AssertWithinScrollContent(body, Find(scene, "Section:merchant_rankings"));
        AssertWithinScrollContent(body, Find(scene, "Section:merchant_detail"));
    }

    [Fact]
    public void Merchants_AdjustmentsSearchTabsAndSelectionStayInSync()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.Merchants);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        SegmentedControlState lookback = State<SegmentedControlState>(scene, "Control:Merchants:MerchantLookback");
        Assert.True(InvokeAccept(lookback.Segments[0]));
        scene.Refresh();
        Assert.Equal(3, session.Filters.EffectiveMerchantLookbackMonths);

        Assert.True(InvokeClick(Find(scene, "Control:Merchants:AdjustView")));
        scene.Refresh();
        Assert.True(session.Presentation.Merchants.AdjustViewOpen);
        Assert.Equal("Adjust view", Text(scene, "MerchantsAdjustPopover:Title"));

        string group = session.ControlOptions(DashboardPageId.Merchants, "exclude_groups")[0];
        PorticoMultiSelectState<string> groups = scene.MultiSelectState(DashboardPageId.Merchants, "exclude_groups")
            ?? throw new Xunit.Sdk.XunitException("Expected the merchant adjustment group picker state.");
        Assert.True(InvokeAccept(Find(scene, "Control:Merchants:exclude_groups")));
        Assert.True(groups.IsOpen);
        Assert.True(InvokeAccept(Find(scene, $"MultiSelectCheckbox:Control:Merchants:exclude_groups:{group}")));
        scene.Refresh();
        Assert.Contains(group, session.ControlValues(DashboardPageId.Merchants, "exclude_groups"));
        Assert.True(session.Filters.MerchantAdjustments!.IsModified);

        TextInputState search = State<TextInputState>(scene, "Control:Merchants:search");
        string selectedMerchant = session.Report.Page(DashboardPageId.Merchants).MerchantsView!.SelectedMerchant!;
        search.Text = selectedMerchant;
        search.OnTextChanged!(search.Text);
        scene.Refresh();
        Assert.Equal(selectedMerchant, session.Presentation.Merchants.Search);

        Assert.True(InvokeAccept(Find(scene, "TableRowSelection:merchant-overview:0")));
        scene.Refresh();
        string tableMerchant = session.Report.Page(DashboardPageId.Merchants).MerchantsView!.Analysis.Overview[0].Merchant;
        Assert.Equal(tableMerchant, session.Presentation.Merchants.SelectedMerchant);

        SegmentedControlState tabs = State<SegmentedControlState>(scene, "MerchantDetailTabs");
        Assert.True(InvokeAccept(tabs.Segments[1]));
        scene.Refresh();
        Assert.Equal("Descriptions", session.Presentation.Merchants.DetailTab);
        Assert.NotNull(FindOrDefault(scene, "Table:merchant-descriptions") ?? FindOrDefault(scene, "merchant-descriptions:Empty"));

        Assert.True(InvokeAccept(Find(scene, "Control:Merchants:ResetAdjustments")));
        scene.Refresh();
        Assert.False(session.Filters.MerchantAdjustments!.IsModified);
        Assert.Empty(session.ControlValues(DashboardPageId.Merchants, "exclude_groups"));

        session.SetControlValues(
            DashboardPageId.Merchants,
            "exclude_groups",
            session.ControlOptions(DashboardPageId.Merchants, "exclude_groups"));
        scene.SelectPage(DashboardPageId.Merchants);
        scene.Refresh();
        Assert.Null(session.Presentation.Merchants.SelectedMerchant);
        Assert.NotNull(Find(scene, "MerchantsEmpty"));
    }

    [Theory]
    [InlineData(1500f, 1000f)]
    [InlineData(1024f, 720f)]
    public void Transactions_RendersTheSourceRegionsAtBothDesktopSizes(float width, float height)
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.TopTransactions);
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        TransactionsPageView view = Assert.IsType<TransactionsPageView>(
            session.Report.Page(DashboardPageId.TopTransactions).TransactionsView);
        Assert.Equal("Transactions", Text(scene, "PageTitle"));
        Assert.StartsWith("Latest transaction ", Text(scene, "TransactionsPageCaption"), StringComparison.Ordinal);
        Assert.NotEmpty(view.Analysis.Results);
        Assert.NotNull(Find(scene, "TransactionsControlBar"));
        Assert.NotNull(Find(scene, "TransactionsMetricDeck"));
        Assert.NotNull(Find(scene, "TransactionsCharts"));
        Assert.NotNull(Find(scene, "Chart:history"));
        Assert.NotNull(Find(scene, "Chart:breakdown"));
        Assert.NotNull(Find(scene, "Section:transactions_table"));
        Assert.NotNull(Find(scene, "Table:transactions-table"));

        LayoutNode body = Find(scene, "PageBody");
        AssertWithinScrollContent(body, Find(scene, "TransactionsControlBar"));
        AssertWithinScrollContent(body, Find(scene, "TransactionsCharts"));
        AssertWithinScrollContent(body, Find(scene, "Section:transactions_table"));
    }

    [Fact]
    public void Transactions_QuickAndMoreFiltersRebuildTheResultAndShowTheEmptyState()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.TopTransactions);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        SegmentedControlState focus = State<SegmentedControlState>(scene, "Control:Transactions:TransactionsFocus");
        Assert.True(InvokeAccept(focus.Segments[1]));
        scene.Refresh();
        Assert.Equal(TransactionExplorerFocus.Largest, session.Filters.TransactionExplorer!.Focus);

        Assert.True(InvokeClick(Find(scene, "Control:Transactions:MoreFilters")));
        scene.Refresh();
        Assert.True(session.Presentation.Transactions.MoreFiltersOpen);
        Assert.Equal("More filters", Text(scene, "TransactionsMoreFiltersPopover:Title"));

        string group = session.ControlOptions(DashboardPageId.TopTransactions, "groups")[0];
        PorticoMultiSelectState<string> groups = scene.MultiSelectState(DashboardPageId.TopTransactions, "groups")
            ?? throw new Xunit.Sdk.XunitException("Expected the transaction group picker state.");
        Assert.True(InvokeAccept(Find(scene, "Control:Transactions:groups")));
        Assert.True(groups.IsOpen);
        Assert.True(InvokeAccept(Find(scene, $"MultiSelectCheckbox:Control:Transactions:groups:{group}")));
        scene.Refresh();
        Assert.Contains(group, session.ControlValues(DashboardPageId.TopTransactions, "groups"));

        TextInputState search = State<TextInputState>(scene, "Control:Transactions:search");
        search.Text = "no matching description";
        search.OnTextChanged!(search.Text);
        scene.Refresh();
        Assert.Equal("no matching description", session.Filters.TransactionExplorer!.Search);
        Assert.NotNull(Find(scene, "TransactionsEmpty"));

        session.SetControlText(DashboardPageId.TopTransactions, "search", string.Empty);
        session.SetControlNumber(DashboardPageId.TopTransactions, "minimum_amount", 100_000m);
        session.SetControlNumber(DashboardPageId.TopTransactions, "maximum_amount", 1_000m);
        scene.SelectPage(DashboardPageId.TopTransactions);
        scene.Refresh();
        Assert.Empty(session.Report.Page(DashboardPageId.TopTransactions).TransactionsView!.Analysis.Results);
        Assert.NotNull(Find(scene, "TransactionsEmpty"));
    }

    private static LayoutNode Find(PorticoDashboardScene scene, string name)
        => FindOrDefault(scene, name)
            ?? throw new Xunit.Sdk.XunitException($"Expected node '{name}'.");

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
}
