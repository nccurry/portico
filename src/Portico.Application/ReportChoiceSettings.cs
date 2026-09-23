namespace Portico.Application;

/// <summary>Available month counts and the default for report requests.</summary>
public sealed record LookbackSettings(IReadOnlyList<int> Months, int DefaultMonths);

/// <summary>Named transaction-set options offered by a report.</summary>
public sealed record FilterSetDefinition(string Key, IReadOnlyList<string> Options, string Default);

/// <summary>Configured choices and defaults for report requests.</summary>
public sealed record ReportChoiceSettings(
    LookbackSettings Lookback,
    IReadOnlyList<FilterSetDefinition> FilterSets,
    IReadOnlyDictionary<string, string> TransactionSetLabels,
    bool DefaultIncomeIsRegular,
    IReadOnlyList<string> DefaultSubscriptionDiscoveryExclusions)
{
    public FilterSetDefinition FilterSet(string key)
    {
        foreach (FilterSetDefinition definition in FilterSets)
        {
            if (string.Equals(definition.Key, key, StringComparison.Ordinal))
                return definition;
        }

        throw new ArgumentException($"Unknown filter set '{key}'.", nameof(key));
    }
}
