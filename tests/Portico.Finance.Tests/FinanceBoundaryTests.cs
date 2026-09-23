using Portico.Finance;

namespace Portico.Finance.Tests;

public sealed class FinanceBoundaryTests
{
    [Fact]
    public void CashFlowWithoutRange_ReturnsOnlyObservedMonthsInOrder()
    {
        FinancialTransaction[] rows =
        [
            Row("march", 2025, 3, 2, -30m, TransactionKind.Expense),
            Row("january", 2025, 1, 2, 100m, TransactionKind.Income),
            Row("transfer", 2025, 2, 2, 50m, TransactionKind.Transfer)
        ];

        IReadOnlyList<MonthlyCashFlow> monthly = CashFlowCalculator.BuildMonthly(rows, new IncomeExpensePolicy([], []));

        Assert.Equal([new YearMonth(2025, 1), new YearMonth(2025, 3)], monthly.Select(row => row.Month));
        Assert.Equal([100m, -30m], monthly.Select(row => row.Surplus));
    }

    [Fact]
    public void CashFlowRange_ExcludesOutsideMonthsAndAllowsReverseRange()
    {
        FinancialTransaction[] rows =
        [
            Row("before", 2025, 1, 1, 100m, TransactionKind.Income),
            Row("inside", 2025, 2, 1, -25m, TransactionKind.Expense),
            Row("after", 2025, 3, 1, 100m, TransactionKind.Income)
        ];
        var policy = new IncomeExpensePolicy([], []);

        MonthlyCashFlow month = Assert.Single(CashFlowCalculator.BuildMonthly(
            rows, policy, new YearMonth(2025, 2), new YearMonth(2025, 2)));

        Assert.Equal(-25m, month.Surplus);
        Assert.Empty(CashFlowCalculator.BuildMonthly(
            rows, policy, new YearMonth(2025, 3), new YearMonth(2025, 2)));
        Assert.Throws<ArgumentException>(() => CashFlowCalculator.BuildMonthly(rows, policy, new YearMonth(2025, 2)));
    }

    [Fact]
    public void CashFlowSummary_CountsPositiveMonthsAndHandlesNoIncome()
    {
        CashFlowSummary summary = CashFlowCalculator.Summarize(
        [
            new MonthlyCashFlow(new YearMonth(2025, 1), 100m, -40m, 40m, 60m, 60m),
            new MonthlyCashFlow(new YearMonth(2025, 2), 0m, -80m, 80m, -80m, null)
        ]);
        CashFlowSummary empty = CashFlowCalculator.Summarize([]);

        Assert.Equal(100m, summary.Income);
        Assert.Equal(120m, summary.NetExpenses);
        Assert.Equal(-20m, summary.Surplus);
        Assert.Equal(-20m, summary.SavingsRatePercent);
        Assert.Equal(-10m, summary.AverageMonthlySurplus);
        Assert.Equal(1, summary.PositiveSurplusMonths);
        Assert.Equal(2, summary.Months);
        Assert.Equal(0m, empty.AverageMonthlySurplus);
        Assert.Null(empty.SavingsRatePercent);
    }

    [Fact]
    public void SpendingAggregate_UsesUncategorizedAndZeroShareForOffsettingRefund()
    {
        FinancialTransaction[] rows =
        [
            Row("charge", 2025, 1, 1, -25m, TransactionKind.Expense, category: " "),
            Row("refund", 2025, 1, 2, 25m, TransactionKind.Expense, category: " "),
            Row("income", 2025, 1, 3, 100m, TransactionKind.Income, category: "Other")
        ];

        SpendingItem item = Assert.Single(CashFlowCalculator.AggregateSpending(rows, row => row.Category));

        Assert.Equal("Uncategorized", item.Entity);
        Assert.Equal(0m, item.Spending);
        Assert.Equal(0m, item.SharePercent);
        Assert.Equal(2, item.TransactionCount);
        Assert.Throws<ArgumentException>(() => CashFlowCalculator.AggregateSpending(
            rows, row => row.Category, new YearMonth(2025, 1)));
    }

    [Fact]
    public void FinancialIndependence_ReturnsFundingValuesAndPositiveRateRunway()
    {
        FinancialIndependenceSummary summary = FinancialIndependenceCalculator.Summarize(
            1000m, 120m, 5m, annualIncome: 20m, withdrawalRatePercent: 4m);

        Assert.Equal(50m, summary.AnnualReturn);
        Assert.Equal(100m, summary.NetAnnualSpending);
        Assert.Equal(-50m, summary.AnnualSurplus);
        Assert.Equal(40m, summary.SustainableSpending);
        Assert.Equal(2500m, summary.FinancialIndependenceTarget);
        Assert.Equal(-1500m, summary.FundingGap);
        Assert.InRange(summary.RunwayYears!.Value, 13m, 15m);
    }

