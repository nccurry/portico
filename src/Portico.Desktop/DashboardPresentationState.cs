using System.Globalization;
using Portico.Finance;

namespace Portico.Desktop;

/// <summary>Holds Home-only detail state without leaking it into finance calculations.</summary>
public sealed record HomePresentationState(IReadOnlySet<string> ExpandedAccountGroups)
{
    /// <summary>Creates the source page's initially collapsed account details.</summary>
    public static HomePresentationState Default { get; } = new(new HashSet<string>(StringComparer.Ordinal));
}

/// <summary>Holds Income and savings report inputs and visible detail state.</summary>
public sealed record IncomeSavingsPresentationState(
    IncomeSavingsAdjustments RegularAdjustments,
    IncomeSavingsAdjustments ActualAdjustments,
    string DetailMonth,
    string DetailTab,
    bool AdjustCalculationOpen,
    bool MonthlyTotalsExpanded)
{
    private static readonly IncomeSavingsAdjustments EmptyAdjustments = new(
        [], [], [], [], [], false, 0m, false, 0m, 0m);

    /// <summary>Creates the initial state before session settings supply real defaults.</summary>
    public static IncomeSavingsPresentationState Default { get; } = new(
        EmptyAdjustments,
        EmptyAdjustments,
        string.Empty,
        "Included",
        false,
        false);

    /// <summary>Gets the adjustment set for the active Regular or Actual calculation.</summary>
    public IncomeSavingsAdjustments Adjustments(bool regular)
        => regular ? RegularAdjustments : ActualAdjustments;

    /// <summary>Preserves the old public view of Regular excluded income categories.</summary>
    public IReadOnlySet<string> ExcludedIncomeCategories
        => RegularAdjustments.ExcludedIncomeCategories.ToHashSet(StringComparer.Ordinal);
}

/// <summary>Holds the selected Spending by category detail without mixing it into report inputs.</summary>
public sealed record SpendingPresentationState(
    string? SelectedGroup,
    string? SelectedCategory,
    string DetailMonth,
    string DetailTab,
    bool AdjustViewOpen,
    bool ExcludedRowsExpanded)
{
    /// <summary>Creates the source page's initial detail state.</summary>
    public static SpendingPresentationState Default { get; } = new(null, null, "all", "", false, false);

    /// <summary>Gets the selected entity for the current breakdown.</summary>
    public string? SelectedEntity(SpendingBreakdown breakdown)
        => breakdown == SpendingBreakdown.Group ? SelectedGroup : SelectedCategory;
}

/// <summary>Chooses the source's configured preset or one single-entity Year over year view.</summary>
public enum YearOverYearViewMode
{
    /// <summary>Shows one card for each selected category in a configured transaction set.</summary>
    Preset,

    /// <summary>Shows one selected expense category.</summary>
    SingleCategory,

    /// <summary>Shows one selected expense group.</summary>
    SingleGroup
}

/// <summary>Holds the current Year over year choice and expanded card details.</summary>
public sealed record YearOverYearPresentationState(
    YearOverYearViewMode ViewMode,
    string? PresetSetKey,
    IReadOnlySet<string> PresetCategories,
    string? SingleCategory,
    string? SingleGroup,
    IReadOnlySet<string> ExpandedDetails)
{
    /// <summary>Creates the source page's initial configured-preset state.</summary>
    public static YearOverYearPresentationState Default { get; } = new(
        YearOverYearViewMode.Preset,
        null,
        new HashSet<string>(StringComparer.Ordinal),
        null,
        null,
        new HashSet<string>(StringComparer.Ordinal));
}

/// <summary>Holds Subscriptions display state that does not change its financial rules.</summary>
public sealed record SubscriptionsPresentationState(
    string? SelectedMerchant,
    string HistoryLookback,
    string TimelineScope,
    bool SettingsOpen,
    bool MonthlyTotalsExpanded,
    bool IndividualChargesExpanded)
{
    /// <summary>Creates the source page's initially closed detail state.</summary>
    public static SubscriptionsPresentationState Default { get; } = new(null, "12m", "active_recent", false, false, false);
}

/// <summary>Holds Spending by merchant detail state without mixing it into report inputs.</summary>
public sealed record MerchantsPresentationState(
    string? SelectedMerchant,
    string DetailMonth,
    string DetailTab,
    bool AdjustViewOpen,
    string Search)
{
    /// <summary>Creates the source page's initial detail state.</summary>
    public static MerchantsPresentationState Default { get; } = new(null, "all", "Breakdown", false, string.Empty);
}

