using System.Numerics;

using Portico.Adapters;
using Portico.App;
using Portico.CaptureHost;
using Portico.Dashboard;
using Portico.Finance;
using Roci.Core;
using Roci.Input;
using Roci.TestUtilities;
using Roci.Ui;
using Roci.Ui.Widgets;

namespace Portico.App.Tests;

public sealed class PorticoDataHealthPageTests
{
    [Theory]
    [InlineData(1500f, 1000f)]
    [InlineData(1024f, 720f)]
    public void DataHealth_RendersTheSourceRegionsAtBothDesktopSizes(float width, float height)
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.DataHealth);
        var scene = new PorticoDashboardScene(new Vector2(width, height), session);
        scene.Stage.RefreshLayout(new MockTextMeasurer());

        DataHealthPageView view = Assert.IsType<DataHealthPageView>(session.Report.Page(DashboardPageId.DataHealth).DataHealthView);
        Assert.Equal("Data health", Text(scene, "PageTitle"));
        Assert.Equal("Review source freshness, mapping gaps, and suspicious records.", Text(scene, "DataHealthPageCaption"));
        Assert.Null(view.EmptyMessage);
        Assert.Equal(6, view.Analysis.Checks.Count);
        Assert.NotNull(Find(scene, "DataHealthControlBar"));
        Assert.NotNull(Find(scene, "DataHealthMetricDeck"));
        Assert.NotNull(Find(scene, "Section:health_checks"));
        Assert.NotNull(Find(scene, "Table:health-queue"));
        Assert.NotNull(Find(scene, "DataHealthSelectedCheckControl"));
        Assert.NotNull(Find(scene, "Section:health_detail"));
        Assert.True(FindOrDefault(scene, "Table:health-detail") is not null
            || FindOrDefault(scene, "DataHealthDetailEmpty") is not null);

        LayoutNode body = Find(scene, "PageBody");
        AssertWithinScrollContent(body, Find(scene, "DataHealthControlBar"));
        AssertWithinScrollContent(body, Find(scene, "Section:health_checks"));
        AssertWithinScrollContent(body, Find(scene, "Section:health_detail"));
    }

    [Fact]
    public void DataHealth_CheckSettingsAndCheckSelectionRebuildTheTypedReport()
    {
        DashboardSession session = PorticoDemoSessionFactory.Create();
        session.SelectPage(DashboardPageId.DataHealth);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        Assert.True(InvokeClick(Find(scene, "Control:DataHealth:CheckSettings")));
        scene.Refresh();
        Assert.True(session.Presentation.DataHealth.CheckSettingsOpen);
        Assert.Equal("Check settings", Text(scene, "DataHealthCheckSettingsPopover:Title"));

        SliderState staleDays = State<SliderState>(scene, "Control:DataHealth:stale_threshold");
        Assert.Equal("Stale account threshold: 7 days", Text(scene, "DataHealthSettings:stale_threshold:Label"));
        Assert.Equal(280f, staleDays.MinTrackLength);
        staleDays.OnValueChanged!(14f);
        scene.Refresh();
        Assert.Equal(14, session.Filters.DataHealth!.StaleAccountDays);
        Assert.Equal("14", session.ControlValue(DashboardPageId.DataHealth, "stale_threshold"));
        Assert.Throws<ArgumentOutOfRangeException>(() => session.SetControlNumber(
            DashboardPageId.DataHealth,
            "stale_threshold",
            0m));

        Assert.True(InvokeAccept(Find(scene, "Control:DataHealth:same_category")));
        scene.Refresh();
        Assert.True(session.Filters.DataHealth!.DuplicateRequireSameCategory);
        session.SetControlNumber(DashboardPageId.DataHealth, "duplicate_days", 2m);
        session.SetControlNumber(DashboardPageId.DataHealth, "duplicate_minimum", 20m);
        session.SetControlToggle(DashboardPageId.DataHealth, "same_account", false);
        session.SetControlToggle(DashboardPageId.DataHealth, "same_description", false);
        session.SetControlToggle(DashboardPageId.DataHealth, "include_inactive", true);
        Assert.Equal(2, session.Filters.DataHealth.DuplicateDays);
        Assert.Equal(20m, session.Filters.DataHealth.DuplicateMinimum);
        Assert.False(session.Filters.DataHealth.DuplicateRequireSameAccount);
        Assert.False(session.Filters.DataHealth.DuplicateRequireSameDescription);
        Assert.True(session.Filters.DataHealth.IncludeInactive);

        DataHealthPageView beforeSelection = session.Report.Page(DashboardPageId.DataHealth).DataHealthView!;
        int nextIndex = beforeSelection.Analysis.Checks
            .Select((check, index) => (check, index))
            .First(item => !string.Equals(item.check.Id, beforeSelection.SelectedCheckId, StringComparison.Ordinal))
            .index;
        Assert.True(InvokeAccept(Find(scene, $"TableRowSelection:health-queue:{nextIndex}")));
        scene.Refresh();
        DataHealthPageView selected = session.Report.Page(DashboardPageId.DataHealth).DataHealthView!;
        Assert.Equal(beforeSelection.Analysis.Checks[nextIndex].Id, selected.SelectedCheckId);
        Assert.Equal(selected.SelectedCheck.Name, Text(scene, "Section:health_detail:Title"));

        scene.SelectPage(DashboardPageId.Budget);
        scene.Refresh();
        scene.SelectPage(DashboardPageId.DataHealth);
        scene.Refresh();
        Assert.Equal(selected.SelectedCheckId, session.Report.Page(DashboardPageId.DataHealth).DataHealthView!.SelectedCheckId);
        Assert.True(session.Presentation.DataHealth.CheckSettingsOpen);
    }

    [Fact]
    public void DataHealth_EmptySourceUsesTheSharedEmptyPanel()
    {
        string root = FindRepositoryRoot();
        FinanceSettings settings = TomlConfigurationLoader.LoadFinance(Path.Combine(root, "portico-demo.toml"));
        DashboardDefinition definition = TomlConfigurationLoader.LoadDashboard(Path.Combine(root, "dashboard.toml"));
        var session = new DashboardSession(new PortfolioSnapshot([], [], []), settings, definition, PorticoDemoSessionFactory.CaptureDate);
        session.SelectPage(DashboardPageId.DataHealth);
        var scene = new PorticoDashboardScene(new Vector2(1500f, 1000f), session);

        DataHealthPageView view = Assert.IsType<DataHealthPageView>(session.Report.Page(DashboardPageId.DataHealth).DataHealthView);
        Assert.Equal("No transaction or balance data is available.", view.EmptyMessage);
        Assert.NotNull(Find(scene, "DataHealthEmpty"));
    }

    private static LayoutNode Find(PorticoDashboardScene scene, string name)
        => FindOrDefault(scene, name)
            ?? throw new Xunit.Sdk.XunitException($"Expected node '{name}'.");

    private static LayoutNode? FindOrDefault(PorticoDashboardScene scene, string name)
        => scene.Stage.Root.GetSelfAndDescendants()
            .SingleOrDefault(node => string.Equals(node.Name, name, StringComparison.Ordinal));

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

    private static string FindRepositoryRoot()
    {
        var current = new DirectoryInfo(Path.GetFullPath(Directory.GetCurrentDirectory()));
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "Portico.Roci.slnx"))
                && File.Exists(Path.Combine(current.FullName, "portico-demo.toml"))
                && File.Exists(Path.Combine(current.FullName, "dashboard.toml")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        throw new DirectoryNotFoundException("Could not find the Portico repository root.");
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
