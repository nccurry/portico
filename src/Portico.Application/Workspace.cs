using Portico.Finance;

using System.Text.Json.Serialization;

namespace Portico.Application;

/// <summary>A fixed portfolio and financial policy for semantic report requests.</summary>
public sealed partial class Workspace
{
    private readonly PortfolioSnapshot _snapshot;
    private readonly FinanceSettings _settings;

    internal Workspace(PortfolioSnapshot snapshot, FinanceSettings settings, DateOnly? asOfDate)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        _snapshot = new PortfolioSnapshot(
            snapshot.Transactions.ToArray(),
            snapshot.Balances.ToArray(),
            snapshot.Budgets.ToArray());
        _settings = CopySettings(settings ?? throw new ArgumentNullException(nameof(settings)));
        ReportChoices = new ReportChoices(_settings);
        AsOfDate = asOfDate ?? _snapshot.LatestDate ?? new DateOnly(2000, 1, 1);
    }

    public DateOnly AsOfDate { get; }

    /// <summary>Read-only configured choices for report requests and presentation controls.</summary>
    [JsonIgnore]
    public ReportChoices ReportChoices { get; }

    private static FinanceSettings CopySettings(FinanceSettings settings)
    {
        return settings with
        {
            Lookback = settings.Lookback with { Months = settings.Lookback.Months.ToArray() },
            IncomeSavings = settings.IncomeSavings with
            {
                ExcludeCategories = settings.IncomeSavings.ExcludeCategories.ToArray(),
                ExcludeGroups = settings.IncomeSavings.ExcludeGroups.ToArray()
            },
            TransactionSets = settings.TransactionSets.Select(set => set with
            {
                Groups = set.Groups.ToArray(),
                Categories = set.Categories.ToArray(),
                Accounts = set.Accounts.ToArray(),
                Merchants = set.Merchants.ToArray(),
                TransactionsLike = set.TransactionsLike.ToArray(),
                Includes = set.Includes.ToArray(),
                Excludes = set.Excludes.ToArray()
            }).ToArray(),
            FilterSets = settings.FilterSets.Select(set => set with
            {
                Options = set.Options.ToArray()
            }).ToArray(),
            Subscriptions = settings.Subscriptions with
            {
                KnownCategories = settings.Subscriptions.KnownCategories.ToArray(),
                DefaultExcludeCategories = settings.Subscriptions.DefaultExcludeCategories.ToArray(),
                DetectionExcludedCategories = settings.Subscriptions.DetectionExcludedCategories.ToArray()
            },
            FinancialSafety = settings.FinancialSafety with
            {
                EmergencyFundIncludedGroups = settings.FinancialSafety.EmergencyFundIncludedGroups.ToArray(),
                EmergencyFundIncludedAccountPatterns = settings.FinancialSafety.EmergencyFundIncludedAccountPatterns.ToArray(),
                EmergencyFundExcludeCategories = settings.FinancialSafety.EmergencyFundExcludeCategories.ToArray(),
                EmergencyFundExcludeGroups = settings.FinancialSafety.EmergencyFundExcludeGroups.ToArray(),
                DebtIncludedGroups = settings.FinancialSafety.DebtIncludedGroups.ToArray(),
                DebtIncludedAccountPatterns = settings.FinancialSafety.DebtIncludedAccountPatterns.ToArray()
            },
            FinancialIndependence = settings.FinancialIndependence with
            {
                IncludedAccountPatterns = settings.FinancialIndependence.IncludedAccountPatterns.ToArray(),
                IncludedGroups = settings.FinancialIndependence.IncludedGroups.ToArray()
            },
            MerchantAliases = settings.MerchantAliases.ToDictionary(
                pair => pair.Key,
                pair => (IReadOnlyList<string>)pair.Value.ToArray(),
                StringComparer.Ordinal)
        };
    }
}