/// <summary>Holds Transactions display state without mixing it into report inputs.</summary>
public sealed record TransactionsPresentationState(bool MoreFiltersOpen)
{
    /// <summary>Creates the source page's initially closed More filters popover.</summary>
    public static TransactionsPresentationState Default { get; } = new(false);
}

/// <summary>Holds Budget display choices that do not change the budget calculation request.</summary>
public sealed record BudgetPresentationState(
    string? SelectedGroup,
    string TransactionCategory,
    bool AdjustViewOpen,
    bool YearToDateOpen)
{
    /// <summary>Creates the source page's initially closed detail state.</summary>
    public static BudgetPresentationState Default { get; } = new(null, "all", false, false);
}

/// <summary>Holds Financial Independence display choices alongside legacy target state.</summary>
public sealed record FinancialIndependencePresentationState(
    decimal TargetAmount,
    bool AdjustSourceDataOpen,
    bool SourceDetailsOpen,
    string SourceDetailsTab)
{
    /// <summary>Creates the initial display state.</summary>
    public static FinancialIndependencePresentationState Default { get; } = new(1_000_000m, false, false, "Accounts");
}

/// <summary>Holds Data Health display state while typed check settings feed the report.</summary>
public sealed record DataHealthPresentationState(
    decimal StaleThreshold,
    bool IncludeInactive,
    bool CheckSettingsOpen,
    string SelectedCheckId)
{
    /// <summary>Creates the initial display state.</summary>
    public static DataHealthPresentationState Default { get; } = new(30m, false, false, string.Empty);
}

/// <summary>Owns typed page state that is separate from finance settings and reports.</summary>
public sealed class DashboardPresentationState
{
    /// <summary>Gets the Home page's retained state.</summary>
    public HomePresentationState Home { get; private set; } = HomePresentationState.Default;

    /// <summary>Gets the Income and savings page's retained state.</summary>
    public IncomeSavingsPresentationState IncomeSavings { get; private set; } = IncomeSavingsPresentationState.Default;

    /// <summary>Gets the retained Spending by category detail state.</summary>
    public SpendingPresentationState Spending { get; private set; } = SpendingPresentationState.Default;

    /// <summary>Gets the retained Year over year controls and card details.</summary>
    public YearOverYearPresentationState YearOverYear { get; private set; } = YearOverYearPresentationState.Default;

    /// <summary>Gets the retained Subscriptions page display state.</summary>
    public SubscriptionsPresentationState Subscriptions { get; private set; } = SubscriptionsPresentationState.Default;

    /// <summary>Gets the retained Spending by merchant display state.</summary>
    public MerchantsPresentationState Merchants { get; private set; } = MerchantsPresentationState.Default;

    /// <summary>Gets the retained Transactions page display state.</summary>
    public TransactionsPresentationState Transactions { get; private set; } = TransactionsPresentationState.Default;

    /// <summary>Gets the retained Budget page display state.</summary>
    public BudgetPresentationState Budget { get; private set; } = BudgetPresentationState.Default;

    /// <summary>Gets the Financial independence page's retained state.</summary>
    public FinancialIndependencePresentationState FinancialIndependence { get; private set; } = FinancialIndependencePresentationState.Default;

    /// <summary>Gets the Data health page's retained state.</summary>
    public DataHealthPresentationState DataHealth { get; private set; } = DataHealthPresentationState.Default;

