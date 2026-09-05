using Portico.Finance;

namespace Portico.Dashboard;

/// <summary>Represents the finite Home time-frame choices from the reference dashboard.</summary>
public enum HomeTimeFrame
{
    /// <summary>Shows the preceding ninety days.</summary>
    ThreeMonths,

    /// <summary>Shows the preceding one hundred and eighty days.</summary>
    SixMonths,

    /// <summary>Shows the preceding three hundred and sixty-five days.</summary>
    OneYear,

    /// <summary>Shows the preceding seven hundred and thirty days.</summary>
    TwoYears,

    /// <summary>Shows the preceding one thousand eight hundred and twenty-five days.</summary>
    FiveYears,

    /// <summary>Shows every available balance observation.</summary>
    All
}

/// <summary>Describes the effective balance-history window used by the Home report.</summary>
public sealed record HomeReportRange(
    HomeTimeFrame TimeFrame,
    DateOnly RequestedStart,
    DateOnly Start,
    DateOnly End)
{
    /// <summary>
    /// Creates the selected Home balance window from visible balance observations.
    ///
    /// The day counts intentionally match <c>Home.py</c>: 90, 180, 365, 730,
    /// and 1825 days. The effective start cannot precede the first visible
    /// balance. This keeps a five-year or All selection independent from the
    /// shared transaction lookback.
    /// </summary>
    public static HomeReportRange? Create(
        IEnumerable<BalanceObservation> observations,
        HomeTimeFrame timeFrame)
    {
        ArgumentNullException.ThrowIfNull(observations);

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
        DateOnly requestedStart = timeFrame == HomeTimeFrame.All
            ? earliest
            : end.AddDays(-DaysFor(timeFrame));
        DateOnly start = requestedStart < earliest ? earliest : requestedStart;
        return new HomeReportRange(timeFrame, requestedStart, start, end);
    }

    /// <summary>Parses a configured Home control value.</summary>
    public static HomeTimeFrame Parse(string value)
    {
        if (TryParse(value, out HomeTimeFrame timeFrame))
            return timeFrame;

        throw new ArgumentException($"Unsupported Home time frame '{value}'.", nameof(value));
    }

    /// <summary>Checks whether a configured Home control value is supported.</summary>
    public static bool TryParse(string? value, out HomeTimeFrame timeFrame)
    {
        switch (value)
        {
            case "3m":
                timeFrame = HomeTimeFrame.ThreeMonths;
                return true;
            case "6m":
                timeFrame = HomeTimeFrame.SixMonths;
                return true;
            case "1y":
                timeFrame = HomeTimeFrame.OneYear;
                return true;
            case "2y":
                timeFrame = HomeTimeFrame.TwoYears;
                return true;
            case "5y":
                timeFrame = HomeTimeFrame.FiveYears;
                return true;
            case "all":
                timeFrame = HomeTimeFrame.All;
                return true;
            default:
                timeFrame = default;
                return false;
        }
    }

    /// <summary>Formats a Home time-frame value for the configured control.</summary>
    public static string Format(HomeTimeFrame timeFrame)
        => timeFrame switch
        {
            HomeTimeFrame.ThreeMonths => "3m",
            HomeTimeFrame.SixMonths => "6m",
            HomeTimeFrame.OneYear => "1y",
            HomeTimeFrame.TwoYears => "2y",
            HomeTimeFrame.FiveYears => "5y",
            HomeTimeFrame.All => "all",
            _ => throw new ArgumentOutOfRangeException(nameof(timeFrame), timeFrame, "Unsupported Home time frame.")
        };

    /// <summary>Gets the source control label for one time frame.</summary>
    public static string Label(HomeTimeFrame timeFrame)
        => timeFrame switch
        {
            HomeTimeFrame.ThreeMonths => "3M",
            HomeTimeFrame.SixMonths => "6M",
            HomeTimeFrame.OneYear => "1Y",
            HomeTimeFrame.TwoYears => "2Y",
            HomeTimeFrame.FiveYears => "5Y",
            HomeTimeFrame.All => "All",
            _ => throw new ArgumentOutOfRangeException(nameof(timeFrame), timeFrame, "Unsupported Home time frame.")
        };

    private static int DaysFor(HomeTimeFrame timeFrame)
        => timeFrame switch
        {
            HomeTimeFrame.ThreeMonths => 90,
            HomeTimeFrame.SixMonths => 180,
            HomeTimeFrame.OneYear => 365,
            HomeTimeFrame.TwoYears => 730,
            HomeTimeFrame.FiveYears => 1825,
            HomeTimeFrame.All => 0,
            _ => throw new ArgumentOutOfRangeException(nameof(timeFrame), timeFrame, "Unsupported Home time frame.")
        };
}
