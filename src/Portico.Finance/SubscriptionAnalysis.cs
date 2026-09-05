namespace Portico.Finance;

/// <summary>Represents one normalized expense charge used by subscription analysis.</summary>
public sealed record SubscriptionChargeEntry(FinancialTransaction Transaction, string Merchant, decimal Amount);

/// <summary>Represents one known or detected subscription inventory item.</summary>
public sealed record SubscriptionInventoryEntry(
    string Merchant,
    string Source,
    string Status,
    string Cadence,
    int Confidence,
    DateOnly FirstDate,
    DateOnly LastDate,
    DateOnly? NextExpectedDate,
    decimal? MonthlyRunRate,
    decimal TrailingTwelveMonthSpend,
    decimal PriceChange,
    DateOnly? PriceChangeDate,
    string Category,
    string Account,
    int ChargeCount,
    string BundleType);

/// <summary>Represents one observed and inferred subscription lifecycle episode.</summary>
public sealed record SubscriptionLifecycleEntry(
    string Merchant,
    int Episode,
    DateOnly EpisodeStart,
    DateOnly ObservedEnd,
    DateOnly ActiveUntil,
    DateOnly InactiveAfter,
    DateOnly DisplayEnd,
    string Status,
    bool IsCurrent,
    string Cadence,
    string Category,
    string Account,
    int ChargeCount,
    decimal LatestChargeAmount,
    decimal? MonthlyRunRate,
    DateOnly? NextExpectedDate,
    decimal PriceChange,
    DateOnly? PriceChangeDate);

/// <summary>Represents one month in the source subscription history charts.</summary>
public sealed record SubscriptionHistoryEntry(
    YearMonth Month,
    decimal ActualSpend,
    decimal RollingAverage,
    int ActiveMerchants);

/// <summary>Represents the source subscription metric deck.</summary>
public sealed record SubscriptionAnalysisSummary(
    int ActiveCount,
    decimal MonthlyRunRate,
    decimal TrailingTwelveMonthSpend,
    decimal PriorTwelveMonthSpend,
    decimal? AnnualChangePercent,
    int PendingEstimateCount);

/// <summary>Contains the typed financial output for the source Subscriptions page.</summary>
public sealed record SubscriptionAnalysisResult(
    DateOnly? LatestDataDate,
    IReadOnlyList<SubscriptionInventoryEntry> Inventory,
    IReadOnlyList<SubscriptionInventoryEntry> Active,
    IReadOnlyList<SubscriptionInventoryEntry> Candidates,
    IReadOnlyList<SubscriptionInventoryEntry> Inactive,
    IReadOnlyList<SubscriptionLifecycleEntry> Lifecycles,
    IReadOnlyList<SubscriptionHistoryEntry> History,
    SubscriptionAnalysisSummary Summary,
    IReadOnlyList<SubscriptionChargeEntry> KnownCharges,
    IReadOnlyList<SubscriptionChargeEntry> CandidateCharges);

/// <summary>Builds source-compatible subscription inventory, discovery, lifecycle, and history results.</summary>
public static class SubscriptionAnalysisCalculator
{
    private static readonly (string Cadence, int Days, int Months, int MinimumGap, int MaximumGap)[] Cadences =
    [
        ("Monthly", 30, 1, 20, 40),
        ("Quarterly", 91, 3, 75, 105),
        ("Annual", 365, 12, 330, 400)
    ];

