using Portico.Desktop.Ui;
using Portico.Desktop.Ui.Components;
using Roci.Core;
using Roci.Ui;

namespace Portico.Desktop.Ui.Pages;

/// <summary>Builds the source-shaped Home report while leaving other pages configuration-driven.</summary>
internal sealed class PorticoHomePageRenderer
{
    private static readonly string[] RequiredSections =
    [
        "net_worth",
        "what_changed",
        "account_groups",
        "financial_safety"
    ];

    private readonly DashboardSession _session;

    /// <summary>Creates the renderer around the session that owns retained Home detail state.</summary>
    public PorticoHomePageRenderer(DashboardSession session)
    {
        _session = session ?? throw new ArgumentNullException(nameof(session));
    }

    /// <summary>Gets whether a configured page supplies the complete source-shaped Home grammar.</summary>
    public bool CanRender(DashboardPageDefinition page)
    {
        ArgumentNullException.ThrowIfNull(page);

        return page.Id == DashboardPageId.Home
            && page.Sections.Count == RequiredSections.Length
            && RequiredSections.All(id => page.Sections.Any(section => section.Id == id))
            && page.Widgets.Count == RequiredSections.Length
            && HasWidget(page, "net_worth", "home.net_worth")
            && HasWidget(page, "what_changed", "home.attribution")
            && HasWidget(page, "account_groups", "home.accounts")
            && HasWidget(page, "financial_safety", "home.safety");
    }

    /// <summary>Builds the Home report in configured section order.</summary>
    public void Build(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool, float?> buildWidget,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, float?> buildMetricBandWidget,
        Func<string?, string> display)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentNullException.ThrowIfNull(page);
        ArgumentNullException.ThrowIfNull(report);
        ArgumentNullException.ThrowIfNull(buildWidget);
        ArgumentNullException.ThrowIfNull(buildMetricBandWidget);
        ArgumentNullException.ThrowIfNull(display);

        DashboardWidgetReport netWorth = ReportFor(report, WidgetFor(page, "net_worth"));
        if (netWorth.Series.Count == 0 && netWorth.Metrics.Count == 0)
        {
            ui.EmptyPanel(
                "No balance history is available yet.",
                "Refresh after your spreadsheet has account balances.",
                "Empty:home-balance-history");
            return;
        }

