using Portico.Finance;

namespace Portico.Application;

public sealed partial class Workspace
{
    /// <summary>Gets the configured default Income calculation mode.</summary>
    public bool DefaultIncomeIsRegular
        => _reportChoiceSettings.DefaultIncomeIsRegular;

    /// <summary>Gets independent adjustment values for an Income calculation mode.</summary>
    public IncomeSavingsAdjustments IncomeAdjustments(bool regular)
        => CopyAdjustments(IncomeSavingsAdjustments.Default(_settings, regular));

    /// <summary>Gets independent default adjustments for Spending reports.</summary>
    public SpendingAdjustments DefaultSpendingAdjustments()
        => SpendingAdjustments.Default(_settings.Thresholds.Expense);
}