    /// <summary>Builds every source subscription page region from the current settings and controls.</summary>
    public static SubscriptionAnalysisResult Build(
        IEnumerable<FinancialTransaction> transactions,
        SubscriptionSettings settings,
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases,
        IEnumerable<string> subscriptionCategories,
        IEnumerable<string> discoveryExclusions,
        int minimumConfidence)
    {
        ArgumentNullException.ThrowIfNull(transactions);
        ArgumentNullException.ThrowIfNull(settings);
        ArgumentNullException.ThrowIfNull(aliases);
        ArgumentNullException.ThrowIfNull(subscriptionCategories);
        ArgumentNullException.ThrowIfNull(discoveryExclusions);
        if (minimumConfidence is < 70 or > 100)
            throw new ArgumentOutOfRangeException(nameof(minimumConfidence));

        FinancialTransaction[] source = transactions.ToArray();
        if (source.Length == 0)
            return Empty();

        DateOnly latest = source.Max(transaction => transaction.Date);
        string[] selectedCategories = Values(subscriptionCategories);
        string[] excludedCategories = Values(discoveryExclusions);
        SubscriptionChargeEntry[] expenses = source
            .Where(transaction => transaction.Kind == TransactionKind.Expense)
            .Select(transaction => new SubscriptionChargeEntry(
                transaction,
                MerchantNameNormalizer.Normalize(transaction.Description, aliases),
                decimal.Abs(transaction.Amount)))
            .OrderBy(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .ToArray();
        SubscriptionChargeEntry[] known = expenses
            .Where(entry => selectedCategories.Contains(entry.Transaction.Category, StringComparer.Ordinal))
            .ToArray();
        SubscriptionInventoryEntry[] inventory = known
            .GroupBy(entry => entry.Merchant, StringComparer.Ordinal)
            .Select(group => CreateInventory(group.ToArray(), latest, "Categorized"))
            .OrderBy(entry => entry.Status, StringComparer.Ordinal)
            .ThenByDescending(entry => entry.FirstDate)
            .ThenBy(entry => entry.Merchant, StringComparer.Ordinal)
            .ToArray();
        SubscriptionLifecycleEntry[] lifecycles = BuildLifecycles(known, inventory, latest);
        SubscriptionInventoryEntry[] candidates = FindCandidates(
            expenses,
            selectedCategories,
            excludedCategories,
            settings.DetectionExcludedCategories,
            latest,
            minimumConfidence);
        SubscriptionHistoryEntry[] history = BuildHistory(known, lifecycles, latest);
        SubscriptionInventoryEntry[] active = inventory
            .Where(entry => string.Equals(entry.Status, "Active", StringComparison.Ordinal))
            .OrderByDescending(entry => CurrentEpisodeStart(lifecycles, entry.Merchant) ?? entry.FirstDate)
            .ThenBy(entry => entry.Merchant, StringComparer.Ordinal)
            .ToArray();
        SubscriptionInventoryEntry[] inactive = inventory
            .Where(entry => string.Equals(entry.Status, "Inactive", StringComparison.Ordinal))
            .OrderByDescending(entry => entry.LastDate)
            .ThenBy(entry => entry.Merchant, StringComparer.Ordinal)
            .ToArray();
        SubscriptionChargeEntry[] candidateCharges = expenses
            .Where(entry => EligibleCandidate(entry, selectedCategories, excludedCategories, settings.DetectionExcludedCategories))
            .ToArray();
        return new SubscriptionAnalysisResult(
            latest,
            inventory,
            active,
            candidates,
            inactive,
            lifecycles,
            history,
            Summarize(inventory, known, latest),
            known,
            candidateCharges);
    }

    /// <summary>Returns the selected merchant's source charges for an inventory or detected candidate row.</summary>
    public static IReadOnlyList<SubscriptionChargeEntry> ChargesFor(
        SubscriptionAnalysisResult analysis,
        string merchant,
        bool candidate)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        ArgumentException.ThrowIfNullOrWhiteSpace(merchant);
        IReadOnlyList<SubscriptionChargeEntry> source = candidate ? analysis.CandidateCharges : analysis.KnownCharges;
        return source
            .Where(entry => string.Equals(entry.Merchant, merchant, StringComparison.Ordinal))
            .OrderByDescending(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .ToArray();
    }

    private static SubscriptionAnalysisResult Empty()
        => new(
            null,
            [],
            [],
            [],
            [],
            [],
            [],
            new SubscriptionAnalysisSummary(0, 0m, 0m, 0m, null, 0),
            [],
            []);

    private static SubscriptionInventoryEntry[] FindCandidates(
        IReadOnlyList<SubscriptionChargeEntry> expenses,
        IReadOnlyList<string> selectedCategories,
        IReadOnlyList<string> discoveryExclusions,
        IReadOnlyList<string> detectedExclusions,
        DateOnly latest,
        int minimumConfidence)
    {
        return expenses
            .Where(entry => EligibleCandidate(entry, selectedCategories, discoveryExclusions, detectedExclusions))
            .GroupBy(entry => entry.Merchant, StringComparer.Ordinal)
            .Select(group => Candidate(group.ToArray(), latest, minimumConfidence))
            .Where(entry => entry is not null)
            .Select(entry => entry!)
            .OrderBy(entry => entry.Status, StringComparer.Ordinal)
            .ThenByDescending(entry => entry.LastDate)
            .ThenByDescending(entry => entry.Confidence)
            .ToArray();
    }

    private static SubscriptionInventoryEntry? Candidate(
        IReadOnlyList<SubscriptionChargeEntry> entries,
        DateOnly latest,
        int minimumConfidence)
    {
        int uniqueMonths = entries.Select(entry => entry.Transaction.Month).Distinct().Count();
        if (entries.Count < 3 || uniqueMonths < 3 || entries.Count > uniqueMonths * 1.25m)
            return null;

        (string cadence, decimal regularity) = InferCadence(entries.Select(entry => entry.Transaction.Date));
        if (!IsKnownCadence(cadence) || regularity < .70m)
            return null;

        decimal median = Median(entries.Select(entry => entry.Amount));
        decimal standardDeviation = StandardDeviation(entries.Select(entry => entry.Amount));
        decimal amountVariation = median == 0m ? 1m : standardDeviation / median;
        int confidence = (int)decimal.Round(
            regularity * 50m
            + Math.Min(entries.Count / 6m, 1m) * 15m
            + Math.Min(uniqueMonths / 6m, 1m) * 15m
            + Math.Max(0m, 1m - amountVariation / .5m) * 20m,
            0,
            MidpointRounding.ToEven);
        if (confidence < minimumConfidence)
            return null;

        SubscriptionInventoryEntry row = CreateInventory(entries, latest, "Detected");
        if (!string.Equals(row.Status, "Active", StringComparison.Ordinal))
            return null;
        return row with
        {
            Cadence = cadence,
            Confidence = confidence,
            BundleType = "Single stream"
        };
    }

    private static SubscriptionInventoryEntry CreateInventory(
        IReadOnlyList<SubscriptionChargeEntry> source,
        DateOnly latest,
        string origin)
    {
        SubscriptionChargeEntry[] entries = source
            .OrderBy(entry => entry.Transaction.Date)
            .ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal)
            .ToArray();
        int uniqueMonths = entries.Select(entry => entry.Transaction.Month).Distinct().Count();
        (string cadence, decimal regularity) = InferCadence(entries.Select(entry => entry.Transaction.Date));
        bool merchantBundle = entries.Length > uniqueMonths * 1.25m || string.Equals(cadence, "Multiple", StringComparison.Ordinal);
        string bundle = merchantBundle ? "Merchant bundle" : string.Equals(cadence, "Pending", StringComparison.Ordinal) ? "Pending" : "Single stream";
        if (merchantBundle)
            cadence = "Multiple";

        DateOnly first = entries[0].Transaction.Date;
        DateOnly last = entries[^1].Transaction.Date;
        (DateOnly? nextExpected, _, DateOnly inactiveAfter) = Boundaries(last, cadence);
        decimal? runRate = MonthlyRunRate(entries, cadence, latest);
        (decimal priceChange, DateOnly? priceDate) = LatestPriceChange(SplitEpisodes(entries, cadence)[^1], cadence);
        int confidence = cadence switch
        {
            "Pending" => entries.Length == 1 ? 40 : 60,
            "Multiple" => Math.Min(85, 55 + uniqueMonths * 3),
            _ => (int)decimal.Round(Math.Min(100m, regularity * 70m + Math.Min(entries.Length / 6m, 1m) * 30m), 0, MidpointRounding.ToEven)
        };
        return new SubscriptionInventoryEntry(
            entries[0].Merchant,
            origin,
            latest <= inactiveAfter ? "Active" : "Inactive",
            cadence,
            confidence,
            first,
            last,
            nextExpected,
            runRate,
            entries.Where(entry => entry.Transaction.Date > latest.AddYears(-1)).Sum(entry => entry.Amount),
            priceChange,
            priceDate,
            Mode(entries.Select(entry => entry.Transaction.Category)),
            Mode(entries.Select(entry => entry.Transaction.Account)),
            entries.Length,
            bundle);
    }

