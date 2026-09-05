using Portico.Dashboard;
using Portico.Finance;

namespace Portico.Dashboard.Tests;

public sealed class DashboardPresentationTests
{
    [Fact]
    public void Definition_MapsEveryControlKindToOneTypedRoute()
    {
        DashboardDefinition definition = Definition();

        Assert.Empty(definition.Validate());
        Assert.Equal(
            Enum.GetValues<DashboardControlKind>().Order(),
            definition.Pages.SelectMany(page => page.Controls).Select(control => control.Kind).Distinct().Order());

        foreach (DashboardPageDefinition page in definition.Pages)
        {
            foreach (DashboardControlDefinition control in page.Controls)
            {
                Assert.True(DashboardControlMappings.TryResolve(page.Id, control.Id, out DashboardControlMapping? mapping));
                Assert.NotNull(mapping);
                Assert.Equal(control.Kind, mapping.Kind);
                Assert.Equal(control.Source, mapping.Source);
                Assert.True(DashboardControlMappings.TryValidate(mapping, out string? problem), problem);
            }
        }
    }

    [Fact]
    public void Session_UsesTomlDefaultsAndRoutesEveryConfiguredControlType()
    {
        var session = new DashboardSession(new PortfolioSnapshot([], [], []), Settings(), Definition());

        Assert.Equal(HomeTimeFrame.FiveYears, session.Filters.HomeTimeFrame);
        Assert.False(session.Filters.RegularIncome);
        Assert.Contains("Salary", session.Presentation.IncomeSavings.ExcludedIncomeCategories);
        Assert.Equal("Excluded", session.Presentation.IncomeSavings.DetailTab);
        Assert.Equal(1_250_000m, session.Presentation.FinancialIndependence.TargetAmount);
        Assert.Equal(45m, session.Presentation.DataHealth.StaleThreshold);
        Assert.True(session.Presentation.DataHealth.IncludeInactive);

        string originalSpendingSet = session.Filters.SpendingSet;
        DashboardReport initialReport = session.Report;
        session.SetControlValue(DashboardPageId.IncomeSavings, "income_view", "regular");
        Assert.True(session.Filters.RegularIncome);
        Assert.NotSame(initialReport, session.Report);

        session.SetControlValue(DashboardPageId.Home, "time_frame", "all");
        Assert.Equal(HomeTimeFrame.All, session.Filters.HomeTimeFrame);
        Assert.NotSame(initialReport, session.Report);
        Assert.True(session.Filters.RegularIncome);
        Assert.Equal(originalSpendingSet, session.Filters.SpendingSet);
        session.SetControlValues(DashboardPageId.IncomeSavings, "exclude_income_categories", ["Bonus", "Salary"]);
        Assert.Equal(["Bonus", "Salary"], session.Presentation.IncomeSavings.ExcludedIncomeCategories.Order());
        session.SetControlValue(DashboardPageId.IncomeSavings, "detail_tab", "Included");
        Assert.Equal("Included", session.Presentation.IncomeSavings.DetailTab);
        session.SetControlNumber(DashboardPageId.FinancialIndependence, "target_amount", 1_400_000m);
        Assert.Equal(1_400_000m, session.Presentation.FinancialIndependence.TargetAmount);
        session.InvokeControlAction(DashboardPageId.FinancialIndependence, "reset_scenario");
        Assert.Equal(1_250_000m, session.Presentation.FinancialIndependence.TargetAmount);
        session.SetControlNumber(DashboardPageId.DataHealth, "stale_threshold", 60m);
        Assert.Equal(60m, session.Presentation.DataHealth.StaleThreshold);
        session.SetControlToggle(DashboardPageId.DataHealth, "include_inactive", false);
        Assert.False(session.Presentation.DataHealth.IncludeInactive);
        session.SetControlValue(DashboardPageId.Spending, "spending_view", "all");
        Assert.Equal("all", session.Filters.SpendingSet);
        session.SetControlValue(DashboardPageId.YearOverYear, "spending_view", "utilities");
        Assert.Equal("utilities", session.Filters.YearOverYearSet);
    }

