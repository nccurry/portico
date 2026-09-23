using Portico.Finance;

namespace Portico.Application;

/// <summary>Selects the Spending by category view and its detail.</summary>
public sealed record SpendingReportRequest(
    string? TransactionSet = null,
    int? LookbackMonths = null,
    SpendingComparison Comparison = SpendingComparison.PreviousPeriod,
    SpendingBreakdown Breakdown = SpendingBreakdown.Category,
    SpendingAdjustments? Adjustments = null,
    string? Entity = null,
    YearMonth? DetailMonth = null);

/// <summary>One selected entity's values in matched months.</summary>
public sealed record SpendingHistoryMonth(
    YearMonth CurrentMonth,
    YearMonth ComparisonMonth,
    decimal Current,
    decimal Comparison);

/// <summary>Totals for the selected Spending entity and month range.</summary>
public sealed record SpendingDetailSummary(
    decimal Spending,
    decimal AverageMonthlySpending,
    decimal SharePercent,
    decimal ComparisonSpending,
    decimal Change,
    decimal? ChangePercent);

/// <summary>One category within a selected Spending group.</summary>
public sealed record SpendingCategoryDetail(
    string Category,
    decimal Spending,
    decimal SharePercent,
    decimal AverageMonthlySpending,
    decimal ComparisonSpending,
    decimal Change,
    decimal? ChangePercent,
    int Transactions);

/// <summary>Financial values and the selected detail for Spending by category.</summary>
public sealed record SpendingReport(
    SpendingAnalysisResult Analysis,
    SpendingBreakdown Breakdown,
    DateOnly? LatestExpenseDate,
    SpendingOverviewEntry? SelectedEntity,
    YearMonth? DetailMonth,
    YearMonth? ComparisonMonth,
    IReadOnlyList<SpendingLedgerEntry> CurrentDetail,
    IReadOnlyList<SpendingLedgerEntry> ComparisonDetail,
    IReadOnlyList<SpendingHistoryMonth> History,
    SpendingDetailSummary DetailSummary,
    IReadOnlyList<SpendingCategoryDetail> Categories,
    IReadOnlyList<SpendingMerchantTotal> Merchants)
{
    public IReadOnlyList<SpendingOverviewEntry> Ranked => Analysis.Overview
        .Where(entry => entry.Spending > 0m).Take(10).ToArray();

    public IReadOnlyList<SpendingOverviewEntry> Trended => Ranked.Take(5).ToArray();

    public int ExcludedCount => Analysis.CurrentLedger.Count(entry => !entry.Included);

    public decimal ExcludedSpending => Analysis.CurrentLedger
        .Where(entry => !entry.Included)
        .Sum(entry => entry.NetSpending);
}

/// <summary>Spending by one merchant in the selected detail.</summary>
public sealed record SpendingMerchantTotal(
    string Merchant,
    decimal Spending,
    decimal SharePercent,
    int Transactions,
    decimal AverageTransaction,
    DateOnly LastTransaction);

