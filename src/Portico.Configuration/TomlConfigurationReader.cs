using System.Globalization;
using Portico.Application;
using Portico.Finance;
using Tomlyn;
using Tomlyn.Model;

namespace Portico.Configuration;

/// <summary>Reads the versioned main and secret files without exposing their values in problems.</summary>
public sealed class TomlConfigurationReader : IConfigurationReader
{
    private readonly string _workingDirectory;

    public TomlConfigurationReader(string? workingDirectory = null)
    {
        _workingDirectory = Path.GetFullPath(workingDirectory ?? Directory.GetCurrentDirectory());
    }

    public async Task<ConfigurationReadOutcome> ReadAsync(
        ConfigurationSelection selection,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(selection);
        cancellationToken.ThrowIfCancellationRequested();

        var problems = new List<PorticoProblem>();
        string? mainPath = ResolveFile(selection.ConfigurationPath ?? "portico.toml", "configuration", problems);
        if (mainPath is null)
            return new PorticoFailure(problems);

        TomlTable? main = await ReadDocumentAsync(mainPath, "configuration", problems, cancellationToken);
        if (main is null)
            return new PorticoFailure(problems);

        CheckKeys(main, "", problems,
            "schema_version", "data", "lookback", "thresholds", "merchants",
            "transaction_sets", "filter_sets", "income_savings", "subscriptions",
            "budget", "data_health", "financial_safety", "financial_independence");
        CheckVersion(main, "schema_version", problems);

        TomlTable data = Table(main, "data", "", problems);
        CheckKeys(data, "data", problems, "source", "directory");
        string sourceName = RequiredString(data, "source", "data", problems);
        SourceKind? kind = sourceName switch
        {
            "local_csv" => SourceKind.LocalCsv,
            "google_sheets" => SourceKind.GoogleSheets,
            "" => null,
            _ => null
        };
        if (sourceName.Length > 0 && kind is null)
            Add(problems, "config.invalid-source", "Choose local_csv or google_sheets.", "data.source");

        string? directory = OptionalString(data, "directory", "data", problems);
        if (kind == SourceKind.LocalCsv && string.IsNullOrWhiteSpace(directory))
            Add(problems, "config.missing-field", "A local CSV directory is required.", "data.directory");
        if (kind == SourceKind.GoogleSheets && directory is not null)
            Add(problems, "config.invalid-value", "A Google Sheets source cannot set a local directory.", "data.directory");

        TomlTable lookback = Table(main, "lookback", "", problems);
        CheckKeys(lookback, "lookback", problems, "lookback_months", "default_lookback_months");
        IReadOnlyList<int> months = Integers(lookback, "lookback_months", "lookback", problems);
        int defaultMonths = Integer(lookback, "default_lookback_months", "lookback", problems);
        if (!HasProblem(problems, "lookback.lookback_months")
            && (months.Count is < 2 or > 5 || months.Any(month => month is < 1 or > 120)
                || months.Distinct().Count() != months.Count))
            Add(problems, "config.invalid-value", "Choose 2 to 5 distinct month counts from 1 through 120.", "lookback.lookback_months");
        if (!HasProblem(problems, "lookback.lookback_months")
            && !HasProblem(problems, "lookback.default_lookback_months")
            && !months.Contains(defaultMonths))
            Add(problems, "config.invalid-value", "The default must be one of the lookback choices.", "lookback.default_lookback_months");

        TomlTable thresholds = Table(main, "thresholds", "", problems);
        CheckKeys(thresholds, "thresholds", problems, "expense", "income", "duplicate_minimum", "duplicate_days");
        decimal expense = Number(thresholds, "expense", "thresholds", problems);
        decimal income = Number(thresholds, "income", "thresholds", problems);
        decimal duplicateMinimum = Number(thresholds, "duplicate_minimum", "thresholds", problems);
        int duplicateDays = Integer(thresholds, "duplicate_days", "thresholds", problems);
        Range(expense, 1_000m, 100_000m, "thresholds.expense", problems);
        Range(income, 5_000m, 100_000m, "thresholds.income", problems);
        Range(duplicateMinimum, 0m, 1_000m, "thresholds.duplicate_minimum", problems);
        Range(duplicateDays, 0, 7, "thresholds.duplicate_days", problems);

        TomlTable merchants = Table(main, "merchants", "", problems);
        CheckKeys(merchants, "merchants", problems, "aliases");
        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases = Aliases(merchants, problems);
        IReadOnlyList<TransactionSetDefinition> transactionSets = TransactionSets(main, problems);
        IReadOnlyList<FilterSetDefinition> filterSets = FilterSets(main, transactionSets, problems);

        TomlTable savings = Table(main, "income_savings", "", problems);
        CheckKeys(savings, "income_savings", problems,
            "default_view", "target_rate", "exclude_categories", "exclude_groups");
        string defaultView = RequiredString(savings, "default_view", "income_savings", problems);
        if (defaultView.Length > 0 && defaultView is not ("regular" or "actual"))
            Add(problems, "config.invalid-value", "Choose regular or actual.", "income_savings.default_view");
        decimal targetRate = Number(savings, "target_rate", "income_savings", problems);
        Range(targetRate, 0m, 100m, "income_savings.target_rate", problems);
        var savingsSettings = new IncomeSavingsSettings(
            defaultView,
            targetRate,
            Strings(savings, "exclude_categories", "income_savings", problems),
            Strings(savings, "exclude_groups", "income_savings", problems));

        TomlTable subscriptions = Table(main, "subscriptions", "", problems);
        CheckKeys(subscriptions, "subscriptions", problems,
            "known_categories", "minimum_confidence", "stale_after_days",
            "default_exclude_categories", "detection_excluded_categories");
        int minimumConfidence = Integer(subscriptions, "minimum_confidence", "subscriptions", problems);
        int staleAfterDays = Integer(subscriptions, "stale_after_days", "subscriptions", problems);
        Range(minimumConfidence, 70, 100, "subscriptions.minimum_confidence", problems);
        Range(staleAfterDays, 1, 365, "subscriptions.stale_after_days", problems);
        var subscriptionSettings = new SubscriptionSettings(
            Strings(subscriptions, "known_categories", "subscriptions", problems),
            minimumConfidence,
            staleAfterDays,
            Strings(subscriptions, "default_exclude_categories", "subscriptions", problems),
            Strings(subscriptions, "detection_excluded_categories", "subscriptions", problems));

        TomlTable budget = Table(main, "budget", "", problems);
        CheckKeys(budget, "budget", problems, "history_months");
        int historyMonths = Integer(budget, "history_months", "budget", problems);
        Range(historyMonths, 1, 120, "budget.history_months", problems);

        TomlTable health = Table(main, "data_health", "", problems);
        CheckKeys(health, "data_health", problems,
            "stale_account_days", "duplicate_require_same_account",
            "duplicate_require_same_category", "duplicate_require_same_description");
        int staleAccountDays = Integer(health, "stale_account_days", "data_health", problems);
        Range(staleAccountDays, 1, 365, "data_health.stale_account_days", problems);
        var healthSettings = new DataHealthSettings(
            staleAccountDays,
            Boolean(health, "duplicate_require_same_account", "data_health", problems),
            Boolean(health, "duplicate_require_same_category", "data_health", problems),
            Boolean(health, "duplicate_require_same_description", "data_health", problems));

        TomlTable safety = Table(main, "financial_safety", "", problems);
        CheckKeys(safety, "financial_safety", problems,
            "emergency_fund_target_months", "emergency_fund_included_groups",
            "emergency_fund_included_account_patterns", "emergency_fund_spending_lookback_months",
            "emergency_fund_exclude_categories", "emergency_fund_exclude_groups",
            "debt_included_groups", "debt_included_account_patterns", "debt_baseline_date");
        int emergencyMonths = Integer(safety, "emergency_fund_target_months", "financial_safety", problems);
        int emergencyLookback = Integer(safety, "emergency_fund_spending_lookback_months", "financial_safety", problems);
        Range(emergencyMonths, 1, 24, "financial_safety.emergency_fund_target_months", problems);
        Range(emergencyLookback, 1, 120, "financial_safety.emergency_fund_spending_lookback_months", problems);
        var safetySettings = new FinancialSafetySettings(
            emergencyMonths,
            Strings(safety, "emergency_fund_included_groups", "financial_safety", problems),
            Strings(safety, "emergency_fund_included_account_patterns", "financial_safety", problems),
            emergencyLookback,
            Strings(safety, "emergency_fund_exclude_categories", "financial_safety", problems),
            Strings(safety, "emergency_fund_exclude_groups", "financial_safety", problems),
            Strings(safety, "debt_included_groups", "financial_safety", problems),
            Strings(safety, "debt_included_account_patterns", "financial_safety", problems),
            Date(safety, "debt_baseline_date", "financial_safety", problems));

        TomlTable independence = Table(main, "financial_independence", "", problems);
        CheckKeys(independence, "financial_independence", problems,
            "expected_return_rate", "withdrawal_rate", "target_amount",
            "spending_lookback_months", "projection_years", "included_account_patterns", "included_groups");
        decimal expectedReturn = Number(independence, "expected_return_rate", "financial_independence", problems);
        decimal withdrawalRate = Number(independence, "withdrawal_rate", "financial_independence", problems);
        decimal targetAmount = Number(independence, "target_amount", "financial_independence", problems);
        int spendingLookback = Integer(independence, "spending_lookback_months", "financial_independence", problems);
        int projectionYears = Integer(independence, "projection_years", "financial_independence", problems);
        Range(expectedReturn, 0m, 20m, "financial_independence.expected_return_rate", problems);
        Range(withdrawalRate, 0.5m, 10m, "financial_independence.withdrawal_rate", problems);
        Range(targetAmount, 1m, 100_000_000m, "financial_independence.target_amount", problems);
        if (!HasProblem(problems, "financial_independence.spending_lookback_months")
            && spendingLookback is not (6 or 12 or 24 or 36))
            Add(problems, "config.invalid-value", "Choose 6, 12, 24, or 36 months.", "financial_independence.spending_lookback_months");
        Range(projectionYears, 1, 100, "financial_independence.projection_years", problems);
        var independenceSettings = new FinancialIndependenceSettings(
            expectedReturn,
            withdrawalRate,
            targetAmount,
            spendingLookback,
            projectionYears,
            Strings(independence, "included_account_patterns", "financial_independence", problems),
            Strings(independence, "included_groups", "financial_independence", problems));

        SourceRequest? source = null;
        if (kind == SourceKind.LocalCsv && !string.IsNullOrWhiteSpace(directory))
        {
            try
            {
                source = new LocalCsvSourceRequest(Path.GetFullPath(directory, Path.GetDirectoryName(mainPath)!));
            }
            catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
            {
                Add(problems, "config.invalid-value", "Choose a valid local data directory.", "data.directory");
            }
        }
        else if (kind == SourceKind.GoogleSheets)
        {
            string secretPath = selection.SecretsPath ?? Path.Combine(Path.GetDirectoryName(mainPath)!, "portico.secrets.toml");
            string? resolvedSecretPath = ResolveFile(secretPath, "secrets", problems);
            if (resolvedSecretPath is not null)
            {
                TomlTable? secrets = await ReadDocumentAsync(resolvedSecretPath, "secrets", problems, cancellationToken);
                if (secrets is not null)
                    source = GoogleSource(secrets, problems);
            }
        }

        if (problems.Count > 0)
            return new PorticoFailure(problems);

        var settings = new FinanceSettings(
            new LookbackSettings(months, defaultMonths),
            new ThresholdSettings(expense, income, duplicateMinimum, duplicateDays),
            savingsSettings,
            transactionSets,
            filterSets,
            subscriptionSettings,
            new BudgetSettings(historyMonths),
            healthSettings,
            safetySettings,
            independenceSettings,
            aliases);
        return new ConfigurationReadSuccess(new WorkspaceConfiguration(settings, source!));
    }

