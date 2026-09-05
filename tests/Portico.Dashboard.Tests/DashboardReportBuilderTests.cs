using Portico.Dashboard;
using Portico.Finance;

namespace Portico.Dashboard.Tests;

public sealed class DashboardReportBuilderTests
{
    [Fact]
    public void Build_ReturnsEveryPorticoPageAndUsesConfiguredFinanceRules()
    {
        FinanceSettings settings = Settings();
        PortfolioSnapshot snapshot = Snapshot();

        DashboardReport report = DashboardReportBuilder.Build(
            snapshot,
            settings,
            new DashboardFilters(3, "discretionary", "all", true));

        Assert.Equal(10, report.Pages.Count);
        DashboardWidgetReport home = report.Page(DashboardPageId.Home).Widgets["home.overview"];
        Assert.Equal(4, home.Metrics.Count);
        Assert.Equal("$2,450", home.Metrics[0].Display);
        DashboardWidgetReport spending = report.Page(DashboardPageId.Spending).Widgets["spending.categories"];
        Assert.Equal("Flight", Assert.Single(spending.Series).Points[0].Category);
        DashboardWidgetReport top = report.Page(DashboardPageId.TopTransactions).Widgets["top.table"];
        Assert.DoesNotContain(top.Rows, row => row.Values.Contains("Hidden charge"));
        Assert.NotEmpty(report.Page(DashboardPageId.FinancialIndependence).Widgets["fi.projection"].Series);
        DashboardWidgetReport subscriptions = report.Page(DashboardPageId.Subscriptions).Widgets["subscriptions.active"];
        Assert.NotEmpty(subscriptions.TimelineRanges);
        Assert.Equal(new DateOnly(2024, 2, 29), subscriptions.DateGuide);
        Assert.NotEmpty(report.Page(DashboardPageId.Subscriptions).Widgets["subscriptions.monthly"].Series.Single().Points);
        Assert.NotEmpty(report.Page(DashboardPageId.FinancialIndependence).Widgets["fi.sensitivity"].HeatmapCells);
        Assert.Equal(3, report.Page(DashboardPageId.Home).Widgets["home.safety"].Metrics.Count);
    }

    [Fact]
    public void Build_AppliesLookbackAndRegularIncomeExclusions()
    {
        FinanceSettings settings = Settings();
        PortfolioSnapshot snapshot = Snapshot();

        DashboardReport regular = DashboardReportBuilder.Build(snapshot, settings, new DashboardFilters(1, "all", "all", true));
        DashboardReport actual = DashboardReportBuilder.Build(snapshot, settings, new DashboardFilters(1, "all", "all", false));

        DashboardWidgetReport regularCashFlow = regular.Page(DashboardPageId.IncomeSavings).Widgets["income.cash_flow"];
        DashboardWidgetReport actualCashFlow = actual.Page(DashboardPageId.IncomeSavings).Widgets["income.cash_flow"];
        Assert.Equal(1000m, regularCashFlow.Metrics.Single(metric => metric.Label == "Surplus").Value);
        Assert.Equal(980m, actualCashFlow.Metrics.Single(metric => metric.Label == "Surplus").Value);
        Assert.Single(regularCashFlow.Series.Single(series => series.Id == "income").Points);
    }

    [Fact]
    public void Build_TopTransactionsUsesSeparateConfiguredIncomeAndExpenseThresholds()
    {
        PortfolioSnapshot source = Snapshot();
        PortfolioSnapshot snapshot = source with
        {
            Transactions =
            [
                .. source.Transactions,
                Row("large-expense", 2024, 2, 10, "Flight", "Travel", "Large expense", -10_000m, TransactionKind.Expense),
                Row("small-expense", 2024, 2, 11, "Flight", "Travel", "Small expense", -9_999m, TransactionKind.Expense),
                Row("large-income", 2024, 2, 12, "Bonus", "Income", "Large income", 50_000m, TransactionKind.Income),
                Row("small-income", 2024, 2, 13, "Bonus", "Income", "Small income", 49_999m, TransactionKind.Income)
            ]
        };
        FinanceSettings settings = Settings() with { Thresholds = new ThresholdSettings(10_000m, 50_000m, 10m, 1) };

        DashboardPageReport page = DashboardReportBuilder.Build(
            snapshot,
            settings,
            new DashboardFilters(1, "all", "all", true))
            .Page(DashboardPageId.TopTransactions);

        Assert.Equal("Large expense", Assert.Single(page.Widgets["top.expenses"].Series.Single().Points).Label);
        Assert.Equal("Large income", Assert.Single(page.Widgets["top.incomes"].Series.Single().Points).Label);
        Assert.Equal(
            ["Large income", "Small income", "Large expense"],
            page.Widgets["top.table"].Rows.Take(3).Select(row => row.Values[1]));
    }

