using Portico.Finance;

namespace Portico.Application.Tests;

public sealed class WorkspaceReportOptionsTests
{
    [Fact]
    public async Task TransactionChoicesUseVisibleDistinctSortedValuesAndExpenseFilter()
    {
        PortfolioSnapshot snapshot = Snapshot();
        Workspace workspace = await ReportWorkspaceFixture.Open(snapshot with
        {
            Transactions = [.. snapshot.Transactions,
                Transaction("spaced", 2026, 2, 3, " Living ", "Food", "Checking", -1m, TransactionKind.Expense)]
        });

        Assert.Equal(["Bills", "Living", "Pay", "Subscriptions"],
            workspace.TransactionChoices(TransactionChoiceField.Group));
        Assert.Equal(["Bills", "Living", "Subscriptions"],
            workspace.TransactionChoices(TransactionChoiceField.Group, expensesOnly: true));
        Assert.Equal(["Cloud", "Food", "Utility Bill"],
            workspace.TransactionChoices(TransactionChoiceField.Category, expensesOnly: true));
        Assert.Equal(["Checking", "Payroll"],
            workspace.TransactionChoices(TransactionChoiceField.Account));
        Assert.Throws<ArgumentOutOfRangeException>(() =>
            workspace.TransactionChoices((TransactionChoiceField)99));
    }

    [Fact]
    public async Task BudgetChoicesCombineVisibleTransactionsAndBudgetsForSelectedGroupAndMonth()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(Snapshot());

        Assert.Equal([new YearMonth(2026, 3), new YearMonth(2026, 2), new YearMonth(2026, 1)],
            workspace.BudgetMonths());
        Assert.Equal(["Bills", "Housing", "Living", "Subscriptions"], workspace.BudgetGroups());
        Assert.Equal(["Food", "Groceries"], workspace.BudgetCategories("Living", new YearMonth(2026, 2)));
        Assert.Empty(workspace.BudgetCategories("Living", new YearMonth(2026, 3)));
        Assert.Equal(["Cloud", "Food", "Utility Bill"], workspace.IncomeCategories(TransactionKind.Expense));
        Assert.Equal(["Salary"], workspace.IncomeCategories(TransactionKind.Income));
        Assert.Equal(["Bills", "Living", "Subscriptions"], workspace.IncomeExpenseGroups());
    }

    [Fact]
    public async Task AccountAndSubscriptionDefaultsOnlyOfferAvailableVisibleValues()
    {
        FinanceSettings settings = ReportWorkspaceFixture.Settings() with
        {
            Subscriptions = ReportWorkspaceFixture.Settings().Subscriptions with
            {
                KnownCategories = ["Cloud", "Missing", "Food"]
            }
        };
        ReportChoiceSettings choices = ReportWorkspaceFixture.Choices() with
        {
            DefaultSubscriptionDiscoveryExclusions = ["Food", "Utility Bill", "Cloud", "Missing"]
        };
        Workspace workspace = await ReportWorkspaceFixture.Open(Snapshot(), settings: settings, choices: choices);

        Assert.Equal(["Brokerage", "Checking"], workspace.FinancialIndependenceAccounts());
        Assert.Equal(["Cloud", "Food"], workspace.SubscriptionCategoryDefaults());
        Assert.Equal(["Cloud"], workspace.SubscriptionDiscoveryDefaults(["Food"]));
        Assert.Equal(["Food", "Cloud"], workspace.SubscriptionDiscoveryDefaults([]));
        Assert.Equal(1, workspace.DefaultDataHealthOptions().StaleAccountDays);
        Assert.Equal(1000m, workspace.DefaultFinancialIndependenceTargetAmount);
    }

    [Fact]
    public async Task EmptyWorkspaceHasNoDataDrivenChoices()
    {
        Workspace workspace = await ReportWorkspaceFixture.Open(new PortfolioSnapshot([], [], []));

        Assert.Empty(workspace.TransactionChoices(TransactionChoiceField.Category));
        Assert.Empty(workspace.IncomeCategories(TransactionKind.Income));
        Assert.Empty(workspace.IncomeExpenseGroups());
        Assert.Empty(workspace.BudgetMonths());
        Assert.Empty(workspace.BudgetGroups());
        Assert.Empty(workspace.BudgetCategories("Living", new YearMonth(2026, 2)));
        Assert.Empty(workspace.FinancialIndependenceAccounts());
        Assert.Empty(workspace.SubscriptionCategoryDefaults());
        Assert.Empty(workspace.SubscriptionDiscoveryDefaults([]));
    }

    private static PortfolioSnapshot Snapshot() => new(
    [
        Transaction("food", 2026, 2, 1, "Living", "Food", "Checking", -20m, TransactionKind.Expense),
        Transaction("cloud", 2026, 3, 1, "Subscriptions", "Cloud", "Checking", -12m, TransactionKind.Expense),
        Transaction("bill", 2026, 3, 2, "Bills", "Utility Bill", "Checking", -40m, TransactionKind.Expense),
        Transaction("pay", 2026, 3, 3, "Pay", "Salary", "Payroll", 100m, TransactionKind.Income),
        Transaction("hidden", 2026, 4, 1, "Hidden", "Secret", "Hidden", -50m, TransactionKind.Expense, true),
        Transaction("blank", 2026, 2, 2, " ", " ", " ", -1m, TransactionKind.Expense)
    ],
    [
        Balance("brokerage", "Brokerage", false),
        Balance("checking", "Checking", false),
        Balance("duplicate", "Checking", false),
        Balance("hidden", "Private", true),
        Balance("blank", " ", false)
    ],
    [
        new BudgetEntry(new YearMonth(2026, 1), "Rent", "Housing", TransactionKind.Expense, 500m, false),
        new BudgetEntry(new YearMonth(2026, 2), "Groceries", "Living", TransactionKind.Expense, 100m, false),
        new BudgetEntry(new YearMonth(2026, 4), "Secret", "Hidden", TransactionKind.Expense, 50m, true)
    ]);

    private static FinancialTransaction Transaction(
        string id, int year, int month, int day, string group, string category,
        string account, decimal amount, TransactionKind kind, bool hidden = false)
        => new(id, new DateOnly(year, month, day), category, group, account, id, amount, kind, hidden);

    private static BalanceObservation Balance(string id, string account, bool hidden)
        => new(id, account, "Assets", new DateOnly(2026, 3, 1), TimeOnly.MinValue,
            100m, AccountClass.Asset, hidden);
}
