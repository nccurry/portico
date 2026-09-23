namespace Portico.Desktop;

/// <summary>The finite widget report names supported by the desktop layout.</summary>
public static class DashboardWidgetReports
{
    public static IReadOnlySet<string> SupportedWidgetReports { get; } = new HashSet<string>(StringComparer.Ordinal)
    {
        "home.net_worth", "home.overview", "home.attribution", "home.accounts", "home.inventory", "home.safety",
        "income.summary", "income.cash_flow", "income.savings_rate", "income.detail", "income.included_categories",
        "income.included_transactions", "income.excluded_transactions", "income.monthly_totals",
        "spending.monthly", "spending.categories",
        "spending.summary", "spending.trend", "spending.ranking", "spending.overview", "spending.detail_summary", "spending.detail_history",
        "spending.detail_categories", "spending.detail_merchants", "spending.detail_transactions", "spending.excluded",
        "yoy.comparison", "yoy.totals",
        "subscriptions.active", "subscriptions.monthly", "subscriptions.summary", "subscriptions.lifecycle", "subscriptions.history_spend", "subscriptions.history_active", "subscriptions.candidates", "subscriptions.inactive", "subscriptions.detail_charge_history", "subscriptions.detail_charges", "subscriptions.detail_monthly_totals",
        "merchants.ranking", "merchants.history", "merchants.summary", "merchants.overview", "merchants.detail_summary", "merchants.detail_history", "merchants.detail_categories", "merchants.detail_accounts", "merchants.detail_descriptions", "merchants.detail_transactions", "merchants.excluded",
        "budget.summary", "budget.pace", "budget.comparison", "budget.performance", "budget.group_summary", "budget.history", "budget.categories", "budget.category_table", "budget.transactions", "budget.ytd_summary", "budget.ytd_table", "budget.table",
        "top.expenses", "top.incomes", "top.table", "transactions.summary", "transactions.history", "transactions.breakdown", "transactions.table",
        "fi.summary", "fi.projection", "fi.funding", "fi.sensitivity", "fi.source_accounts", "fi.source_spending", "fi.source_transactions",
        "health.summary", "health.queue", "health.detail", "health.findings"
    };

}
