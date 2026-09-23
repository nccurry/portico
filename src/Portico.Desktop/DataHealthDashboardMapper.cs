using System.Globalization;
using Portico.Application;
using Portico.Finance;
using static Portico.Desktop.PlanHealthFormat;

namespace Portico.Desktop;

public sealed partial record DashboardPageReport
{
    public DataHealthPageView? DataHealthView { get; init; }
}

/// <summary>One named check shown by the desktop's Data Health page.</summary>
public sealed record DataHealthCheckView(DataHealthCheck Check, string Name, string Action, string Status)
{
    public string Id => Check.Id;
    public int FindingCount => Check.FindingCount;
    public decimal FinancialScope => Check.FinancialScope;
    public IReadOnlyList<DataHealthRecord> Records => Check.Records;
    public IReadOnlyList<DataHealthDuplicatePair> DuplicatePairs => Check.DuplicatePairs;
};

/// <summary>The ordered check list used by the existing desktop renderer.</summary>
public sealed record DataHealthAnalysisView(IReadOnlyList<DataHealthCheckView> Checks);

/// <summary>Data Health page detail with wording owned by Desktop.</summary>
public sealed record DataHealthPageView(
    string? LatestDataCaption,
    DataHealthAnalysisView Analysis,
    string SelectedCheckId,
    DataHealthCheckView SelectedCheck,
    string? EmptyMessage = null);