    [Fact]
    public void Build_BudgetCountsOnlyExpenseTransactionsAsActualSpending()
    {
        PortfolioSnapshot source = Snapshot();
        PortfolioSnapshot snapshot = source with
        {
            Transactions = [
                .. source.Transactions,
                Row("food-income", 2024, 2, 20, "Food", "Income", "Food reimbursement", 500m, TransactionKind.Income)
            ]
        };

        DashboardReport report = DashboardReportBuilder.Build(
            snapshot,
            Settings(),
            new DashboardFilters(1, "all", "all", true));

        DashboardWidgetReport budget = report.Page(DashboardPageId.Budget).Widgets["budget.table"];
        ReportTableRow food = Assert.Single(budget.Rows, row => row.Values[0] == "Food");

        Assert.Equal("$200", food.Values[2]);
    }

    [Fact]
    public void Build_BudgetUsesTheConfiguredLookbackPeriod()
    {
        PortfolioSnapshot source = Snapshot();
        PortfolioSnapshot snapshot = source with
        {
            Budgets = [
                .. source.Budgets,
                new BudgetEntry(new YearMonth(2024, 1), "Food", "Living", TransactionKind.Expense, 100m, false)
            ]
        };

        DashboardWidgetReport oneMonth = DashboardReportBuilder.Build(
            snapshot,
            Settings(),
            new DashboardFilters(1, "all", "all", true))
            .Page(DashboardPageId.Budget)
            .Widgets["budget.table"];
        DashboardWidgetReport threeMonths = DashboardReportBuilder.Build(
            snapshot,
            Settings(),
            new DashboardFilters(3, "all", "all", true))
            .Page(DashboardPageId.Budget)
            .Widgets["budget.table"];

        Assert.Equal(275m, oneMonth.Metrics.Single(metric => metric.Label == "Budgeted").Value);
        Assert.Equal(375m, threeMonths.Metrics.Single(metric => metric.Label == "Budgeted").Value);
    }

    [Fact]
    public void Build_BudgetHistoryUsesTheConfiguredHistoryLength()
    {
        PortfolioSnapshot source = Snapshot();
        PortfolioSnapshot snapshot = source with
        {
            Budgets =
            [
                .. source.Budgets,
                new BudgetEntry(new YearMonth(2024, 1), "Food", "Living", TransactionKind.Expense, 100m, false)
            ]
        };
        FinanceSettings oneMonthSettings = Settings() with { Budget = new BudgetSettings(1) };

        DashboardWidgetReport oneMonth = DashboardReportBuilder.Build(
            snapshot,
            oneMonthSettings,
            new DashboardFilters(3, "all", "all", true))
            .Page(DashboardPageId.Budget)
            .Widgets["budget.history"];

        Assert.All(oneMonth.Series, series => Assert.Equal([new DateOnly(2024, 2, 1)], series.Points.Select(point => point.Date)));

        FinanceSettings twoMonthSettings = oneMonthSettings with { Budget = new BudgetSettings(2) };
        DashboardWidgetReport twoMonths = DashboardReportBuilder.Build(
            snapshot,
            twoMonthSettings,
            new DashboardFilters(3, "all", "all", true))
            .Page(DashboardPageId.Budget)
            .Widgets["budget.history"];

        Assert.All(twoMonths.Series, series => Assert.Equal(
            [new DateOnly(2024, 1, 1), new DateOnly(2024, 2, 1)],
            series.Points.Select(point => point.Date)));
    }

