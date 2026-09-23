namespace Portico.Finance;

/// <summary>Describes the editable checks used by the Data Health page.</summary>
public sealed record DataHealthCheckOptions(
    int StaleAccountDays,
    int DuplicateDays,
    decimal DuplicateMinimum,
    bool DuplicateRequireSameAccount,
    bool DuplicateRequireSameCategory,
    bool DuplicateRequireSameDescription,
    bool IncludeInactive)
{
    /// <summary>Checks that every option stays inside the supported source ranges.</summary>
    public void Validate()
    {
        if (StaleAccountDays is < 1 or > 365)
            throw new ArgumentOutOfRangeException(nameof(StaleAccountDays));
        if (DuplicateDays is < 0 or > 7)
            throw new ArgumentOutOfRangeException(nameof(DuplicateDays));
        if (DuplicateMinimum is < 0m or > 1_000m)
            throw new ArgumentOutOfRangeException(nameof(DuplicateMinimum));
    }

    /// <summary>Creates the default editable checks from finance settings.</summary>
    public static DataHealthCheckOptions From(FinanceSettings settings)
    {
        ArgumentNullException.ThrowIfNull(settings);
        return new DataHealthCheckOptions(
            settings.DataHealth.StaleAccountDays,
            settings.Thresholds.DuplicateDays,
            settings.Thresholds.DuplicateMinimum,
            settings.DataHealth.DuplicateRequireSameAccount,
            settings.DataHealth.DuplicateRequireSameCategory,
            settings.DataHealth.DuplicateRequireSameDescription,
            IncludeInactive: false);
    }
}

/// <summary>Names a missing source field without prescribing its display wording.</summary>
public enum DataHealthMissingField
{
    AccountId,
    Account,
    Description,
    Group
}

/// <summary>Classifies a transaction whose amount reverses its usual direction.</summary>
public enum DataHealthReversalKind
{
    ExpenseRefund,
    IncomeReversal
}

/// <summary>Identifies the missing fields on one record.</summary>
public sealed record DataHealthMissingFields(IReadOnlyList<DataHealthMissingField> Fields);

/// <summary>Counts the days since an account's latest balance.</summary>
public sealed record DataHealthStaleDays(int Days);

/// <summary>Identifies one refund or income reversal.</summary>
public sealed record DataHealthReversal(DataHealthReversalKind Kind);

/// <summary>Typed facts used to describe a Data Health finding.</summary>
public union DataHealthRecordDetail(DataHealthMissingFields, DataHealthStaleDays, DataHealthReversal);

/// <summary>Describes one data quality record.</summary>
public sealed record DataHealthRecord(
    DateOnly? Date,
    string Description,
    string Account,
    string Category,
    string Group,
    decimal? Amount,
    DataHealthRecordDetail? Details);

/// <summary>Describes one potential pair of duplicate transactions.</summary>
public sealed record DataHealthDuplicatePair(
    FinancialTransaction First,
    FinancialTransaction Second,
    int DaysApart);

/// <summary>Identifies a source-data check.</summary>
public enum DataHealthCheckKind
{
    Uncategorized,
    IncompleteTransactions,
    AccountMapping,
    StaleAccounts,
    Duplicates,
    Reversals
}

/// <summary>Classifies the result of a source-data check.</summary>
public enum DataHealthCheckStatus
{
    Passed,
    NeedsAttention,
    Review
}

/// <summary>Describes one health check and its underlying records.</summary>
public sealed record DataHealthCheckResult(
    DataHealthCheckKind Kind,
    DataHealthCheckStatus StatusKind,
    decimal FinancialScope,
    IReadOnlyList<DataHealthRecord> Records,
    IReadOnlyList<DataHealthDuplicatePair> DuplicatePairs)
{
    /// <summary>Gets the stable identifier used to select this check.</summary>
    public string Id => Kind switch
    {
        DataHealthCheckKind.Uncategorized => "uncategorized",
        DataHealthCheckKind.IncompleteTransactions => "incomplete",
        DataHealthCheckKind.AccountMapping => "account_mapping",
        DataHealthCheckKind.StaleAccounts => "stale_accounts",
        DataHealthCheckKind.Duplicates => "duplicates",
        DataHealthCheckKind.Reversals => "reversals",
        _ => throw new ArgumentOutOfRangeException(nameof(Kind))
    };

    /// <summary>Gets how many rows need attention or review for this check.</summary>
    public int FindingCount => Records.Count;
}

/// <summary>Contains data quality checks for one transaction snapshot.</summary>
public sealed record DataHealthAnalysisResult(
    DataHealthCheckOptions Options,
    IReadOnlyList<DataHealthCheckResult> Checks,
    DateOnly? LatestTransactionDate,
    DateOnly? LatestBalanceDate,
    int AccountCount)
{
    /// <summary>Gets the total count of checks that need attention.</summary>
    public int NeedsAttention => Checks
        .Where(check => check.StatusKind == DataHealthCheckStatus.NeedsAttention)
        .Sum(check => check.FindingCount);

    /// <summary>Gets the total count of checks that need review.</summary>
    public int ReviewItems => Checks
        .Where(check => check.StatusKind == DataHealthCheckStatus.Review)
        .Sum(check => check.FindingCount);
}

