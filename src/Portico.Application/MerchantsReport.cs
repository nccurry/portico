using Portico.Finance;

namespace Portico.Application;

/// <summary>Selects the merchant comparison and one merchant's detail.</summary>
public sealed record MerchantsReportRequest(
    string? TransactionSetKey = null,
    int? LookbackMonths = null,
    SpendingComparison Comparison = SpendingComparison.PreviousPeriod,
    SpendingAdjustments? Adjustments = null,
    string? SelectedMerchant = null,
    YearMonth? DetailMonth = null);

/// <summary>Merchant ranking, comparison, and selected merchant detail.</summary>
public sealed record MerchantsReport(
    DateOnly? LatestExpenseDate,
    MerchantAnalysisResult Analysis,
    string? SelectedMerchant,
    YearMonth? DetailMonth,
    IReadOnlyList<MerchantHistoryEntry> SelectedHistory,
    IReadOnlyList<MerchantDetailBreakdownEntry> SelectedCategories,
    IReadOnlyList<MerchantDetailBreakdownEntry> SelectedAccounts,
    IReadOnlyList<MerchantDescriptionEntry> SelectedDescriptions,
    IReadOnlyList<SpendingLedgerEntry> SelectedTransactions);

public sealed partial class Workspace
{
    /// <summary>Calculates merchant ranking and selected merchant detail.</summary>
    public MerchantsReport Merchants(MerchantsReportRequest? request = null)
    {
        request ??= new MerchantsReportRequest();
        if (!Enum.IsDefined(request.Comparison))
            throw new ArgumentOutOfRangeException(nameof(request), "Unsupported merchant comparison.");
        FinancialTransaction[] visible = _snapshot.Transactions.Where(transaction => !transaction.IsHidden).ToArray();
        MerchantAnalysisResult analysis = MerchantAnalysisCalculator.Build(
            visible,
            _settings,
            request.TransactionSetKey ?? _settings.FilterSet("spending").Default,
            request.LookbackMonths ?? _settings.Lookback.DefaultMonths,
            request.Comparison,
            request.Adjustments ?? SpendingAdjustments.Default(_settings.Thresholds.Expense));
        string? selected = analysis.Overview.Any(entry => string.Equals(
                entry.Merchant, request.SelectedMerchant, StringComparison.Ordinal))
            ? request.SelectedMerchant
            : analysis.Overview.FirstOrDefault()?.Merchant;
        IReadOnlyList<MerchantHistoryEntry> history = selected is null
            ? []
            : MerchantAnalysisCalculator.History(analysis, selected, _settings.MerchantAliases);
        IReadOnlyList<MerchantDetailBreakdownEntry> categories = selected is null
            ? []
            : MerchantAnalysisCalculator.Breakdown(analysis.CurrentLedger, selected, "Category", _settings.MerchantAliases);
        IReadOnlyList<MerchantDetailBreakdownEntry> accounts = selected is null
            ? []
            : MerchantAnalysisCalculator.Breakdown(analysis.CurrentLedger, selected, "Account", _settings.MerchantAliases);
        IReadOnlyList<MerchantDescriptionEntry> descriptions = selected is null
            ? []
            : MerchantAnalysisCalculator.Descriptions(analysis.CurrentLedger, selected, _settings.MerchantAliases);
        IReadOnlyList<SpendingLedgerEntry> transactions = selected is null
            ? []
            : MerchantAnalysisCalculator.Transactions(
                analysis.CurrentLedger, selected, request.DetailMonth, _settings.MerchantAliases);
        DateOnly? latest = visible.Where(transaction => transaction.Kind == TransactionKind.Expense)
            .Select(transaction => (DateOnly?)transaction.Date).Max();
        return new MerchantsReport(
            latest, analysis, selected, request.DetailMonth, history, categories, accounts, descriptions, transactions);
    }
}