    [Fact]
    public void Build_DataHealthUsesConfiguredDuplicateAmountAndDateRules()
    {
        PortfolioSnapshot source = Snapshot();
        PortfolioSnapshot snapshot = source with
        {
            Transactions = [
                .. source.Transactions,
                Row("first-duplicate", 2024, 2, 10, "Food", "Living", "Same store", -50m, TransactionKind.Expense),
                Row("second-duplicate", 2024, 2, 11, "Food", "Living", "Same store", -50m, TransactionKind.Expense),
                Row("old-match", 2024, 2, 20, "Food", "Living", "Same store", -50m, TransactionKind.Expense)
            ]
        };

        DashboardWidgetReport health = DashboardReportBuilder.Build(
            snapshot,
            Settings(),
            new DashboardFilters(3, "all", "all", true))
            .Page(DashboardPageId.DataHealth)
            .Widgets["health.summary"];

        Assert.Equal(1m, health.Metrics.Single(metric => metric.Label == "Possible duplicates").Value);
    }

    [Fact]
    public void Build_SubscriptionsUsesConfiguredCandidateRulesAndFreshnessThreshold()
    {
        PortfolioSnapshot source = Snapshot();
        PortfolioSnapshot snapshot = source with
        {
            Transactions =
            [
                .. source.Transactions,
                Row("food-jan", 2024, 1, 7, "Food", "Living", "FOOD BOX", -10m, TransactionKind.Expense),
                Row("food-feb", 2024, 2, 7, "Food", "Living", "FOOD BOX", -10m, TransactionKind.Expense),
                Row("food-mar", 2024, 3, 7, "Food", "Living", "FOOD BOX", -10m, TransactionKind.Expense),
                Row("coffee-jan", 2024, 1, 7, "Coffee", "Fun", "COFFEE CLUB", -10m, TransactionKind.Expense),
                Row("coffee-feb", 2024, 2, 7, "Coffee", "Fun", "COFFEE CLUB", -10m, TransactionKind.Expense),
                Row("coffee-mar", 2024, 3, 7, "Coffee", "Fun", "COFFEE CLUB", -10m, TransactionKind.Expense)
            ]
        };
        FinanceSettings baseSettings = Settings();
        FinanceSettings strict = baseSettings with
        {
            Subscriptions = baseSettings.Subscriptions with
            {
                MinimumConfidence = 90,
                StaleAfterDays = 3,
                DefaultExcludeCategories = ["Food"]
            }
        };

        DashboardWidgetReport strictReport = DashboardReportBuilder.Build(
            snapshot,
            strict,
            new DashboardFilters(3, "all", "all", true),
            new DateOnly(2024, 4, 15))
            .Page(DashboardPageId.Subscriptions)
            .Widgets["subscriptions.active"];

        Assert.Contains(strictReport.Rows, row => row.Values[0] == "Video Service");
        Assert.DoesNotContain(strictReport.Rows, row => row.Values[0] == "FOOD BOX");
        Assert.DoesNotContain(strictReport.Rows, row => row.Values[0] == "COFFEE CLUB");
        ReportMetric strictAge = strictReport.Metrics.Single(metric => metric.Label == "Data age");
        Assert.Equal("39 days old", strictAge.Display);
        Assert.Equal("negative", strictAge.Tone);

        FinanceSettings permissive = strict with
        {
            Subscriptions = strict.Subscriptions with { MinimumConfidence = 80 }
        };
        DashboardWidgetReport permissiveReport = DashboardReportBuilder.Build(
            snapshot,
            permissive,
            new DashboardFilters(3, "all", "all", true),
            new DateOnly(2024, 4, 15))
            .Page(DashboardPageId.Subscriptions)
            .Widgets["subscriptions.active"];

        Assert.Contains(permissiveReport.Rows, row => row.Values[0] == "COFFEE CLUB" && row.Values[1] == "Detected (85%)");
    }