    private static SubscriptionLifecycleEntry[] BuildLifecycles(
        IReadOnlyList<SubscriptionChargeEntry> known,
        IReadOnlyList<SubscriptionInventoryEntry> inventory,
        DateOnly latest)
    {
        Dictionary<string, SubscriptionInventoryEntry> inventoryByMerchant = inventory
            .ToDictionary(entry => entry.Merchant, StringComparer.Ordinal);
        var rows = new List<SubscriptionLifecycleEntry>();
        foreach (IGrouping<string, SubscriptionChargeEntry> group in known.GroupBy(entry => entry.Merchant, StringComparer.Ordinal))
        {
            SubscriptionChargeEntry[] allEntries = group.OrderBy(entry => entry.Transaction.Date).ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal).ToArray();
            SubscriptionInventoryEntry inventoryEntry = inventoryByMerchant[group.Key];
            IReadOnlyList<SubscriptionChargeEntry>[] episodes = SplitEpisodes(allEntries, inventoryEntry.Cadence);
            for (int index = 0; index < episodes.Length; index++)
            {
                IReadOnlyList<SubscriptionChargeEntry> episode = episodes[index];
                bool current = index == episodes.Length - 1;
                DateOnly first = episode[0].Transaction.Date;
                DateOnly last = episode[^1].Transaction.Date;
                (DateOnly? nextExpected, DateOnly activeUntil, DateOnly inactiveAfter) = Boundaries(last, inventoryEntry.Cadence);
                (decimal priceChange, DateOnly? priceDate) = LatestPriceChange(episode, inventoryEntry.Cadence);
                rows.Add(new SubscriptionLifecycleEntry(
                    group.Key,
                    index + 1,
                    first,
                    last,
                    activeUntil,
                    inactiveAfter,
                    inactiveAfter < latest ? inactiveAfter : latest,
                    current ? inventoryEntry.Status : "Inactive",
                    current,
                    inventoryEntry.Cadence,
                    Mode(episode.Select(entry => entry.Transaction.Category)),
                    Mode(episode.Select(entry => entry.Transaction.Account)),
                    episode.Count,
                    episode[^1].Amount,
                    current ? inventoryEntry.MonthlyRunRate : MonthlyRunRate(episode, inventoryEntry.Cadence, last),
                    nextExpected,
                    priceChange,
                    priceDate));
            }
        }