    [Fact]
    public void Session_RejectsValuesOutsideTheTypedControlDefinitions()
    {
        var session = new DashboardSession(new PortfolioSnapshot([], [], []), Settings(), Definition());

        Assert.Throws<ArgumentException>(() => session.SetControlValue(DashboardPageId.Home, "time_frame", "10y"));
        Assert.Throws<ArgumentException>(() => session.SetControlValues(DashboardPageId.IncomeSavings, "exclude_income_categories", ["Unknown"]));
        Assert.Throws<ArgumentOutOfRangeException>(() => session.SetControlNumber(DashboardPageId.FinancialIndependence, "target_amount", 3_000_000m));
        Assert.Throws<ArgumentOutOfRangeException>(() => session.SetControlNumber(DashboardPageId.FinancialIndependence, "target_amount", 1_425_000m));
        Assert.Throws<ArgumentException>(() => session.SetControlToggle(DashboardPageId.IncomeSavings, "income_view", true));
        Assert.Throws<ArgumentException>(() => session.InvokeControlAction(DashboardPageId.FinancialIndependence, "target_amount"));
        Assert.Throws<ArgumentException>(() => session.ControlValue(DashboardPageId.DataHealth, "not_configured"));
    }

    [Fact]
    public void Session_RejectsReadingAKnownControlThatThePageDoesNotConfigure()
    {
        DashboardDefinition definition = Definition();
        DashboardPageDefinition dataHealth = definition.Pages.Single(page => page.Id == DashboardPageId.DataHealth) with
        {
            Controls = []
        };
        DashboardDefinition withoutDataHealthControls = definition with
        {
            Pages = definition.Pages.Select(page => page.Id == dataHealth.Id ? dataHealth : page).ToArray()
        };
        var session = new DashboardSession(new PortfolioSnapshot([], [], []), Settings(), withoutDataHealthControls);

        Assert.Throws<ArgumentException>(() => session.ControlValue(DashboardPageId.DataHealth, "stale_threshold"));
    }

    [Fact]
    public void MappingValidation_RejectsRoutesWithoutARealHandler()
    {
        Assert.False(
            DashboardControlMappings.TryValidate(
                new DashboardControlMapping(
                    DashboardControlKind.Select,
                    DashboardControlSource.IncomeView,
                    DashboardControlBehavior.ReportInput),
                out string? reportProblem));
        Assert.Contains("report-filter", reportProblem, StringComparison.Ordinal);

        Assert.False(
            DashboardControlMappings.TryValidate(
                new DashboardControlMapping(
                    DashboardControlKind.Select,
                    DashboardControlSource.IncomeView,
                    DashboardControlBehavior.ReportInput,
                    "spending"),
                out string? mismatchedReportProblem));
        Assert.Contains("report-filter", mismatchedReportProblem, StringComparison.Ordinal);

        Assert.False(
            DashboardControlMappings.TryValidate(
                new DashboardControlMapping(
                    DashboardControlKind.Toggle,
                    DashboardControlSource.HomeTimeFrame,
                    DashboardControlBehavior.DisplayState),
                out string? displayProblem));
        Assert.Contains("display-state", displayProblem, StringComparison.Ordinal);

        Assert.False(
            DashboardControlMappings.TryValidate(
                new DashboardControlMapping(
                    DashboardControlKind.ActionReset,
                    DashboardControlSource.HomeTimeFrame,
                    DashboardControlBehavior.Action),
                out string? actionProblem));
        Assert.Contains("action handler", actionProblem, StringComparison.Ordinal);
    }