    [Theory]
    [InlineData(HomeTimeFrame.ThreeMonths, 2025, 12, 1)]
    [InlineData(HomeTimeFrame.SixMonths, 2025, 9, 2)]
    [InlineData(HomeTimeFrame.OneYear, 2025, 3, 1)]
    [InlineData(HomeTimeFrame.TwoYears, 2024, 3, 1)]
    [InlineData(HomeTimeFrame.FiveYears, 2021, 3, 2)]
    [InlineData(HomeTimeFrame.All, 2020, 1, 1)]
    public void HomeReportRange_UsesTheSourceDayCountsAndVisibleBalanceBounds(
        HomeTimeFrame timeFrame,
        int expectedYear,
        int expectedMonth,
        int expectedDay)
    {
        BalanceObservation[] balances =
        [
            Balance("checking", "Checking", "Cash", 2020, 1, 1, 100m),
            Balance("checking", "Checking", "Cash", 2026, 3, 1, 500m)
        ];

        HomeReportRange range = Assert.IsType<HomeReportRange>(HomeReportRange.Create(balances, timeFrame));

        Assert.Equal(new DateOnly(expectedYear, expectedMonth, expectedDay), range.Start);
        Assert.Equal(new DateOnly(2026, 3, 1), range.End);
        Assert.Equal(timeFrame, range.TimeFrame);
    }

    [Fact]
    public void HomeReportRange_ClampsShortHistoryAndReturnsNullForNoVisibleBalances()
    {
        BalanceObservation[] shortHistory =
        [
            Balance("checking", "Checking", "Cash", 2026, 2, 15, 100m),
            Balance("checking", "Checking", "Cash", 2026, 3, 1, 150m)
        ];

        HomeReportRange shortRange = Assert.IsType<HomeReportRange>(
            HomeReportRange.Create(shortHistory, HomeTimeFrame.FiveYears));

        Assert.Equal(new DateOnly(2021, 3, 2), shortRange.RequestedStart);
        Assert.Equal(new DateOnly(2026, 2, 15), shortRange.Start);
        Assert.Equal(new DateOnly(2026, 3, 1), shortRange.End);

        HomeReportRange oneObservation = Assert.IsType<HomeReportRange>(HomeReportRange.Create(
            [Balance("checking", "Checking", "Cash", 2026, 3, 1, 150m)],
            HomeTimeFrame.OneYear));
        Assert.Equal(new DateOnly(2025, 3, 1), oneObservation.RequestedStart);
        Assert.Equal(new DateOnly(2026, 3, 1), oneObservation.Start);
        Assert.Equal(oneObservation.Start, oneObservation.End);

        Assert.Null(HomeReportRange.Create([Balance("hidden", "Hidden", "Cash", 2026, 3, 1, 1m, true)], HomeTimeFrame.All));
    }

    [Fact]
    public void HomeReportRange_OnlyAcceptsTheConfiguredSourceChoices()
    {
        Assert.True(HomeReportRange.TryParse("5y", out HomeTimeFrame timeFrame));
        Assert.Equal(HomeTimeFrame.FiveYears, timeFrame);
        Assert.False(HomeReportRange.TryParse("10y", out _));
        Assert.False(HomeReportRange.TryParse(null, out _));
        Assert.Throws<ArgumentException>(() => HomeReportRange.Parse("10y"));
    }

