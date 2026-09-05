using System.Globalization;
using Portico.Dashboard;
using Portico.Finance;
using Tomlyn;
using Tomlyn.Model;

namespace Portico.Adapters;

/// <summary>Loads Portico calculation, dashboard, and optional public-sheet TOML files.</summary>
public static class TomlConfigurationLoader
{
    /// <summary>Loads the existing Portico finance configuration without changing its schema.</summary>
    public static FinanceSettings LoadFinance(string path)
    {
        TomlTable root = Read(path);
        var errors = new List<ConfigurationError>();

        TomlTable data = Table(root, "data", errors);
        string source = String(data, "source", "data", errors).ToLowerInvariant();
        WorkbookSourceKind kind = source switch
        {
            "local" => WorkbookSourceKind.LocalCsv,
            "remote" or "google-sheets" => WorkbookSourceKind.GoogleSheets,
            _ => AddAndReturn(errors, "data.source", "must be 'local', 'remote', or 'google-sheets'.", WorkbookSourceKind.LocalCsv)
        };
        var dataSettings = new DataSourceSettings(kind, OptionalString(data, "directory", "data", errors));

        TomlTable lookback = Table(root, "lookback", errors);
        IReadOnlyList<int> lookbackMonths = Integers(lookback, "lookback_months", "lookback", errors);
        int defaultMonths = Integer(lookback, "default_lookback_months", "lookback", errors);
        if (lookbackMonths.Count == 0)
            errors.Add(new ConfigurationError("lookback.lookback_months", "must contain at least one positive month count."));
        if (lookbackMonths.Any(value => value <= 0))
            errors.Add(new ConfigurationError("lookback.lookback_months", "values must be positive."));
        if (!lookbackMonths.Contains(defaultMonths))
            errors.Add(new ConfigurationError("lookback.default_lookback_months", "must appear in lookback_months."));

        TomlTable thresholds = Table(root, "thresholds", errors);
        var thresholdSettings = new ThresholdSettings(
            Decimal(thresholds, "expense", "thresholds", errors),
            Decimal(thresholds, "income", "thresholds", errors),
            Decimal(thresholds, "duplicate_minimum", "thresholds", errors),
            Integer(thresholds, "duplicate_days", "thresholds", errors));

        TomlTable incomeSavings = Table(root, "income_savings", errors);
        string defaultView = String(incomeSavings, "default_view", "income_savings", errors);
        if (!string.Equals(defaultView, "regular", StringComparison.OrdinalIgnoreCase)
            && !string.Equals(defaultView, "actual", StringComparison.OrdinalIgnoreCase))
        {
            errors.Add(new ConfigurationError("income_savings.default_view", "must be 'regular' or 'actual'."));
        }
        var incomeSettings = new IncomeSavingsSettings(
            defaultView,
            Decimal(incomeSavings, "target_rate", "income_savings", errors),
            Strings(incomeSavings, "exclude_categories", "income_savings", errors),
            Strings(incomeSavings, "exclude_groups", "income_savings", errors));

        IReadOnlyDictionary<string, IReadOnlyList<string>> aliases = ParseAliases(root, errors);
        IReadOnlyList<TransactionSetDefinition> transactionSets = ParseTransactionSets(root, errors);
        IReadOnlyList<FilterSetDefinition> filterSets = ParseFilterSets(root, transactionSets, errors);

        TomlTable subscriptions = Table(root, "subscriptions", errors);
        var subscriptionSettings = new SubscriptionSettings(
            Strings(subscriptions, "known_categories", "subscriptions", errors),
            Integer(subscriptions, "minimum_confidence", "subscriptions", errors),
            Integer(subscriptions, "stale_after_days", "subscriptions", errors),
            Strings(subscriptions, "default_exclude_categories", "subscriptions", errors),
            Strings(subscriptions, "detection_excluded_categories", "subscriptions", errors));

        TomlTable budget = Table(root, "budget", errors);
        var budgetSettings = new BudgetSettings(Integer(budget, "history_months", "budget", errors));

        TomlTable dataHealth = Table(root, "data_health", errors);
        var healthSettings = new DataHealthSettings(
            Integer(dataHealth, "stale_account_days", "data_health", errors),
            Boolean(dataHealth, "duplicate_require_same_account", "data_health", errors),
            Boolean(dataHealth, "duplicate_require_same_category", "data_health", errors),
            Boolean(dataHealth, "duplicate_require_same_description", "data_health", errors));

        TomlTable safety = Table(root, "financial_safety", errors);
        var safetySettings = new FinancialSafetySettings(
            Integer(safety, "emergency_fund_target_months", "financial_safety", errors),
            Strings(safety, "emergency_fund_included_groups", "financial_safety", errors),
            Strings(safety, "emergency_fund_included_account_patterns", "financial_safety", errors),
            Integer(safety, "emergency_fund_spending_lookback_months", "financial_safety", errors),
            Strings(safety, "emergency_fund_exclude_categories", "financial_safety", errors),
            Strings(safety, "emergency_fund_exclude_groups", "financial_safety", errors),
            Strings(safety, "debt_included_groups", "financial_safety", errors),
            Strings(safety, "debt_included_account_patterns", "financial_safety", errors),
            OptionalDate(safety, "debt_baseline_date", "financial_safety", errors));

        TomlTable independence = Table(root, "financial_independence", errors);
        var independenceSettings = new FinancialIndependenceSettings(
            Decimal(independence, "expected_return_rate", "financial_independence", errors),
            Decimal(independence, "withdrawal_rate", "financial_independence", errors),
            Decimal(independence, "target_amount", "financial_independence", errors),
            Integer(independence, "spending_lookback_months", "financial_independence", errors),
            Integer(independence, "projection_years", "financial_independence", errors),
            Strings(independence, "included_account_patterns", "financial_independence", errors),
            Strings(independence, "included_groups", "financial_independence", errors));

        ValidateFinance(
            kind,
            dataSettings,
            new LookbackSettings(lookbackMonths, defaultMonths),
            thresholdSettings,
            incomeSettings,
            subscriptionSettings,
            budgetSettings,
            healthSettings,
            safetySettings,
            independenceSettings,
            errors);
        ThrowIfErrors(errors);
        return new FinanceSettings(
            dataSettings,
            new LookbackSettings(lookbackMonths, defaultMonths),
            thresholdSettings,
            incomeSettings,
            transactionSets,
            filterSets,
            subscriptionSettings,
            budgetSettings,
            healthSettings,
            safetySettings,
            independenceSettings,
            aliases);
    }

