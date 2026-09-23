using Portico.Finance;

namespace Portico.Application;

/// <summary>Chooses preset categories or one expense category or group.</summary>
public enum YearOverYearSelection
{
    Preset,
    Category,
    Group
}

/// <summary>Selects the year-over-year comparisons to calculate.</summary>
public sealed record YearOverYearReportRequest(
    YearOverYearSelection Selection = YearOverYearSelection.Preset,
    string? PresetSetKey = null,
    IReadOnlySet<string>? PresetCategories = null,
    string? Entity = null);

/// <summary>Explains why no year-over-year comparison was selected or found.</summary>
public enum YearOverYearEmptyReason
{
    NoPresetCategories,
    NoPresetSelection,
    NoCategories,
    NoGroups,
    NoMatchingHistory
}

/// <summary>Available choices and selected financial comparisons.</summary>
public sealed record YearOverYearReport(
    DateOnly? LatestTransactionDate,
    IReadOnlyList<string> PresetCategories,
    IReadOnlyList<string> Categories,
    IReadOnlyList<string> Groups,
    IReadOnlyList<YearOverYearComparison> Comparisons,
    YearOverYearEmptyReason? EmptyReason);

public sealed partial class Workspace
{
    /// <summary>Calculates selected year-over-year expense comparisons.</summary>
    public YearOverYearReport YearOverYear(YearOverYearReportRequest? request = null)
    {
        request ??= new YearOverYearReportRequest();
        FinancialTransaction[] visible = _snapshot.Transactions.Where(transaction => !transaction.IsHidden).ToArray();
        string presetSetKey = request.PresetSetKey ?? _reportChoiceSettings.FilterSet("year_over_year").Default;
        IReadOnlyList<string> presets = YearOverYearAnalysisCalculator.PresetCategories(
            visible, _settings, presetSetKey);
        IReadOnlyList<string> categories = YearOverYearAnalysisCalculator.Entities(
            visible, YearOverYearDimension.Category);
        IReadOnlyList<string> groups = YearOverYearAnalysisCalculator.Entities(
            visible, YearOverYearDimension.Group);

        IEnumerable<(YearOverYearDimension Dimension, string Entity, string? SetKey)> selected = request.Selection switch
        {
            YearOverYearSelection.Preset => presets
                .Where(category => request.PresetCategories?.Contains(category) == true)
                .Select(category => (YearOverYearDimension.Category, category, (string?)presetSetKey)),
            YearOverYearSelection.Category when !string.IsNullOrWhiteSpace(request.Entity) =>
                [(YearOverYearDimension.Category, request.Entity, null)],
            YearOverYearSelection.Group when !string.IsNullOrWhiteSpace(request.Entity) =>
                [(YearOverYearDimension.Group, request.Entity, null)],
            YearOverYearSelection.Category or YearOverYearSelection.Group => [],
            _ => throw new ArgumentOutOfRangeException(nameof(request), "Unsupported year-over-year selection.")
        };
        YearOverYearComparison[] comparisons = selected
            .Select(item => YearOverYearAnalysisCalculator.Build(
                visible, _settings, item.SetKey, item.Dimension, item.Entity))
            .OfType<YearOverYearComparison>()
            .ToArray();
        YearOverYearEmptyReason? emptyReason = comparisons.Length > 0 ? null : request.Selection switch
        {
            YearOverYearSelection.Preset when presets.Count == 0 => YearOverYearEmptyReason.NoPresetCategories,
            YearOverYearSelection.Preset => YearOverYearEmptyReason.NoPresetSelection,
            YearOverYearSelection.Category when categories.Count == 0 => YearOverYearEmptyReason.NoCategories,
            YearOverYearSelection.Group when groups.Count == 0 => YearOverYearEmptyReason.NoGroups,
            _ => YearOverYearEmptyReason.NoMatchingHistory
        };
        return new YearOverYearReport(
            visible.Length == 0 ? null : visible.Max(transaction => transaction.Date),
            presets, categories, groups, comparisons, emptyReason);
    }
}
