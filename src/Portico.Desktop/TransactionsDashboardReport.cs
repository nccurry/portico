using System.Globalization;
using Portico.Finance;
using static Portico.Desktop.ExploreDashboardFormatting;

namespace Portico.Desktop;

/// <summary>Page data that the transaction renderer uses beyond individual widgets.</summary>
public sealed record TransactionsPageView(
    string? LatestDataCaption,
    TransactionExplorerAnalysisResult Analysis,
    string? EmptyMessage = null);

public sealed partial record DashboardPageReport
{
    public TransactionsPageView? TransactionsView { get; init; }
}

/// <summary>Turns a filtered transaction inventory into the configured desktop widgets.</summary>
public static class TransactionsDashboardReport
{
    public static DashboardPageReport Build(TransactionExplorerAnalysisResult analysis)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        ReportMetric[] summary =
        [
            Metric("Transactions", analysis.Summary.TransactionCount,
                analysis.Summary.TransactionCount.ToString(CultureInfo.InvariantCulture)),
            Metric("Money out", analysis.Summary.Outflow),
            Metric("Money in", analysis.Summary.Inflow),
            new ReportMetric("Net amount", analysis.Summary.NetAmount, SignedMoney(analysis.Summary.NetAmount),
                analysis.Summary.NetAmount > 0m ? "positive" : analysis.Summary.NetAmount < 0m ? "negative" : null)
        ];
        ReportSeries[] history = analysis.Results
            .GroupBy(entry => entry.Transaction.Kind)
            .OrderBy(group => group.Key)
            .Select(group => Series(group.Key.ToString().ToLowerInvariant(), KindLabel(group.Key),
                group.Select(entry => Point(entry.Transaction.Date, entry.Transaction.Amount,
                    entry.Transaction.Description))))
            .ToArray();
        DashboardWidgetReport table = Table(analysis.Results);
        var widgets = new Dictionary<string, DashboardWidgetReport>(StringComparer.Ordinal)
        {
            ["transactions.summary"] = new(summary, [], [], []),
            ["transactions.history"] = Chart(history),
            ["transactions.breakdown"] = Chart(Series("magnitude", "Total magnitude",
                analysis.Breakdown.Take(12).Select(entry => Point(entry.Entity, entry.Magnitude)))),
            ["transactions.table"] = table,
            ["top.expenses"] = Chart(history.Where(series => series.Id == "expense").ToArray()),
            ["top.incomes"] = Chart(history.Where(series => series.Id == "income").ToArray()),
            ["top.table"] = table
        };
        string? caption = analysis.EndDate is DateOnly date
            ? $"Latest transaction {date.ToString("MMM d, yyyy", CultureInfo.InvariantCulture)}"
            : null;
        return new DashboardPageReport(DashboardPageId.TopTransactions, widgets)
        {
            TransactionsView = new(caption, analysis,
                analysis.Results.Count == 0 ? "No transactions match this view." : null)
        };
    }

    private static DashboardWidgetReport Table(IReadOnlyList<TransactionExplorerEntry> entries)
        => new([], [], ["Date", "Description", "Merchant", "Type", "Group", "Category", "Account", "Amount", "Occurrences", "Flags"],
            entries.Select(entry => new ReportTableRow(
                [Date(entry.Transaction.Date), entry.Transaction.Description, entry.Merchant,
                    KindLabel(entry.Transaction.Kind), entry.Transaction.Group, entry.Transaction.Category,
                    entry.Transaction.Account, SignedMoney(entry.Transaction.Amount),
                    entry.Occurrences.ToString(CultureInfo.InvariantCulture), Flags(entry)],
                entry.Transaction.Amount < 0m ? "negative" : entry.Transaction.Amount > 0m ? "positive" : null))
                .ToArray(),
            entries.Count == 0 ? "No transactions match this view." : null);

    private static string Flags(TransactionExplorerEntry entry)
    {
        var values = new List<string>(3);
        if (entry.IsOneOff)
            values.Add("One-off");
        if (entry.IsUnusual)
            values.Add("Unusual amount");
        if (entry.IsReversal)
            values.Add("Refund / reversal");
        return string.Join(", ", values);
    }

    private static string KindLabel(TransactionKind kind)
        => kind switch
        {
            TransactionKind.Income => "Income",
            TransactionKind.Expense => "Expense",
            TransactionKind.Transfer => "Transfer",
            _ => "Unknown"
        };
}
