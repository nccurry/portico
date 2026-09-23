using Portico.Finance;

namespace Portico.Application;

public sealed partial class Workspace
{
    /// <summary>Calculates the filtered transaction inventory and breakdown.</summary>
    public TransactionExplorerAnalysisResult Transactions(TransactionExplorerFilters? filters = null)
        => TransactionExplorerAnalysisCalculator.Build(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden),
            _settings.MerchantAliases,
            filters ?? TransactionExplorerFilters.Default);
}