    private string? ResolveFile(string path, string field, List<PorticoProblem> problems)
    {
        try
        {
            return Path.GetFullPath(path, _workingDirectory);
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            Add(problems, "config.invalid-path", "Choose a valid file path.", field);
            return null;
        }
    }

    private static async Task<TomlTable?> ReadDocumentAsync(
        string path,
        string field,
        List<PorticoProblem> problems,
        CancellationToken cancellationToken)
    {
        string content;
        try
        {
            content = await File.ReadAllTextAsync(path, cancellationToken);
        }
        catch (FileNotFoundException)
        {
            Add(problems, "config.file-not-found", "The selected file does not exist.", field);
            return null;
        }
        catch (DirectoryNotFoundException)
        {
            Add(problems, "config.file-not-found", "The selected file does not exist.", field);
            return null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            Add(problems, "config.file-unreadable", "The selected file cannot be read.", field);
            return null;
        }

        try
        {
            TomlTable? table = TomlSerializer.Deserialize<TomlTable>(content);
            if (table is null)
                Add(problems, "config.invalid-toml", "The selected file is not valid TOML.", field);
            return table;
        }
        catch (TomlException)
        {
            Add(problems, "config.invalid-toml", "The selected file is not valid TOML.", field);
            return null;
        }
    }

    private static SourceRequest? GoogleSource(TomlTable root, List<PorticoProblem> problems)
    {
        CheckKeys(root, "secrets", problems, "schema_version", "sheets");
        CheckVersion(root, "secrets.schema_version", problems);
        TomlTable sheets = Table(root, "sheets", "", problems);
        CheckKeys(sheets, "sheets", problems,
            "transactions", "balance_history", "categories", "accounts");
        string transactions = Secret(sheets, "transactions", problems);
        string balances = Secret(sheets, "balance_history", problems);
        string categories = Secret(sheets, "categories", problems);
        string accounts = Secret(sheets, "accounts", problems);
        return transactions.Length > 0 && balances.Length > 0
            && categories.Length > 0 && accounts.Length > 0
                ? new GoogleSheetsSourceRequest(transactions, balances, categories, accounts)
                : null;
    }