    [Fact]
    public void Build_HomeUsesTheSelectedRangeForHistoryMetricsGroupsAndInventory()
    {
        PortfolioSnapshot snapshot = new(
            [],
            [
                Balance("checking", "Checking", "Cash", 2025, 11, 1, 300m),
                Balance("card", "Card", "Debt", 2025, 11, 1, 150m, accountClass: AccountClass.Liability),
                Balance("checking", "Checking", "Cash", 2025, 12, 20, 400m),
                Balance("card", "Card", "Debt", 2025, 12, 20, 140m, accountClass: AccountClass.Liability),
                Balance("checking", "Checking", "Cash", 2026, 3, 1, 500m),
                Balance("card", "Card", "Debt", 2026, 3, 1, 100m, accountClass: AccountClass.Liability)
            ],
            []);

        DashboardPageReport home = DashboardReportBuilder.Build(
            snapshot,
            Settings(),
            new DashboardFilters(3, "all", "all", true, HomeTimeFrame.ThreeMonths))
            .Page(DashboardPageId.Home);

        DashboardWidgetReport netWorth = home.Widgets["home.net_worth"];
        Assert.Equal(new DateOnly(2025, 12, 1), netWorth.Series[0].Points.First().Date);
        Assert.Equal(new DateOnly(2026, 3, 1), netWorth.Series[0].Points.Last().Date);
        Assert.All(netWorth.Series.SelectMany(series => series.Points), point =>
            Assert.InRange(point.Date!.Value, new DateOnly(2025, 12, 1), new DateOnly(2026, 3, 1)));
        Assert.All(
            netWorth.Series.Single(series => series.Id == "net-worth").Points.Skip(1),
            point => Assert.Equal(DayOfWeek.Sunday, point.Date!.Value.DayOfWeek));
        Assert.Equal(150m, netWorth.Series.Single(series => series.Id == "net-worth").Points.First().Y);
        Assert.Equal(400m, netWorth.Series.Single(series => series.Id == "net-worth").Points.Last().Y);
        Assert.Equal("$400", netWorth.Metrics.Single(metric => metric.Label == "Net worth").Display);
        Assert.Equal("+$250 over 3M", netWorth.Metrics.Single(metric => metric.Label == "Net worth").Detail);
        Assert.Equal("-$50 over 3M", netWorth.Metrics.Single(metric => metric.Label == "Liabilities").Detail);

        DashboardWidgetReport groups = home.Widgets["home.accounts"];
        ReportMetric cash = groups.Metrics.Single(metric => metric.Label == "Cash");
        ReportMetric debt = groups.Metrics.Single(metric => metric.Label == "Debt");
        Assert.Equal("+$200 over 3M", cash.Detail);
        Assert.Equal("-$50 over 3M", debt.Detail);
        Assert.Equal("positive", debt.Tone);
        Assert.Equal(
            ["Debt", "Cash"],
            home.Widgets["home.attribution"].Series.Single().Points.Select(point => point.Category));
        Assert.Equal(200m, home.Widgets["home.attribution"].Series.Single().Points.Single(point => point.Category == "Cash").Y);
        Assert.Equal(50m, home.Widgets["home.attribution"].Series.Single().Points.Single(point => point.Category == "Debt").Y);

        ReportTableRow card = home.Widgets["home.inventory"].Rows.Single(row => row.Values[1] == "Card");
        Assert.Equal(["Debt", "Card", "$100", "-$50"], card.Values);
        Assert.Equal("positive", card.Tone);
    }

    [Fact]
    public void Build_HomeClipsMetricsToTheEarliestBalanceAndUsesEmptyReportsWithoutBalances()
    {
        PortfolioSnapshot shortHistory = new(
            [],
            [
                Balance("checking", "Checking", "Cash", 2026, 2, 15, 100m),
                Balance("checking", "Checking", "Cash", 2026, 3, 1, 150m)
            ],
            []);

        DashboardPageReport clipped = DashboardReportBuilder.Build(
            shortHistory,
            Settings(),
            new DashboardFilters(3, "all", "all", true, HomeTimeFrame.FiveYears))
            .Page(DashboardPageId.Home);

        ReportMetric netWorth = clipped.Widgets["home.net_worth"].Metrics.Single(metric => metric.Label == "Net worth");
        Assert.Equal("+$50 since Feb 2026", netWorth.Detail);
        Assert.Equal(new DateOnly(2026, 2, 15), clipped.Widgets["home.net_worth"].Series[0].Points.First().Date);

        DashboardPageReport empty = DashboardReportBuilder.Build(
            new PortfolioSnapshot([], [], []),
            Settings(),
            new DashboardFilters(3, "all", "all", true, HomeTimeFrame.All))
            .Page(DashboardPageId.Home);

        Assert.Empty(empty.Widgets["home.net_worth"].Series);
        Assert.Empty(empty.Widgets["home.attribution"].Series);
        Assert.Equal("No visible account balances are available.", empty.Widgets["home.net_worth"].EmptyMessage);
        Assert.Equal("No visible account balances are available.", empty.Widgets["home.attribution"].EmptyMessage);
    }

