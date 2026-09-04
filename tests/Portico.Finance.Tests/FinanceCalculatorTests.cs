using Portico.Finance;

namespace Portico.Finance.Tests;

public sealed class FinanceCalculatorTests
{
    [Fact]
    public void MonthlyCashFlow_HandlesIncomeExpenseRefundTransferAndEmptyMonths()
    {
        FinancialTransaction[] transactions =
        [
            Transaction("income", 2024, 1, 2, "Salary", "Income", 1000m, TransactionKind.Income),
            Transaction("charge", 2024, 1, 3, "Food", "Living", -250m, TransactionKind.Expense),
            Transaction("refund", 2024, 1, 4, "Food", "Living", 50m, TransactionKind.Expense),
            Transaction("transfer", 2024, 2, 1, "Transfer", "Transfers", -700m, TransactionKind.Transfer),
            Transaction("income", 2024, 3, 1, "Salary", "Income", 1200m, TransactionKind.Income)
        ];

        IReadOnlyList<MonthlyCashFlow> result = CashFlowCalculator.BuildMonthly(
            transactions,
            new IncomeExpensePolicy([], []),
            new YearMonth(2024, 1),
            new YearMonth(2024, 3));

        Assert.Collection(
            result,
            january =>
            {
                Assert.Equal(1000m, january.Income);
                Assert.Equal(-200m, january.SignedExpense);
                Assert.Equal(200m, january.NetExpenses);
                Assert.Equal(800m, january.Surplus);
                Assert.Equal(80m, january.SavingsRatePercent);
            },
            february =>
            {
                Assert.Equal(0m, february.Income);
                Assert.Equal(0m, february.NetExpenses);
                Assert.Equal(0m, february.Surplus);
                Assert.Null(february.SavingsRatePercent);
            },
            march => Assert.Equal(1200m, march.Surplus));
    }

    [Theory]
    [InlineData(0, 0, 0)]
    [InlineData(100, 25, 75)]
    [InlineData(100, 150, -50)]
    public void MonthlyCashFlow_UsesNullSavingsRateWithoutIncome(int income, int expenses, int expectedSurplus)
    {
        var rows = new List<FinancialTransaction>();
        if (income != 0)
            rows.Add(Transaction("income", 2024, 2, 1, "Salary", "Income", income, TransactionKind.Income));
        if (expenses != 0)
            rows.Add(Transaction("expense", 2024, 2, 2, "Food", "Living", -expenses, TransactionKind.Expense));

        MonthlyCashFlow result = Assert.Single(CashFlowCalculator.BuildMonthly(
            rows,
            new IncomeExpensePolicy([], []),
            new YearMonth(2024, 2),
            new YearMonth(2024, 2)));

        Assert.Equal((decimal)expectedSurplus, result.Surplus);
        if (income == 0)
            Assert.Null(result.SavingsRatePercent);
        else
            Assert.Equal((decimal)expectedSurplus / income * 100m, result.SavingsRatePercent);
    }

    [Fact]
    public void MonthlyCashFlow_AppliesCategoryAndGroupExclusions()
    {
        FinancialTransaction[] rows =
        [
            Transaction("income", 2024, 1, 1, "Salary", "Income", 1000m, TransactionKind.Income),
            Transaction("travel", 2024, 1, 2, "Flight", "Travel", -300m, TransactionKind.Expense),
            Transaction("rent", 2024, 1, 3, "Rent", "Housing", -600m, TransactionKind.Expense)
        ];

        MonthlyCashFlow result = Assert.Single(CashFlowCalculator.BuildMonthly(
            rows,
            new IncomeExpensePolicy(["Flight"], ["Travel"]),
            new YearMonth(2024, 1),
            new YearMonth(2024, 1)));

        Assert.Equal(600m, result.NetExpenses);
        Assert.Equal(400m, result.Surplus);
    }

    [Fact]
    public void SpendingAggregate_UsesPositiveDisplayValuesAndStableTies()
    {
        FinancialTransaction[] rows =
        [
            Transaction("a", 2024, 1, 1, "Alpha", "Home", -30m, TransactionKind.Expense),
            Transaction("b", 2024, 1, 2, "Beta", "Home", -20m, TransactionKind.Expense),
            Transaction("c", 2024, 1, 3, "Alpha", "Home", 10m, TransactionKind.Expense)
        ];

        IReadOnlyList<SpendingItem> result = CashFlowCalculator.AggregateSpending(rows, row => row.Category);

        Assert.Collection(
            result,
            alpha =>
            {
                Assert.Equal("Alpha", alpha.Entity);
                Assert.Equal(20m, alpha.Spending);
                Assert.Equal(50m, alpha.SharePercent);
                Assert.Equal(2, alpha.TransactionCount);
            },
            beta => Assert.Equal(20m, beta.Spending));
    }

