using System.Globalization;

namespace Portico.Finance;

/// <summary>Identifies one calendar month without a time zone or a day.</summary>
public readonly record struct YearMonth : IComparable<YearMonth>
{
    /// <summary>Creates a calendar month.</summary>
    public YearMonth(int year, int month)
    {
        if (year is < 1 or > 9999)
            throw new ArgumentOutOfRangeException(nameof(year));
        if (month is < 1 or > 12)
            throw new ArgumentOutOfRangeException(nameof(month));

        Year = year;
        Month = month;
    }

    /// <summary>Gets the four-digit calendar year.</summary>
    public int Year { get; }

    /// <summary>Gets the one-based calendar month.</summary>
    public int Month { get; }

    /// <summary>Gets the first day of this month.</summary>
    public DateOnly Start => new(Year, Month, 1);

    /// <summary>Gets the last day of this month.</summary>
    public DateOnly End => Start.AddMonths(1).AddDays(-1);

    /// <summary>Creates a month from a date.</summary>
    public static YearMonth From(DateOnly value) => new(value.Year, value.Month);

    /// <summary>Parses an ISO year-month value.</summary>
    public static YearMonth Parse(string value)
    {
        if (!TryParse(value, out YearMonth month))
            throw new FormatException("A month must use the YYYY-MM format.");

        return month;
    }

    /// <summary>Tries to parse an ISO year-month value.</summary>
    public static bool TryParse(string? value, out YearMonth month)
    {
        month = default;
        if (string.IsNullOrWhiteSpace(value) || value.Length != 7 || value[4] != '-')
            return false;

        return int.TryParse(value[..4], CultureInfo.InvariantCulture, out int year)
            && int.TryParse(value[5..], CultureInfo.InvariantCulture, out int number)
            && TryCreate(year, number, out month);
    }

    /// <summary>Returns all months from the inclusive start through the inclusive end.</summary>
    public static IReadOnlyList<YearMonth> InclusiveRange(YearMonth start, YearMonth end)
    {
        if (start.CompareTo(end) > 0)
            return [];

        var months = new List<YearMonth>();
        for (YearMonth current = start; current.CompareTo(end) <= 0; current = current.AddMonths(1))
            months.Add(current);
        return months;
    }

    /// <summary>Adds whole calendar months.</summary>
    public YearMonth AddMonths(int months)
    {
        DateOnly result = Start.AddMonths(months);
        return From(result);
    }

    /// <inheritdoc />
    public int CompareTo(YearMonth other)
    {
        int year = Year.CompareTo(other.Year);
        return year != 0 ? year : Month.CompareTo(other.Month);
    }

    /// <inheritdoc />
    public override string ToString() => $"{Year:D4}-{Month:D2}";

    private static bool TryCreate(int year, int month, out YearMonth value)
    {
        value = default;
        if (year is < 1 or > 9999 || month is < 1 or > 12)
            return false;

        value = new YearMonth(year, month);
        return true;
    }
}
