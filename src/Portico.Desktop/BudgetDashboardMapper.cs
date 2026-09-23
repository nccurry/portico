using System.Globalization;
using Portico.Application;
using Portico.Finance;
using static Portico.Desktop.PlanHealthFormat;

namespace Portico.Desktop;

public sealed partial record DashboardPageReport
{
    public BudgetPageView? BudgetView { get; init; }
}

/// <summary>Budget detail used by the existing desktop page.</summary>
public sealed record BudgetPageView(
    string? LatestDataCaption,
    BudgetAnalysisResult Analysis,
    string? SelectedGroup,
    string TransactionCategory,
    IReadOnlyList<FinancialTransaction> VisibleTransactions,
    string? EmptyMessage = null);

/// <summary>Turns the semantic Budget report into desktop widgets and copy.</summary>
public static class BudgetDashboardMapper
{
    /// <summary>Convenient for direct callers; the host supplies its workspace date and visibility for exact captions.</summary>
    public static DashboardPageReport Build(BudgetReport report)
    {
        ArgumentNullException.ThrowIfNull(report);
        return Build(report, report.Analysis.Request.ThroughDate, report.Transactions.Count > 0);
    }

    public static DashboardPageReport Build(BudgetReport report, DateOnly reportDate, bool hasVisibleTransactions)
    {
        ArgumentNullException.ThrowIfNull(report);
        BudgetAnalysisResult analysis = report.Analysis;
        BudgetGroupDetail? detail = report.GroupDetail;
        string category = report.SelectedCategory ?? "all";
        string? empty = analysis.EmptyReason switch
        {
            null => null,
            BudgetEmptyReason.NoGroupsSelected => "Select at least one budget group.",
            _ => throw new ArgumentOutOfRangeException(nameof(report))
        };
        DashboardWidgetReport performance = PerformanceTable(analysis.Groups, analysis.MonthProgress, "Group");
        decimal ytdBudget = analysis.YearToDate.Sum(entry => entry.Budget);
        decimal ytdSpent = analysis.YearToDate.Sum(entry => entry.Spent);
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["budget.summary"] = new(SummaryMetrics(analysis), [], [], [], empty),
            ["budget.pace"] = Chart(
                Series("actual", "Actual cumulative", analysis.DailyPace.Select(entry => Point(entry.Date, entry.ActualCumulative))),
                Series("ideal", "Ideal pace", analysis.DailyPace.Select(entry => Point(entry.Date, entry.IdealCumulative)))),
            ["budget.comparison"] = Chart(
                Series("budget", "Budget", analysis.Groups.Select(entry => Point(entry.Entity, entry.Budget))),
                Series("actual", "Spent", analysis.Groups.Select(entry => Point(entry.Entity, entry.Spent)))),
            ["budget.performance"] = performance,
            ["budget.group_summary"] = detail is null
                ? new([], [], [], [], empty ?? "Select a budget group to inspect it.")
                : Metrics(
                    Metric("Spent", detail.Performance.Spent),
                    Metric("Budget", detail.Performance.Budget),
                    Metric("Typical month", detail.Performance.TypicalSpending),
                    Metric("Outside the plan", detail.Performance.OutsidePlan)),
            ["budget.history"] = detail is null
                ? new([], [], [], [], "Select a budget group to see its history.")
                : Chart(
                    Series("budget", "Budget", detail.History.Select(entry => Point(entry.Month.Start, entry.Budget))),
                    Series("spent", "Spent", detail.History.Select(entry => Point(entry.Month.Start, entry.Spent)))),
            ["budget.categories"] = detail is null
                ? new([], [], [], [], "Select a budget group to see its category drivers.")
                : Chart(
                    Series("budget", "Budget", detail.Categories.Select(entry => Point(entry.Entity, entry.Budget))),
                    Series("spent", "Spent", detail.Categories.Select(entry => Point(entry.Entity, entry.Spent)))),
            ["budget.category_table"] = detail is null
                ? new([], [], [], [], "Select a budget group to see its category drivers.")
                : PerformanceTable(detail.Categories, analysis.MonthProgress, "Category"),
            ["budget.transactions"] = new(
                [], [], ["Date", "Category", "Description", "Account", "Net spending"],
                report.Transactions.Select(transaction => new ReportTableRow([
                    Date(transaction.Date), transaction.Category, transaction.Description,
                    transaction.Account, Money(-transaction.Amount)
                ])).ToArray(),
                detail is null ? "Select a budget group to inspect its transactions."
                    : "No transactions match this category selection."),
            ["budget.ytd_summary"] = Metrics(
                Metric("YTD spending", ytdSpent),
                Metric("YTD budget", ytdBudget),
                Metric("YTD remaining", ytdBudget - ytdSpent),
                new ReportMetric("YTD used", ytdBudget > 0m ? ytdSpent / ytdBudget * 100m : null,
                    Percent(ytdBudget > 0m ? ytdSpent / ytdBudget * 100m : null),
                    ytdSpent > ytdBudget && ytdBudget > 0m ? "negative" : null)),
            ["budget.ytd_table"] = PerformanceTable(analysis.YearToDate, 1m, "Group"),
            ["budget.table"] = performance
        };
        return new DashboardPageReport(DashboardPageId.Budget, widgets)
        {
            BudgetView = new BudgetPageView(
                hasVisibleTransactions ? $"Spending through {Date(reportDate)}" : null,
                analysis, report.SelectedGroup, category, report.Transactions, empty)
        };
    }

    private static IReadOnlyList<ReportMetric> SummaryMetrics(BudgetAnalysisResult analysis)
    {
        BudgetSummary summary = analysis.Summary;
        decimal paceDelta = summary.PercentUsed - analysis.MonthProgress * 100m;
        int within = analysis.Groups.Count(entry => entry.Budget > 0m && entry.Spent <= entry.Budget);
        int budgeted = analysis.Groups.Count(entry => entry.Budget > 0m);
        int outside = analysis.Groups.Count(entry => entry.OutsidePlan > 0m);
        return
        [
            new("Spending", summary.Spent, Money(summary.Spent), summary.VersusTypical > 0m ? "negative" : null,
                summary.TypicalSpending > 0m ? $"{SignedMoney(summary.VersusTypical)} vs typical" : null),
            new("Remaining", summary.Remaining, Money(summary.Remaining), summary.Remaining < 0m ? "negative" : null,
                $"{Money(summary.Budget)} budget"),
            new("Budget used", summary.PercentUsed, Percent(summary.PercentUsed), summary.PercentUsed > 100m ? "negative" : null,
                analysis.MonthProgress < 1m ? $"{paceDelta:+0.0;-0.0;0.0} pts vs month elapsed"
                    : $"{within} of {budgeted} groups within budget"),
            new("Outside the plan", summary.OutsidePlan, Money(summary.OutsidePlan), summary.OutsidePlan > 0m ? "negative" : null,
                $"{outside} unbudgeted categories")
        ];
    }

    private static DashboardWidgetReport PerformanceTable(
        IReadOnlyList<BudgetPerformanceEntry> entries, decimal monthProgress, string entityLabel)
        => new([], [], [entityLabel, "Status", "Budget", "Spent", "Remaining", "Used", "Vs typical", "Outside plan"],
            entries.Select(entry =>
            {
                string status = Status(entry, monthProgress);
                return new ReportTableRow([
                    entry.Entity, status, Money(entry.Budget), Money(entry.Spent), Money(entry.Remaining),
                    Percent(entry.PercentUsed), SignedMoney(entry.VersusTypical), Money(entry.OutsidePlan)
                ], status switch { "Over budget" or "Outside plan" => "negative", "Ahead of pace" => "warning", _ => null });
            }).ToArray(),
            entries.Count == 0 ? "No budget data is available for this selection." : null);

    private static string Status(BudgetPerformanceEntry entry, decimal progress)
    {
        if (entry.Budget <= 0m && entry.Spent > 0m)
            return "Outside plan";
        if (entry.Budget > 0m && entry.Spent > entry.Budget)
            return "Over budget";
        if (entry.Budget > 0m && progress < 1m && entry.PercentUsed > progress * 100m + 10m)
            return "Ahead of pace";
        return "On pace";
    }
}