    [Fact]
    public void Definition_RejectsUnmappedControlsAndInvalidControlShape()
    {
        DashboardPageDefinition home = Definition().Pages.Single(page => page.Id == DashboardPageId.Home) with
        {
            Controls =
            [
                new DashboardControlDefinition(
                    "not_mapped",
                    "Unmapped",
                    DashboardControlKind.Select,
                    DashboardControlSource.IncomeView,
                    Options: ["regular"],
                    DefaultValue: "regular"),
                new DashboardControlDefinition(
                    "time_frame",
                    "Time frame",
                    DashboardControlKind.SegmentedChoice,
                    DashboardControlSource.HomeTimeFrame,
                    OptionSource: (DashboardControlOptionSource)99,
                    Options: ["1y", "1y"],
                    DefaultValue: "9y")
            ]
        };
        DashboardDefinition invalid = new(1, "Portico", [home]);

        IReadOnlyList<string> problems = invalid.Validate();

        Assert.Contains(problems, problem => problem.Contains("does not have a C# mapping", StringComparison.Ordinal));
        Assert.Contains(problems, problem => problem.Contains("unsupported option source", StringComparison.Ordinal));
        Assert.Contains(problems, problem => problem.Contains("blank or duplicate options", StringComparison.Ordinal));
        Assert.Contains(problems, problem => problem.Contains("default must be one of its options", StringComparison.Ordinal));
    }

    [Fact]
    public void Definition_RejectsUnsupportedHomeTimeFrameOptions()
    {
        DashboardDefinition definition = Definition();
        DashboardPageDefinition home = definition.Pages.Single(page => page.Id == DashboardPageId.Home) with
        {
            Controls =
            [
                new DashboardControlDefinition(
                    "time_frame",
                    "Time frame",
                    DashboardControlKind.SegmentedChoice,
                    DashboardControlSource.HomeTimeFrame,
                    Options: ["3m", "10y"],
                    DefaultValue: "10y",
                    Width: DashboardControlWidth.Full)
            ]
        };
        DashboardDefinition invalid = definition with
        {
            Pages = definition.Pages.Select(page => page.Id == home.Id ? home : page).ToArray()
        };

        Assert.Contains(
            invalid.Validate(),
            problem => problem.Contains("unsupported Home time-frame option '10y'", StringComparison.Ordinal));
    }

    [Fact]
    public void Definition_RejectsConflictingLegacyAndTypedReportDefaults()
    {
        DashboardDefinition definition = Definition();
        DashboardPageDefinition income = definition.Pages.Single(page => page.Id == DashboardPageId.IncomeSavings) with
        {
            Filters =
            [
                new DashboardFilterDefinition(
                    "legacy_income_view",
                    "Legacy income view",
                    DashboardFilterKind.Select,
                    "income_view",
                    "regular",
                    ["regular", "actual"])
            ]
        };
        DashboardDefinition invalid = definition with
        {
            Pages = definition.Pages.Select(page => page.Id == income.Id ? income : page).ToArray()
        };

        Assert.Contains(
            invalid.Validate(),
            problem => problem.Contains("report input 'income_view' has conflicting defaults", StringComparison.Ordinal));
    }

    [Fact]
    public void Definition_RejectsNumericRangesWhoseMaximumDoesNotMatchTheirStep()
    {
        DashboardDefinition definition = Definition();
        DashboardPageDefinition configuredFinancialIndependence = definition.Pages.Single(page => page.Id == DashboardPageId.FinancialIndependence);
        DashboardPageDefinition financialIndependence = configuredFinancialIndependence with
        {
            Controls = configuredFinancialIndependence.Controls
                .Select(control => control.Id == "target_amount" ? control with { Maximum = 2_010_000m } : control)
                .ToArray()
        };
        DashboardDefinition invalid = definition with
        {
            Pages = definition.Pages
                .Select(page => page.Id == financialIndependence.Id ? financialIndependence : page)
                .ToArray()
        };

        Assert.Contains(
            invalid.Validate(),
            problem => problem.Contains("target_amount", StringComparison.Ordinal)
                && problem.Contains("positive step", StringComparison.Ordinal));
    }