    [Fact]
    public void FinancialIndependence_HandlesIncomeCoverageAndZeroWithdrawalRate()
    {
        FinancialIndependenceSummary covered = FinancialIndependenceCalculator.Summarize(1000m, 100m, 0m, 150m);
        FinancialIndependenceSummary unavailableTarget = FinancialIndependenceCalculator.Summarize(
            1000m, 100m, 0m, withdrawalRatePercent: 0m);

        Assert.Equal(0m, covered.NetAnnualSpending);
        Assert.Equal(0m, covered.FinancialIndependenceTarget);
        Assert.Null(covered.RunwayYears);
        Assert.Equal(decimal.MaxValue, unavailableTarget.FinancialIndependenceTarget);
        Assert.Equal(10m, unavailableTarget.RunwayYears);
    }

    [Fact]
    public void FinancialIndependenceProjection_RejectsInvalidHorizonAndKeepsStartingPoint()
    {
        PortfolioProjectionPoint start = Assert.Single(FinancialIndependenceCalculator.Project(100m, 50m, 5m, 0));

        Assert.Equal(0, start.Year);
        Assert.Equal(100m, start.Balance);
        Assert.Throws<ArgumentOutOfRangeException>(() => FinancialIndependenceCalculator.Project(100m, 50m, 5m, -1));
        Assert.Throws<ArgumentOutOfRangeException>(() => FinancialIndependenceCalculator.Project(100m, 50m, 5m, 101));
    }

    [Fact]
    public void FinancialIndependenceSensitivity_KeepsRowMajorOrderAndIncomeAssumption()
    {
        IReadOnlyList<RunwaySensitivityCell> cells = FinancialIndependenceCalculator.BuildSensitivity(
            100m, 60m, 10m, [-50m, 0m], [0m, 100m]);

        Assert.Equal([(30m, 0m), (30m, 100m), (60m, 0m), (60m, 100m)],
            cells.Select(cell => (cell.AnnualSpending, cell.ReturnRate)));
        Assert.Equal(5m, cells[0].RunwayYears);
        Assert.Null(cells[1].RunwayYears);
        Assert.Equal(2m, cells[2].RunwayYears);
        Assert.Null(cells[3].RunwayYears);
    }

    [Fact]
    public void FinancialIndependenceSource_UsesLatestVisibleExpenseMonthAndStableAccountOrder()
    {
        FinancialIndependenceSourceAnalysis source = FinancialIndependenceSourceAnalysisCalculator.Build(
        [
            new AccountBalance("b", "Beta", "Investing", 100m, AccountClass.Asset),
            new AccountBalance("a", "Alpha", "Investing", 100m, AccountClass.Asset),
            new AccountBalance("c", "Cash", "Cash", 20m, AccountClass.Asset)
        ],
        [
            Row("old", 2024, 12, 1, -100m, TransactionKind.Expense),
            Row("current-b", 2025, 2, 3, -20m, TransactionKind.Expense),
            Row("current-a", 2025, 2, 3, -10m, TransactionKind.Expense),
            Row("hidden", 2025, 3, 1, -1000m, TransactionKind.Expense, hidden: true),
            Row("income", 2025, 4, 1, 1000m, TransactionKind.Income)
        ], new FinancialIndependenceSourceFilters(["Beta", "Alpha"], 2, SpendingAdjustments.Default(100m)));

        Assert.Equal(["Alpha", "Beta"], source.Accounts.Select(account => account.Account));
        Assert.Equal(["current-a", "current-b"], source.Expenses.Select(row => row.Id));
        Assert.Equal([0m, 30m], source.MonthlySpending.Select(row => row.Spending));
        Assert.Equal(180m, source.AnnualSpending);
        Assert.Equal(new YearMonth(2025, 2), source.EndMonth);
    }

    [Fact]
    public void FinancialIndependenceSource_EmptyExpensesKeepsSelectedAccounts()
    {
        FinancialIndependenceSourceAnalysis source = FinancialIndependenceSourceAnalysisCalculator.Build(
            [new AccountBalance("cash", "Cash", "Cash", 50m, AccountClass.Asset)],
            [Row("hidden", 2025, 2, 1, -100m, TransactionKind.Expense, hidden: true)],
            new FinancialIndependenceSourceFilters(["Cash"], 12, SpendingAdjustments.Default(100m)));

        Assert.Equal(50m, source.PortfolioValue);
        Assert.Empty(source.Expenses);
        Assert.Empty(source.MonthlySpending);
        Assert.Equal(0m, source.AnnualSpending);
        Assert.Null(source.StartMonth);
        Assert.Null(source.EndMonth);
    }

