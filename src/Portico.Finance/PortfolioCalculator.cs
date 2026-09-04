namespace Portico.Finance;

/// <summary>Represents an account's latest signed balance.</summary>
public sealed record AccountBalance(string Account, string Group, decimal SignedBalance, AccountClass AccountClass);

/// <summary>Represents a net-worth total for one date.</summary>
public sealed record NetWorthPoint(DateOnly Date, decimal Assets, decimal Liabilities, decimal NetWorth);

/// <summary>Calculates net-worth and account views from balance observations.</summary>
public static class PortfolioCalculator
{
    /// <summary>Gets one latest signed balance per visible account as of a date.</summary>
    public static IReadOnlyList<AccountBalance> LatestBalances(
        IEnumerable<BalanceObservation> observations,
        DateOnly? asOf = null,
        IEnumerable<string>? accounts = null)
    {
        ArgumentNullException.ThrowIfNull(observations);

        var selected = accounts is null ? null : new HashSet<string>(accounts, StringComparer.Ordinal);
        var latest = new Dictionary<string, BalanceObservation>(StringComparer.Ordinal);
        foreach (BalanceObservation observation in observations)
        {
            if (observation.IsHidden
                || asOf.HasValue && observation.Date > asOf.Value
                || selected is not null && !selected.Contains(observation.Account))
            {
                continue;
            }

            if (!latest.TryGetValue(observation.AccountId, out BalanceObservation? current)
                || observation.Date > current.Date
                || observation.Date == current.Date && observation.Time >= current.Time)
            {
                latest[observation.AccountId] = observation;
            }
        }

        return latest.Values
            .Select(value => new AccountBalance(
                value.Account,
                value.Group,
                value.AccountClass == AccountClass.Liability ? -value.Balance : value.Balance,
                value.AccountClass))
            .OrderBy(value => value.Group, StringComparer.Ordinal)
            .ThenBy(value => value.Account, StringComparer.Ordinal)
            .ToArray();
    }

    /// <summary>Builds a net-worth history from the latest account value at each observed date.</summary>
    public static IReadOnlyList<NetWorthPoint> BuildNetWorthHistory(IEnumerable<BalanceObservation> observations)
    {
        ArgumentNullException.ThrowIfNull(observations);

        BalanceObservation[] values = observations.Where(value => !value.IsHidden).ToArray();
        DateOnly[] dates = values.Select(value => value.Date).Distinct().Order().ToArray();
        var history = new List<NetWorthPoint>(dates.Length);
        foreach (DateOnly date in dates)
        {
            IReadOnlyList<AccountBalance> balances = LatestBalances(values, date);
            decimal assets = balances.Where(value => value.AccountClass == AccountClass.Asset).Sum(value => value.SignedBalance);
            decimal liabilities = balances.Where(value => value.AccountClass == AccountClass.Liability).Sum(value => value.SignedBalance);
            history.Add(new NetWorthPoint(date, assets, liabilities, assets + liabilities));
        }

        return history;
    }
}