    [Fact]
    public void TransactionSetMatcher_ComposesIncludesExcludesAndAliases()
    {
        FinancialTransaction[] rows =
        [
            Transaction("groceries", 2024, 1, 1, "Groceries", "Living", -20m, TransactionKind.Expense, "WHOLE FOODS 12"),
            Transaction("rent", 2024, 1, 2, "Rent", "Housing", -700m, TransactionKind.Expense),
            Transaction("fuel", 2024, 1, 3, "Fuel", "Transport", -30m, TransactionKind.Expense)
        ];
        TransactionSetDefinition[] sets =
        [
            Set("all"),
            Set("housing", groups: ["Housing"]),
            Set("food", merchants: ["Whole Foods"]),
            Set("discretionary", includes: ["all"], excludes: ["housing"])
        ];
        var aliases = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
        {
            ["Whole Foods"] = ["WHOLE FOODS"]
        };

        IReadOnlyList<FinancialTransaction> discretionary = TransactionSetMatcher.Select(rows, "discretionary", sets, aliases);
        IReadOnlyList<FinancialTransaction> food = TransactionSetMatcher.Select(rows, "food", sets, aliases);

        Assert.Equal(["groceries", "fuel"], discretionary.Select(row => row.Id));
        Assert.Equal("groceries", Assert.Single(food).Id);
    }