    [Fact]
    public void FinancialIndependenceSource_DefaultFiltersPreferAssetsUnlessRulesSelectGroupsOrNames()
    {
        AccountBalance[] accounts =
        [
            new("brokerage", "Brokerage", "Investing", 100m, AccountClass.Asset),
            new("card", "Card", "Debt", -20m, AccountClass.Liability),
            new("cash", "Cash", "Cash", 10m, AccountClass.Asset)
        ];
        FinanceSettings settings = Settings();

        FinancialIndependenceSourceFilters assets = FinancialIndependenceSourceAnalysisCalculator.DefaultFilters(accounts, settings);
        FinancialIndependenceSourceFilters selected = FinancialIndependenceSourceAnalysisCalculator.DefaultFilters(
            accounts,
            settings with
            {
                FinancialIndependence = settings.FinancialIndependence with
                {
                    IncludedGroups = ["Debt"],
                    IncludedAccountPatterns = ["broker"]
                }
            });

        Assert.Equal(["Brokerage", "Cash"], assets.IncludedAccounts);
        Assert.Equal(12, assets.SpendingLookbackMonths);
        Assert.Equal(100m, assets.Adjustments.ExpenseLimit);
        Assert.Equal(["Brokerage", "Card"], selected.IncludedAccounts);
    }

    [Fact]
    public void FinancialIndependenceSource_AppliesCategoryAndDescriptionExclusions()
    {
        SpendingAdjustments adjustments = SpendingAdjustments.Default(100m) with
        {
            ExcludedCategories = ["Travel"],
            IncludedDescriptions = ["market"],
            ExcludedDescriptions = ["online"]
        };
        FinancialTransaction[] rows =
        [
            Row("market", 2025, 2, 1, -40m, TransactionKind.Expense) with { Description = "Market shop" },
            Row("travel", 2025, 2, 2, -50m, TransactionKind.Expense, category: "Travel") with { Description = "Market ticket" },
            Row("online", 2025, 2, 3, -20m, TransactionKind.Expense) with { Description = "Market online" },
            Row("coffee", 2025, 2, 4, -10m, TransactionKind.Expense) with { Description = "Cafe" }
        ];

        FinancialIndependenceSourceAnalysis source = FinancialIndependenceSourceAnalysisCalculator.Build(
            [], rows, new FinancialIndependenceSourceFilters([], 1, adjustments));

        Assert.Equal("market", Assert.Single(source.Expenses).Id);
        Assert.Equal(480m, source.AnnualSpending);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(121)]
    public void FinancialIndependenceSource_RejectsUnboundedLookback(int months)
    {
        var filters = new FinancialIndependenceSourceFilters([], months, SpendingAdjustments.Default(100m));

        Assert.Throws<ArgumentOutOfRangeException>(filters.Validate);
    }

    [Fact]
    public void FinancialIndependenceScenario_RejectsInvalidAssumptions()
    {
        var valid = new FinancialIndependenceScenario(100m, 20m, 10m, 7m, 4m, 30);
        valid.Validate();

        Assert.Throws<ArgumentOutOfRangeException>(() => (valid with { Assets = -1m }).Validate());
        Assert.Throws<ArgumentOutOfRangeException>(() => (valid with { AnnualSpending = -1m }).Validate());
        Assert.Throws<ArgumentOutOfRangeException>(() => (valid with { AnnualIncome = -1m }).Validate());
        Assert.Throws<ArgumentOutOfRangeException>(() => (valid with { ExpectedReturnRate = 101m }).Validate());
        Assert.Throws<ArgumentOutOfRangeException>(() => (valid with { WithdrawalRate = 0m }).Validate());
        Assert.Throws<ArgumentOutOfRangeException>(() => (valid with { ProjectionYears = 101 }).Validate());
    }

    [Fact]
    public void SnapshotLatestDate_UsesTransactionsAndBalancesButNotBudgets()
    {
        var snapshot = new PortfolioSnapshot(
            [Row("transaction", 2025, 2, 1, -1m, TransactionKind.Expense)],
            [new BalanceObservation("account", "Account", "Cash", new DateOnly(2025, 3, 2), new TimeOnly(8, 0), 10m, AccountClass.Asset, false)],
            [new BudgetEntry(new YearMonth(2025, 12), "Food", "Living", TransactionKind.Expense, 50m, false)]);

        Assert.Equal(new DateOnly(2025, 3, 2), snapshot.LatestDate);
        Assert.Equal(new DateOnly(2025, 2, 1), (snapshot with { Balances = [] }).LatestDate);
        Assert.Null((snapshot with { Transactions = [], Balances = [] }).LatestDate);
    }