    /// <summary>Gets whether one Home account group's details are expanded.</summary>
    public bool IsHomeAccountGroupExpanded(string group)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(group);
        return Home.ExpandedAccountGroups.Contains(group);
    }

    /// <summary>Sets whether one Home account group's details are expanded.</summary>
    public void SetHomeAccountGroupExpanded(string group, bool expanded)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(group);
        var groups = new HashSet<string>(Home.ExpandedAccountGroups, StringComparer.Ordinal);
        if (expanded)
            groups.Add(group);
        else
            groups.Remove(group);
        Home = Home with { ExpandedAccountGroups = groups };
    }

    /// <summary>Sets the excluded Income and savings categories.</summary>
    public void SetIncomeExcludedCategories(IEnumerable<string> values)
    {
        ArgumentNullException.ThrowIfNull(values);
        IncomeSavings = IncomeSavings with
        {
            RegularAdjustments = IncomeSavings.RegularAdjustments with
            {
                ExcludedIncomeCategories = NormalizeValues(values)
            }
        };
    }

    /// <summary>Sets configured Income and savings adjustment defaults for both calculation views.</summary>
    public void InitializeIncomeSavings(IncomeSavingsAdjustments regular, IncomeSavingsAdjustments actual)
    {
        ArgumentNullException.ThrowIfNull(regular);
        ArgumentNullException.ThrowIfNull(actual);
        IncomeSavings = new IncomeSavingsPresentationState(
            regular,
            actual,
            string.Empty,
            "Included",
            false,
            false);
    }

    /// <summary>Gets the active Income and savings adjustment set.</summary>
    public IncomeSavingsAdjustments IncomeSavingsAdjustments(bool regular)
        => IncomeSavings.Adjustments(regular);

    /// <summary>Updates the adjustment set for the active Income calculation view.</summary>
    public void SetIncomeSavingsAdjustments(bool regular, IncomeSavingsAdjustments adjustments)
    {
        ArgumentNullException.ThrowIfNull(adjustments);
        IncomeSavings = regular
            ? IncomeSavings with { RegularAdjustments = adjustments }
            : IncomeSavings with { ActualAdjustments = adjustments };
    }

    /// <summary>Sets the selected Income and savings tab.</summary>
    public void SetIncomeDetailTab(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        IncomeSavings = IncomeSavings with { DetailTab = value };
    }

    /// <summary>Sets the selected Income and savings month detail.</summary>
    public void SetIncomeDetailMonth(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        IncomeSavings = IncomeSavings with { DetailMonth = value };
    }

    /// <summary>Sets whether the source-style Adjust calculation popover is open.</summary>
    public void SetIncomeAdjustCalculationOpen(bool open)
        => IncomeSavings = IncomeSavings with { AdjustCalculationOpen = open };

    /// <summary>Sets whether Monthly totals is expanded.</summary>
    public void SetIncomeMonthlyTotalsExpanded(bool expanded)
        => IncomeSavings = IncomeSavings with { MonthlyTotalsExpanded = expanded };

    /// <summary>Sets the entity selected in the current Spending breakdown.</summary>
    public void SetSpendingSelectedEntity(SpendingBreakdown breakdown, string? entity)
    {
        if (entity is not null)
            ArgumentException.ThrowIfNullOrWhiteSpace(entity);
        Spending = breakdown == SpendingBreakdown.Group
            ? Spending with { SelectedGroup = entity }
            : Spending with { SelectedCategory = entity };
    }

    /// <summary>Sets the Spending detail month or the all-months value.</summary>
    public void SetSpendingDetailMonth(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        Spending = Spending with { DetailMonth = value };
    }

    /// <summary>Sets the active selected-detail tab.</summary>
    public void SetSpendingDetailTab(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        Spending = Spending with { DetailTab = value };
    }

    /// <summary>Sets whether the source-style Adjust view popover is open.</summary>
    public void SetSpendingAdjustViewOpen(bool open)
        => Spending = Spending with { AdjustViewOpen = open };

    /// <summary>Sets whether excluded rows are visible below the report.</summary>
    public void SetSpendingExcludedRowsExpanded(bool expanded)
        => Spending = Spending with { ExcludedRowsExpanded = expanded };

    /// <summary>Sets the active Year over year source view mode.</summary>
    public void SetYearOverYearViewMode(YearOverYearViewMode mode)
        => YearOverYear = YearOverYear with { ViewMode = mode };

    /// <summary>Sets the selected preset categories for one configured transaction set.</summary>
    public void SetYearOverYearPresetCategories(string setKey, IEnumerable<string> values)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(setKey);
        ArgumentNullException.ThrowIfNull(values);
        YearOverYear = YearOverYear with
        {
            PresetSetKey = setKey,
            PresetCategories = NormalizeSet(values)
        };
    }

    /// <summary>Sets the selected single category.</summary>
    public void SetYearOverYearSingleCategory(string? value)
    {
        if (value is not null)
            ArgumentException.ThrowIfNullOrWhiteSpace(value);
        YearOverYear = YearOverYear with { SingleCategory = value };
    }

    /// <summary>Sets the selected single group.</summary>
    public void SetYearOverYearSingleGroup(string? value)
    {
        if (value is not null)
            ArgumentException.ThrowIfNullOrWhiteSpace(value);
        YearOverYear = YearOverYear with { SingleGroup = value };
    }

    /// <summary>Sets whether one Year over year comparison card shows its details.</summary>
    public void SetYearOverYearDetailsExpanded(string entity, bool expanded)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(entity);
        var details = new HashSet<string>(YearOverYear.ExpandedDetails, StringComparer.Ordinal);
        if (expanded)
            details.Add(entity);
        else
            details.Remove(entity);
        YearOverYear = YearOverYear with { ExpandedDetails = details };
    }

    /// <summary>Sets the selected Subscriptions inventory merchant.</summary>
    public void SetSubscriptionSelectedMerchant(string? merchant)
    {
        if (merchant is not null)
            ArgumentException.ThrowIfNullOrWhiteSpace(merchant);
        Subscriptions = Subscriptions with { SelectedMerchant = merchant };
    }

    /// <summary>Sets the visible Subscriptions history range.</summary>
    public void SetSubscriptionHistoryLookback(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        Subscriptions = Subscriptions with { HistoryLookback = value };
    }

    /// <summary>Sets the visible Subscriptions lifecycle scope.</summary>
    public void SetSubscriptionTimelineScope(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        Subscriptions = Subscriptions with { TimelineScope = value };
    }

    /// <summary>Sets whether the source-style Subscription settings expander is open.</summary>
    public void SetSubscriptionSettingsOpen(bool open)
        => Subscriptions = Subscriptions with { SettingsOpen = open };

    /// <summary>Sets whether selected subscription monthly totals are visible.</summary>
    public void SetSubscriptionMonthlyTotalsExpanded(bool expanded)
        => Subscriptions = Subscriptions with { MonthlyTotalsExpanded = expanded };

    /// <summary>Sets whether selected subscription charge rows are visible.</summary>
    public void SetSubscriptionIndividualChargesExpanded(bool expanded)
        => Subscriptions = Subscriptions with { IndividualChargesExpanded = expanded };

    /// <summary>Sets the selected Spending by merchant detail entity.</summary>
    public void SetMerchantSelectedMerchant(string? merchant)
    {
        if (merchant is not null)
            ArgumentException.ThrowIfNullOrWhiteSpace(merchant);
        Merchants = Merchants with { SelectedMerchant = merchant };
    }

    /// <summary>Sets the Spending by merchant detail month or all-months value.</summary>
    public void SetMerchantDetailMonth(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        Merchants = Merchants with { DetailMonth = value };
    }

    /// <summary>Sets the selected Spending by merchant detail tab.</summary>
    public void SetMerchantDetailTab(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        Merchants = Merchants with { DetailTab = value };
    }

    /// <summary>Sets whether the source-style Spending by merchant Adjust view popover is open.</summary>
    public void SetMerchantAdjustViewOpen(bool open)
        => Merchants = Merchants with { AdjustViewOpen = open };

    /// <summary>Sets the source Spending by merchant search text.</summary>
    public void SetMerchantSearch(string value)
    {
        ArgumentNullException.ThrowIfNull(value);
        Merchants = Merchants with { Search = value };
    }

    /// <summary>Sets whether the source-style Transactions More filters popover is open.</summary>
    public void SetTransactionsMoreFiltersOpen(bool open)
        => Transactions = Transactions with { MoreFiltersOpen = open };

    /// <summary>Sets the selected Budget group for the source detail section.</summary>
    public void SetBudgetSelectedGroup(string? group)
    {
        if (group is not null)
            ArgumentException.ThrowIfNullOrWhiteSpace(group);
        Budget = Budget with { SelectedGroup = group };
    }

    /// <summary>Sets the Budget transaction category or the all-categories choice.</summary>
    public void SetBudgetTransactionCategory(string category)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(category);
        Budget = Budget with { TransactionCategory = category };
    }

    /// <summary>Sets whether the Budget Adjust view popover is open.</summary>
    public void SetBudgetAdjustViewOpen(bool open)
        => Budget = Budget with { AdjustViewOpen = open };

    /// <summary>Sets whether the Budget year-to-date detail is expanded.</summary>
    public void SetBudgetYearToDateOpen(bool open)
        => Budget = Budget with { YearToDateOpen = open };

    /// <summary>Sets the Financial independence target shown by the scenario control.</summary>
    public void SetFinancialIndependenceTargetAmount(decimal value)
        => FinancialIndependence = FinancialIndependence with { TargetAmount = value };

    /// <summary>Restores the Financial independence display inputs to their configured initial value.</summary>
    public void ResetFinancialIndependence(decimal targetAmount)
        => FinancialIndependence = FinancialIndependence with
        {
            TargetAmount = targetAmount,
            AdjustSourceDataOpen = false,
            SourceDetailsOpen = false,
            SourceDetailsTab = "Accounts"
        };

    /// <summary>Sets whether Financial Independence source controls are open.</summary>
    public void SetFinancialIndependenceAdjustSourceDataOpen(bool open)
        => FinancialIndependence = FinancialIndependence with { AdjustSourceDataOpen = open };

    /// <summary>Sets whether Financial Independence source details are expanded.</summary>
    public void SetFinancialIndependenceSourceDetailsOpen(bool open)
        => FinancialIndependence = FinancialIndependence with { SourceDetailsOpen = open };

    /// <summary>Sets the active Financial Independence source-details tab.</summary>
    public void SetFinancialIndependenceSourceDetailsTab(string tab)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(tab);
        FinancialIndependence = FinancialIndependence with { SourceDetailsTab = tab };
    }

    /// <summary>Sets the Data health stale-account threshold.</summary>
    public void SetDataHealthStaleThreshold(decimal value)
        => DataHealth = DataHealth with { StaleThreshold = value };

    /// <summary>Sets whether the Data health page includes inactive items.</summary>
    public void SetDataHealthIncludeInactive(bool value)
        => DataHealth = DataHealth with { IncludeInactive = value };

    /// <summary>Sets whether the Data Health check-settings popover is open.</summary>
    public void SetDataHealthCheckSettingsOpen(bool open)
        => DataHealth = DataHealth with { CheckSettingsOpen = open };

    /// <summary>Sets the selected Data Health check detail.</summary>
    public void SetDataHealthSelectedCheck(string checkId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(checkId);
        DataHealth = DataHealth with { SelectedCheckId = checkId };
    }

    /// <summary>Gets the configured control value formatted for a native Roci control.</summary>
    public string ValueFor(DashboardControlSource source)
        => source switch
        {
            DashboardControlSource.IncomeDetailTab => IncomeSavings.DetailTab,
            DashboardControlSource.IncomeDetailMonth => IncomeSavings.DetailMonth,
            DashboardControlSource.IncomeAdjustCalculation => IncomeSavings.AdjustCalculationOpen.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.SpendingDetailMonth => Spending.DetailMonth,
            DashboardControlSource.SpendingAdjustView => Spending.AdjustViewOpen.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.SubscriptionSettingsOpen => Subscriptions.SettingsOpen.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.SubscriptionHistoryLookback => Subscriptions.HistoryLookback,
            DashboardControlSource.SubscriptionTimelineScope => Subscriptions.TimelineScope,
            DashboardControlSource.MerchantAdjustView => Merchants.AdjustViewOpen.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.MerchantSearch => Merchants.Search,
            DashboardControlSource.MerchantDetailMonth => Merchants.DetailMonth,
            DashboardControlSource.MerchantDetailTab => Merchants.DetailTab,
            DashboardControlSource.TransactionsMoreFilters => Transactions.MoreFiltersOpen.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.BudgetAdjustView => Budget.AdjustViewOpen.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.BudgetTransactionCategory => Budget.TransactionCategory,
            DashboardControlSource.BudgetYearToDate => Budget.YearToDateOpen.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.FinancialIndependenceTargetAmount => FinancialIndependence.TargetAmount.ToString(CultureInfo.InvariantCulture),
            DashboardControlSource.FinancialIndependenceAdjustSourceData => FinancialIndependence.AdjustSourceDataOpen.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.FinancialIndependenceSourceDetails => FinancialIndependence.SourceDetailsOpen.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.FinancialIndependenceSourceDetailsTab => FinancialIndependence.SourceDetailsTab,
            DashboardControlSource.DataHealthStaleThreshold => DataHealth.StaleThreshold.ToString(CultureInfo.InvariantCulture),
            DashboardControlSource.DataHealthIncludeInactive => DataHealth.IncludeInactive.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.DataHealthCheckSettings => DataHealth.CheckSettingsOpen.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            DashboardControlSource.DataHealthSelectedCheck => DataHealth.SelectedCheckId,
            _ => throw new ArgumentException($"Control source '{source}' does not hold one display value.", nameof(source))
        };

    /// <summary>Gets the configured multi-select value set.</summary>
    public IReadOnlySet<string> ValuesFor(DashboardControlSource source)
        => source == DashboardControlSource.IncomeExcludedCategories
            ? IncomeSavings.ExcludedIncomeCategories
            : throw new ArgumentException($"Control source '{source}' does not hold multiple values.", nameof(source));

    private static IReadOnlyList<string> NormalizeValues(IEnumerable<string> values)
        => values
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value.Trim())
            .Distinct(StringComparer.Ordinal)
            .ToArray();

    private static IReadOnlySet<string> NormalizeSet(IEnumerable<string> values)
        => new HashSet<string>(NormalizeValues(values), StringComparer.Ordinal);
}