    [Fact]
    public void TransactionSetMatcher_RejectsCyclesAndUnknownReferences()
    {
        TransactionSetDefinition[] cycle = [Set("first", includes: ["second"]), Set("second", includes: ["first"])];
        ArgumentException cycleError = Assert.Throws<ArgumentException>(() => TransactionSetMatcher.Select([], "first", cycle, EmptyAliases()));
        Assert.Contains("cycle", cycleError.Message, StringComparison.OrdinalIgnoreCase);

        TransactionSetDefinition[] unknown = [Set("first", includes: ["missing"])];
        ArgumentException unknownError = Assert.Throws<ArgumentException>(() => TransactionSetMatcher.Select([], "first", unknown, EmptyAliases()));
        Assert.Contains("unknown", unknownError.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void PortfolioCalculator_UsesLatestVisibleBalanceAndSignsLiabilities()
    {
        BalanceObservation[] observations =
        [
            Balance("checking", "Checking", "Cash", 2024, 1, 1, 8, 100m, AccountClass.Asset),
            Balance("checking", "Checking", "Cash", 2024, 1, 1, 9, 120m, AccountClass.Asset),
            Balance("card", "Card", "Debt", 2024, 1, 1, 8, 60m, AccountClass.Liability),
            Balance("hidden", "Hidden", "Cash", 2024, 1, 2, 8, 999m, AccountClass.Asset, true)
        ];

        IReadOnlyList<AccountBalance> latest = PortfolioCalculator.LatestBalances(observations);
        IReadOnlyList<NetWorthPoint> history = PortfolioCalculator.BuildNetWorthHistory(observations);

        Assert.Equal(2, latest.Count);
        Assert.Equal(-60m, Assert.Single(latest, value => value.Account == "Card").SignedBalance);
        NetWorthPoint point = Assert.Single(history);
        Assert.Equal(120m, point.Assets);
        Assert.Equal(-60m, point.Liabilities);
        Assert.Equal(60m, point.NetWorth);
    }

    [Theory]
    [InlineData(0, 100, 0, 0)]
    [InlineData(1000, 100, 0, 10)]
    [InlineData(1000, 0, 7, 0)]
    public void FinancialIndependence_RunwayHandlesDepletionAndSustainability(
        int portfolio,
        int spending,
        int rate,
        int expectedRunway)
    {
        FinancialIndependenceSummary result = FinancialIndependenceCalculator.Summarize(portfolio, spending, rate);

        if (spending == 0 || portfolio * rate / 100m >= spending)
            Assert.Null(result.RunwayYears);
        else
            Assert.Equal((decimal)expectedRunway, decimal.Truncate(result.RunwayYears!.Value));
    }

    [Fact]
    public void FinancialIndependence_ProjectsRecurrenceAndKeepsBalancesNonNegative()
    {
        IReadOnlyList<PortfolioProjectionPoint> result = FinancialIndependenceCalculator.Project(100m, 80m, 10m, 3, 20m);

        Assert.Collection(
            result,
            year0 => Assert.Equal(100m, year0.Balance),
            year1 => Assert.Equal(50m, year1.Balance),
            year2 => Assert.Equal(0m, year2.Balance),
            year3 => Assert.Equal(0m, year3.Balance));
    }

    [Fact]
    public void FinancialSafety_UsesCompletedMonthsAndConfiguredAccountScopes()
    {
        FinancialTransaction[] transactions =
        [
            Transaction("jan", 2024, 1, 2, "Food", "Living", -100m, TransactionKind.Expense),
            Transaction("feb", 2024, 2, 2, "Food", "Living", -200m, TransactionKind.Expense),
            Transaction("travel", 2024, 2, 3, "Flight", "Travel", -1000m, TransactionKind.Expense),
            Transaction("mar", 2024, 3, 2, "Food", "Living", -300m, TransactionKind.Expense),
            Transaction("apr", 2024, 4, 2, "Food", "Living", -999m, TransactionKind.Expense)
        ];
        BalanceObservation[] balances =
        [
            Balance("cash", "Checking", "Cash", 2024, 3, 31, 8, 900m, AccountClass.Asset),
            Balance("debt", "Card", "Debt", 2024, 1, 31, 8, 1000m, AccountClass.Liability),
            Balance("debt", "Card", "Debt", 2024, 3, 31, 8, 600m, AccountClass.Liability),
            Balance("invest", "Brokerage", "Investments", 2024, 3, 31, 8, 5000m, AccountClass.Asset)
        ];
        var safety = new FinancialSafetySettings(
            3,
            ["Cash"],
            [],
            3,
            [],
            ["Travel"],
            ["Debt"],
            [],
            null);
        var financialIndependence = new FinancialIndependenceSettings(7m, 4m, 10000m, 12, 10, [], ["Investments"]);

        FinancialSafetySummary result = FinancialSafetyCalculator.Summarize(
            transactions,
            balances,
            safety,
            financialIndependence,
            new DateOnly(2024, 4, 15));

        Assert.Equal(900m, result.EmergencyFundBalance);
        Assert.Equal(200m, result.EmergencyFundAverageMonthlySpending);
        Assert.Equal(600m, result.EmergencyFundTarget);
        Assert.Equal(4.5m, result.EmergencyFundMonthsCovered);
        Assert.Equal(600m, result.DebtBalance);
        Assert.Equal(1000m, result.DebtBaselineBalance);
        Assert.Equal(400m, result.DebtPaidDown);
        Assert.Equal(40m, result.DebtProgressPercent);
        Assert.Equal(new DateOnly(2024, 1, 31), result.DebtBaselineDate);
        Assert.Equal(5000m, result.FinancialIndependencePortfolio);
        Assert.Equal(50m, result.FinancialIndependenceProgressPercent);
    }

    [Fact]
    public void FinancialSafety_HandlesMissingScopesAndZeroBaselines()
    {
        var safety = new FinancialSafetySettings(6, [], [], 6, [], [], [], [], null);
        var financialIndependence = new FinancialIndependenceSettings(7m, 4m, 0m, 12, 10, [], []);

        FinancialSafetySummary result = FinancialSafetyCalculator.Summarize(
            [],
            [],
            safety,
            financialIndependence,
            new DateOnly(2024, 4, 15));

        Assert.Equal(0m, result.EmergencyFundBalance);
        Assert.Null(result.EmergencyFundMonthsCovered);
        Assert.Equal(0m, result.DebtBalance);
        Assert.Null(result.DebtProgressPercent);
        Assert.Null(result.DebtBaselineDate);
        Assert.Equal(0m, result.FinancialIndependencePortfolio);
        Assert.Null(result.FinancialIndependenceProgressPercent);
    }

    [Fact]
    public void YearMonth_HandlesLeapBoundaryRangeAndInvalidInput()
    {
        Assert.Equal(new YearMonth(2024, 2), YearMonth.From(new DateOnly(2024, 2, 29)));
        Assert.Equal([new YearMonth(2023, 12), new YearMonth(2024, 1), new YearMonth(2024, 2)], YearMonth.InclusiveRange(new YearMonth(2023, 12), new YearMonth(2024, 2)));
        Assert.False(YearMonth.TryParse("2024-13", out _));
        Assert.True(YearMonth.TryParse("2024-02", out YearMonth parsed));
        Assert.Equal(new YearMonth(2024, 2), parsed);
    }

    private static FinancialTransaction Transaction(
        string id,
        int year,
        int month,
        int day,
        string category,
        string group,
        decimal amount,
        TransactionKind kind,
        string? description = null)
        => new(id, new DateOnly(year, month, day), category, group, "Account", description ?? category, amount, kind);

    private static BalanceObservation Balance(
        string id,
        string account,
        string group,
        int year,
        int month,
        int day,
        int hour,
        decimal balance,
        AccountClass accountClass,
        bool hidden = false)
        => new(id, account, group, new DateOnly(year, month, day), new TimeOnly(hour, 0), balance, accountClass, hidden);

    private static TransactionSetDefinition Set(
        string key,
        IReadOnlyList<string>? groups = null,
        IReadOnlyList<string>? merchants = null,
        IReadOnlyList<string>? includes = null,
        IReadOnlyList<string>? excludes = null)
        => new(key, key, groups ?? [], [], [], merchants ?? [], [], includes ?? [], excludes ?? []);

    private static IReadOnlyDictionary<string, IReadOnlyList<string>> EmptyAliases()
        => new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);
}
