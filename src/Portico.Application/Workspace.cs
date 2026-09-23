using Portico.Finance;

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
        _settings = settings ?? throw new ArgumentNullException(nameof(settings));
        AsOfDate = asOfDate ?? _snapshot.LatestDate ?? new DateOnly(2000, 1, 1);
    }

    public DateOnly AsOfDate { get; }
}