    private static string Secret(TomlTable sheets, string key, List<PorticoProblem> problems)
    {
        if (sheets.TryGetValue(key, out object? value) && value is string text
            && !string.IsNullOrWhiteSpace(text))
            return text;
        Add(problems, "config.missing-secret", "A Google Sheets setting is missing or empty.", $"sheets.{key}");
        return "";
    }

    private static IReadOnlyDictionary<string, IReadOnlyList<string>> Aliases(
        TomlTable merchants,
        List<PorticoProblem> problems)
    {
        TomlTable table = Table(merchants, "aliases", "merchants", problems);
        var aliases = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);
        foreach ((string key, object? value) in table)
        {
            if (string.IsNullOrWhiteSpace(key) || value is not TomlArray array)
            {
                Add(problems, "config.invalid-value", "Each merchant alias must be an array of strings.", "merchants.aliases");
                continue;
            }
            aliases.Add(key, StringArray(array, "merchants.aliases", problems));
        }
        return aliases;
    }

    private static IReadOnlyList<TransactionSetDefinition> TransactionSets(
        TomlTable root,
        List<PorticoProblem> problems)
    {
        TomlTable table = Table(root, "transaction_sets", "", problems);
        var sets = new List<TransactionSetDefinition>();
        foreach ((string key, object? value) in table)
        {
            if (string.IsNullOrWhiteSpace(key) || value is not TomlTable definition)
            {
                Add(problems, "config.invalid-value", "Each transaction set must be a named table.", "transaction_sets");
                continue;
            }
            CheckKeys(definition, "transaction_sets", problems,
                "label", "groups", "categories", "accounts", "merchants",
                "transactions_like", "includes", "excludes");
            sets.Add(new TransactionSetDefinition(
                key,
                RequiredString(definition, "label", "transaction_sets", problems),
                Strings(definition, "groups", "transaction_sets", problems),
                Strings(definition, "categories", "transaction_sets", problems),
                Strings(definition, "accounts", "transaction_sets", problems),
                Strings(definition, "merchants", "transaction_sets", problems),
                Strings(definition, "transactions_like", "transaction_sets", problems),
                Strings(definition, "includes", "transaction_sets", problems),
                Strings(definition, "excludes", "transaction_sets", problems)));
        }
        if (sets.Count == 0)
            Add(problems, "config.missing-field", "Define at least one transaction set.", "transaction_sets");
        ValidateSetReferences(sets, problems);
        return sets;
    }

    private static void ValidateSetReferences(
        IReadOnlyList<TransactionSetDefinition> sets,
        List<PorticoProblem> problems)
    {
        var byKey = sets.ToDictionary(set => set.Key, StringComparer.Ordinal);
        var done = new HashSet<string>(StringComparer.Ordinal);
        var active = new HashSet<string>(StringComparer.Ordinal);
        foreach (TransactionSetDefinition set in sets)
            Visit(set.Key);

        void Visit(string key)
        {
            if (done.Contains(key))
                return;
            if (!active.Add(key))
            {
                Add(problems, "config.invalid-reference", "Transaction sets cannot refer to themselves in a cycle.", "transaction_sets");
                return;
            }
            foreach (string reference in byKey[key].Includes.Concat(byKey[key].Excludes))
            {
                if (byKey.ContainsKey(reference))
                    Visit(reference);
                else
                    Add(problems, "config.invalid-reference", "A transaction set refers to a missing set.", "transaction_sets");
            }
            active.Remove(key);
            done.Add(key);
        }
    }

    private static IReadOnlyList<FilterSetDefinition> FilterSets(
        TomlTable root,
        IReadOnlyList<TransactionSetDefinition> transactionSets,
        List<PorticoProblem> problems)
    {
        TomlTable table = Table(root, "filter_sets", "", problems);
        var available = transactionSets.Select(set => set.Key).ToHashSet(StringComparer.Ordinal);
        var sets = new List<FilterSetDefinition>();
        foreach ((string key, object? value) in table)
        {
            if (string.IsNullOrWhiteSpace(key) || value is not TomlTable definition)
            {
                Add(problems, "config.invalid-value", "Each filter set must be a named table.", "filter_sets");
                continue;
            }
            CheckKeys(definition, "filter_sets", problems, "options", "default");
            IReadOnlyList<string> options = Strings(definition, "options", "filter_sets", problems);
            string defaultValue = RequiredString(definition, "default", "filter_sets", problems);
            if (options.Count == 0 || options.Any(option => !available.Contains(option)))
                Add(problems, "config.invalid-reference", "Filter choices must name existing transaction sets.", "filter_sets.options");
            if (!options.Contains(defaultValue, StringComparer.Ordinal))
                Add(problems, "config.invalid-reference", "The default must be a filter choice.", "filter_sets.default");
            sets.Add(new FilterSetDefinition(key, options, defaultValue));
        }
        foreach (string required in new[] { "spending", "year_over_year" })
        {
            if (!sets.Any(set => set.Key == required))
                Add(problems, "config.missing-field", "A required filter set is missing.", $"filter_sets.{required}");
        }
        return sets;
    }

    private static void CheckVersion(TomlTable table, string field, List<PorticoProblem> problems)
    {
        if (!table.TryGetValue("schema_version", out object? value) || value is not long and not int
            || Convert.ToInt64(value, CultureInfo.InvariantCulture) != 1)
            Add(problems, "config.schema-version", "The file requires schema_version = 1.", field);
    }

    private static void CheckKeys(
        TomlTable table,
        string parent,
        List<PorticoProblem> problems,
        params string[] allowed)
    {
        foreach (string key in table.Keys)
        {
            if (allowed.Contains(key, StringComparer.Ordinal))
                continue;
            string field = parent.Length == 0 && key == "weekly_summary"
                ? "weekly_summary"
                : parent.Length == 0 ? "configuration" : parent;
            Add(problems, "config.unknown-key", "The file contains an unsupported setting.", field);
        }
    }

    private static TomlTable Table(
        TomlTable parent,
        string key,
        string prefix,
        List<PorticoProblem> problems)
    {
        if (parent.TryGetValue(key, out object? value) && value is TomlTable table)
            return table;
        Add(problems, "config.missing-field", "A required table is missing or invalid.", Field(prefix, key));
        return new TomlTable();
    }

    private static string RequiredString(
        TomlTable table,
        string key,
        string prefix,
        List<PorticoProblem> problems)
    {
        if (table.TryGetValue(key, out object? value) && value is string text
            && !string.IsNullOrWhiteSpace(text))
            return text;
        Add(problems, "config.missing-field", "A non-empty text value is required.", Field(prefix, key));
        return "";
    }

    private static string? OptionalString(
        TomlTable table,
        string key,
        string prefix,
        List<PorticoProblem> problems)
    {
        if (!table.TryGetValue(key, out object? value))
            return null;
        if (value is string text)
            return text;
        Add(problems, "config.invalid-value", "A text value is required.", Field(prefix, key));
        return null;
    }

    private static int Integer(
        TomlTable table,
        string key,
        string prefix,
        List<PorticoProblem> problems)
    {
        if (table.TryGetValue(key, out object? value) && TryInteger(value, out int number))
            return number;
        Add(problems, "config.missing-field", "An integer is required.", Field(prefix, key));
        return 0;
    }

    private static IReadOnlyList<int> Integers(
        TomlTable table,
        string key,
        string prefix,
        List<PorticoProblem> problems)
    {
        string field = Field(prefix, key);
        if (!table.TryGetValue(key, out object? value) || value is not TomlArray array)
        {
            Add(problems, "config.missing-field", "An integer array is required.", field);
            return [];
        }
        var values = new List<int>(array.Count);
        foreach (object? item in array)
        {
            if (TryInteger(item, out int number))
                values.Add(number);
            else
                Add(problems, "config.invalid-value", "The array must contain only integers.", field);
        }
        return values;
    }

    private static IReadOnlyList<string> Strings(
        TomlTable table,
        string key,
        string prefix,
        List<PorticoProblem> problems)
    {
        string field = Field(prefix, key);
        if (!table.TryGetValue(key, out object? value) || value is not TomlArray array)
        {
            Add(problems, "config.missing-field", "A text array is required.", field);
            return [];
        }
        return StringArray(array, field, problems);
    }

    private static IReadOnlyList<string> StringArray(
        TomlArray array,
        string field,
        List<PorticoProblem> problems)
    {
        var values = new List<string>(array.Count);
        foreach (object? item in array)
        {
            if (item is string text && !string.IsNullOrWhiteSpace(text))
                values.Add(text);
            else
                Add(problems, "config.invalid-value", "The array must contain only non-empty text.", field);
        }
        return values;
    }

    private static decimal Number(
        TomlTable table,
        string key,
        string prefix,
        List<PorticoProblem> problems)
    {
        if (table.TryGetValue(key, out object? value))
        {
            if (value is long integer)
                return integer;
            if (value is int number)
                return number;
            if (value is double floating && double.IsFinite(floating))
            {
                try
                {
                    return Convert.ToDecimal(floating, CultureInfo.InvariantCulture);
                }
                catch (OverflowException)
                {
                    // Report the same safe field error as other invalid numbers.
                }
            }
        }
        Add(problems, "config.missing-field", "A finite number is required.", Field(prefix, key));
        return 0m;
    }

    private static bool Boolean(
        TomlTable table,
        string key,
        string prefix,
        List<PorticoProblem> problems)
    {
        if (table.TryGetValue(key, out object? value) && value is bool result)
            return result;
        Add(problems, "config.missing-field", "True or false is required.", Field(prefix, key));
        return false;
    }

    private static DateOnly? Date(
        TomlTable table,
        string key,
        string prefix,
        List<PorticoProblem> problems)
    {
        string? value = OptionalString(table, key, prefix, problems);
        if (string.IsNullOrEmpty(value))
            return null;
        if (DateOnly.TryParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out DateOnly date))
            return date;
        Add(problems, "config.invalid-value", "Use an empty value or a date in YYYY-MM-DD form.", Field(prefix, key));
        return null;
    }

    private static bool TryInteger(object? value, out int result)
    {
        if (value is long number && number is >= int.MinValue and <= int.MaxValue)
        {
            result = (int)number;
            return true;
        }
        if (value is int integer)
        {
            result = integer;
            return true;
        }
        result = 0;
        return false;
    }

    private static void Range<T>(T value, T minimum, T maximum, string field, List<PorticoProblem> problems)
        where T : IComparable<T>
    {
        if (!HasProblem(problems, field)
            && (value.CompareTo(minimum) < 0 || value.CompareTo(maximum) > 0))
            Add(problems, "config.invalid-value", "The value is outside the supported range.", field);
    }

    private static bool HasProblem(List<PorticoProblem> problems, string field)
        => problems.Any(problem => problem.Field == field);

    private static string Field(string prefix, string key) => prefix.Length == 0 ? key : $"{prefix}.{key}";

    private static void Add(List<PorticoProblem> problems, string code, string message, string field)
        => problems.Add(new PorticoProblem(code, message, field));
}