    [Fact]
    public void Build_HomeKeepsTheConfiguredLabelWhenTheEarliestObservationIsWithinOneWeek()
    {
        PortfolioSnapshot snapshot = new(
            [],
            [
                Balance("checking", "Checking", "Cash", 2025, 12, 5, 100m),
                Balance("checking", "Checking", "Cash", 2026, 3, 1, 150m)
            ],
            []);

        ReportMetric netWorth = DashboardReportBuilder.Build(
            snapshot,
            Settings(),
            new DashboardFilters(3, "all", "all", true, HomeTimeFrame.ThreeMonths))
            .Page(DashboardPageId.Home)
            .Widgets["home.net_worth"]
            .Metrics
            .Single(metric => metric.Label == "Net worth");

        Assert.Equal("+$50 over 3M", netWorth.Detail);
    }

    [Fact]
    public void Build_HomeUsesNetContributionForAccountsInsideAMixedGroup()
    {
        PortfolioSnapshot snapshot = new(
            [],
            [
                Balance("cash", "Cash", "Mixed", 2025, 12, 1, 100m),
                Balance("card", "Card", "Mixed", 2025, 12, 1, 100m, accountClass: AccountClass.Liability),
                Balance("cash", "Cash", "Mixed", 2026, 3, 1, 150m),
                Balance("card", "Card", "Mixed", 2026, 3, 1, 75m, accountClass: AccountClass.Liability)
            ],
            []);

        DashboardPageReport home = DashboardReportBuilder.Build(
            snapshot,
            Settings(),
            new DashboardFilters(3, "all", "all", true, HomeTimeFrame.ThreeMonths))
            .Page(DashboardPageId.Home);

        Assert.Equal("$75", home.Widgets["home.accounts"].Metrics.Single().Display);
        Assert.Equal(
            ["Mixed", "Card", "-$75", "+$25"],
            home.Widgets["home.inventory"].Rows.Single(row => row.Values[1] == "Card").Values);
    }

    [Fact]
    public void Build_HomeKeepsUnmappedBalancesInNetWorthButOmitsThemFromAccountViews()
    {
        PortfolioSnapshot snapshot = new(
            [],
            [
                Balance("checking", "Checking", "Cash", 2025, 12, 1, 100m),
                Balance("unmapped", "Unmapped", " ", 2025, 12, 1, 80m),
                Balance("checking", "Checking", "Cash", 2026, 3, 1, 150m),
                Balance("unmapped", "Unmapped", " ", 2026, 3, 1, 90m)
            ],
            []);

        DashboardPageReport home = DashboardReportBuilder.Build(
            snapshot,
            Settings(),
            new DashboardFilters(3, "all", "all", true, HomeTimeFrame.ThreeMonths))
            .Page(DashboardPageId.Home);

        Assert.Equal(240m, home.Widgets["home.net_worth"].Series.Single(series => series.Id == "net-worth").Points.Last().Y);
        Assert.Equal(["Cash"], home.Widgets["home.accounts"].Metrics.Select(metric => metric.Label));
        Assert.Equal(["Checking"], home.Widgets["home.inventory"].Rows.Select(row => row.Values[1]));

        DashboardPageReport unmappedOnly = DashboardReportBuilder.Build(
            new PortfolioSnapshot([], [Balance("unmapped", "Unmapped", " ", 2026, 3, 1, 90m)], []),
            Settings(),
            new DashboardFilters(3, "all", "all", true, HomeTimeFrame.ThreeMonths))
            .Page(DashboardPageId.Home);

        Assert.Equal("No mapped balance groups are available.", unmappedOnly.Widgets["home.accounts"].EmptyMessage);
    }

    [Fact]
    public void Build_HomeMatchesDuplicateAccountNamesByStableAccountId()
    {
        PortfolioSnapshot snapshot = new(
            [],
            [
                Balance("brokerage-one", "Brokerage", "Investments", 2025, 12, 1, 100m),
                Balance("brokerage-two", "Brokerage", "Investments", 2025, 12, 1, 300m),
                Balance("brokerage-one", "Brokerage", "Investments", 2026, 3, 1, 150m),
                Balance("brokerage-two", "Brokerage", "Investments", 2026, 3, 1, 200m)
            ],
            []);

        DashboardPageReport home = DashboardReportBuilder.Build(
            snapshot,
            Settings(),
            new DashboardFilters(3, "all", "all", true, HomeTimeFrame.ThreeMonths))
            .Page(DashboardPageId.Home);

        ReportMetric group = Assert.Single(home.Widgets["home.accounts"].Metrics);
        Assert.Equal("Investments", group.Label);
        Assert.Equal(350m, group.Value);
        Assert.Equal("-$50 over 3M", group.Detail);
        Assert.Equal(-50m, home.Widgets["home.attribution"].Series.Single().Points.Single().Y);
        Assert.Equal(
            [
                ["Investments", "Brokerage", "$200", "-$100"],
                ["Investments", "Brokerage", "$150", "+$50"]
            ],
            home.Widgets["home.inventory"].Rows.Select(row => row.Values).ToArray());
    }