public sealed partial class Workspace
{
    /// <summary>Calculates Spending by category from visible expense transactions.</summary>
    public SpendingReport Spending(SpendingReportRequest? request = null)
    {
        request ??= new SpendingReportRequest();
        int lookback = request.LookbackMonths ?? _reportChoiceSettings.Lookback.DefaultMonths;
        if (lookback <= 0)
            throw new ArgumentOutOfRangeException(nameof(request), "Spending lookback must be positive.");
        if (!Enum.IsDefined(request.Comparison) || !Enum.IsDefined(request.Breakdown))
            throw new ArgumentOutOfRangeException(nameof(request), "Unsupported Spending comparison or breakdown.");

        string setKey = request.TransactionSet ?? _reportChoiceSettings.FilterSet("spending").Default;
        _settings.TransactionSet(setKey);
        SpendingAnalysisResult analysis = SpendingAnalysisCalculator.Build(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden),
            _settings,
            setKey,
            lookback,
            request.Comparison,
            request.Breakdown,
            request.Adjustments ?? SpendingAdjustments.Default(_settings.Thresholds.Expense));
        DateOnly? latestExpenseDate = _snapshot.Transactions
            .Where(transaction => !transaction.IsHidden && transaction.Kind == TransactionKind.Expense)
            .Select(transaction => (DateOnly?)transaction.Date)
            .Max();
        SpendingOverviewEntry? selected = analysis.Overview
            .FirstOrDefault(entry => string.Equals(entry.Entity, request.Entity, StringComparison.Ordinal))
            ?? analysis.Overview.FirstOrDefault();
        int monthIndex = -1;
        if (request.DetailMonth is YearMonth month)
        {
            for (int index = 0; index < analysis.Period.CurrentMonths.Count; index++)
            {
                if (analysis.Period.CurrentMonths[index] == month)
                {
                    monthIndex = index;
                    break;
                }
            }
        }
        YearMonth? detailMonth = monthIndex < 0 ? null : analysis.Period.CurrentMonths[monthIndex];
        YearMonth? comparisonMonth = monthIndex < 0 ? null : analysis.Period.ComparisonMonths[monthIndex];
        SpendingLedgerEntry[] current = Detail(analysis.CurrentLedger, request.Breakdown, selected?.Entity, detailMonth);
        SpendingLedgerEntry[] comparison = Detail(
            analysis.ComparisonLedger, request.Breakdown, selected?.Entity, comparisonMonth);
        SpendingHistoryMonth[] history = selected is null
            ? []
            : SpendingAnalysisCalculator.EntityHistory(analysis, request.Breakdown, selected.Entity)
                .Select(row => new SpendingHistoryMonth(row.CurrentMonth, row.ComparisonMonth, row.Current, row.Comparison))
                .ToArray();
        SpendingMerchantTotal[] merchants = SpendingAnalysisCalculator.Merchants(current, _settings.MerchantAliases)
            .Select(row => new SpendingMerchantTotal(
                row.Merchant, row.Spending, row.SharePercent, row.Transactions,
                row.AverageTransaction, row.LastTransaction))
            .ToArray();
        int monthCount = detailMonth is null ? analysis.Period.CurrentMonths.Count : 1;
        decimal spending = current.Sum(entry => entry.NetSpending);
        decimal compared = comparison.Sum(entry => entry.NetSpending);
        decimal change = spending - compared;
        var summary = new SpendingDetailSummary(
            spending,
            monthCount == 0 ? 0m : spending / monthCount,
            analysis.Summary.TotalSpending == 0m ? 0m : spending / analysis.Summary.TotalSpending * 100m,
            compared,
            change,
            compared == 0m ? null : change / decimal.Abs(compared) * 100m);
        SpendingCategoryDetail[] categories = request.Breakdown == SpendingBreakdown.Group
            ? CategoryDetail(current, comparison, monthCount)
            : [];
        return new SpendingReport(
            analysis, request.Breakdown, latestExpenseDate, selected, detailMonth, comparisonMonth,
            current, comparison, history, summary, categories, merchants);
    }

    private static SpendingCategoryDetail[] CategoryDetail(
        IReadOnlyList<SpendingLedgerEntry> current,
        IReadOnlyList<SpendingLedgerEntry> comparison,
        int monthCount)
    {
        static string Category(SpendingLedgerEntry entry)
            => string.IsNullOrWhiteSpace(entry.Transaction.Category) ? "Unknown" : entry.Transaction.Category;

        var currentTotals = current.GroupBy(Category, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => (Spending: group.Sum(entry => entry.NetSpending), Count: group.Count()),
                StringComparer.Ordinal);
        var comparisonTotals = comparison.GroupBy(Category, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Sum(entry => entry.NetSpending), StringComparer.Ordinal);
        decimal total = currentTotals.Values.Sum(value => value.Spending);
        return currentTotals.Keys.Union(comparisonTotals.Keys, StringComparer.Ordinal)
            .Select(category =>
            {
                (decimal spending, int count) = currentTotals.GetValueOrDefault(category);
                decimal compared = comparisonTotals.GetValueOrDefault(category);
                decimal change = spending - compared;
                return new SpendingCategoryDetail(
                    category,
                    spending,
                    total == 0m ? 0m : spending / total * 100m,
                    monthCount == 0 ? 0m : spending / monthCount,
                    compared,
                    change,
                    compared == 0m ? null : change / decimal.Abs(compared) * 100m,
                    count);
            })
            .OrderByDescending(category => category.Spending)
            .ThenBy(category => category.Category, StringComparer.Ordinal)
            .ToArray();
    }

    private static SpendingLedgerEntry[] Detail(
        IReadOnlyList<SpendingLedgerEntry> ledger,
        SpendingBreakdown breakdown,
        string? entity,
        YearMonth? month)
    {
        if (string.IsNullOrWhiteSpace(entity))
            return [];
        return ledger
            .Where(entry => entry.Included
                && (month is null || entry.Transaction.Month == month.Value)
                && string.Equals(
                    breakdown == SpendingBreakdown.Group
                        ? string.IsNullOrWhiteSpace(entry.Transaction.Group) ? "Unknown" : entry.Transaction.Group
                        : string.IsNullOrWhiteSpace(entry.Transaction.Category) ? "Unknown" : entry.Transaction.Category,
                    entity,
                    StringComparison.Ordinal))
            .OrderByDescending(entry => decimal.Abs(entry.NetSpending))
            .ThenByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .ToArray();
    }
}
