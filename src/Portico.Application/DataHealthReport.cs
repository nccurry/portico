using Portico.Finance;

namespace Portico.Application;

/// <summary>Selects Data Health checks and the detail to inspect.</summary>
public sealed record DataHealthReportRequest(
    DataHealthCheckOptions? Options = null,
    string? SelectedCheckId = null);

/// <summary>Classifies one Data Health check without presentation wording.</summary>
public enum DataHealthCheckStatus
{
    Passed,
    NeedsAttention,
    Review
}

/// <summary>One check in the fixed Data Health queue.</summary>
public sealed record DataHealthCheck(
    string Id,
    DataHealthCheckStatus Status,
    decimal FinancialScope,
    IReadOnlyList<DataHealthRecord> Records,
    IReadOnlyList<DataHealthDuplicatePair> DuplicatePairs)
{
    public int FindingCount => Records.Count;
}

/// <summary>Data Health queue and selected detail, before desktop presentation.</summary>
public sealed record DataHealthReport(
    DataHealthCheckOptions Options,
    IReadOnlyList<DataHealthCheck> Checks,
    DataHealthCheck SelectedCheck,
    DateOnly EvaluationDate,
    DateOnly? LatestTransactionDate,
    DateOnly? LatestBalanceDate,
    int TransactionCount,
    int AccountCount,
    bool IsEmpty)
{
    public int NeedsAttention => Checks
        .Where(check => check.Status == DataHealthCheckStatus.NeedsAttention)
        .Sum(check => check.FindingCount);

    public int ReviewItems => Checks
        .Where(check => check.Status == DataHealthCheckStatus.Review)
        .Sum(check => check.FindingCount);
}

public sealed partial class Workspace
{
    /// <summary>Calculates the ordered Data Health queue and selected check.</summary>
    public DataHealthReport DataHealth(DataHealthReportRequest? request = null)
    {
        request ??= new DataHealthReportRequest();
        DataHealthCheckOptions options = request.Options ?? DataHealthCheckOptions.From(_settings);
        DateOnly evaluationDate = _snapshot.LatestDate ?? AsOfDate;
        DataHealthAnalysisResult analysis = DataHealthAnalysisCalculator.Build(
            _snapshot.Transactions,
            _snapshot.Balances,
            options,
            evaluationDate);
        DataHealthCheck[] checks = analysis.Checks.Select(check => new DataHealthCheck(
            check.Id,
            check.Status switch
            {
                "Passed" => DataHealthCheckStatus.Passed,
                "Needs attention" => DataHealthCheckStatus.NeedsAttention,
                "Review" => DataHealthCheckStatus.Review,
                _ => throw new InvalidOperationException("Unknown Data Health check status.")
            },
            check.FinancialScope,
            check.Records,
            check.DuplicatePairs)).ToArray();
        DataHealthCheck selected = checks.FirstOrDefault(check => string.Equals(
            check.Id, request.SelectedCheckId, StringComparison.Ordinal)) ?? checks[0];

        return new DataHealthReport(
            options,
            checks,
            selected,
            evaluationDate,
            analysis.LatestTransactionDate,
            analysis.LatestBalanceDate,
            _snapshot.Transactions.Count(transaction => options.IncludeInactive || !transaction.IsHidden),
            analysis.AccountCount,
            _snapshot.Transactions.Count == 0 && _snapshot.Balances.Count == 0);
    }
}