/// <summary>Turns typed Data Health checks into the existing desktop widgets.</summary>
public static class DataHealthDashboardMapper
{
    public static DashboardPageReport Build(DataHealthReport report)
    {
        ArgumentNullException.ThrowIfNull(report);
        DataHealthCheckView[] checks = report.Checks.Select(check => new DataHealthCheckView(
            check, CheckName(check.Kind), CheckAction(check.Kind), StatusName(check.Status))).ToArray();
        DataHealthCheckView selected = checks.Single(check => check.Id == report.SelectedCheck.Id);
        DashboardWidgetReport queue = new([], [],
            ["Status", "Check", "Findings", "Financial scope", "Next step"],
            checks.Select(check => new ReportTableRow([
                check.Status,
                check.Name,
                check.FindingCount.ToString(CultureInfo.InvariantCulture),
                check.FindingCount == 0 ? "—" : Money(check.FinancialScope),
                check.Action
            ], Tone(check.Check.Status))).ToArray());
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["health.summary"] = Metrics(
                new ReportMetric("Needs attention", report.NeedsAttention,
                    report.NeedsAttention.ToString(CultureInfo.InvariantCulture),
                    report.NeedsAttention == 0 ? "positive" : "negative"),
                new ReportMetric("Review items", report.ReviewItems,
                    report.ReviewItems.ToString(CultureInfo.InvariantCulture),
                    report.ReviewItems == 0 ? "positive" : "warning"),
                new ReportMetric("Transactions through", report.LatestTransactionDate?.DayNumber,
                    DateOrNoData(report.LatestTransactionDate), null,
                    $"{report.TransactionCount.ToString(CultureInfo.InvariantCulture)} rows"),
                new ReportMetric("Balances through", report.LatestBalanceDate?.DayNumber,
                    DateOrNoData(report.LatestBalanceDate), null,
                    $"{report.AccountCount.ToString(CultureInfo.InvariantCulture)} accounts")),
            ["health.queue"] = queue,
            ["health.detail"] = Detail(selected),
            ["health.findings"] = queue
        };
        return new DashboardPageReport(DashboardPageId.DataHealth, widgets)
        {
            DataHealthView = new DataHealthPageView(
                "Review source freshness, mapping gaps, and suspicious records.",
                new DataHealthAnalysisView(checks), selected.Id, selected,
                report.IsEmpty ? "No transaction or balance data is available." : null)
        };
    }

    private static DashboardWidgetReport Detail(DataHealthCheckView check)
    {
        if (check.Check.Kind == DataHealthCheckKind.Duplicates)
            return new([], [],
                ["Date 1", "Date 2", "Days apart", "Amount", "Account 1", "Account 2", "Description 1", "Description 2"],
                check.DuplicatePairs.Select(pair => new ReportTableRow([
                    Date(pair.First.Date), Date(pair.Second.Date), pair.DaysApart.ToString(CultureInfo.InvariantCulture),
                    Money(decimal.Abs(pair.First.Amount)), pair.First.Account, pair.Second.Account,
                    pair.First.Description, pair.Second.Description
                ], "warning")).ToArray(),
                check.FindingCount == 0 ? "No findings for this check." : null);

        if (check.Check.Kind is DataHealthCheckKind.AccountMapping or DataHealthCheckKind.StaleAccounts)
            return new([], [],
                ["Latest date", "Account", "Group", "Balance",
                    check.Check.Kind == DataHealthCheckKind.StaleAccounts ? "Days stale" : "Missing fields"],
                check.Records.Select(record => new ReportTableRow([
                    DateOrNoData(record.Date), record.Account, record.Group,
                    record.Amount is null ? "—" : Money(record.Amount.Value), DetailsText(record.Details)
                ], Tone(check.Check.Status))).ToArray(),
                check.FindingCount == 0 ? "No findings for this check." : null);

        string detailsColumn = check.Check.Kind switch
        {
            DataHealthCheckKind.IncompleteTransactions => "Missing fields",
            DataHealthCheckKind.Reversals => "Review reason",
            _ => "Details"
        };
        return new([], [], ["Date", "Description", "Account", "Category", "Group", "Amount", detailsColumn],
            check.Records.Select(record => new ReportTableRow([
                DateOrNoData(record.Date), record.Description, record.Account, record.Category, record.Group,
                record.Amount is null ? "—" : Money(record.Amount.Value), DetailsText(record.Details)
            ], Tone(check.Check.Status))).ToArray(),
            check.FindingCount == 0 ? "No findings for this check." : null);
    }

    private static string DetailsText(DataHealthRecordDetail? details)
        => details switch
        {
            null => string.Empty,
            DataHealthMissingFields missing => string.Join(", ", missing.Fields.Select(MissingFieldName)),
            DataHealthStaleDays stale => $"{stale.Days.ToString(CultureInfo.InvariantCulture)} days old",
            DataHealthReversal reversal => reversal.Kind switch
            {
                DataHealthReversalKind.ExpenseRefund => "Expense refund",
                DataHealthReversalKind.IncomeReversal => "Income reversal",
                _ => throw new ArgumentOutOfRangeException(nameof(details))
            }
        };

    private static string MissingFieldName(DataHealthMissingField field)
        => field switch
        {
            DataHealthMissingField.AccountId => "Account ID",
            DataHealthMissingField.Account => "Account",
            DataHealthMissingField.Description => "Description",
            DataHealthMissingField.Group => "Group",
            _ => throw new ArgumentOutOfRangeException(nameof(field))
        };

    private static string? Tone(DataHealthCheckStatus status) => status switch
    {
        DataHealthCheckStatus.NeedsAttention => "negative",
        DataHealthCheckStatus.Review => "warning",
        DataHealthCheckStatus.Passed => "positive",
        _ => throw new ArgumentOutOfRangeException(nameof(status))
    };

    private static string StatusName(DataHealthCheckStatus status) => status switch
    {
        DataHealthCheckStatus.Passed => "Passed",
        DataHealthCheckStatus.NeedsAttention => "Needs attention",
        DataHealthCheckStatus.Review => "Review",
        _ => throw new ArgumentOutOfRangeException(nameof(status))
    };

    private static string CheckName(DataHealthCheckKind kind) => kind switch
    {
        DataHealthCheckKind.Uncategorized => "Missing classifications",
        DataHealthCheckKind.IncompleteTransactions => "Missing transaction details",
        DataHealthCheckKind.AccountMapping => "Account mapping gaps",
        DataHealthCheckKind.StaleAccounts => "Stale balance accounts",
        DataHealthCheckKind.Duplicates => "Potential duplicate transactions",
        DataHealthCheckKind.Reversals => "Refunds and income reversals",
        _ => throw new ArgumentOutOfRangeException(nameof(kind))
    };

    private static string CheckAction(DataHealthCheckKind kind) => kind switch
    {
        DataHealthCheckKind.Uncategorized => "Assign a category with a valid group and type.",
        DataHealthCheckKind.IncompleteTransactions => "Fill the missing identifying fields in the Transactions sheet.",
        DataHealthCheckKind.AccountMapping => "Map each account to an ID, group, and asset or liability class.",
        DataHealthCheckKind.StaleAccounts => "Refresh or reconnect accounts that stopped reporting balances.",
        DataHealthCheckKind.Duplicates => "Confirm whether each pair represents the same underlying charge.",
        DataHealthCheckKind.Reversals => "Confirm that refunds, clawbacks, and corrections are categorized as intended.",
        _ => throw new ArgumentOutOfRangeException(nameof(kind))
    };
}