    private static DashboardDefinition Definition()
        => new(
            1,
            "Portico",
            [
                Page(
                    DashboardPageId.Home,
                    "home.overview",
                    [
                        new DashboardControlDefinition(
                            "time_frame",
                            "Time frame",
                            DashboardControlKind.SegmentedChoice,
                            DashboardControlSource.HomeTimeFrame,
                            Options: ["3m", "6m", "1y", "2y", "5y", "all"],
                            DefaultValue: "5y",
                            Width: DashboardControlWidth.Full)
                    ]),
                Page(
                    DashboardPageId.IncomeSavings,
                    "income.cash_flow",
                    [
                        new DashboardControlDefinition(
                            "income_view",
                            "View",
                            DashboardControlKind.Select,
                            DashboardControlSource.IncomeView,
                            Options: ["regular", "actual"],
                            DefaultValue: "actual"),
                        new DashboardControlDefinition(
                            "exclude_income_categories",
                            "Exclude income categories",
                            DashboardControlKind.MultiSelect,
                            DashboardControlSource.IncomeExcludedCategories,
                            Options: ["Salary", "Bonus"],
                            DefaultValues: ["Salary"]),
                        new DashboardControlDefinition(
                            "detail_tab",
                            "Month detail",
                            DashboardControlKind.TabChoice,
                            DashboardControlSource.IncomeDetailTab,
                            Options: ["Included", "Excluded"],
                            DefaultValue: "Excluded")
                    ]),
                Page(
                    DashboardPageId.Spending,
                    "spending.categories",
                    [
                        new DashboardControlDefinition(
                            "spending_view",
                            "View",
                            DashboardControlKind.Select,
                            DashboardControlSource.Spending,
                            Options: ["all", "discretionary"],
                            DefaultValue: "discretionary")
                    ]),
                Page(
                    DashboardPageId.YearOverYear,
                    "yoy.comparison",
                    [
                        new DashboardControlDefinition(
                            "spending_view",
                            "View",
                            DashboardControlKind.Select,
                            DashboardControlSource.YearOverYear,
                            Options: ["all", "utilities"],
                            DefaultValue: "utilities")
                    ]),
                Page(
                    DashboardPageId.FinancialIndependence,
                    "fi.summary",
                    [
                        new DashboardControlDefinition(
                            "target_amount",
                            "Target amount",
                            DashboardControlKind.NumberInput,
                            DashboardControlSource.FinancialIndependenceTargetAmount,
                            DefaultValue: "1250000",
                            Minimum: 500_000m,
                            Maximum: 2_000_000m,
                            Step: 50_000m),
                        new DashboardControlDefinition(
                            "reset_scenario",
                            "Reset scenario",
                            DashboardControlKind.ActionReset,
                            DashboardControlSource.FinancialIndependenceReset)
                    ]),
                Page(
                    DashboardPageId.DataHealth,
                    "health.summary",
                    [
                        new DashboardControlDefinition(
                            "stale_threshold",
                            "Stale after days",
                            DashboardControlKind.Slider,
                            DashboardControlSource.DataHealthStaleThreshold,
                            DefaultValue: "45",
                            Minimum: 0m,
                            Maximum: 90m,
                            Step: 5m),
                        new DashboardControlDefinition(
                            "include_inactive",
                            "Include inactive",
                            DashboardControlKind.Toggle,
                            DashboardControlSource.DataHealthIncludeInactive,
                            DefaultValue: "true")
                    ])
            ]);

    private static DashboardPageDefinition Page(
        DashboardPageId id,
        string report,
        IReadOnlyList<DashboardControlDefinition> controls)
        => new(id, id.ToString(), "Page", [], [new DashboardWidgetDefinition("report", "Report", DashboardWidgetKind.Metric, report)])
        {
            Controls = controls
        };

    private static FinanceSettings Settings()
    {
        TransactionSetDefinition[] transactionSets =
        [
            new TransactionSetDefinition("all", "All", [], [], [], [], [], [], []),
            new TransactionSetDefinition("discretionary", "Discretionary", [], [], [], [], [], ["all"], []),
            new TransactionSetDefinition("utilities", "Utilities", [], [], [], [], [], ["all"], [])
        ];
        return new FinanceSettings(
            new DataSourceSettings(WorkbookSourceKind.LocalCsv, "demo/data"),
            new LookbackSettings([3, 6, 12, 24], 12),
            new ThresholdSettings(1_000m, 5_000m, 10m, 1),
            new IncomeSavingsSettings("regular", 20m, [], []),
            transactionSets,
            [
                new FilterSetDefinition("spending", ["all", "discretionary"], "discretionary"),
                new FilterSetDefinition("year_over_year", ["all", "utilities"], "utilities")
            ],
            new SubscriptionSettings([], 80, 45, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 5, [], []),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal));
    }
}
