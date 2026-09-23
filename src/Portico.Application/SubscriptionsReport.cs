using Portico.Finance;

namespace Portico.Application;

/// <summary>Selects subscription categories, discovery rules, and merchant detail.</summary>
public sealed record SubscriptionsReportRequest(
    IReadOnlyList<string>? Categories = null,
    IReadOnlyList<string>? DiscoveryExclusions = null,
    int? MinimumConfidence = null,
    string? SelectedMerchant = null);

/// <summary>Subscription analysis and the selected merchant's charge history.</summary>
public sealed record SubscriptionsReport(
    SubscriptionAnalysisResult Analysis,
    int? DataAgeDays,
    bool DataIsStale,
    string? SelectedMerchant,
    bool SelectedMerchantIsCandidate,
    IReadOnlyList<SubscriptionChargeEntry> SelectedCharges);

public sealed partial class Workspace
{
    /// <summary>Calculates subscription inventory and selected charge detail.</summary>
    public SubscriptionsReport Subscriptions(SubscriptionsReportRequest? request = null)
    {
        request ??= new SubscriptionsReportRequest();
        FinancialTransaction[] visible = _snapshot.Transactions.Where(transaction => !transaction.IsHidden).ToArray();
        int confidence = request.MinimumConfidence ?? _settings.Subscriptions.MinimumConfidence;
        SubscriptionAnalysisResult analysis = SubscriptionAnalysisCalculator.Build(
            visible,
            _settings.Subscriptions,
            _settings.MerchantAliases,
            request.Categories ?? _settings.Subscriptions.KnownCategories,
            request.DiscoveryExclusions ?? _reportChoiceSettings.DefaultSubscriptionDiscoveryExclusions,
            confidence);
        string? selected = !string.IsNullOrWhiteSpace(request.SelectedMerchant)
            && analysis.Active.Concat(analysis.Candidates).Concat(analysis.Inactive)
                .Any(entry => string.Equals(entry.Merchant, request.SelectedMerchant, StringComparison.Ordinal))
                ? request.SelectedMerchant
                : analysis.Active.FirstOrDefault()?.Merchant
                    ?? analysis.Candidates.FirstOrDefault()?.Merchant
                    ?? analysis.Inactive.FirstOrDefault()?.Merchant;
        bool candidate = selected is not null
            && analysis.Candidates.Any(entry => string.Equals(entry.Merchant, selected, StringComparison.Ordinal));
        IReadOnlyList<SubscriptionChargeEntry> charges = selected is null
            ? []
            : SubscriptionAnalysisCalculator.ChargesFor(analysis, selected, candidate);
        int? ageDays = analysis.LatestDataDate is DateOnly date
            ? Math.Max(0, AsOfDate.DayNumber - date.DayNumber)
            : null;
        return new SubscriptionsReport(
            analysis,
            ageDays,
            ageDays is int age && age > _settings.Subscriptions.StaleAfterDays,
            selected,
            candidate,
            charges);
    }
}
