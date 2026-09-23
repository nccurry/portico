using Portico.Application;

namespace Portico.Desktop;

/// <summary>Maps the existing Home control values to semantic report periods.</summary>
public static class HomeTimeFrameOptions
{
    public static bool TryParse(string? value, out HomePeriod period)
    {
        switch (value)
        {
            case "3m":
                period = HomePeriod.ThreeMonths;
                return true;
            case "6m":
                period = HomePeriod.SixMonths;
                return true;
            case "1y":
                period = HomePeriod.OneYear;
                return true;
            case "2y":
                period = HomePeriod.TwoYears;
                return true;
            case "5y":
                period = HomePeriod.FiveYears;
                return true;
            case "all":
                period = HomePeriod.All;
                return true;
            default:
                period = default;
                return false;
        }
    }
}
