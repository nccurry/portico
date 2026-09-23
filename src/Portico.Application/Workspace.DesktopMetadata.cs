namespace Portico.Application;

public sealed partial class Workspace
{
    /// <summary>Whether any loaded transaction is visible in the desktop.</summary>
    public bool HasVisibleTransactions => _snapshot.Transactions.Any(transaction => !transaction.IsHidden);
}