    /// <summary>Loads the separate TOML file that controls dashboard navigation and widgets.</summary>
    public static DashboardDefinition LoadDashboard(string path)
    {
        TomlTable root = Read(path);
        var errors = new List<ConfigurationError>();
        int schemaVersion = Integer(root, "schema_version", "dashboard", errors);
        string appTitle = String(root, "app_title", "dashboard", errors);
        IReadOnlyList<TomlTable> pageTables = Tables(root, "pages", "dashboard", errors);
        var pages = new List<DashboardPageDefinition>(pageTables.Count);
        for (int index = 0; index < pageTables.Count; index++)
            pages.Add(ParsePage(pageTables[index], index, errors));

        var definition = new DashboardDefinition(schemaVersion, appTitle, pages);
        foreach (string problem in definition.Validate())
            errors.Add(new ConfigurationError("dashboard", problem));
        ThrowIfErrors(errors);
        return definition;
    }

    /// <summary>Loads public-sheet URLs from a small optional TOML file.</summary>
    public static SheetUrlSettings LoadSheetUrls(string path)
    {
        TomlTable root = Read(path);
        var errors = new List<ConfigurationError>();
        TomlTable sheets = Table(root, "sheets", errors);
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach ((string key, object? value) in sheets)
        {
            if (value is not string url || string.IsNullOrWhiteSpace(url))
                errors.Add(new ConfigurationError($"sheets.{key}", "must be a non-empty URL."));
            else
                values[key] = url;
        }

        ThrowIfErrors(errors);
        return new SheetUrlSettings(values);
    }

    private static DashboardPageDefinition ParsePage(TomlTable table, int index, List<ConfigurationError> errors)
    {
        string path = $"dashboard.pages[{index}]";
        string rawId = String(table, "id", path, errors);
        DashboardPageId id = ParsePageId(rawId, $"{path}.id", errors);
        string title = String(table, "title", path, errors);
        string description = String(table, "description", path, errors);
        bool visible = OptionalBoolean(table, "visible", true, path, errors);
        string group = String(table, "group", path, errors);
        int order = Integer(table, "order", path, errors);
        string railLabel = String(table, "rail_label", path, errors);
        string pageHeading = String(table, "page_heading", path, errors);
        string icon = String(table, "icon", path, errors);
        IReadOnlyList<TomlTable> filters = OptionalTables(table, "filters", path, errors);
        IReadOnlyList<TomlTable> sections = OptionalTables(table, "sections", path, errors);
        IReadOnlyList<TomlTable> controls = OptionalTables(table, "controls", path, errors);
        IReadOnlyList<TomlTable> widgets = Tables(table, "widgets", path, errors);
        var parsedFilters = new List<DashboardFilterDefinition>(filters.Count);
        for (int filterIndex = 0; filterIndex < filters.Count; filterIndex++)
        {
            TomlTable filter = filters[filterIndex];
            string filterPath = $"{path}.filters[{filterIndex}]";
            string kind = String(filter, "kind", filterPath, errors);
            parsedFilters.Add(new DashboardFilterDefinition(
                String(filter, "id", filterPath, errors),
                String(filter, "label", filterPath, errors),
                ParseFilterKind(kind, $"{filterPath}.kind", errors),
                String(filter, "source", filterPath, errors),
                String(filter, "default", filterPath, errors),
                Strings(filter, "options", filterPath, errors)));
        }

        var parsedSections = new List<DashboardSectionDefinition>(sections.Count);
        for (int sectionIndex = 0; sectionIndex < sections.Count; sectionIndex++)
        {
            TomlTable section = sections[sectionIndex];
            string sectionPath = $"{path}.sections[{sectionIndex}]";
            parsedSections.Add(new DashboardSectionDefinition(
                String(section, "id", sectionPath, errors),
                String(section, "title", sectionPath, errors),
                ParseSectionLayout(String(section, "layout", sectionPath, errors), $"{sectionPath}.layout", errors),
                Integer(section, "order", sectionPath, errors),
                OptionalString(section, "description", sectionPath, errors)));
        }

        var parsedControls = new List<DashboardControlDefinition>(controls.Count);
        for (int controlIndex = 0; controlIndex < controls.Count; controlIndex++)
        {
            TomlTable control = controls[controlIndex];
            string controlPath = $"{path}.controls[{controlIndex}]";
            string kind = String(control, "kind", controlPath, errors);
            parsedControls.Add(new DashboardControlDefinition(
                String(control, "id", controlPath, errors),
                String(control, "label", controlPath, errors),
                ParseControlKind(kind, $"{controlPath}.kind", errors),
                ParseControlSource(String(control, "source", controlPath, errors), $"{controlPath}.source", errors),
                ParseControlOptionSource(OptionalString(control, "option_source", controlPath, errors) ?? "static", $"{controlPath}.option_source", errors),
                OptionalStrings(control, "options", controlPath, errors),
                OptionalScalarString(control, "default", controlPath, errors),
                OptionalStrings(control, "defaults", controlPath, errors),
                OptionalDecimal(control, "minimum", controlPath, errors),
                OptionalDecimal(control, "maximum", controlPath, errors),
                OptionalDecimal(control, "step", controlPath, errors),
                ParseControlWidth(OptionalString(control, "width", controlPath, errors) ?? "compact", $"{controlPath}.width", errors),
                OptionalString(control, "section", controlPath, errors)));
        }

        var parsedWidgets = new List<DashboardWidgetDefinition>(widgets.Count);
        for (int widgetIndex = 0; widgetIndex < widgets.Count; widgetIndex++)
        {
            TomlTable widget = widgets[widgetIndex];
            string widgetPath = $"{path}.widgets[{widgetIndex}]";
            string kind = String(widget, "kind", widgetPath, errors);
            parsedWidgets.Add(new DashboardWidgetDefinition(
                String(widget, "id", widgetPath, errors),
                String(widget, "title", widgetPath, errors),
                ParseWidgetKind(kind, $"{widgetPath}.kind", errors),
                String(widget, "report", widgetPath, errors),
                OptionalInteger(widget, "span", 1, widgetPath, errors),
                OptionalString(widget, "description", widgetPath, errors),
                OptionalStrings(widget, "bar_series", widgetPath, errors),
                OptionalString(widget, "section", widgetPath, errors),
                OptionalAxisTitle(widget, "x_axis_title", widgetPath, errors),
                OptionalAxisTitle(widget, "y_axis_title", widgetPath, errors)));
        }

        return new DashboardPageDefinition(
            id,
            title,
            description,
            parsedFilters,
            parsedWidgets,
            visible,
            ParseNavigationGroup(group, $"{path}.group", errors),
            order,
            railLabel,
            pageHeading,
            ParseNavigationIcon(icon, $"{path}.icon", errors))
        {
            Sections = parsedSections,
            Controls = parsedControls
        };
    }

