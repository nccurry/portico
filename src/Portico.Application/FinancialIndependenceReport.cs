using Portico.Finance;

namespace Portico.Application;

/// <summary>Selects the source values and annual assumptions for Financial Independence.</summary>
public sealed record FinancialIndependenceReportRequest(
    FinancialIndependenceSourceFilters? Source = null,
    FinancialIndependenceScenario? Scenario = null);

/// <summary>Financial Independence values, before desktop presentation.</summary>
public sealed record FinancialIndependenceReport(
    FinancialIndependenceSourceFilters SourceFilters,
    FinancialIndependenceSourceAnalysis Source,
    FinancialIndependenceScenario Scenario,
    FinancialIndependenceSummary Summary,
    IReadOnlyList<PortfolioProjectionPoint> Projection,
    IReadOnlyList<RunwaySensitivityCell> Sensitivity,
    DateOnly? LatestTransactionDate,
    DateOnly? LatestBalanceDate);

public sealed partial class Workspace
{
    /// <summary>Calculates source, scenario, projection, and sensitivity values.</summary>
    public FinancialIndependenceReport FinancialIndependence(
        FinancialIndependenceReportRequest? request = null)
    {
        request ??= new FinancialIndependenceReportRequest();
        IReadOnlyList<AccountBalance> accounts = PortfolioCalculator.LatestBalances(_snapshot.Balances);
        FinancialIndependenceSourceFilters filters = request.Source
            ?? FinancialIndependenceSourceAnalysisCalculator.DefaultFilters(accounts, _settings);
        FinancialIndependenceSourceAnalysis source = FinancialIndependenceSourceAnalysisCalculator.Build(
            accounts,
            _snapshot.Transactions,
            filters);
        FinancialIndependenceScenario scenario = request.Scenario
            ?? FinancialIndependenceSourceAnalysisCalculator.DefaultScenario(
                source, _settings.FinancialIndependence);
        scenario.Validate();

        FinancialIndependenceSummary summary = FinancialIndependenceCalculator.Summarize(
            scenario.Assets,
            scenario.AnnualSpending,
            scenario.ExpectedReturnRate,
            scenario.AnnualIncome,
            scenario.WithdrawalRate);
        IReadOnlyList<PortfolioProjectionPoint> projection = FinancialIndependenceCalculator.Project(
            scenario.Assets,
            scenario.AnnualSpending,
            scenario.ExpectedReturnRate,
            scenario.ProjectionYears,
            scenario.AnnualIncome);
        decimal[] returnRates = [0m, 3m, 5m, scenario.ExpectedReturnRate, 9m];
        IReadOnlyList<RunwaySensitivityCell> sensitivity = FinancialIndependenceCalculator.BuildSensitivity(
            scenario.Assets,
            scenario.AnnualSpending,
            scenario.AnnualIncome,
            [-20m, -10m, 0m, 10m, 20m],
            returnRates.Distinct().Order().ToArray());

        return new FinancialIndependenceReport(
            filters,
            source,
            scenario,
            summary,
            projection,
            sensitivity,
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden)
                .Select(transaction => (DateOnly?)transaction.Date).Max(),
            _snapshot.Balances.Where(balance => !balance.IsHidden)
                .Select(balance => (DateOnly?)balance.Date).Max());
    }
}
