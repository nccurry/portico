using Portico.Finance;

namespace Portico.Finance.Tests;

public sealed class DataHealthAnalysisTests
{
    [Fact]
    public void Build_ReturnsEverySourceCheckWithItsOwnTypedFindingRows()
    {
        FinancialTransaction[] transactions =
        [
            Transaction("uncategorized", new DateOnly(2026, 6, 1), "", "Uncategorized", "Checking", "Unknown", -20m, TransactionKind.Unknown),
            Transaction("incomplete", new DateOnly(2026, 6, 2), "Food", "Living", "", "", -30m, TransactionKind.Expense),
            Transaction("first", new DateOnly(2026, 6, 3), "Food", "Living", "Checking", "Coffee", -40m, TransactionKind.Expense),
            Transaction("second", new DateOnly(2026, 6, 4), "Food", "Living", "Checking", "Coffee", -40m, TransactionKind.Expense),
            Transaction("refund", new DateOnly(2026, 6, 5), "Food", "Living", "Checking", "Store refund", 15m, TransactionKind.Expense)
        ];
        BalanceObservation[] balances =
        [
            new("", "Old account", "", new DateOnly(2026, 5, 1), new TimeOnly(9, 0), 100m, AccountClass.Asset, false),
            new("current", "Current account", "Savings", new DateOnly(2026, 6, 5), new TimeOnly(9, 0), 200m, AccountClass.Asset, false)
        ];

        DataHealthAnalysisResult result = DataHealthAnalysisCalculator.Build(
            transactions,
            balances,
            Options(),
            new DateOnly(2026, 6, 10));

        Assert.Equal(
        [
            "uncategorized",
            "incomplete",
            "account_mapping",
            "stale_accounts",
            "duplicates",
            "reversals"
        ], result.Checks.Select(check => check.Id));
        Assert.Equal(
        [
            DataHealthCheckKind.Uncategorized,
            DataHealthCheckKind.IncompleteTransactions,
            DataHealthCheckKind.AccountMapping,
            DataHealthCheckKind.StaleAccounts,
            DataHealthCheckKind.Duplicates,
            DataHealthCheckKind.Reversals
        ], result.Checks.Select(check => check.Kind));
        Assert.Equal(1, Check(result, "uncategorized").FindingCount);
        Assert.Equal(1, Check(result, "incomplete").FindingCount);
        Assert.Equal(1, Check(result, "account_mapping").FindingCount);
        Assert.Equal(1, Check(result, "stale_accounts").FindingCount);
        Assert.Equal(1, Check(result, "duplicates").FindingCount);
        Assert.Equal(1, Check(result, "reversals").FindingCount);
        Assert.Equal(DataHealthCheckKind.Duplicates, Check(result, "duplicates").Kind);
        Assert.Equal(DataHealthCheckStatus.Review, Check(result, "duplicates").StatusKind);
        Assert.Equal([DataHealthMissingField.Account, DataHealthMissingField.Description],
            Assert.Single(Check(result, "incomplete").Records).Details switch
            {
                DataHealthMissingFields missing => missing.Fields,
                _ => []
            });
        Assert.Equal([DataHealthMissingField.AccountId, DataHealthMissingField.Group],
            Assert.Single(Check(result, "account_mapping").Records).Details switch
            {
                DataHealthMissingFields missing => missing.Fields,
                _ => []
            });
        Assert.Equal(40, Assert.Single(Check(result, "stale_accounts").Records).Details switch
        {
            DataHealthStaleDays stale => stale.Days,
            _ => -1
        });
        Assert.Equal(DataHealthReversalKind.ExpenseRefund,
            Assert.Single(Check(result, "reversals").Records).Details switch
            {
                DataHealthReversal reversal => reversal.Kind,
                _ => (DataHealthReversalKind)(-1)
            });
        Assert.Null(Assert.Single(Check(result, "duplicates").Records).Details);
        Assert.Equal(4, result.NeedsAttention);
        Assert.Equal(2, result.ReviewItems);
    }