    private static IReadOnlyDictionary<string, IReadOnlyList<string>> ParseAliases(TomlTable root, List<ConfigurationError> errors)
    {
        TomlTable merchants = Table(root, "merchants", errors);
        TomlTable aliases = Table(merchants, "aliases", errors);
        var result = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);
        foreach ((string merchant, object? value) in aliases)
        {
            if (value is not TomlArray array)
            {
                errors.Add(new ConfigurationError($"merchants.aliases.{merchant}", "must be an array of strings."));
                continue;
            }

            result[merchant] = Strings(array, $"merchants.aliases.{merchant}", errors);
        }

        return result;
    }

    private static IReadOnlyList<TransactionSetDefinition> ParseTransactionSets(TomlTable root, List<ConfigurationError> errors)
    {
        TomlTable sets = Table(root, "transaction_sets", errors);
        var result = new List<TransactionSetDefinition>(sets.Count);
        foreach ((string key, object? value) in sets)
        {
            if (value is not TomlTable table)
            {
                errors.Add(new ConfigurationError($"transaction_sets.{key}", "must be a table."));
                continue;
            }

            string path = $"transaction_sets.{key}";
            result.Add(new TransactionSetDefinition(
                key,
                String(table, "label", path, errors),
                Strings(table, "groups", path, errors),
                Strings(table, "categories", path, errors),
                Strings(table, "accounts", path, errors),
                Strings(table, "merchants", path, errors),
                Strings(table, "transactions_like", path, errors),
                Strings(table, "includes", path, errors),
                Strings(table, "excludes", path, errors)));
        }

        if (result.Count == 0)
            errors.Add(new ConfigurationError("transaction_sets", "must contain at least one named set."));
        return result;
    }

    private static IReadOnlyList<FilterSetDefinition> ParseFilterSets(
        TomlTable root,
        IReadOnlyList<TransactionSetDefinition> transactionSets,
        List<ConfigurationError> errors)
    {
        TomlTable sets = Table(root, "filter_sets", errors);
        var available = new HashSet<string>(transactionSets.Select(set => set.Key), StringComparer.Ordinal);
        var result = new List<FilterSetDefinition>(sets.Count);
        foreach ((string key, object? value) in sets)
        {
            if (value is not TomlTable table)
            {
                errors.Add(new ConfigurationError($"filter_sets.{key}", "must be a table."));
                continue;
            }

            string path = $"filter_sets.{key}";
            IReadOnlyList<string> options = Strings(table, "options", path, errors);
            string defaultValue = String(table, "default", path, errors);
            if (options.Count == 0)
                errors.Add(new ConfigurationError($"{path}.options", "must contain at least one transaction set."));
            if (!options.Contains(defaultValue, StringComparer.Ordinal))
                errors.Add(new ConfigurationError($"{path}.default", "must be listed in options."));
            foreach (string option in options)
            {
                if (!available.Contains(option))
                    errors.Add(new ConfigurationError($"{path}.options", $"references unknown transaction set '{option}'."));
            }

            result.Add(new FilterSetDefinition(key, options, defaultValue));
        }

        EnsureFilterSet(result, "spending", errors);
        EnsureFilterSet(result, "year_over_year", errors);
        return result;
    }

    private static void EnsureFilterSet(IReadOnlyList<FilterSetDefinition> definitions, string key, List<ConfigurationError> errors)
    {
        if (!definitions.Any(definition => string.Equals(definition.Key, key, StringComparison.Ordinal)))
            errors.Add(new ConfigurationError("filter_sets", $"must define '{key}'."));
    }

    private static void ValidateFinance(
        WorkbookSourceKind kind,
        DataSourceSettings data,
        LookbackSettings lookback,
        ThresholdSettings thresholds,
        IncomeSavingsSettings income,
        SubscriptionSettings subscriptions,
        BudgetSettings budget,
        DataHealthSettings health,
        FinancialSafetySettings safety,
        FinancialIndependenceSettings independence,
        List<ConfigurationError> errors)
    {
        if (kind == WorkbookSourceKind.LocalCsv && string.IsNullOrWhiteSpace(data.Directory))
            errors.Add(new ConfigurationError("data.directory", "is required when data.source is local."));
        if (kind == WorkbookSourceKind.GoogleSheets && !string.IsNullOrWhiteSpace(data.Directory))
            errors.Add(new ConfigurationError("data.directory", "must be empty when data.source is remote."));
        if (lookback.Months.Count is < 2 or > 5 || lookback.Months.Any(month => month is < 1 or > 120))
            errors.Add(new ConfigurationError("lookback.lookback_months", "must contain 2-5 values from 1 through 120."));
        if (thresholds.Expense is < 1_000m or > 100_000m
            || thresholds.Income is < 5_000m or > 100_000m
            || thresholds.DuplicateMinimum is < 0m or > 1_000m
            || thresholds.DuplicateDays is < 0 or > 7)
        {
            errors.Add(new ConfigurationError("thresholds", "values are outside the supported ranges."));
        }
        if (income.TargetRate is < 0m or > 100m)
            errors.Add(new ConfigurationError("income_savings.target_rate", "must be from 0 through 100."));
        if (subscriptions.MinimumConfidence is < 70 or > 100 || subscriptions.StaleAfterDays is < 1 or > 365)
            errors.Add(new ConfigurationError("subscriptions", "minimum_confidence must be 70-100 and stale_after_days must be 1-365."));
        if (budget.HistoryMonths is < 1 or > 120)
            errors.Add(new ConfigurationError("budget.history_months", "must be from 1 through 120."));
        if (health.StaleAccountDays is < 1 or > 365)
            errors.Add(new ConfigurationError("data_health.stale_account_days", "must be from 1 through 365."));
        if (safety.EmergencyFundTargetMonths is < 1 or > 24
            || safety.EmergencyFundSpendingLookbackMonths is < 1 or > 120)
        {
            errors.Add(new ConfigurationError("financial_safety", "target months must be 1-24 and spending lookback must be 1-120."));
        }
        if (independence.ExpectedReturnRate is < 0m or > 20m
            || independence.WithdrawalRate is < 0.5m or > 10m
            || independence.TargetAmount is < 1m or > 100_000_000m
            || independence.SpendingLookbackMonths is not (6 or 12 or 24 or 36)
            || independence.ProjectionYears is < 1 or > 100)
        {
            errors.Add(new ConfigurationError("financial_independence", "values are outside the supported ranges."));
        }
    }

    private static TomlTable Read(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
            throw new ConfigurationException([new ConfigurationError("configuration", "path is required.")]);
        if (!File.Exists(path))
            throw new ConfigurationException([new ConfigurationError(path, "file does not exist.")]);

        try
        {
            return TomlSerializer.Deserialize<TomlTable>(File.ReadAllText(path))
                ?? throw new ConfigurationException([new ConfigurationError(path, "file is empty.")]);
        }
        catch (ConfigurationException)
        {
            throw;
        }
        catch (Exception exception)
        {
            throw new ConfigurationException([new ConfigurationError(path, $"cannot parse TOML: {exception.Message}")]);
        }
    }

    private static TomlTable Table(TomlTable parent, string key, List<ConfigurationError> errors)
    {
        if (parent.TryGetValue(key, out object? value) && value is TomlTable table)
            return table;
        errors.Add(new ConfigurationError(key, "is required and must be a table."));
        return new TomlTable();
    }

    private static IReadOnlyList<TomlTable> Tables(TomlTable parent, string key, string prefix, List<ConfigurationError> errors)
    {
        if (parent.TryGetValue(key, out object? value) && value is TomlTableArray tables)
            return tables.Cast<TomlTable>().ToArray();
        errors.Add(new ConfigurationError($"{prefix}.{key}", "is required and must be an array of tables."));
        return [];
    }

    private static IReadOnlyList<TomlTable> OptionalTables(TomlTable parent, string key, string prefix, List<ConfigurationError> errors)
    {
        if (!parent.TryGetValue(key, out object? value))
            return [];
        if (value is TomlTableArray tables)
            return tables.Cast<TomlTable>().ToArray();
        errors.Add(new ConfigurationError($"{prefix}.{key}", "must be an array of tables."));
        return [];
    }

    private static string String(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (table.TryGetValue(key, out object? value) && value is string text && !string.IsNullOrWhiteSpace(text))
            return text;
        errors.Add(new ConfigurationError($"{prefix}.{key}", "is required and must be a non-empty string."));
        return string.Empty;
    }

    private static string? OptionalString(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (!table.TryGetValue(key, out object? value))
            return null;
        if (value is string text)
            return string.IsNullOrWhiteSpace(text) ? null : text;
        errors.Add(new ConfigurationError($"{prefix}.{key}", "must be a string."));
        return null;
    }

    private static string? OptionalAxisTitle(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (!table.TryGetValue(key, out object? value))
            return null;
        if (value is string text)
            return text;
        errors.Add(new ConfigurationError($"{prefix}.{key}", "must be a string."));
        return null;
    }

    private static string? OptionalScalarString(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (!table.TryGetValue(key, out object? value))
            return null;

        return value switch
        {
            string text => text,
            bool boolean => boolean.ToString().ToLowerInvariant(),
            _ when TryDecimal(value, out decimal number) => number.ToString(CultureInfo.InvariantCulture),
            _ => AddAndReturn(errors, $"{prefix}.{key}", "must be a string, number, or true/false value.", (string?)null)
        };
    }

    private static int Integer(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (table.TryGetValue(key, out object? value) && TryInteger(value, out int result))
            return result;
        errors.Add(new ConfigurationError($"{prefix}.{key}", "is required and must be an integer."));
        return 0;
    }

    private static int OptionalInteger(TomlTable table, string key, int defaultValue, string prefix, List<ConfigurationError> errors)
    {
        if (!table.TryGetValue(key, out object? value))
            return defaultValue;
        if (TryInteger(value, out int result))
            return result;
        errors.Add(new ConfigurationError($"{prefix}.{key}", "must be an integer."));
        return defaultValue;
    }

    private static decimal Decimal(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (table.TryGetValue(key, out object? value) && TryDecimal(value, out decimal result))
            return result;
        errors.Add(new ConfigurationError($"{prefix}.{key}", "is required and must be a number."));
        return 0m;
    }

    private static decimal? OptionalDecimal(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (!table.TryGetValue(key, out object? value))
            return null;
        if (TryDecimal(value, out decimal result))
            return result;
        errors.Add(new ConfigurationError($"{prefix}.{key}", "must be a number."));
        return null;
    }

    private static bool Boolean(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (table.TryGetValue(key, out object? value) && value is bool result)
            return result;
        errors.Add(new ConfigurationError($"{prefix}.{key}", "is required and must be true or false."));
        return false;
    }

    private static bool OptionalBoolean(TomlTable table, string key, bool defaultValue, string prefix, List<ConfigurationError> errors)
    {
        if (!table.TryGetValue(key, out object? value))
            return defaultValue;
        if (value is bool result)
            return result;
        errors.Add(new ConfigurationError($"{prefix}.{key}", "must be true or false."));
        return defaultValue;
    }

    private static DateOnly? OptionalDate(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        string? value = OptionalString(table, key, prefix, errors);
        if (string.IsNullOrWhiteSpace(value))
            return null;
        if (DateOnly.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.None, out DateOnly result))
            return result;
        errors.Add(new ConfigurationError($"{prefix}.{key}", "must be empty or an ISO 8601 date."));
        return null;
    }

    private static IReadOnlyList<int> Integers(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (!table.TryGetValue(key, out object? value) || value is not TomlArray array)
        {
            errors.Add(new ConfigurationError($"{prefix}.{key}", "is required and must be an array of integers."));
            return [];
        }

        var result = new List<int>(array.Count);
        foreach (object? item in array)
        {
            if (TryInteger(item, out int number))
                result.Add(number);
            else
                errors.Add(new ConfigurationError($"{prefix}.{key}", "must contain only integers."));
        }

        return result;
    }

    private static IReadOnlyList<string> Strings(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (!table.TryGetValue(key, out object? value) || value is not TomlArray array)
        {
            errors.Add(new ConfigurationError($"{prefix}.{key}", "is required and must be an array of strings."));
            return [];
        }

        return Strings(array, $"{prefix}.{key}", errors);
    }

    private static IReadOnlyList<string>? OptionalStrings(TomlTable table, string key, string prefix, List<ConfigurationError> errors)
    {
        if (!table.TryGetValue(key, out object? value))
            return null;
        if (value is TomlArray array)
            return Strings(array, $"{prefix}.{key}", errors);

        errors.Add(new ConfigurationError($"{prefix}.{key}", "must be an array of strings."));
        return null;
    }

    private static IReadOnlyList<string> Strings(TomlArray array, string path, List<ConfigurationError> errors)
    {
        var result = new List<string>(array.Count);
        foreach (object? item in array)
        {
            if (item is string text)
                result.Add(text);
            else
                errors.Add(new ConfigurationError(path, "must contain only strings."));
        }

        return result;
    }

    private static bool TryInteger(object? value, out int result)
    {
        switch (value)
        {
            case long longValue when longValue is >= int.MinValue and <= int.MaxValue:
                result = (int)longValue;
                return true;
            case int intValue:
                result = intValue;
                return true;
            default:
                result = 0;
                return false;
        }
    }

    private static bool TryDecimal(object? value, out decimal result)
    {
        switch (value)
        {
            case long longValue:
                result = longValue;
                return true;
            case double doubleValue:
                result = Convert.ToDecimal(doubleValue, CultureInfo.InvariantCulture);
                return true;
            case decimal decimalValue:
                result = decimalValue;
                return true;
            default:
                result = 0m;
                return false;
        }
    }

    private static DashboardPageId ParsePageId(string value, string path, List<ConfigurationError> errors)
        => ParseEnum(value, path, errors, new Dictionary<string, DashboardPageId>(StringComparer.OrdinalIgnoreCase)
        {
            ["home"] = DashboardPageId.Home,
            ["income_savings"] = DashboardPageId.IncomeSavings,
            ["spending"] = DashboardPageId.Spending,
            ["year_over_year"] = DashboardPageId.YearOverYear,
            ["subscriptions"] = DashboardPageId.Subscriptions,
            ["merchants"] = DashboardPageId.Merchants,
            ["budget"] = DashboardPageId.Budget,
            ["top_transactions"] = DashboardPageId.TopTransactions,
            ["financial_independence"] = DashboardPageId.FinancialIndependence,
            ["data_health"] = DashboardPageId.DataHealth
        });

    private static DashboardFilterKind ParseFilterKind(string value, string path, List<ConfigurationError> errors)
        => ParseEnum(value, path, errors, new Dictionary<string, DashboardFilterKind>(StringComparer.OrdinalIgnoreCase)
        {
            ["select"] = DashboardFilterKind.Select
        });

    private static DashboardControlKind ParseControlKind(string value, string path, List<ConfigurationError> errors)
        => ParseEnum(value, path, errors, new Dictionary<string, DashboardControlKind>(StringComparer.OrdinalIgnoreCase)
        {
            ["select"] = DashboardControlKind.Select,
            ["segmented_choice"] = DashboardControlKind.SegmentedChoice,
            ["multi_select"] = DashboardControlKind.MultiSelect,
            ["number_input"] = DashboardControlKind.NumberInput,
            ["slider"] = DashboardControlKind.Slider,
            ["toggle"] = DashboardControlKind.Toggle,
            ["tab_choice"] = DashboardControlKind.TabChoice,
            ["action_reset"] = DashboardControlKind.ActionReset,
            ["text_multi_select"] = DashboardControlKind.TextMultiSelect,
            ["popover"] = DashboardControlKind.Popover,
            ["collapsible"] = DashboardControlKind.Collapsible,
            ["text_input"] = DashboardControlKind.TextInput
        });

    private static DashboardControlSource ParseControlSource(string value, string path, List<ConfigurationError> errors)
        => ParseEnum(value, path, errors, new Dictionary<string, DashboardControlSource>(StringComparer.OrdinalIgnoreCase)
        {
            ["lookback"] = DashboardControlSource.Lookback,
            ["spending"] = DashboardControlSource.Spending,
            ["year_over_year"] = DashboardControlSource.YearOverYear,
            ["year_over_year_view"] = DashboardControlSource.YearOverYearView,
            ["year_over_year_preset_categories"] = DashboardControlSource.YearOverYearPresetCategories,
            ["year_over_year_single_category"] = DashboardControlSource.YearOverYearSingleCategory,
            ["year_over_year_single_group"] = DashboardControlSource.YearOverYearSingleGroup,
            ["income_view"] = DashboardControlSource.IncomeView,
            ["income_lookback"] = DashboardControlSource.IncomeLookback,
            ["income_calculation"] = DashboardControlSource.IncomeCalculation,
            ["income_adjust_calculation"] = DashboardControlSource.IncomeAdjustCalculation,
            ["income_reset"] = DashboardControlSource.IncomeReset,
            ["income_excluded_income_categories"] = DashboardControlSource.IncomeExcludedIncomeCategories,
            ["income_excluded_expense_groups"] = DashboardControlSource.IncomeExcludedExpenseGroups,
            ["income_excluded_expense_categories"] = DashboardControlSource.IncomeExcludedExpenseCategories,
            ["income_included_descriptions"] = DashboardControlSource.IncomeIncludedDescriptions,
            ["income_excluded_descriptions"] = DashboardControlSource.IncomeExcludedDescriptions,
            ["income_exclude_large_income"] = DashboardControlSource.IncomeExcludeLargeIncome,
            ["income_income_limit"] = DashboardControlSource.IncomeIncomeLimit,
            ["income_exclude_large_expenses"] = DashboardControlSource.IncomeExcludeLargeExpenses,
            ["income_expense_limit"] = DashboardControlSource.IncomeExpenseLimit,
            ["income_target_rate"] = DashboardControlSource.IncomeTargetRate,
            ["income_detail_month"] = DashboardControlSource.IncomeDetailMonth,
            ["home_time_frame"] = DashboardControlSource.HomeTimeFrame,
            ["income_excluded_categories"] = DashboardControlSource.IncomeExcludedCategories,
            ["financial_independence_target_amount"] = DashboardControlSource.FinancialIndependenceTargetAmount,
            ["data_health_stale_threshold"] = DashboardControlSource.DataHealthStaleThreshold,
            ["data_health_include_inactive"] = DashboardControlSource.DataHealthIncludeInactive,
            ["health_check_settings"] = DashboardControlSource.DataHealthCheckSettings,
            ["health_stale_days"] = DashboardControlSource.DataHealthStaleThreshold,
            ["health_duplicate_days"] = DashboardControlSource.DataHealthDuplicateDays,
            ["health_duplicate_minimum"] = DashboardControlSource.DataHealthDuplicateMinimum,
            ["health_same_account"] = DashboardControlSource.DataHealthDuplicateSameAccount,
            ["health_same_category"] = DashboardControlSource.DataHealthDuplicateSameCategory,
            ["health_same_description"] = DashboardControlSource.DataHealthDuplicateSameDescription,
            ["health_include_inactive"] = DashboardControlSource.DataHealthIncludeInactive,
            ["health_selected_check"] = DashboardControlSource.DataHealthSelectedCheck,
            ["income_detail_tab"] = DashboardControlSource.IncomeDetailTab,
            ["financial_independence_reset"] = DashboardControlSource.FinancialIndependenceReset,
            ["spending_comparison"] = DashboardControlSource.SpendingComparison,
            ["spending_breakdown"] = DashboardControlSource.SpendingBreakdown,
            ["spending_excluded_groups"] = DashboardControlSource.SpendingExcludedGroups,
            ["spending_excluded_categories"] = DashboardControlSource.SpendingExcludedCategories,
            ["spending_included_descriptions"] = DashboardControlSource.SpendingIncludedDescriptions,
            ["spending_excluded_descriptions"] = DashboardControlSource.SpendingExcludedDescriptions,
            ["spending_exclude_large_expenses"] = DashboardControlSource.SpendingExcludeLargeExpenses,
            ["spending_expense_limit"] = DashboardControlSource.SpendingExpenseLimit,
            ["spending_detail_month"] = DashboardControlSource.SpendingDetailMonth,
            ["spending_adjust_view"] = DashboardControlSource.SpendingAdjustView,
            ["spending_reset"] = DashboardControlSource.SpendingReset,
            ["subscription_categories"] = DashboardControlSource.SubscriptionCategories,
            ["subscription_discovery_exclusions"] = DashboardControlSource.SubscriptionDiscoveryExclusions,
            ["subscription_minimum_confidence"] = DashboardControlSource.SubscriptionMinimumConfidence,
            ["subscription_settings_open"] = DashboardControlSource.SubscriptionSettingsOpen,
            ["subscription_history_lookback"] = DashboardControlSource.SubscriptionHistoryLookback,
            ["subscription_timeline_scope"] = DashboardControlSource.SubscriptionTimelineScope,
            ["merchant_lookback"] = DashboardControlSource.MerchantLookback,
            ["merchant_spending"] = DashboardControlSource.MerchantSpending,
            ["merchant_comparison"] = DashboardControlSource.MerchantComparison,
            ["merchant_excluded_groups"] = DashboardControlSource.MerchantExcludedGroups,
            ["merchant_excluded_categories"] = DashboardControlSource.MerchantExcludedCategories,
            ["merchant_included_descriptions"] = DashboardControlSource.MerchantIncludedDescriptions,
            ["merchant_excluded_descriptions"] = DashboardControlSource.MerchantExcludedDescriptions,
            ["merchant_exclude_large_expenses"] = DashboardControlSource.MerchantExcludeLargeExpenses,
            ["merchant_expense_limit"] = DashboardControlSource.MerchantExpenseLimit,
            ["merchant_adjust_view"] = DashboardControlSource.MerchantAdjustView,
            ["merchant_reset"] = DashboardControlSource.MerchantReset,
            ["merchant_search"] = DashboardControlSource.MerchantSearch,
            ["merchant_detail_month"] = DashboardControlSource.MerchantDetailMonth,
            ["merchant_detail_tab"] = DashboardControlSource.MerchantDetailTab,
            ["transactions_lookback"] = DashboardControlSource.TransactionsLookback,
            ["transactions_type"] = DashboardControlSource.TransactionsType,
            ["transactions_focus"] = DashboardControlSource.TransactionsFocus,
            ["transactions_search"] = DashboardControlSource.TransactionsSearch,
            ["transactions_groups"] = DashboardControlSource.TransactionsGroups,
            ["transactions_categories"] = DashboardControlSource.TransactionsCategories,
            ["transactions_accounts"] = DashboardControlSource.TransactionsAccounts,
            ["transactions_minimum_amount"] = DashboardControlSource.TransactionsMinimumAmount,
            ["transactions_maximum_amount"] = DashboardControlSource.TransactionsMaximumAmount,
            ["transactions_largest_count"] = DashboardControlSource.TransactionsLargestCount,
            ["transactions_breakdown"] = DashboardControlSource.TransactionsBreakdown,
            ["transactions_more_filters"] = DashboardControlSource.TransactionsMoreFilters,
            ["budget_month"] = DashboardControlSource.BudgetMonth,
            ["budget_groups"] = DashboardControlSource.BudgetGroups,
            ["budget_adjust_view"] = DashboardControlSource.BudgetAdjustView,
            ["budget_reset"] = DashboardControlSource.BudgetReset,
            ["budget_excluded_groups"] = DashboardControlSource.BudgetExcludedGroups,
            ["budget_excluded_categories"] = DashboardControlSource.BudgetExcludedCategories,
            ["budget_included_descriptions"] = DashboardControlSource.BudgetIncludedDescriptions,
            ["budget_excluded_descriptions"] = DashboardControlSource.BudgetExcludedDescriptions,
            ["budget_exclude_large_expenses"] = DashboardControlSource.BudgetExcludeLargeExpenses,
            ["budget_expense_limit"] = DashboardControlSource.BudgetExpenseLimit,
            ["budget_selected_group"] = DashboardControlSource.BudgetSelectedGroup,
            ["budget_transaction_category"] = DashboardControlSource.BudgetTransactionCategory,
            ["budget_year_to_date"] = DashboardControlSource.BudgetYearToDate,
            ["fi_assets"] = DashboardControlSource.FinancialIndependenceAssets,
            ["fi_spending"] = DashboardControlSource.FinancialIndependenceSpending,
            ["fi_income"] = DashboardControlSource.FinancialIndependenceIncome,
            ["fi_return_rate"] = DashboardControlSource.FinancialIndependenceReturnRate,
            ["fi_withdrawal_rate"] = DashboardControlSource.FinancialIndependenceWithdrawalRate,
            ["fi_years"] = DashboardControlSource.FinancialIndependenceProjectionYears,
            ["fi_adjust_source_data"] = DashboardControlSource.FinancialIndependenceAdjustSourceData,
            ["fi_included_accounts"] = DashboardControlSource.FinancialIndependenceIncludedAccounts,
            ["fi_spending_lookback"] = DashboardControlSource.FinancialIndependenceSpendingLookback,
            ["fi_excluded_groups"] = DashboardControlSource.FinancialIndependenceExcludedGroups,
            ["fi_excluded_categories"] = DashboardControlSource.FinancialIndependenceExcludedCategories,
            ["fi_included_descriptions"] = DashboardControlSource.FinancialIndependenceIncludedDescriptions,
            ["fi_excluded_descriptions"] = DashboardControlSource.FinancialIndependenceExcludedDescriptions,
            ["fi_exclude_large_expenses"] = DashboardControlSource.FinancialIndependenceExcludeLargeExpenses,
            ["fi_expense_limit"] = DashboardControlSource.FinancialIndependenceExpenseLimit,
            ["fi_source_details"] = DashboardControlSource.FinancialIndependenceSourceDetails,
            ["fi_source_tab"] = DashboardControlSource.FinancialIndependenceSourceDetailsTab
        });

    private static DashboardControlOptionSource ParseControlOptionSource(string value, string path, List<ConfigurationError> errors)
        => ParseEnum(value, path, errors, new Dictionary<string, DashboardControlOptionSource>(StringComparer.OrdinalIgnoreCase)
        {
            ["static"] = DashboardControlOptionSource.Static,
            ["spending_groups"] = DashboardControlOptionSource.SpendingGroups,
            ["spending_categories"] = DashboardControlOptionSource.SpendingCategories,
            ["spending_months"] = DashboardControlOptionSource.SpendingMonths,
            ["income_income_categories"] = DashboardControlOptionSource.IncomeIncomeCategories,
            ["income_expense_groups"] = DashboardControlOptionSource.IncomeExpenseGroups,
            ["income_expense_categories"] = DashboardControlOptionSource.IncomeExpenseCategories,
            ["income_months"] = DashboardControlOptionSource.IncomeMonths,
            ["year_over_year_preset_categories"] = DashboardControlOptionSource.YearOverYearPresetCategories,
            ["year_over_year_categories"] = DashboardControlOptionSource.YearOverYearCategories,
            ["year_over_year_groups"] = DashboardControlOptionSource.YearOverYearGroups,
            ["all_categories"] = DashboardControlOptionSource.AllCategories,
            ["all_groups"] = DashboardControlOptionSource.AllGroups,
            ["all_accounts"] = DashboardControlOptionSource.AllAccounts,
            ["subscription_discovery_categories"] = DashboardControlOptionSource.SubscriptionDiscoveryCategories,
            ["merchant_months"] = DashboardControlOptionSource.MerchantMonths,
            ["budget_months"] = DashboardControlOptionSource.BudgetMonths,
            ["budget_groups"] = DashboardControlOptionSource.BudgetGroups,
            ["budget_transaction_categories"] = DashboardControlOptionSource.BudgetTransactionCategories,
            ["fi_accounts"] = DashboardControlOptionSource.FinancialIndependenceAccounts,
            ["health_checks"] = DashboardControlOptionSource.DataHealthChecks
        });

    private static DashboardControlWidth ParseControlWidth(string value, string path, List<ConfigurationError> errors)
        => ParseEnum(value, path, errors, new Dictionary<string, DashboardControlWidth>(StringComparer.OrdinalIgnoreCase)
        {
            ["compact"] = DashboardControlWidth.Compact,
            ["full"] = DashboardControlWidth.Full
        });

    private static DashboardSectionLayout ParseSectionLayout(string value, string path, List<ConfigurationError> errors)
        => ParseEnum(value, path, errors, new Dictionary<string, DashboardSectionLayout>(StringComparer.OrdinalIgnoreCase)
        {
            ["flow"] = DashboardSectionLayout.Flow
        });

    private static DashboardNavigationGroup ParseNavigationGroup(string value, string path, List<ConfigurationError> errors)
        => ParseEnum(value, path, errors, new Dictionary<string, DashboardNavigationGroup>(StringComparer.OrdinalIgnoreCase)
        {
            ["standalone"] = DashboardNavigationGroup.Standalone,
            ["analyze"] = DashboardNavigationGroup.Analyze,
            ["plan"] = DashboardNavigationGroup.Plan,
            ["maintain"] = DashboardNavigationGroup.Maintain
        });

    private static DashboardNavigationIcon ParseNavigationIcon(string value, string path, List<ConfigurationError> errors)
        => ParseEnum(value, path, errors, new Dictionary<string, DashboardNavigationIcon>(StringComparer.OrdinalIgnoreCase)
        {
            ["home"] = DashboardNavigationIcon.Home,
            ["savings"] = DashboardNavigationIcon.Savings,
            ["storefront"] = DashboardNavigationIcon.Storefront,
            ["category"] = DashboardNavigationIcon.Category,
            ["compare_arrows"] = DashboardNavigationIcon.CompareArrows,
            ["subscriptions"] = DashboardNavigationIcon.Subscriptions,
            ["receipt_long"] = DashboardNavigationIcon.ReceiptLong,
            ["account_balance_wallet"] = DashboardNavigationIcon.AccountBalanceWallet,
            ["monitoring"] = DashboardNavigationIcon.Monitoring,
            ["health_and_safety"] = DashboardNavigationIcon.HealthAndSafety
        });

    private static DashboardWidgetKind ParseWidgetKind(string value, string path, List<ConfigurationError> errors)
        => ParseEnum(value, path, errors, new Dictionary<string, DashboardWidgetKind>(StringComparer.OrdinalIgnoreCase)
        {
            ["metric"] = DashboardWidgetKind.Metric,
            ["line_chart"] = DashboardWidgetKind.LineChart,
            ["area_chart"] = DashboardWidgetKind.AreaChart,
            ["bar_chart"] = DashboardWidgetKind.BarChart,
            ["horizontal_bar_chart"] = DashboardWidgetKind.HorizontalBarChart,
            ["combo_chart"] = DashboardWidgetKind.ComboChart,
            ["scatter_chart"] = DashboardWidgetKind.ScatterChart,
            ["sparkline"] = DashboardWidgetKind.Sparkline,
            ["table"] = DashboardWidgetKind.Table,
            ["timeline"] = DashboardWidgetKind.Timeline,
            ["heatmap"] = DashboardWidgetKind.Heatmap
        });

    private static T ParseEnum<T>(string value, string path, List<ConfigurationError> errors, IReadOnlyDictionary<string, T> known)
        where T : struct
    {
        if (known.TryGetValue(value, out T parsed))
            return parsed;
        errors.Add(new ConfigurationError(path, $"has unknown value '{value}'."));
        return default;
    }

    private static T AddAndReturn<T>(List<ConfigurationError> errors, string path, string message, T fallback)
    {
        errors.Add(new ConfigurationError(path, message));
        return fallback;
    }

    private static void ThrowIfErrors(List<ConfigurationError> errors)
    {
        if (errors.Count > 0)
            throw new ConfigurationException(errors);
    }
}