    [Fact]
    public void FinanceSettings_FindsExactKeysAndRejectsUnknownOnes()
    {
        FinanceSettings settings = Settings();

        Assert.Equal("all", settings.TransactionSet("all").Key);
        Assert.Equal("spending", settings.FilterSet("spending").Key);
        Assert.Throws<ArgumentException>(() => settings.TransactionSet("ALL"));
        Assert.Throws<ArgumentException>(() => settings.FilterSet("missing"));
    }

    [Fact]
    public void YearMonth_ParsesExactlyAndCrossesCalendarYear()
    {
        YearMonth december = YearMonth.Parse("2024-12");

        Assert.Equal("2024-12", december.ToString());
        Assert.Equal(new DateOnly(2024, 12, 1), december.Start);
        Assert.Equal(new DateOnly(2024, 12, 31), december.End);
        Assert.Equal(new YearMonth(2025, 1), december.AddMonths(1));
        Assert.Empty(YearMonth.InclusiveRange(new YearMonth(2025, 2), new YearMonth(2025, 1)));
        Assert.False(YearMonth.TryParse(null, out _));
        Assert.False(YearMonth.TryParse("2024/12", out _));
        Assert.False(YearMonth.TryParse("2024-00", out _));
        Assert.Throws<FormatException>(() => YearMonth.Parse("December 2024"));
        Assert.Throws<ArgumentOutOfRangeException>(() => new YearMonth(0, 1));
        Assert.Throws<ArgumentOutOfRangeException>(() => new YearMonth(2024, 13));
    }

    [Fact]
    public void YearMonth_InclusiveRangeStopsAtMaximumSupportedMonth()
    {
        IReadOnlyList<YearMonth> months = YearMonth.InclusiveRange(
            new YearMonth(9999, 11), new YearMonth(9999, 12));

        Assert.Equal([new YearMonth(9999, 11), new YearMonth(9999, 12)], months);
    }

    [Fact]
    public void YearMonth_EndReturnsLastRepresentableDate()
    {
        Assert.Equal(DateOnly.MaxValue, new YearMonth(9999, 12).End);
    }

    [Fact]
    public void IncomeSavingsOptions_ExcludeBlankValuesAndSortByStableName()
    {
        FinancialTransaction[] rows =
        [
            Row("income-one", 2025, 1, 1, 10m, TransactionKind.Income, "Salary"),
            Row("income-two", 2025, 1, 2, 20m, TransactionKind.Income, " Bonus "),
            Row("income-three", 2025, 1, 3, 30m, TransactionKind.Income, "Salary"),
            Row("expense-one", 2025, 1, 4, -10m, TransactionKind.Expense, "Food") with { Group = " Housing " },
            Row("expense-two", 2025, 1, 5, -20m, TransactionKind.Expense, " ") with { Group = "Living" }
        ];

        Assert.Equal(["Bonus", "Salary"], IncomeSavingsAnalysisCalculator.Categories(rows, TransactionKind.Income));
        Assert.Equal(["Food"], IncomeSavingsAnalysisCalculator.Categories(rows, TransactionKind.Expense));
        Assert.Equal(["Housing", "Living"], IncomeSavingsAnalysisCalculator.ExpenseGroups(rows));
    }

    private static FinanceSettings Settings()
        => new(
            new LookbackSettings([1, 3, 12], 3),
            new ThresholdSettings(100m, 1_000m, 10m, 1),
            new IncomeSavingsSettings("regular", 20m, [], []),
            [new TransactionSetDefinition("all", "All", [], [], [], [], [], [], [])],
            [new FilterSetDefinition("spending", ["all"], "all")],
            new SubscriptionSettings([], 80, 45, [], []),
            new BudgetSettings(12),
            new DataHealthSettings(7, true, false, true),
            new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null),
            new FinancialIndependenceSettings(7m, 4m, 1_000_000m, 12, 5, [], []),
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal));

    private static FinancialTransaction Row(
        string id, int year, int month, int day, decimal amount, TransactionKind kind,
        string category = "Food", bool hidden = false)
        => new(id, new DateOnly(year, month, day), category, "Living", "Checking", id, amount, kind, hidden);
}