        return rows
            .OrderBy(entry => string.Equals(entry.Status, "Active", StringComparison.Ordinal) ? 0 : 1)
            .ThenByDescending(entry => string.Equals(entry.Status, "Inactive", StringComparison.Ordinal) ? entry.DisplayEnd : entry.EpisodeStart)
            .ThenBy(entry => entry.Merchant, StringComparer.Ordinal)
            .ThenByDescending(entry => entry.Episode)
            .ToArray();
    }

    private static SubscriptionHistoryEntry[] BuildHistory(
        IReadOnlyList<SubscriptionChargeEntry> known,
        IReadOnlyList<SubscriptionLifecycleEntry> lifecycles,
        DateOnly latest)
    {
        if (known.Count == 0)
            return [];

        YearMonth start = known.Min(entry => entry.Transaction.Month);
        YearMonth end = YearMonth.From(latest);
        YearMonth[] months = YearMonth.InclusiveRange(start, end).ToArray();
        Dictionary<YearMonth, decimal> actual = known
            .GroupBy(entry => entry.Transaction.Month)
            .ToDictionary(group => group.Key, group => group.Sum(entry => entry.Amount));
        var history = new List<SubscriptionHistoryEntry>(months.Length);
        for (int index = 0; index < months.Length; index++)
        {
            YearMonth month = months[index];
            decimal spend = actual.GetValueOrDefault(month);
            decimal rolling = months
                .Skip(Math.Max(0, index - 2))
                .Take(index - Math.Max(0, index - 2) + 1)
                .Sum(value => actual.GetValueOrDefault(value))
                / Math.Min(index + 1, 3);
            int active = lifecycles
                .Where(entry => entry.EpisodeStart <= month.End && (entry.ActiveUntil < latest ? entry.ActiveUntil : latest) >= month.Start)
                .Select(entry => entry.Merchant)
                .Distinct(StringComparer.Ordinal)
                .Count();
            history.Add(new SubscriptionHistoryEntry(month, spend, rolling, active));
        }

        return history.ToArray();
    }

    private static SubscriptionAnalysisSummary Summarize(
        IReadOnlyList<SubscriptionInventoryEntry> inventory,
        IReadOnlyList<SubscriptionChargeEntry> known,
        DateOnly latest)
    {
        SubscriptionInventoryEntry[] active = inventory.Where(entry => string.Equals(entry.Status, "Active", StringComparison.Ordinal)).ToArray();
        decimal trailing = known.Where(entry => entry.Transaction.Date > latest.AddYears(-1)).Sum(entry => entry.Amount);
        DateOnly priorStart = latest.AddYears(-2);
        DateOnly trailingStart = latest.AddYears(-1);
        decimal prior = known.Where(entry => entry.Transaction.Date > priorStart && entry.Transaction.Date <= trailingStart).Sum(entry => entry.Amount);
        return new SubscriptionAnalysisSummary(
            active.Length,
            active.Where(entry => entry.MonthlyRunRate is not null).Sum(entry => entry.MonthlyRunRate!.Value),
            trailing,
            prior,
            prior == 0m ? null : (trailing - prior) / prior * 100m,
            active.Count(entry => entry.MonthlyRunRate is null));
    }

    private static bool EligibleCandidate(
        SubscriptionChargeEntry entry,
        IReadOnlyList<string> subscriptionCategories,
        IReadOnlyList<string> discoveryExclusions,
        IReadOnlyList<string> detectionExclusions)
        => !subscriptionCategories.Contains(entry.Transaction.Category, StringComparer.Ordinal)
            && !discoveryExclusions.Contains(entry.Transaction.Category, StringComparer.Ordinal)
            && !detectionExclusions.Contains(entry.Transaction.Category, StringComparer.Ordinal);

    private static DateOnly? CurrentEpisodeStart(IReadOnlyList<SubscriptionLifecycleEntry> lifecycles, string merchant)
        => lifecycles
            .Where(entry => entry.IsCurrent && string.Equals(entry.Merchant, merchant, StringComparison.Ordinal))
            .Select(entry => (DateOnly?)entry.EpisodeStart)
            .FirstOrDefault();

    private static IReadOnlyList<SubscriptionChargeEntry>[] SplitEpisodes(
        IReadOnlyList<SubscriptionChargeEntry> source,
        string cadence)
    {
        var episodes = new List<IReadOnlyList<SubscriptionChargeEntry>>();
        var current = new List<SubscriptionChargeEntry>();
        foreach (SubscriptionChargeEntry entry in source.OrderBy(item => item.Transaction.Date).ThenBy(item => item.Transaction.Id, StringComparer.Ordinal))
        {
            if (current.Count > 0)
            {
                (_, _, DateOnly inactiveAfter) = Boundaries(current[^1].Transaction.Date, cadence);
                if (entry.Transaction.Date > inactiveAfter)
                {
                    episodes.Add(current.ToArray());
                    current = [];
                }
            }
            current.Add(entry);
        }
        if (current.Count > 0)
            episodes.Add(current.ToArray());
        return episodes.ToArray();
    }

    private static (DateOnly? NextExpected, DateOnly ActiveUntil, DateOnly InactiveAfter) Boundaries(DateOnly lastDate, string cadence)
    {
        (string Cadence, int Days, int Months, int MinimumGap, int MaximumGap) match = Cadences
            .FirstOrDefault(value => string.Equals(value.Cadence, cadence, StringComparison.Ordinal));
        int days = match.Days;
        if (days == 0)
        {
            DateOnly inactive = lastDate.AddDays(90);
            return (null, inactive, inactive);
        }

        DateOnly next = lastDate.AddDays(days);
        DateOnly inactiveAfter = next.AddDays(Math.Min(days, 90));
        return (next, inactiveAfter, inactiveAfter);
    }

    private static (string Cadence, decimal Regularity) InferCadence(IEnumerable<DateOnly> dates)
    {
        DateOnly[] unique = dates.Distinct().Order().ToArray();
        if (unique.Length < 3)
            return ("Pending", 0m);

        int[] gaps = unique.Zip(unique.Skip(1), (previous, current) => current.DayNumber - previous.DayNumber).ToArray();
        var best = Cadences[0];
        decimal bestScore = -1m;
        foreach ((string cadence, int days, int months, int minimum, int maximum) candidate in Cadences)
        {
            decimal score = gaps.Count(gap => gap >= candidate.minimum && gap <= candidate.maximum) / (decimal)gaps.Length;
            if (score > bestScore)
            {
                best = candidate;
                bestScore = score;
            }
        }

        return bestScore >= .70m ? (best.Cadence, bestScore) : ("Multiple", bestScore);
    }

    private static decimal? MonthlyRunRate(
        IReadOnlyList<SubscriptionChargeEntry> entries,
        string cadence,
        DateOnly latestDate)
    {
        (string Cadence, int Days, int Months, int MinimumGap, int MaximumGap) match = Cadences
            .FirstOrDefault(value => string.Equals(value.Cadence, cadence, StringComparison.Ordinal));
        int months = match.Months;
        if (months > 0)
            return entries.OrderBy(entry => entry.Transaction.Date).ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal).Last().Amount / months;
        if (string.Equals(cadence, "Pending", StringComparison.Ordinal))
            return null;

        YearMonth first = entries.Min(entry => entry.Transaction.Month);
        YearMonth latest = YearMonth.From(latestDate);
        YearMonth start = first.CompareTo(latest.AddMonths(-11)) > 0 ? first : latest.AddMonths(-11);
        int observedMonths = (latest.Year - start.Year) * 12 + latest.Month - start.Month + 1;
        return entries.Where(entry => entry.Transaction.Date >= start.Start).Sum(entry => entry.Amount) / observedMonths;
    }

    private static (decimal Change, DateOnly? Date) LatestPriceChange(
        IReadOnlyList<SubscriptionChargeEntry> source,
        string cadence)
    {
        if (!IsKnownCadence(cadence))
            return (0m, null);

        SubscriptionChargeEntry[] entries = source.OrderBy(entry => entry.Transaction.Date).ThenBy(entry => entry.Transaction.Id, StringComparer.Ordinal).ToArray();
        decimal change = 0m;
        DateOnly? date = null;
        for (int index = 1; index < entries.Length; index++)
        {
            decimal previous = entries[index - 1].Amount;
            decimal current = entries[index].Amount;
            decimal difference = current - previous;
            decimal percent = previous == 0m ? 0m : decimal.Abs(difference) / previous;
            if (decimal.Abs(difference) >= .5m && percent >= .05m)
            {
                change = difference;
                date = entries[index].Transaction.Date;
            }
        }

        return (change, date);
    }

    private static bool IsKnownCadence(string cadence)
        => Cadences.Any(value => string.Equals(value.Cadence, cadence, StringComparison.Ordinal));

    private static string[] Values(IEnumerable<string> values)
        => values
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value.Trim())
            .Distinct(StringComparer.Ordinal)
            .ToArray();

    private static string Mode(IEnumerable<string> values)
        => values
            .Select(value => string.IsNullOrWhiteSpace(value) ? "Unknown" : value.Trim())
            .GroupBy(value => value, StringComparer.Ordinal)
            .OrderByDescending(group => group.Count())
            .ThenBy(group => group.Key, StringComparer.Ordinal)
            .Select(group => group.Key)
            .FirstOrDefault("Unknown");

    private static decimal Median(IEnumerable<decimal> values)
    {
        decimal[] ordered = values.Order().ToArray();
        if (ordered.Length == 0)
            return 0m;
        int middle = ordered.Length / 2;
        return ordered.Length % 2 == 1 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2m;
    }

    private static decimal StandardDeviation(IEnumerable<decimal> source)
    {
        decimal[] values = source.ToArray();
        if (values.Length == 0)
            return 0m;
        decimal mean = values.Average();
        double variance = values.Select(value => Math.Pow((double)(value - mean), 2d)).Average();
        return (decimal)Math.Sqrt(variance);
    }
}
