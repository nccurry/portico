using Portico.Dashboard;
using Roci.Launch;
using Portico.App;
using Roci.Testing;

namespace Portico.CaptureHost;

/// <summary>Defines the fixed Portico page states and capture sizes used by visual checks.</summary>
public static class PorticoCaptureCatalog
{
    /// <summary>Launch state that always uses the checked-in synthetic demo session.</summary>
    public const string DemoLaunchState = "demo";

    /// <summary>Frame number saved for each baseline capture.</summary>
    public const int CaptureFrame = 8;

    private static readonly CaptureScenario[] Scenarios =
    [
        new("home", static session =>
        {
            session.SelectPage(DashboardPageId.Home);
            session.SetControlValue(DashboardPageId.Home, "time_frame", "1y");
        }),
        new("home-all", static session =>
        {
            session.SelectPage(DashboardPageId.Home);
            session.SetControlValue(DashboardPageId.Home, "time_frame", "all");
        }),
        new("income-savings", static session =>
        {
            session.SelectPage(DashboardPageId.IncomeSavings);
        }),
        new("income-adjusted", static session =>
        {
            session.SelectPage(DashboardPageId.IncomeSavings);
            session.SetControlValue(DashboardPageId.IncomeSavings, "calculation", "actual");
            session.SetControlValues(
                DashboardPageId.IncomeSavings,
                "exclude_income_categories",
                ["Salary", "Interest"]);
            session.SetControlValue(DashboardPageId.IncomeSavings, "detail_tab", "Excluded");
        }),
        new("spending", static session =>
        {
            session.SelectPage(DashboardPageId.Spending);
            session.SetFilter("lookback", "3");
            session.SetFilter("spending", "all");
        }),
        new("spending-adjusted", static session =>
        {
            session.SelectPage(DashboardPageId.Spending);
            session.SetControlValue(DashboardPageId.Spending, "lookback", "3");
            session.SetControlValue(DashboardPageId.Spending, "spending_view", "all");
            session.SetControlValue(DashboardPageId.Spending, "comparison", "last_year");
            session.SetControlValue(DashboardPageId.Spending, "breakdown", "group");
            string group = session.ControlOptions(DashboardPageId.Spending, "exclude_groups")[0];
            session.SetControlValues(DashboardPageId.Spending, "exclude_groups", [group]);
            ReportTableRow? first = session.Report.Page(DashboardPageId.Spending)
                .Widgets["spending.overview"]
                .Rows
                .FirstOrDefault();
            if (first is not null)
                session.SetSpendingSelectedEntity(session.Filters.SpendingBreakdown, first.Values[0]);
        }),
        new("year-over-year", static session =>
        {
            session.SelectPage(DashboardPageId.YearOverYear);
        }),
        new("year-over-year-single-category", static session =>
        {
            session.SelectPage(DashboardPageId.YearOverYear);
            session.SetControlValue(DashboardPageId.YearOverYear, "view", "single_category");
        }),
        new("subscriptions", static session => session.SelectPage(DashboardPageId.Subscriptions)),
        new("merchants", static session =>
        {
            session.SelectPage(DashboardPageId.Merchants);
            session.SetFilter("lookback", "3");
            session.SetFilter("spending", "all");
        }),
        new("budget", static session =>
        {
            session.SelectPage(DashboardPageId.Budget);
            session.SetFilter("lookback", "3");
        }),
        new("top-transactions", static session =>
        {
            session.SelectPage(DashboardPageId.TopTransactions);
            session.SetFilter("lookback", "3");
        }),
        new("financial-independence", static session => session.SelectPage(DashboardPageId.FinancialIndependence)),
        new("data-health", static session => session.SelectPage(DashboardPageId.DataHealth)),
        new("home-hidden", static session => session.SelectPage(DashboardPageId.Home), static state => state.ToggleHideValues()),
        new("spending-loading", static session => session.SelectPage(DashboardPageId.Spending), static state => state.BeginRefresh()),
        new("budget-refresh-failed", static session => session.SelectPage(DashboardPageId.Budget), static state =>
        {
            state.BeginRefresh();
            state.CompleteRefresh(PorticoRefreshResult.Failed());
        }),
        new("data-health-refresh-unavailable", static session => session.SelectPage(DashboardPageId.DataHealth), static state =>
        {
            state.BeginRefresh();
            state.CompleteRefresh(PorticoRefreshResult.Unavailable());
        })
    ];

    private static readonly CaptureSize[] CaptureSizes =
    [
        new CaptureSize(1500, 1000),
        new CaptureSize(1024, 720)
    ];

    /// <summary>Launch states and page scenarios accepted by the test-only capture host.</summary>
    public static readonly GameRunCatalog<DashboardSession, string> RunCatalog = CreateRunCatalog();

    /// <summary>Named current-dashboard captures at both required desktop sizes.</summary>
    public static readonly GameRunCaptureCatalog CaptureCatalog =
        new GameRunCaptureCatalogBuilder<DashboardSession, string>(RunCatalog)
            .Captures(CreateCaptureCases())
            .Build();

    /// <summary>Creates and configures one fixed demo session for a resolved page scenario.</summary>
    public static DashboardSession CreateSession(GameRunContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        DashboardSession session = PorticoDemoSessionFactory.Create();
        RunCatalog.ApplyScenario(session, context);
        return session;
    }

    /// <summary>Creates visual-only state for a fixed capture scenario.</summary>
    public static PorticoDashboardDisplayState CreateDisplayState(GameRunContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        var state = new PorticoDashboardDisplayState(isDemoData: true);
        Scenarios
            .SingleOrDefault(scenario => string.Equals(scenario.Id, context.ScenarioId, StringComparison.Ordinal))
            ?.ConfigureDisplayState
            ?.Invoke(state);
        return state;
    }

    private static GameRunCatalog<DashboardSession, string> CreateRunCatalog()
    {
        var builder = new GameRunCatalogBuilder<DashboardSession, string>(DemoLaunchState)
            .LaunchState(DemoLaunchState, static (_, context) => context.LaunchStateId);

        foreach (CaptureScenario scenario in Scenarios)
        {
            builder.Scenario(
                DemoLaunchState,
                scenario.Id,
                (session, _) => scenario.Configure(session));
        }

        return builder.Build();
    }

    private static CaptureCase[] CreateCaptureCases()
    {
        var cases = new List<CaptureCase>(Scenarios.Length * CaptureSizes.Length);
        foreach (CaptureScenario scenario in Scenarios)
        {
            foreach (CaptureSize captureSize in CaptureSizes)
            {
                cases.Add(new CaptureCase(
                    $"portico-current-{scenario.Id}-{captureSize.Width}x{captureSize.Height}",
                    DemoLaunchState)
                {
                    ScenarioId = scenario.Id,
                    CaptureFrame = CaptureFrame,
                    CaptureSize = captureSize,
                    Verification = new CaptureVerificationOptions
                    {
                        ExpectedSize = captureSize,
                        MinimumUniqueColors = 4
                    }
                });
            }
        }

        return cases.ToArray();
    }

    private sealed record CaptureScenario(
        string Id,
        Action<DashboardSession> Configure,
        Action<PorticoDashboardDisplayState>? ConfigureDisplayState = null);
}
