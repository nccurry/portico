using Portico.Application;
using Portico.Finance;

namespace Portico.Desktop;

/// <summary>Current typed report requests selected by desktop controls.</summary>
public sealed record DashboardFilters(
    int LookbackMonths,
    string SpendingSet,
    string YearOverYearSet,
    bool RegularIncome,
    HomePeriod HomeTimeFrame = HomePeriod.OneYear,
    SpendingComparison SpendingComparison = SpendingComparison.PreviousPeriod,
    SpendingBreakdown SpendingBreakdown = SpendingBreakdown.Category,
    SpendingAdjustments? SpendingAdjustments = null,
    int IncomeLookbackMonths = 0,
    int MerchantLookbackMonths = 0,
    string? MerchantSet = null,
    SpendingComparison MerchantComparison = SpendingComparison.PreviousPeriod,
    SpendingAdjustments? MerchantAdjustments = null,
    IReadOnlyList<string>? SubscriptionCategories = null,
    IReadOnlyList<string>? SubscriptionDiscoveryExclusions = null,
    int SubscriptionMinimumConfidence = 0,
    TransactionExplorerFilters? TransactionExplorer = null,
    BudgetRequest? Budget = null,
    FinancialIndependenceSourceFilters? FinancialIndependenceSource = null,
    FinancialIndependenceScenario? FinancialIndependenceScenario = null,
    DataHealthCheckOptions? DataHealth = null)
{
    public int EffectiveIncomeLookbackMonths => IncomeLookbackMonths > 0 ? IncomeLookbackMonths : LookbackMonths;

    public int EffectiveMerchantLookbackMonths => MerchantLookbackMonths > 0 ? MerchantLookbackMonths : LookbackMonths;
}
