using Portico.Finance;

namespace Portico.Application;

/// <summary>Balance-history periods supported by Home.</summary>
public enum HomePeriod
{
    ThreeMonths,
    SixMonths,
    OneYear,
    TwoYears,
    FiveYears,
    All
}

/// <summary>Selects Home balance history and cash-flow policy.</summary>
public sealed record HomeReportRequest(
    HomePeriod Period = HomePeriod.OneYear,
    int? CashFlowLookbackMonths = null,
    bool? RegularIncome = null);

/// <summary>The requested and available dates for visible balance history.</summary>
public sealed record HomeBalanceWindow(HomePeriod Period, DateOnly RequestedStart, DateOnly Start, DateOnly End);

/// <summary>One mapped group, using signed balances so debt reduces net worth.</summary>
public sealed record HomeGroupMovement(
    string Group,
    decimal OpeningSignedBalance,
    decimal ClosingSignedBalance,
    bool LiabilitiesOnly)
{
    public decimal NetWorthChange => ClosingSignedBalance - OpeningSignedBalance;
}

/// <summary>One visible mapped account, identified by its stable source ID.</summary>
public sealed record HomeAccountMovement(
    string AccountId,
    string Account,
    string Group,
    AccountClass AccountClass,
    decimal OpeningSignedBalance,
    decimal ClosingSignedBalance)
{
    public decimal NetWorthChange => ClosingSignedBalance - OpeningSignedBalance;
}

/// <summary>Financial values for Home, without desktop presentation choices.</summary>
public sealed record HomeReport(
    HomeBalanceWindow? Window,
    IReadOnlyList<NetWorthPoint> NetWorthHistory,
    IReadOnlyList<HomeGroupMovement> Groups,
    IReadOnlyList<HomeAccountMovement> Accounts,
    CashFlowSummary CashFlow,
    FinancialSafetySummary Safety)
{
    public NetWorthPoint? Opening => NetWorthHistory.FirstOrDefault();

    public NetWorthPoint? Closing => NetWorthHistory.LastOrDefault();
}

public sealed partial class Workspace
{
    /// <summary>Calculates Home values from this workspace's fixed portfolio.</summary>
    public HomeReport Home(HomeReportRequest? request = null)
    {
        request ??= new HomeReportRequest();
        int days = request.Period switch
        {
            HomePeriod.ThreeMonths => 90,
            HomePeriod.SixMonths => 180,
            HomePeriod.OneYear => 365,
            HomePeriod.TwoYears => 730,
            HomePeriod.FiveYears => 1825,
            HomePeriod.All => 0,
            _ => throw new ArgumentOutOfRangeException(nameof(request), "Unsupported Home period.")
        };

        HomeBalanceWindow? window = BalanceWindow(_snapshot.Balances, request.Period, days);
        IReadOnlyList<NetWorthPoint> history = window is null ? [] : BuildHistory(_snapshot.Balances, window);
        IReadOnlyList<AccountBalance> closing = window is null
            ? []
            : PortfolioCalculator.LatestBalances(_snapshot.Balances, window.End);
        IReadOnlyList<AccountBalance> opening = window is null
            ? []
            : PortfolioCalculator.LatestBalances(_snapshot.Balances, window.Start);
        var openingById = opening.ToDictionary(account => account.AccountId, StringComparer.Ordinal);

        AccountBalance[] mapped = closing.Where(account => !string.IsNullOrWhiteSpace(account.Group)).ToArray();
        HomeGroupMovement[] groups = mapped
            .GroupBy(account => account.Group, StringComparer.Ordinal)
            .Select(group => new HomeGroupMovement(
                group.Key,
                group.Sum(account => openingById.TryGetValue(account.AccountId, out AccountBalance? previous)
                    ? previous.SignedBalance : 0m),
                group.Sum(account => account.SignedBalance),
                group.All(account => account.AccountClass == AccountClass.Liability)))
            .OrderByDescending(group => decimal.Abs(group.ClosingSignedBalance))
            .ThenBy(group => group.Group, StringComparer.Ordinal)
            .ToArray();
        HomeAccountMovement[] accounts = mapped
            .OrderBy(account => account.Group, StringComparer.Ordinal)
            .ThenByDescending(account => decimal.Abs(account.SignedBalance))
            .ThenBy(account => account.Account, StringComparer.Ordinal)
            .ThenBy(account => account.AccountId, StringComparer.Ordinal)
            .Select(account => new HomeAccountMovement(
                account.AccountId,
                account.Account,
                account.Group,
                account.AccountClass,
                openingById.TryGetValue(account.AccountId, out AccountBalance? previous)
                    ? previous.SignedBalance : 0m,
                account.SignedBalance))
            .ToArray();

        YearMonth? latestMonth = _snapshot.LatestDate is DateOnly date ? YearMonth.From(date) : null;
        int lookbackMonths = request.CashFlowLookbackMonths ?? _settings.Lookback.DefaultMonths;
        if (lookbackMonths <= 0)
            throw new ArgumentOutOfRangeException(nameof(request), "Cash-flow lookback must be positive.");
        YearMonth? startMonth = latestMonth is null
            ? null
            : latestMonth.Value.AddMonths(-Math.Min(
                lookbackMonths - 1,
                (latestMonth.Value.Year - 1) * 12 + latestMonth.Value.Month - 1));
        IncomeExpensePolicy policy = (request.RegularIncome
            ?? string.Equals(_settings.IncomeSavings.DefaultView, "regular", StringComparison.OrdinalIgnoreCase))
            ? IncomeExpensePolicy.From(_settings.IncomeSavings)
            : new IncomeExpensePolicy([], []);
        CashFlowSummary cashFlow = CashFlowCalculator.Summarize(CashFlowCalculator.BuildMonthly(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden),
            policy,
            startMonth,
            startMonth is null ? null : latestMonth));
        FinancialSafetySummary safety = FinancialSafetyCalculator.Summarize(
            _snapshot.Transactions,
            _snapshot.Balances,
            _settings.FinancialSafety,
            _settings.FinancialIndependence,
            AsOfDate);

