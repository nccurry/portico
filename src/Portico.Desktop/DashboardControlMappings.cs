using System.Globalization;

using Portico.Finance;

namespace Portico.Desktop;

/// <summary>Describes whether a typed control changes a report, visible state, or an action.</summary>
public enum DashboardControlBehavior
{
    /// <summary>Changes a typed report request and rebuilds the report.</summary>
    ReportInput,

    /// <summary>Changes retained page presentation only.</summary>
    DisplayState,

    /// <summary>Runs a named page action.</summary>
    Action
}

/// <summary>Maps one known TOML control to a typed C# target.</summary>
public sealed record DashboardControlMapping(
    DashboardControlKind Kind,
    DashboardControlSource Source,
    DashboardControlBehavior Behavior,
    string? ReportFilterSource = null);

/// <summary>Holds the finite control map accepted by the desktop dashboard.</summary>
public static class DashboardControlMappings
{
    private static readonly IReadOnlyDictionary<(DashboardPageId PageId, string ControlId), DashboardControlMapping> Mappings =
        new Dictionary<(DashboardPageId PageId, string ControlId), DashboardControlMapping>
        {
            [(DashboardPageId.Home, "time_frame")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.HomeTimeFrame,
                DashboardControlBehavior.ReportInput,
                "home_time_frame"),
            [(DashboardPageId.IncomeSavings, "income_view")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.IncomeView,
                DashboardControlBehavior.ReportInput,
                "income_view"),
            [(DashboardPageId.IncomeSavings, "detail_tab")] = new(
                DashboardControlKind.TabChoice,
                DashboardControlSource.IncomeDetailTab,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.IncomeSavings, "lookback")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.IncomeLookback,
                DashboardControlBehavior.ReportInput,
                "income_lookback"),
            [(DashboardPageId.IncomeSavings, "calculation")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.IncomeCalculation,
                DashboardControlBehavior.ReportInput,
                "income_calculation"),
            [(DashboardPageId.IncomeSavings, "adjust_calculation")] = new(
                DashboardControlKind.Popover,
                DashboardControlSource.IncomeAdjustCalculation,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.IncomeSavings, "reset_adjustments")] = new(
                DashboardControlKind.ActionReset,
                DashboardControlSource.IncomeReset,
                DashboardControlBehavior.Action),
            [(DashboardPageId.IncomeSavings, "exclude_income_categories")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.IncomeExcludedIncomeCategories,
                DashboardControlBehavior.ReportInput,
                "income_excluded_income_categories"),
            [(DashboardPageId.IncomeSavings, "exclude_expense_groups")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.IncomeExcludedExpenseGroups,
                DashboardControlBehavior.ReportInput,
                "income_excluded_expense_groups"),
            [(DashboardPageId.IncomeSavings, "exclude_expense_categories")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.IncomeExcludedExpenseCategories,
                DashboardControlBehavior.ReportInput,
                "income_excluded_expense_categories"),
            [(DashboardPageId.IncomeSavings, "include_transaction_names")] = new(
                DashboardControlKind.TextMultiSelect,
                DashboardControlSource.IncomeIncludedDescriptions,
                DashboardControlBehavior.ReportInput,
                "income_included_descriptions"),
            [(DashboardPageId.IncomeSavings, "exclude_transaction_names")] = new(
                DashboardControlKind.TextMultiSelect,
                DashboardControlSource.IncomeExcludedDescriptions,
                DashboardControlBehavior.ReportInput,
                "income_excluded_descriptions"),
            [(DashboardPageId.IncomeSavings, "exclude_large_income")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.IncomeExcludeLargeIncome,
                DashboardControlBehavior.ReportInput,
                "income_exclude_large_income"),
            [(DashboardPageId.IncomeSavings, "income_limit")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.IncomeIncomeLimit,
                DashboardControlBehavior.ReportInput,
                "income_income_limit"),
            [(DashboardPageId.IncomeSavings, "exclude_large_expenses")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.IncomeExcludeLargeExpenses,
                DashboardControlBehavior.ReportInput,
                "income_exclude_large_expenses"),
            [(DashboardPageId.IncomeSavings, "expense_limit")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.IncomeExpenseLimit,
                DashboardControlBehavior.ReportInput,
                "income_expense_limit"),
            [(DashboardPageId.IncomeSavings, "savings_rate_target")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.IncomeTargetRate,
                DashboardControlBehavior.ReportInput,
                "income_target_rate"),
            [(DashboardPageId.IncomeSavings, "detail_month")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.IncomeDetailMonth,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Spending, "spending_view")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.Spending,
                DashboardControlBehavior.ReportInput,
                "spending"),
            [(DashboardPageId.Spending, "lookback")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.Lookback,
                DashboardControlBehavior.ReportInput,
                "lookback"),
            [(DashboardPageId.Spending, "comparison")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.SpendingComparison,
                DashboardControlBehavior.ReportInput,
                "spending_comparison"),
            [(DashboardPageId.Spending, "breakdown")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.SpendingBreakdown,
                DashboardControlBehavior.ReportInput,
                "spending_breakdown"),
            [(DashboardPageId.Spending, "exclude_groups")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.SpendingExcludedGroups,
                DashboardControlBehavior.ReportInput,
                "spending_excluded_groups"),
            [(DashboardPageId.Spending, "exclude_categories")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.SpendingExcludedCategories,
                DashboardControlBehavior.ReportInput,
                "spending_excluded_categories"),
            [(DashboardPageId.Spending, "include_transaction_names")] = new(
                DashboardControlKind.TextMultiSelect,
                DashboardControlSource.SpendingIncludedDescriptions,
                DashboardControlBehavior.ReportInput,
                "spending_included_descriptions"),
            [(DashboardPageId.Spending, "exclude_transaction_names")] = new(
                DashboardControlKind.TextMultiSelect,
                DashboardControlSource.SpendingExcludedDescriptions,
                DashboardControlBehavior.ReportInput,
                "spending_excluded_descriptions"),
            [(DashboardPageId.Spending, "exclude_large_expenses")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.SpendingExcludeLargeExpenses,
                DashboardControlBehavior.ReportInput,
                "spending_exclude_large_expenses"),
            [(DashboardPageId.Spending, "expense_limit")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.SpendingExpenseLimit,
                DashboardControlBehavior.ReportInput,
                "spending_expense_limit"),
            [(DashboardPageId.Spending, "detail_month")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.SpendingDetailMonth,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Spending, "adjust_view")] = new(
                DashboardControlKind.Popover,
                DashboardControlSource.SpendingAdjustView,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Spending, "reset_adjustments")] = new(
                DashboardControlKind.ActionReset,
                DashboardControlSource.SpendingReset,
                DashboardControlBehavior.Action),
            [(DashboardPageId.YearOverYear, "view")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.YearOverYearView,
                DashboardControlBehavior.ReportInput,
                "year_over_year_view"),
            [(DashboardPageId.YearOverYear, "preset_categories")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.YearOverYearPresetCategories,
                DashboardControlBehavior.ReportInput,
                "year_over_year_preset_categories"),
            [(DashboardPageId.YearOverYear, "single_category")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.YearOverYearSingleCategory,
                DashboardControlBehavior.ReportInput,
                "year_over_year_single_category"),
            [(DashboardPageId.YearOverYear, "single_group")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.YearOverYearSingleGroup,
                DashboardControlBehavior.ReportInput,
                "year_over_year_single_group"),
            [(DashboardPageId.YearOverYear, "spending_view")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.YearOverYear,
                DashboardControlBehavior.ReportInput,
                "year_over_year"),
            [(DashboardPageId.Subscriptions, "subscription_settings")] = new(
                DashboardControlKind.Collapsible,
                DashboardControlSource.SubscriptionSettingsOpen,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Subscriptions, "subscription_categories")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.SubscriptionCategories,
                DashboardControlBehavior.ReportInput,
                "subscription_categories"),
            [(DashboardPageId.Subscriptions, "discovery_exclusions")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.SubscriptionDiscoveryExclusions,
                DashboardControlBehavior.ReportInput,
                "subscription_discovery_exclusions"),
            [(DashboardPageId.Subscriptions, "minimum_confidence")] = new(
                DashboardControlKind.Slider,
                DashboardControlSource.SubscriptionMinimumConfidence,
                DashboardControlBehavior.ReportInput,
                "subscription_minimum_confidence"),
            [(DashboardPageId.Subscriptions, "history_lookback")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.SubscriptionHistoryLookback,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Subscriptions, "timeline_scope")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.SubscriptionTimelineScope,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Merchants, "lookback")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.MerchantLookback,
                DashboardControlBehavior.ReportInput,
                "merchant_lookback"),
            [(DashboardPageId.Merchants, "spending_view")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.MerchantSpending,
                DashboardControlBehavior.ReportInput,
                "merchant_spending"),
            [(DashboardPageId.Merchants, "comparison")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.MerchantComparison,
                DashboardControlBehavior.ReportInput,
                "merchant_comparison"),
            [(DashboardPageId.Merchants, "adjust_view")] = new(
                DashboardControlKind.Popover,
                DashboardControlSource.MerchantAdjustView,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Merchants, "reset_adjustments")] = new(
                DashboardControlKind.ActionReset,
                DashboardControlSource.MerchantReset,
                DashboardControlBehavior.Action),
            [(DashboardPageId.Merchants, "exclude_groups")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.MerchantExcludedGroups,
                DashboardControlBehavior.ReportInput,
                "merchant_excluded_groups"),
            [(DashboardPageId.Merchants, "exclude_categories")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.MerchantExcludedCategories,
                DashboardControlBehavior.ReportInput,
                "merchant_excluded_categories"),
            [(DashboardPageId.Merchants, "include_transaction_names")] = new(
                DashboardControlKind.TextMultiSelect,
                DashboardControlSource.MerchantIncludedDescriptions,
                DashboardControlBehavior.ReportInput,
                "merchant_included_descriptions"),
            [(DashboardPageId.Merchants, "exclude_transaction_names")] = new(
                DashboardControlKind.TextMultiSelect,
                DashboardControlSource.MerchantExcludedDescriptions,
                DashboardControlBehavior.ReportInput,
                "merchant_excluded_descriptions"),
            [(DashboardPageId.Merchants, "exclude_large_expenses")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.MerchantExcludeLargeExpenses,
                DashboardControlBehavior.ReportInput,
                "merchant_exclude_large_expenses"),
            [(DashboardPageId.Merchants, "expense_limit")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.MerchantExpenseLimit,
                DashboardControlBehavior.ReportInput,
                "merchant_expense_limit"),
            [(DashboardPageId.Merchants, "search")] = new(
                DashboardControlKind.TextInput,
                DashboardControlSource.MerchantSearch,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Merchants, "detail_month")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.MerchantDetailMonth,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Merchants, "detail_tab")] = new(
                DashboardControlKind.TabChoice,
                DashboardControlSource.MerchantDetailTab,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.TopTransactions, "lookback")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.TransactionsLookback,
                DashboardControlBehavior.ReportInput,
                "transactions_lookback"),
            [(DashboardPageId.TopTransactions, "type")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.TransactionsType,
                DashboardControlBehavior.ReportInput,
                "transactions_type"),
            [(DashboardPageId.TopTransactions, "focus")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.TransactionsFocus,
                DashboardControlBehavior.ReportInput,
                "transactions_focus"),
            [(DashboardPageId.TopTransactions, "search")] = new(
                DashboardControlKind.TextInput,
                DashboardControlSource.TransactionsSearch,
                DashboardControlBehavior.ReportInput,
                "transactions_search"),
            [(DashboardPageId.TopTransactions, "more_filters")] = new(
                DashboardControlKind.Popover,
                DashboardControlSource.TransactionsMoreFilters,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.TopTransactions, "groups")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.TransactionsGroups,
                DashboardControlBehavior.ReportInput,
                "transactions_groups"),
            [(DashboardPageId.TopTransactions, "categories")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.TransactionsCategories,
                DashboardControlBehavior.ReportInput,
                "transactions_categories"),
            [(DashboardPageId.TopTransactions, "accounts")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.TransactionsAccounts,
                DashboardControlBehavior.ReportInput,
                "transactions_accounts"),
            [(DashboardPageId.TopTransactions, "minimum_amount")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.TransactionsMinimumAmount,
                DashboardControlBehavior.ReportInput,
                "transactions_minimum_amount"),
            [(DashboardPageId.TopTransactions, "maximum_amount")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.TransactionsMaximumAmount,
                DashboardControlBehavior.ReportInput,
                "transactions_maximum_amount"),
            [(DashboardPageId.TopTransactions, "largest_count")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.TransactionsLargestCount,
                DashboardControlBehavior.ReportInput,
                "transactions_largest_count"),
            [(DashboardPageId.TopTransactions, "breakdown")] = new(
                DashboardControlKind.SegmentedChoice,
                DashboardControlSource.TransactionsBreakdown,
                DashboardControlBehavior.ReportInput,
                "transactions_breakdown"),
            [(DashboardPageId.Budget, "month")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.BudgetMonth,
                DashboardControlBehavior.ReportInput,
                "budget_month"),
            [(DashboardPageId.Budget, "groups")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.BudgetGroups,
                DashboardControlBehavior.ReportInput,
                "budget_groups"),
            [(DashboardPageId.Budget, "adjust_view")] = new(
                DashboardControlKind.Popover,
                DashboardControlSource.BudgetAdjustView,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Budget, "reset_adjustments")] = new(
                DashboardControlKind.ActionReset,
                DashboardControlSource.BudgetReset,
                DashboardControlBehavior.Action),
            [(DashboardPageId.Budget, "exclude_groups")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.BudgetExcludedGroups,
                DashboardControlBehavior.ReportInput,
                "budget_excluded_groups"),
            [(DashboardPageId.Budget, "exclude_categories")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.BudgetExcludedCategories,
                DashboardControlBehavior.ReportInput,
                "budget_excluded_categories"),
            [(DashboardPageId.Budget, "include_transaction_names")] = new(
                DashboardControlKind.TextMultiSelect,
                DashboardControlSource.BudgetIncludedDescriptions,
                DashboardControlBehavior.ReportInput,
                "budget_included_descriptions"),
            [(DashboardPageId.Budget, "exclude_transaction_names")] = new(
                DashboardControlKind.TextMultiSelect,
                DashboardControlSource.BudgetExcludedDescriptions,
                DashboardControlBehavior.ReportInput,
                "budget_excluded_descriptions"),
            [(DashboardPageId.Budget, "exclude_large_expenses")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.BudgetExcludeLargeExpenses,
                DashboardControlBehavior.ReportInput,
                "budget_exclude_large_expenses"),
            [(DashboardPageId.Budget, "expense_limit")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.BudgetExpenseLimit,
                DashboardControlBehavior.ReportInput,
                "budget_expense_limit"),
            [(DashboardPageId.Budget, "transaction_category")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.BudgetTransactionCategory,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.Budget, "year_to_date")] = new(
                DashboardControlKind.Collapsible,
                DashboardControlSource.BudgetYearToDate,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.FinancialIndependence, "assets")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.FinancialIndependenceAssets,
                DashboardControlBehavior.ReportInput,
                "fi_assets"),
            [(DashboardPageId.FinancialIndependence, "spending")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.FinancialIndependenceSpending,
                DashboardControlBehavior.ReportInput,
                "fi_spending"),
            [(DashboardPageId.FinancialIndependence, "income")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.FinancialIndependenceIncome,
                DashboardControlBehavior.ReportInput,
                "fi_income"),
            [(DashboardPageId.FinancialIndependence, "return_rate")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.FinancialIndependenceReturnRate,
                DashboardControlBehavior.ReportInput,
                "fi_return_rate"),
            [(DashboardPageId.FinancialIndependence, "withdrawal_rate")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.FinancialIndependenceWithdrawalRate,
                DashboardControlBehavior.ReportInput,
                "fi_withdrawal_rate"),
            [(DashboardPageId.FinancialIndependence, "years")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.FinancialIndependenceProjectionYears,
                DashboardControlBehavior.ReportInput,
                "fi_years"),
            [(DashboardPageId.FinancialIndependence, "adjust_source_data")] = new(
                DashboardControlKind.Popover,
                DashboardControlSource.FinancialIndependenceAdjustSourceData,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.FinancialIndependence, "include_accounts")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.FinancialIndependenceIncludedAccounts,
                DashboardControlBehavior.ReportInput,
                "fi_included_accounts"),
            [(DashboardPageId.FinancialIndependence, "spending_lookback")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.FinancialIndependenceSpendingLookback,
                DashboardControlBehavior.ReportInput,
                "fi_spending_lookback"),
            [(DashboardPageId.FinancialIndependence, "exclude_groups")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.FinancialIndependenceExcludedGroups,
                DashboardControlBehavior.ReportInput,
                "fi_excluded_groups"),
            [(DashboardPageId.FinancialIndependence, "exclude_categories")] = new(
                DashboardControlKind.MultiSelect,
                DashboardControlSource.FinancialIndependenceExcludedCategories,
                DashboardControlBehavior.ReportInput,
                "fi_excluded_categories"),
            [(DashboardPageId.FinancialIndependence, "include_transaction_names")] = new(
                DashboardControlKind.TextMultiSelect,
                DashboardControlSource.FinancialIndependenceIncludedDescriptions,
                DashboardControlBehavior.ReportInput,
                "fi_included_descriptions"),
            [(DashboardPageId.FinancialIndependence, "exclude_transaction_names")] = new(
                DashboardControlKind.TextMultiSelect,
                DashboardControlSource.FinancialIndependenceExcludedDescriptions,
                DashboardControlBehavior.ReportInput,
                "fi_excluded_descriptions"),
            [(DashboardPageId.FinancialIndependence, "exclude_large_expenses")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.FinancialIndependenceExcludeLargeExpenses,
                DashboardControlBehavior.ReportInput,
                "fi_exclude_large_expenses"),
            [(DashboardPageId.FinancialIndependence, "expense_limit")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.FinancialIndependenceExpenseLimit,
                DashboardControlBehavior.ReportInput,
                "fi_expense_limit"),
            [(DashboardPageId.FinancialIndependence, "target_amount")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.FinancialIndependenceTargetAmount,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.FinancialIndependence, "reset_scenario")] = new(
                DashboardControlKind.ActionReset,
                DashboardControlSource.FinancialIndependenceReset,
                DashboardControlBehavior.Action),
            [(DashboardPageId.FinancialIndependence, "source_details")] = new(
                DashboardControlKind.Collapsible,
                DashboardControlSource.FinancialIndependenceSourceDetails,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.FinancialIndependence, "source_tab")] = new(
                DashboardControlKind.TabChoice,
                DashboardControlSource.FinancialIndependenceSourceDetailsTab,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.DataHealth, "check_settings")] = new(
                DashboardControlKind.Popover,
                DashboardControlSource.DataHealthCheckSettings,
                DashboardControlBehavior.DisplayState),
            [(DashboardPageId.DataHealth, "stale_threshold")] = new(
                DashboardControlKind.Slider,
                DashboardControlSource.DataHealthStaleThreshold,
                DashboardControlBehavior.ReportInput,
                "health_stale_days"),
            [(DashboardPageId.DataHealth, "duplicate_days")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.DataHealthDuplicateDays,
                DashboardControlBehavior.ReportInput,
                "health_duplicate_days"),
            [(DashboardPageId.DataHealth, "duplicate_minimum")] = new(
                DashboardControlKind.NumberInput,
                DashboardControlSource.DataHealthDuplicateMinimum,
                DashboardControlBehavior.ReportInput,
                "health_duplicate_minimum"),
            [(DashboardPageId.DataHealth, "same_account")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.DataHealthDuplicateSameAccount,
                DashboardControlBehavior.ReportInput,
                "health_same_account"),
            [(DashboardPageId.DataHealth, "same_category")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.DataHealthDuplicateSameCategory,
                DashboardControlBehavior.ReportInput,
                "health_same_category"),
            [(DashboardPageId.DataHealth, "same_description")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.DataHealthDuplicateSameDescription,
                DashboardControlBehavior.ReportInput,
                "health_same_description"),
            [(DashboardPageId.DataHealth, "include_inactive")] = new(
                DashboardControlKind.Toggle,
                DashboardControlSource.DataHealthIncludeInactive,
                DashboardControlBehavior.ReportInput,
                "health_include_inactive"),
            [(DashboardPageId.DataHealth, "selected_check")] = new(
                DashboardControlKind.Select,
                DashboardControlSource.DataHealthSelectedCheck,
                DashboardControlBehavior.DisplayState)
        };

    /// <summary>Returns the C# mapping for one configured page control.</summary>
    public static bool TryResolve(
        DashboardPageId pageId,
        string controlId,
        out DashboardControlMapping? mapping)
        => Mappings.TryGetValue((pageId, controlId), out mapping);

    /// <summary>Returns the C# mapping or throws a clear configuration error.</summary>
    public static DashboardControlMapping Resolve(DashboardPageId pageId, string controlId)
        => TryResolve(pageId, controlId, out DashboardControlMapping? mapping)
            ? mapping!
            : throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not supported.", nameof(controlId));

    /// <summary>Checks that a mapping has a real typed route before a page tries to draw it.</summary>
    public static bool TryValidate(DashboardControlMapping mapping, out string? problem)
    {
        ArgumentNullException.ThrowIfNull(mapping);

        switch (mapping.Behavior)
        {
            case DashboardControlBehavior.ReportInput:
                string? expectedRoute = ReportFilterRouteFor(mapping.Source);
                if (expectedRoute is null
                    || !string.Equals(expectedRoute, mapping.ReportFilterSource, StringComparison.Ordinal))
                {
                    problem = "needs a supported report-filter route";
                    return false;
                }

                problem = null;
                return true;
            case DashboardControlBehavior.DisplayState:
                if (!HasDisplaySetter(mapping.Source, mapping.Kind))
                {
                    problem = "needs a typed display-state setter";
                    return false;
                }

                problem = null;
                return true;
            case DashboardControlBehavior.Action:
                if (mapping.Kind != DashboardControlKind.ActionReset
                    || mapping.Source is not (DashboardControlSource.FinancialIndependenceReset
                        or DashboardControlSource.SpendingReset
                        or DashboardControlSource.IncomeReset
                        or DashboardControlSource.MerchantReset
                        or DashboardControlSource.BudgetReset))
                {
                    problem = "needs a named action handler";
                    return false;
                }

                problem = null;
                return true;
            default:
                problem = "uses an unsupported control behavior";
                return false;
        }
    }

    /// <summary>Checks the finite options owned by a typed control route.</summary>
    public static bool TryValidateConfiguredOptions(
        DashboardControlMapping mapping,
        IReadOnlyList<string> options,
        out string? problem)
    {
        ArgumentNullException.ThrowIfNull(mapping);
        ArgumentNullException.ThrowIfNull(options);

        if (mapping.Source == DashboardControlSource.HomeTimeFrame)
        {
            string? unsupported = options.FirstOrDefault(option => !HomeTimeFrameOptions.TryParse(option, out _));
            if (unsupported is not null)
            {
                problem = $"has unsupported Home time-frame option '{unsupported}'";
                return false;
            }
        }

        if (mapping.Source == DashboardControlSource.SpendingComparison)
        {
            string? unsupported = options.FirstOrDefault(option => !TryParseSpendingComparison(option, out _));
            if (unsupported is not null)
            {
                problem = $"has unsupported Spending comparison option '{unsupported}'";
                return false;
            }
        }

        if (mapping.Source == DashboardControlSource.SpendingBreakdown)
        {
            string? unsupported = options.FirstOrDefault(option => !TryParseSpendingBreakdown(option, out _));
            if (unsupported is not null)
            {
                problem = $"has unsupported Spending breakdown option '{unsupported}'";
                return false;
            }
        }

        if (mapping.Source == DashboardControlSource.IncomeCalculation)
        {
            string? unsupported = options.FirstOrDefault(option => option is not ("regular" or "actual"));
            if (unsupported is not null)
            {
                problem = $"has unsupported Income calculation option '{unsupported}'";
                return false;
            }
        }

        if (mapping.Source == DashboardControlSource.MerchantComparison)
        {
            string? unsupported = options.FirstOrDefault(option => !TryParseSpendingComparison(option, out _));
            if (unsupported is not null)
            {
                problem = $"has unsupported Merchant comparison option '{unsupported}'";
                return false;
            }
        }

        if (mapping.Source == DashboardControlSource.TransactionsLookback)
        {
            string? unsupported = options.FirstOrDefault(option => option is not ("3m" or "6m" or "1y" or "2y" or "all"));
            if (unsupported is not null)
            {
                problem = $"has unsupported Transactions lookback option '{unsupported}'";
                return false;
            }
        }

        if (mapping.Source == DashboardControlSource.TransactionsType)
        {
            string? unsupported = options.FirstOrDefault(option => option is not ("all" or "expenses" or "income" or "transfers"));
            if (unsupported is not null)
            {
                problem = $"has unsupported Transactions type option '{unsupported}'";
                return false;
            }
        }

        if (mapping.Source == DashboardControlSource.TransactionsFocus)
        {
            string? unsupported = options.FirstOrDefault(option => option is not ("all" or "largest" or "one_off" or "unusual" or "reversals"));
            if (unsupported is not null)
            {
                problem = $"has unsupported Transactions focus option '{unsupported}'";
                return false;
            }
        }

        if (mapping.Source == DashboardControlSource.TransactionsBreakdown)
        {
            string? unsupported = options.FirstOrDefault(option => option is not ("group" or "category" or "merchant" or "account" or "type"));
            if (unsupported is not null)
            {
                problem = $"has unsupported Transactions breakdown option '{unsupported}'";
                return false;
            }
        }

        if (mapping.Source == DashboardControlSource.FinancialIndependenceSpendingLookback)
        {
            string? unsupported = options.FirstOrDefault(option => !int.TryParse(option, CultureInfo.InvariantCulture, out int months)
                || months is < 1 or > 120);
            if (unsupported is not null)
            {
                problem = $"has unsupported Financial Independence spending lookback option '{unsupported}'";
                return false;
            }
        }

        problem = null;
        return true;
    }

    private static bool HasDisplaySetter(DashboardControlSource source, DashboardControlKind kind)
        => (source, kind) switch
        {
            (DashboardControlSource.IncomeExcludedCategories, DashboardControlKind.MultiSelect) => true,
            (DashboardControlSource.IncomeDetailTab, DashboardControlKind.TabChoice) => true,
            (DashboardControlSource.IncomeDetailMonth, DashboardControlKind.Select) => true,
            (DashboardControlSource.IncomeAdjustCalculation, DashboardControlKind.Popover) => true,
            (DashboardControlSource.SpendingDetailMonth, DashboardControlKind.Select) => true,
            (DashboardControlSource.SpendingAdjustView, DashboardControlKind.Popover) => true,
            (DashboardControlSource.SubscriptionSettingsOpen, DashboardControlKind.Collapsible) => true,
            (DashboardControlSource.SubscriptionHistoryLookback, DashboardControlKind.Select) => true,
            (DashboardControlSource.SubscriptionTimelineScope, DashboardControlKind.SegmentedChoice) => true,
            (DashboardControlSource.MerchantAdjustView, DashboardControlKind.Popover) => true,
            (DashboardControlSource.MerchantSearch, DashboardControlKind.TextInput) => true,
            (DashboardControlSource.MerchantDetailMonth, DashboardControlKind.Select) => true,
            (DashboardControlSource.MerchantDetailTab, DashboardControlKind.TabChoice) => true,
            (DashboardControlSource.TransactionsMoreFilters, DashboardControlKind.Popover) => true,
            (DashboardControlSource.BudgetAdjustView, DashboardControlKind.Popover) => true,
            (DashboardControlSource.BudgetTransactionCategory, DashboardControlKind.Select) => true,
            (DashboardControlSource.BudgetYearToDate, DashboardControlKind.Collapsible) => true,
            (DashboardControlSource.FinancialIndependenceTargetAmount, DashboardControlKind.NumberInput) => true,
            (DashboardControlSource.FinancialIndependenceAdjustSourceData, DashboardControlKind.Popover) => true,
            (DashboardControlSource.FinancialIndependenceSourceDetails, DashboardControlKind.Collapsible) => true,
            (DashboardControlSource.FinancialIndependenceSourceDetailsTab, DashboardControlKind.TabChoice) => true,
            (DashboardControlSource.DataHealthCheckSettings, DashboardControlKind.Popover) => true,
            (DashboardControlSource.DataHealthSelectedCheck, DashboardControlKind.Select) => true,
            _ => false
        };

    private static string? ReportFilterRouteFor(DashboardControlSource source)
        => source switch
        {
            DashboardControlSource.Lookback => "lookback",
            DashboardControlSource.Spending => "spending",
            DashboardControlSource.SpendingComparison => "spending_comparison",
            DashboardControlSource.SpendingBreakdown => "spending_breakdown",
            DashboardControlSource.SpendingExcludedGroups => "spending_excluded_groups",
            DashboardControlSource.SpendingExcludedCategories => "spending_excluded_categories",
            DashboardControlSource.SpendingIncludedDescriptions => "spending_included_descriptions",
            DashboardControlSource.SpendingExcludedDescriptions => "spending_excluded_descriptions",
            DashboardControlSource.SpendingExcludeLargeExpenses => "spending_exclude_large_expenses",
            DashboardControlSource.SpendingExpenseLimit => "spending_expense_limit",
            DashboardControlSource.YearOverYear => "year_over_year",
            DashboardControlSource.YearOverYearView => "year_over_year_view",
            DashboardControlSource.YearOverYearPresetCategories => "year_over_year_preset_categories",
            DashboardControlSource.YearOverYearSingleCategory => "year_over_year_single_category",
            DashboardControlSource.YearOverYearSingleGroup => "year_over_year_single_group",
            DashboardControlSource.IncomeView => "income_view",
            DashboardControlSource.IncomeLookback => "income_lookback",
            DashboardControlSource.IncomeCalculation => "income_calculation",
            DashboardControlSource.IncomeExcludedIncomeCategories => "income_excluded_income_categories",
            DashboardControlSource.IncomeExcludedExpenseGroups => "income_excluded_expense_groups",
            DashboardControlSource.IncomeExcludedExpenseCategories => "income_excluded_expense_categories",
            DashboardControlSource.IncomeIncludedDescriptions => "income_included_descriptions",
            DashboardControlSource.IncomeExcludedDescriptions => "income_excluded_descriptions",
            DashboardControlSource.IncomeExcludeLargeIncome => "income_exclude_large_income",
            DashboardControlSource.IncomeIncomeLimit => "income_income_limit",
            DashboardControlSource.IncomeExcludeLargeExpenses => "income_exclude_large_expenses",
            DashboardControlSource.IncomeExpenseLimit => "income_expense_limit",
            DashboardControlSource.IncomeTargetRate => "income_target_rate",
            DashboardControlSource.SubscriptionCategories => "subscription_categories",
            DashboardControlSource.SubscriptionDiscoveryExclusions => "subscription_discovery_exclusions",
            DashboardControlSource.SubscriptionMinimumConfidence => "subscription_minimum_confidence",
            DashboardControlSource.MerchantLookback => "merchant_lookback",
            DashboardControlSource.MerchantSpending => "merchant_spending",
            DashboardControlSource.MerchantComparison => "merchant_comparison",
            DashboardControlSource.MerchantExcludedGroups => "merchant_excluded_groups",
            DashboardControlSource.MerchantExcludedCategories => "merchant_excluded_categories",
            DashboardControlSource.MerchantIncludedDescriptions => "merchant_included_descriptions",
            DashboardControlSource.MerchantExcludedDescriptions => "merchant_excluded_descriptions",
            DashboardControlSource.MerchantExcludeLargeExpenses => "merchant_exclude_large_expenses",
            DashboardControlSource.MerchantExpenseLimit => "merchant_expense_limit",
            DashboardControlSource.TransactionsLookback => "transactions_lookback",
            DashboardControlSource.TransactionsType => "transactions_type",
            DashboardControlSource.TransactionsFocus => "transactions_focus",
            DashboardControlSource.TransactionsSearch => "transactions_search",
            DashboardControlSource.TransactionsGroups => "transactions_groups",
            DashboardControlSource.TransactionsCategories => "transactions_categories",
            DashboardControlSource.TransactionsAccounts => "transactions_accounts",
            DashboardControlSource.TransactionsMinimumAmount => "transactions_minimum_amount",
            DashboardControlSource.TransactionsMaximumAmount => "transactions_maximum_amount",
            DashboardControlSource.TransactionsLargestCount => "transactions_largest_count",
            DashboardControlSource.TransactionsBreakdown => "transactions_breakdown",
            DashboardControlSource.HomeTimeFrame => "home_time_frame",
            DashboardControlSource.BudgetMonth => "budget_month",
            DashboardControlSource.BudgetGroups => "budget_groups",
            DashboardControlSource.BudgetExcludedGroups => "budget_excluded_groups",
            DashboardControlSource.BudgetExcludedCategories => "budget_excluded_categories",
            DashboardControlSource.BudgetIncludedDescriptions => "budget_included_descriptions",
            DashboardControlSource.BudgetExcludedDescriptions => "budget_excluded_descriptions",
            DashboardControlSource.BudgetExcludeLargeExpenses => "budget_exclude_large_expenses",
            DashboardControlSource.BudgetExpenseLimit => "budget_expense_limit",
            DashboardControlSource.FinancialIndependenceAssets => "fi_assets",
            DashboardControlSource.FinancialIndependenceSpending => "fi_spending",
            DashboardControlSource.FinancialIndependenceIncome => "fi_income",
            DashboardControlSource.FinancialIndependenceReturnRate => "fi_return_rate",
            DashboardControlSource.FinancialIndependenceWithdrawalRate => "fi_withdrawal_rate",
            DashboardControlSource.FinancialIndependenceProjectionYears => "fi_years",
            DashboardControlSource.FinancialIndependenceIncludedAccounts => "fi_included_accounts",
            DashboardControlSource.FinancialIndependenceSpendingLookback => "fi_spending_lookback",
            DashboardControlSource.FinancialIndependenceExcludedGroups => "fi_excluded_groups",
            DashboardControlSource.FinancialIndependenceExcludedCategories => "fi_excluded_categories",
            DashboardControlSource.FinancialIndependenceIncludedDescriptions => "fi_included_descriptions",
            DashboardControlSource.FinancialIndependenceExcludedDescriptions => "fi_excluded_descriptions",
            DashboardControlSource.FinancialIndependenceExcludeLargeExpenses => "fi_exclude_large_expenses",
            DashboardControlSource.FinancialIndependenceExpenseLimit => "fi_expense_limit",
            DashboardControlSource.DataHealthStaleThreshold => "health_stale_days",
            DashboardControlSource.DataHealthDuplicateDays => "health_duplicate_days",
            DashboardControlSource.DataHealthDuplicateMinimum => "health_duplicate_minimum",
            DashboardControlSource.DataHealthDuplicateSameAccount => "health_same_account",
            DashboardControlSource.DataHealthDuplicateSameCategory => "health_same_category",
            DashboardControlSource.DataHealthDuplicateSameDescription => "health_same_description",
            DashboardControlSource.DataHealthIncludeInactive => "health_include_inactive",
            _ => null
        };

    /// <summary>Parses a configured Spending comparison option.</summary>
    public static bool TryParseSpendingComparison(string? value, out SpendingComparison comparison)
    {
        switch (value)
        {
            case "previous_period":
                comparison = SpendingComparison.PreviousPeriod;
                return true;
            case "last_year":
                comparison = SpendingComparison.LastYear;
                return true;
            default:
                comparison = default;
                return false;
        }
    }

    /// <summary>Parses a configured Spending breakdown option.</summary>
    public static bool TryParseSpendingBreakdown(string? value, out SpendingBreakdown breakdown)
    {
        switch (value)
        {
            case "group":
                breakdown = SpendingBreakdown.Group;
                return true;
            case "category":
                breakdown = SpendingBreakdown.Category;
                return true;
            default:
                breakdown = default;
                return false;
        }
    }
}
