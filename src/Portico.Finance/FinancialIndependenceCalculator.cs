namespace Portico.Finance;

/// <summary>Represents the financial-independence funding and runway result.</summary>
public sealed record FinancialIndependenceSummary(
    decimal AnnualReturn,
    decimal AnnualIncome,
    decimal AnnualSpending,
    decimal AnnualSurplus,
    decimal NetAnnualSpending,
    decimal SustainableSpending,
    decimal FinancialIndependenceTarget,
    decimal FundingGap,
    decimal? RunwayYears);

/// <summary>Represents one year of a portfolio projection.</summary>
public sealed record PortfolioProjectionPoint(
    int Year,
    decimal StartingBalance,
    decimal InvestmentReturn,
    decimal Income,
    decimal Spending,
    decimal Balance);

/// <summary>Represents one cell in a financial-independence sensitivity grid.</summary>
public sealed record RunwaySensitivityCell(decimal AnnualSpending, decimal ReturnRate, decimal? RunwayYears);

/// <summary>Calculates financial-independence funding, projection, and sensitivity results.</summary>
public static class FinancialIndependenceCalculator
{
    /// <summary>Calculates funding and runway values using annual assumptions.</summary>
    public static FinancialIndependenceSummary Summarize(
        decimal portfolioValue,
        decimal annualSpending,
        decimal returnRatePercent,
        decimal annualIncome = 0m,
        decimal withdrawalRatePercent = 4m)
    {
        decimal rate = returnRatePercent / 100m;
        decimal annualReturn = portfolioValue * rate;
        decimal netWithdrawal = annualSpending - annualIncome;
        decimal netAnnualSpending = decimal.Max(netWithdrawal, 0m);
        decimal withdrawalRate = withdrawalRatePercent / 100m;
        decimal target = netAnnualSpending == 0m ? 0m : withdrawalRate > 0m ? netAnnualSpending / withdrawalRate : decimal.MaxValue;

        return new FinancialIndependenceSummary(
            annualReturn,
            annualIncome,
            annualSpending,
            annualReturn + annualIncome - annualSpending,
            netAnnualSpending,
            portfolioValue * withdrawalRate,
            target,
            portfolioValue - target,
            CalculateRunway(portfolioValue, annualSpending, returnRatePercent, annualIncome));
    }

    /// <summary>Projects the annual portfolio recurrence through a requested number of years.</summary>
    public static IReadOnlyList<PortfolioProjectionPoint> Project(
        decimal portfolioValue,
        decimal annualSpending,
        decimal returnRatePercent,
        int years,
        decimal annualIncome = 0m)
    {
        if (years is < 0 or > 100)
            throw new ArgumentOutOfRangeException(nameof(years));

        decimal rate = returnRatePercent / 100m;
        decimal balance = portfolioValue;
        var result = new List<PortfolioProjectionPoint>(years + 1)
        {
            new(0, balance, 0m, 0m, 0m, balance)
        };
        for (int year = 1; year <= years; year++)
        {
            decimal startingBalance = balance;
            decimal investmentReturn = startingBalance * rate;
            balance = decimal.Max(startingBalance + investmentReturn + annualIncome - annualSpending, 0m);
            result.Add(new PortfolioProjectionPoint(year, startingBalance, investmentReturn, annualIncome, annualSpending, balance));
        }

        return result;
    }

    /// <summary>Builds a stable row-major sensitivity grid around baseline assumptions.</summary>
    public static IReadOnlyList<RunwaySensitivityCell> BuildSensitivity(
        decimal portfolioValue,
        decimal annualSpending,
        decimal annualIncome,
        IReadOnlyList<decimal> spendingChangesPercent,
        IReadOnlyList<decimal> returnRatesPercent)
    {
        ArgumentNullException.ThrowIfNull(spendingChangesPercent);
        ArgumentNullException.ThrowIfNull(returnRatesPercent);

        var result = new List<RunwaySensitivityCell>(spendingChangesPercent.Count * returnRatesPercent.Count);
        foreach (decimal spendingChange in spendingChangesPercent)
        {
            decimal scenarioSpending = annualSpending * (1m + spendingChange / 100m);
            foreach (decimal returnRate in returnRatesPercent)
                result.Add(new RunwaySensitivityCell(
                    scenarioSpending,
                    returnRate,
                    CalculateRunway(portfolioValue, scenarioSpending, returnRate, annualIncome)));
        }

        return result;
    }

    private static decimal? CalculateRunway(
        decimal portfolioValue,
        decimal annualSpending,
        decimal returnRatePercent,
        decimal annualIncome)
    {
        decimal netWithdrawal = annualSpending - annualIncome;
        decimal rate = returnRatePercent / 100m;
        if (annualSpending <= 0m || netWithdrawal <= 0m)
            return null;
        if (portfolioValue <= 0m)
            return 0m;
        if (rate <= 0m)
            return portfolioValue / netWithdrawal;
        if (portfolioValue * rate >= netWithdrawal)
            return null;

        double numerator = (double)netWithdrawal;
        double denominator = (double)(netWithdrawal - portfolioValue * rate);
        double years = Math.Log(numerator / denominator) / Math.Log(1d + (double)rate);
        return decimal.CreateChecked(years);
    }
}