        return new HomeReport(window, history, groups, accounts, cashFlow, safety);
    }

    private static HomeBalanceWindow? BalanceWindow(
        IReadOnlyList<BalanceObservation> observations,
        HomePeriod period,
        int days)
    {
        DateOnly[] dates = observations
            .Where(observation => !observation.IsHidden)
            .Select(observation => observation.Date)
            .Distinct()
            .Order()
            .ToArray();
        if (dates.Length == 0)
            return null;

        DateOnly earliest = dates[0];
        DateOnly end = dates[^1];
        DateOnly requestedStart = period == HomePeriod.All
            ? earliest
            : end.AddDays(-Math.Min(days, end.DayNumber));
        DateOnly start = requestedStart < earliest ? earliest : requestedStart;
        return new HomeBalanceWindow(period, requestedStart, start, end);
    }

    private static IReadOnlyList<NetWorthPoint> BuildHistory(
        IReadOnlyList<BalanceObservation> observations,
        HomeBalanceWindow window)
    {
        var dates = new SortedSet<DateOnly> { window.Start, window.End };
        int daysUntilSunday = ((int)DayOfWeek.Sunday - (int)window.Start.DayOfWeek + 7) % 7;
        if (daysUntilSunday > window.End.DayNumber - window.Start.DayNumber)
            return dates.Select(date => NetWorthAt(observations, date)).ToArray();

        for (DateOnly date = window.Start.AddDays(daysUntilSunday); date <= window.End;)
        {
            dates.Add(date);
            if (window.End.DayNumber - date.DayNumber < 7)
                break;
            date = date.AddDays(7);
        }

        return dates.Select(date => NetWorthAt(observations, date)).ToArray();
    }

    private static NetWorthPoint NetWorthAt(IReadOnlyList<BalanceObservation> observations, DateOnly date)
    {
        IReadOnlyList<AccountBalance> accounts = PortfolioCalculator.LatestBalances(observations, date);
        decimal assets = accounts.Where(account => account.AccountClass == AccountClass.Asset)
            .Sum(account => account.SignedBalance);
        decimal liabilities = accounts.Where(account => account.AccountClass == AccountClass.Liability)
            .Sum(account => account.SignedBalance);
        return new NetWorthPoint(date, assets, liabilities, assets + liabilities);
    }
}
