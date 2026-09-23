using System.Collections.ObjectModel;
using Portico.Finance;

namespace Portico.Application;

/// <summary>Configured choices available to report requests and desktop controls.</summary>
public sealed class ReportChoices
{
    internal ReportChoices(FinanceSettings settings)
    {
        LookbackMonths = Array.AsReadOnly(settings.Lookback.Months.ToArray());
        DefaultLookbackMonths = settings.Lookback.DefaultMonths;
        FilterSets = new ReadOnlyDictionary<string, ReportFilterChoices>(settings.FilterSets.ToDictionary(
            set => set.Key,
            set => new ReportFilterChoices(Array.AsReadOnly(set.Options.ToArray()), set.Default),
            StringComparer.Ordinal));
        TransactionSetLabels = new ReadOnlyDictionary<string, string>(settings.TransactionSets.ToDictionary(
            set => set.Key,
            set => set.Label,
            StringComparer.Ordinal));
    }

    public IReadOnlyList<int> LookbackMonths { get; }

    public int DefaultLookbackMonths { get; }

    public IReadOnlyDictionary<string, ReportFilterChoices> FilterSets { get; }

    public IReadOnlyDictionary<string, string> TransactionSetLabels { get; }
}

/// <summary>Named transaction-set options and their configured default.</summary>
public sealed record ReportFilterChoices(IReadOnlyList<string> Options, string Default);