    [Fact]
    public void Build_ClassifiesAnIncomeReversalWithoutDisplayWording()
    {
        DataHealthAnalysisResult result = DataHealthAnalysisCalculator.Build(
            [Transaction("reversal", new DateOnly(2026, 6, 1), "Pay", "Income", "Checking", "Correction", -10m, TransactionKind.Income)],
            [], Options(), new DateOnly(2026, 6, 10));

        DataHealthRecord record = Assert.Single(Check(result, "reversals").Records);
        Assert.Equal(DataHealthReversalKind.IncomeReversal, record.Details switch
        {
            DataHealthReversal reversal => reversal.Kind,
            _ => (DataHealthReversalKind)(-1)
        });
    }

    [Fact]
    public void Build_AppliesDuplicateRulesAndCanIncludeHiddenRecords()
    {
        FinancialTransaction[] transactions =
        [
            Transaction("one", new DateOnly(2026, 6, 1), "Food", "Living", "Checking", "Coffee", -40m, TransactionKind.Expense),
            Transaction("two", new DateOnly(2026, 6, 2), "Travel", "Travel", "Checking", "Different", -40m, TransactionKind.Expense),
            Transaction("hidden", new DateOnly(2026, 6, 3), "", "Uncategorized", "Checking", "Hidden", -10m, TransactionKind.Unknown, true)
        ];

        DataHealthAnalysisResult strict = DataHealthAnalysisCalculator.Build(
            transactions,
            [],
            Options() with { DuplicateRequireSameDescription = true },
            new DateOnly(2026, 6, 10));
        DataHealthAnalysisResult loose = DataHealthAnalysisCalculator.Build(
            transactions,
            [],
            Options() with { DuplicateRequireSameDescription = false, IncludeInactive = true },
            new DateOnly(2026, 6, 10));

        Assert.Equal(DataHealthCheckStatus.Passed, Check(strict, "duplicates").StatusKind);
        Assert.Equal(DataHealthCheckStatus.Passed, Check(strict, "uncategorized").StatusKind);
        Assert.Equal(1, Check(loose, "duplicates").FindingCount);
        Assert.Equal(1, Check(loose, "uncategorized").FindingCount);
    }

    [Fact]
    public void Build_EmptySourcesKeepsEveryCheckAndReportsNoFindings()
    {
        DataHealthAnalysisResult result = DataHealthAnalysisCalculator.Build(
            [],
            [],
            Options(),
            new DateOnly(2026, 6, 10));

        Assert.Equal(6, result.Checks.Count);
        Assert.All(result.Checks, check =>
        {
            Assert.Equal(DataHealthCheckStatus.Passed, check.StatusKind);
            Assert.Equal(0, check.FindingCount);
            Assert.Equal(0m, check.FinancialScope);
        });
        Assert.Null(result.LatestTransactionDate);
        Assert.Null(result.LatestBalanceDate);
        Assert.Equal(0, result.AccountCount);
    }

    [Theory]
    [InlineData(0, 1, 0)]
    [InlineData(1, 8, 0)]
    [InlineData(1, 1, 1001)]
    public void Options_RejectsValuesOutsideTheSourceRanges(int staleDays, int duplicateDays, int duplicateMinimum)
    {
        DataHealthCheckOptions options = Options() with
        {
            StaleAccountDays = staleDays,
            DuplicateDays = duplicateDays,
            DuplicateMinimum = duplicateMinimum
        };

        Assert.Throws<ArgumentOutOfRangeException>(() => options.Validate());
    }

    private static DataHealthCheckResult Check(DataHealthAnalysisResult result, string id)
        => result.Checks.Single(check => string.Equals(check.Id, id, StringComparison.Ordinal));

    private static FinancialTransaction Transaction(
        string id,
        DateOnly date,
        string category,
        string group,
        string account,
        string description,
        decimal amount,
        TransactionKind kind,
        bool hidden = false)
        => new(id, date, category, group, account, description, amount, kind, hidden);

    private static DataHealthCheckOptions Options()
        => new(7, 1, 10m, true, false, true, false);
}