    [Fact]
    public void SupportedWidgetReports_CoversTheCheckedInDashboardGrammar()
    {
        string[] expected =
        [
            "home.net_worth", "income.cash_flow", "spending.categories", "yoy.comparison",
            "subscriptions.active", "merchants.ranking", "budget.table", "top.table",
            "fi.sensitivity", "health.findings"
        ];

        foreach (string report in expected)
            Assert.Contains(report, DashboardReportBuilder.SupportedWidgetReports);
    }

    [Fact]
    public void Session_UsesConfiguredFiltersAndRejectsHiddenPages()
    {
        DashboardDefinition definition = new(
            1,
            "Portico",
            [
                new DashboardPageDefinition(DashboardPageId.Home, "Home", "Overview", [], [new DashboardWidgetDefinition("overview", "Overview", DashboardWidgetKind.Metric, "home.overview")]),
                new DashboardPageDefinition(DashboardPageId.Budget, "Budget", "Budget", [], [new DashboardWidgetDefinition("budget", "Budget", DashboardWidgetKind.Table, "budget.table")], false)
            ]);
        var session = new DashboardSession(Snapshot(), Settings(), definition);

        session.SetFilter("lookback", "1");
        session.SetFilter("income_view", "actual");

        Assert.Equal(1, session.Filters.LookbackMonths);
        Assert.False(session.Filters.RegularIncome);
        Assert.Throws<ArgumentException>(() => session.SelectPage(DashboardPageId.Budget));
        Assert.Throws<ArgumentException>(() => session.SetFilter("lookback", "2"));
    }

    [Fact]
    public void Session_UsesDashboardDeclaredDefaultsBeforeBuildingTheReport()
    {
        DashboardDefinition definition = new(
            1,
            "Portico",
            [
                new DashboardPageDefinition(
                    DashboardPageId.Home,
                    "Home",
                    "Overview",
                    [
                        new DashboardFilterDefinition("lookback", "Lookback", DashboardFilterKind.Select, "lookback", "1", ["1", "3", "12"]),
                        new DashboardFilterDefinition("income", "Income", DashboardFilterKind.Select, "income_view", "actual", ["regular", "actual"]),
                        new DashboardFilterDefinition("spending", "Spending", DashboardFilterKind.Select, "spending", "all", ["all", "discretionary"]),
                        new DashboardFilterDefinition("yoy", "Comparison", DashboardFilterKind.Select, "year_over_year", "all", ["all"])
                    ],
                    [new DashboardWidgetDefinition("overview", "Overview", DashboardWidgetKind.Metric, "home.overview")])
            ]);

        var session = new DashboardSession(Snapshot(), Settings(), definition);

        Assert.Equal(1, session.Filters.LookbackMonths);
        Assert.False(session.Filters.RegularIncome);
        Assert.Equal("all", session.Filters.SpendingSet);
        Assert.Equal("all", session.Filters.YearOverYearSet);
    }

    [Fact]
    public void Build_UsesTheExplicitReportDateForProjectionAndDataHealth()
    {
        DashboardReport report = DashboardReportBuilder.Build(
            Snapshot(),
            Settings(),
            new DashboardFilters(3, "all", "all", true),
            new DateOnly(2030, 6, 1));

        ReportPoint projectionStart = report.Page(DashboardPageId.FinancialIndependence)
            .Widgets["fi.projection"]
            .Series
            .Single()
            .Points
            .First();

        Assert.Equal(new DateOnly(2030, 1, 1), projectionStart.Date);
    }

