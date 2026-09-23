using System.Collections.ObjectModel;

namespace Portico.Application;

/// <summary>Configured choices available to report requests and desktop controls.</summary>
public sealed class ReportChoices
{
    internal ReportChoices(ReportChoiceSettings choices)
    {
        LookbackMonths = Array.AsReadOnly(choices.Lookback.Months.ToArray());
        DefaultLookbackMonths = choices.Lookback.DefaultMonths;
        DefaultIncomeIsRegular = choices.DefaultIncomeIsRegular;
        FilterSets = new ReadOnlyDictionary<string, ReportFilterChoices>(choices.FilterSets.ToDictionary(
            set => set.Key,
            set => new ReportFilterChoices(Array.AsReadOnly(set.Options.ToArray()), set.Default),
            StringComparer.Ordinal));
        TransactionSetLabels = new ReadOnlyDictionary<string, string>(choices.TransactionSetLabels.ToDictionary(
            pair => pair.Key,
            pair => pair.Value,
            StringComparer.Ordinal));
    }

    public IReadOnlyList<int> LookbackMonths { get; }

    public int DefaultLookbackMonths { get; }

    public bool DefaultIncomeIsRegular { get; }

    public IReadOnlyDictionary<string, ReportFilterChoices> FilterSets { get; }

    public IReadOnlyDictionary<string, string> TransactionSetLabels { get; }
}

/// <summary>Named transaction-set options and their configured default.</summary>
public sealed record ReportFilterChoices(IReadOnlyList<string> Options, string Default);