/// <summary>Builds the source data-quality queue without a UI dependency.</summary>
public static class DataHealthAnalysisCalculator
{
    /// <summary>Builds all six source checks for the given snapshot and as-of date.</summary>
    public static DataHealthAnalysisResult Build(
        IEnumerable<FinancialTransaction> transactions,
        IEnumerable<BalanceObservation> balances,
        DataHealthCheckOptions options,
        DateOnly asOfDate)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(balances);
        ArgumentNullException.ThrowIfNull(options);
        options.Validate();

        FinancialTransaction[] transactionValues = transactions
            .Where(transaction => options.IncludeInactive || !transaction.IsHidden)
            .OrderByDescending(transaction => transaction.Date)
            .ThenBy(transaction => transaction.Id, StringComparer.Ordinal)
            .ToArray();
        BalanceObservation[] balanceValues = balances
            .Where(balance => options.IncludeInactive || !balance.IsHidden)
            .ToArray();
        BalanceObservation[] latestBalances = LatestBalances(balanceValues);
        DataHealthDuplicatePair[] duplicates = FindDuplicatePairs(transactionValues, options);
        DataHealthCheckResult[] checks =
        [
            TransactionCheck(
                DataHealthCheckKind.Uncategorized,
                transactionValues.Where(IsUncategorized)),
            TransactionCheck(
                DataHealthCheckKind.IncompleteTransactions,
                transactionValues.Where(IsIncomplete),
                IncompleteDetails),
            BalanceCheck(
                DataHealthCheckKind.AccountMapping,
                latestBalances.Where(IsMissingMapping),
                MissingMappingDetails),
            BalanceCheck(
                DataHealthCheckKind.StaleAccounts,
                latestBalances.Where(balance => asOfDate.DayNumber - balance.Date.DayNumber > options.StaleAccountDays),
                balance => new DataHealthStaleDays(asOfDate.DayNumber - balance.Date.DayNumber)),
            DuplicateCheck(duplicates),
            TransactionCheck(
                DataHealthCheckKind.Reversals,
                transactionValues.Where(IsReversal),
                ReversalDetails,
                DataHealthCheckStatus.Review)
        ];
        return new DataHealthAnalysisResult(
            options,
            checks,
            transactionValues.Select(transaction => (DateOnly?)transaction.Date).Max(),
            balanceValues.Select(balance => (DateOnly?)balance.Date).Max(),
            latestBalances.Length);
    }

    private static DataHealthCheckResult TransactionCheck(
        DataHealthCheckKind kind,
        IEnumerable<FinancialTransaction> transactions,
        Func<FinancialTransaction, DataHealthRecordDetail>? details = null,
        DataHealthCheckStatus findingStatus = DataHealthCheckStatus.NeedsAttention)
    {
        DataHealthRecord[] records = transactions
            .Select(transaction => new DataHealthRecord(
                transaction.Date,
                transaction.Description,
                transaction.Account,
                transaction.Category,
                transaction.Group,
                transaction.Amount,
                details?.Invoke(transaction)))
            .ToArray();
        return Check(kind, findingStatus, records, []);
    }

    private static DataHealthCheckResult BalanceCheck(
        DataHealthCheckKind kind,
        IEnumerable<BalanceObservation> balances,
        Func<BalanceObservation, DataHealthRecordDetail> details)
    {
        DataHealthRecord[] records = balances
            .OrderByDescending(balance => balance.Date)
            .ThenBy(balance => balance.Account, StringComparer.Ordinal)
            .Select(balance => new DataHealthRecord(
                balance.Date,
                balance.Account,
                balance.Account,
                string.Empty,
                balance.Group,
                balance.Balance,
                details(balance)))
            .ToArray();
        return Check(kind, DataHealthCheckStatus.NeedsAttention, records, []);
    }

    private static DataHealthCheckResult DuplicateCheck(IReadOnlyList<DataHealthDuplicatePair> duplicates)
    {
        DataHealthRecord[] records = duplicates
            .Select(pair => new DataHealthRecord(
                pair.First.Date,
                $"{pair.First.Description} / {pair.Second.Description}",
                pair.First.Account,
                pair.First.Category,
                pair.First.Group,
                decimal.Abs(pair.First.Amount),
                null))
            .ToArray();
        return Check(
            DataHealthCheckKind.Duplicates,
            DataHealthCheckStatus.Review,
            records,
            duplicates);
    }

    private static DataHealthCheckResult Check(
        DataHealthCheckKind kind,
        DataHealthCheckStatus findingStatus,
        IReadOnlyList<DataHealthRecord> records,
        IReadOnlyList<DataHealthDuplicatePair> duplicatePairs)
        => new(
            kind,
            records.Count == 0 ? DataHealthCheckStatus.Passed : findingStatus,
            records.Sum(record => decimal.Abs(record.Amount ?? 0m)),
            records,
            duplicatePairs);

    private static BalanceObservation[] LatestBalances(IReadOnlyList<BalanceObservation> balances)
        => balances
            .GroupBy(balance => AccountKey(balance), StringComparer.Ordinal)
            .Select(group => group
                .OrderByDescending(balance => balance.Date)
                .ThenByDescending(balance => balance.Time)
                .First())
            .OrderBy(balance => balance.Account, StringComparer.Ordinal)
            .ToArray();

    private static DataHealthDuplicatePair[] FindDuplicatePairs(
        IReadOnlyList<FinancialTransaction> transactions,
        DataHealthCheckOptions options)
    {
        FinancialTransaction[] candidates = transactions
            .Where(transaction => decimal.Abs(transaction.Amount) >= options.DuplicateMinimum)
            .OrderBy(transaction => transaction.Amount)
            .ThenBy(transaction => transaction.Date)
            .ThenBy(transaction => transaction.Id, StringComparer.Ordinal)
            .ToArray();
        var pairs = new List<DataHealthDuplicatePair>();
        foreach (IGrouping<decimal, FinancialTransaction> amountGroup in candidates.GroupBy(transaction => transaction.Amount))
        {
            FinancialTransaction[] values = amountGroup.ToArray();
            for (int leftIndex = 0; leftIndex < values.Length; leftIndex++)
            {
                FinancialTransaction left = values[leftIndex];
                for (int rightIndex = leftIndex + 1; rightIndex < values.Length; rightIndex++)
                {
                    FinancialTransaction right = values[rightIndex];
                    int daysApart = right.Date.DayNumber - left.Date.DayNumber;
                    if (daysApart > options.DuplicateDays)
                        break;
                    if (options.DuplicateRequireSameAccount
                        && !string.Equals(left.Account, right.Account, StringComparison.Ordinal))
                    {
                        continue;
                    }
                    if (options.DuplicateRequireSameCategory
                        && !string.Equals(left.Category, right.Category, StringComparison.Ordinal))
                    {
                        continue;
                    }
                    if (options.DuplicateRequireSameDescription
                        && !string.Equals(left.Description, right.Description, StringComparison.OrdinalIgnoreCase))
                    {
                        continue;
                    }
                    pairs.Add(new DataHealthDuplicatePair(left, right, daysApart));
                }
            }
        }

        return pairs.ToArray();
    }

    private static bool IsUncategorized(FinancialTransaction transaction)
        => transaction.Kind == TransactionKind.Unknown
            || IsBlank(transaction.Category)
            || IsBlank(transaction.Group)
            || string.Equals(transaction.Group, "Uncategorized", StringComparison.Ordinal);

    private static bool IsIncomplete(FinancialTransaction transaction)
        => IsBlank(transaction.Account) || IsBlank(transaction.Description);

    private static bool IsMissingMapping(BalanceObservation balance)
        => IsBlank(balance.AccountId) || IsBlank(balance.Account) || IsBlank(balance.Group);

    private static bool IsReversal(FinancialTransaction transaction)
        => (transaction.Kind == TransactionKind.Expense && transaction.Amount > 0m)
            || (transaction.Kind == TransactionKind.Income && transaction.Amount < 0m);

    private static DataHealthRecordDetail IncompleteDetails(FinancialTransaction transaction)
        => new DataHealthMissingFields(new[]
        {
            IsBlank(transaction.Account) ? DataHealthMissingField.Account : (DataHealthMissingField?)null,
            IsBlank(transaction.Description) ? DataHealthMissingField.Description : null
        }.OfType<DataHealthMissingField>().ToArray());

    private static DataHealthRecordDetail MissingMappingDetails(BalanceObservation balance)
        => new DataHealthMissingFields(new[]
        {
            IsBlank(balance.AccountId) ? DataHealthMissingField.AccountId : (DataHealthMissingField?)null,
            IsBlank(balance.Account) ? DataHealthMissingField.Account : null,
            IsBlank(balance.Group) ? DataHealthMissingField.Group : null
        }.OfType<DataHealthMissingField>().ToArray());

    private static DataHealthRecordDetail ReversalDetails(FinancialTransaction transaction)
        => new DataHealthReversal(transaction.Kind == TransactionKind.Expense
            ? DataHealthReversalKind.ExpenseRefund : DataHealthReversalKind.IncomeReversal);

    private static string AccountKey(BalanceObservation balance)
        => !IsBlank(balance.AccountId)
            ? balance.AccountId.Trim()
            : !IsBlank(balance.Account)
                ? $"account:{balance.Account.Trim()}"
                : $"row:{balance.Date.DayNumber}:{balance.Time.Ticks}";

    private static bool IsBlank(string? value)
        => string.IsNullOrWhiteSpace(value);
}