    private static FinanceSettings Settings()
    {
        TransactionSetDefinition[] sets =
        [
            Set("all"),
            Set("discretionary", includes: ["all"], excludes: ["housing"]),
            Set("housing", groups: ["Housing"])
        ];
        return new FinanceSettings(
            new DataSourceSettings(WorkbookSourceKind.LocalCsv, "demo/data"),
            new LookbackSettings([1, 3, 12], 3),
            new ThresholdSettings(100m, 1000m, 10m, 1),
            new IncomeSavingsSettings("regular", 20m, [], ["Fun"]),
            sets,
            [new FilterSetDefinition("spending", ["all", "discretionary"], "discretionary"), new FilterSetDefinition("year_over_year", ["all"], "all")],
            new SubscriptionSettings(["Streaming"], 80, 45, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 5, [], ["Investments", "Cash"]),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
            {
                ["Video Service"] = ["VIDEO SERVICE"]
            });
    }

    private static PortfolioSnapshot Snapshot()
        => new(
            [
                Row("salary", 2024, 1, 2, "Salary", "Income", "Pay", 1000m, TransactionKind.Income),
                Row("rent", 2024, 1, 3, "Rent", "Housing", "Rent", -500m, TransactionKind.Expense),
                Row("food", 2024, 1, 4, "Food", "Living", "Market", -100m, TransactionKind.Expense),
                Row("travel", 2024, 1, 5, "Flight", "Travel", "Flight", -300m, TransactionKind.Expense),
                Row("subscription", 2024, 1, 7, "Streaming", "Fun", "VIDEO SERVICE", -20m, TransactionKind.Expense),
                Row("salary2", 2024, 2, 2, "Salary", "Income", "Pay", 1200m, TransactionKind.Income),
                Row("food2", 2024, 2, 4, "Food", "Living", "Market", -200m, TransactionKind.Expense),
                Row("subscription2", 2024, 2, 7, "Streaming", "Fun", "VIDEO SERVICE", -20m, TransactionKind.Expense),
                Row("hidden", 2024, 2, 8, "Food", "Living", "Hidden charge", -999m, TransactionKind.Expense, true)
            ],
            [
                new BalanceObservation("cash", "Checking", "Cash", new DateOnly(2024, 1, 31), new TimeOnly(8, 0), 1500m, AccountClass.Asset, false),
                new BalanceObservation("cash", "Checking", "Cash", new DateOnly(2024, 2, 29), new TimeOnly(8, 0), 1700m, AccountClass.Asset, false),
                new BalanceObservation("invest", "Brokerage", "Investments", new DateOnly(2024, 2, 29), new TimeOnly(8, 0), 1000m, AccountClass.Asset, false),
                new BalanceObservation("card", "Card", "Debt", new DateOnly(2024, 2, 29), new TimeOnly(8, 0), 250m, AccountClass.Liability, false)
            ],
            [
                new BudgetEntry(new YearMonth(2024, 2), "Food", "Living", TransactionKind.Expense, 250m, false),
                new BudgetEntry(new YearMonth(2024, 2), "Streaming", "Fun", TransactionKind.Expense, 25m, false)
            ]);

    private static BalanceObservation Balance(
        string accountId,
        string account,
        string group,
        int year,
        int month,
        int day,
        decimal amount,
        bool hidden = false,
        AccountClass accountClass = AccountClass.Asset)
        => new(
            accountId,
            account,
            group,
            new DateOnly(year, month, day),
            new TimeOnly(8, 0),
            amount,
            accountClass,
            hidden);

    private static FinancialTransaction Row(
        string id,
        int year,
        int month,
        int day,
        string category,
        string group,
        string description,
        decimal amount,
        TransactionKind kind,
        bool hidden = false)
        => new(id, new DateOnly(year, month, day), category, group, "Checking", description, amount, kind, hidden);

    private static TransactionSetDefinition Set(
        string key,
        IReadOnlyList<string>? groups = null,
        IReadOnlyList<string>? includes = null,
        IReadOnlyList<string>? excludes = null)
        => new(key, key, groups ?? [], [], [], [], [], includes ?? [], excludes ?? []);
}