        foreach (DashboardSectionDefinition section in page.Sections.OrderBy(section => section.Order))
        {
            switch (section.Id)
            {
                case "net_worth":
                    BuildConfiguredWidget(ui, page, report, section, buildMetricBandWidget, PorticoSkin.HomeNetWorthWidgetHeight);
                    break;
                case "what_changed":
                    if (ReportFor(report, WidgetFor(page, section.Id)).Series.Count > 0)
                        BuildConfiguredWidget(ui, page, report, section, buildWidget);
                    break;
                case "account_groups":
                    BuildAccountGroups(ui, page, report, section, display);
                    break;
                case "financial_safety":
                    BuildConfiguredWidget(ui, page, report, section, buildWidget);
                    break;
                default:
                    throw new InvalidOperationException($"Home section '{section.Id}' is not supported by the source-shaped layout.");
            }
        }
    }

    private void BuildAccountGroups(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        DashboardSectionDefinition section,
        Func<string?, string> display)
    {
        DashboardWidgetDefinition widget = WidgetFor(page, section.Id);
        DashboardWidgetReport groups = ReportFor(report, widget);
        DashboardWidgetReport inventory = report.Widgets["home.inventory"];

        ui.VStack(PorticoSkin.SectionGap, $"Widget:{widget.Id}")
            .SetCrossAlign(CrossAlignment.Stretch);
        ui.SectionHeading($"Section:{section.Id}", section.Title, section.Description);

        if (groups.Metrics.Count == 0)
        {
            ui.EmptyPanel(widget.Title, groups.EmptyMessage ?? "No visible account balances are available.", $"Empty:{widget.Id}");
            ui.End();
            return;
        }

        ui.HStack(PorticoSkin.SectionGap, "HomeAccountGroupGrid")
            .SetFlexWrap()
            .SetCrossGap(PorticoSkin.SectionGap)
            .SetCrossAlign(CrossAlignment.Start);
        foreach (ReportMetric group in groups.Metrics)
            BuildAccountGroup(ui, group, inventory, display);
        ui.End();
        ui.End();
    }

    private void BuildAccountGroup(
        UiBuilder ui,
        ReportMetric group,
        DashboardWidgetReport inventory,
        Func<string?, string> display)
    {
        IReadOnlyList<ReportTableRow> rows = DetailRows(group.Label, inventory);
        string detailsHeader = $"Account details: {group.Label} ({rows.Count})";

        ui.VStack(PorticoSkin.CompactGap, $"HomeAccountGroup:{group.Label}")
            .SetFlexBasis(PorticoSkin.WidgetMinimumWidth)
            .SetFlexGrow(1f)
            .SetFlexShrink(1f)
            .SetPadding(PorticoSkin.WidgetPadding)
            .SetCornerRadius(PorticoSkin.CardCornerRadius)
            .SetCrossAlign(CrossAlignment.Stretch)
            .SetStyle(PorticoSkin.RaisedPanelStyle);
        ui.SetMetric(group.Label, display(group.Display), group.Tone, $"AccountGroup:{group.Label}")
            .SetMetricDetail(display(group.Detail), group.Tone, $"AccountGroup:{group.Label}");

        ui.Collapsible(detailsHeader, _session.Presentation.IsHomeAccountGroupExpanded(group.Label))
            .SetOnCollapsibleToggled(expanded => _session.Presentation.SetHomeAccountGroupExpanded(group.Label, expanded));
        if (rows.Count == 0)
        {
            ui.EmptyPanel("No accounts", "No account details are available for this group.", $"Empty:{group.Label}");
        }
        else
        {
            PorticoTableRenderer.Build(
                ui,
                $"home-account-details:{group.Label}",
                ["Account", "Balance", "Change"],
                rows,
                display);
        }

        ui.EndCollapsible();
        ui.End();
    }

    private static IReadOnlyList<ReportTableRow> DetailRows(string group, DashboardWidgetReport inventory)
        => inventory.Rows
            .Where(row => row.Values.Count >= 4 && string.Equals(row.Values[0], group, StringComparison.Ordinal))
            .Select(row => new ReportTableRow([row.Values[1], row.Values[2], row.Values[3]], row.Tone))
            .ToArray();

    private static void BuildConfiguredWidget(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        DashboardSectionDefinition section,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, bool, float?> buildWidget,
        float? heightOverride = null)
    {
        DashboardWidgetDefinition widget = WidgetFor(page, section.Id);
        ui.VStack(PorticoSkin.SectionGap, $"Section:{section.Id}")
            .SetCrossAlign(CrossAlignment.Stretch);
        buildWidget(widget, ReportFor(report, widget), false, heightOverride);
        ui.End();
    }

    private static void BuildConfiguredWidget(
        UiBuilder ui,
        DashboardPageDefinition page,
        DashboardPageReport report,
        DashboardSectionDefinition section,
        Action<DashboardWidgetDefinition, DashboardWidgetReport, float?> buildWidget,
        float? heightOverride = null)
    {
        DashboardWidgetDefinition widget = WidgetFor(page, section.Id);
        ui.VStack(PorticoSkin.SectionGap, $"Section:{section.Id}")
            .SetCrossAlign(CrossAlignment.Stretch);
        buildWidget(widget, ReportFor(report, widget), heightOverride);
        ui.End();
    }

    private static bool HasWidget(DashboardPageDefinition page, string section, string report)
        => page.Widgets.Count(widget => widget.Section == section && widget.Report == report) == 1;

    private static DashboardWidgetDefinition WidgetFor(DashboardPageDefinition page, string section)
        => page.Widgets.Single(widget => string.Equals(widget.Section, section, StringComparison.Ordinal));

    private static DashboardWidgetReport ReportFor(DashboardPageReport report, DashboardWidgetDefinition widget)
        => report.Widgets.TryGetValue(widget.Report, out DashboardWidgetReport? item)
            ? item
            : throw new InvalidOperationException($"Home widget '{widget.Id}' has no report '{widget.Report}'.");
}
