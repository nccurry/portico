using System.Globalization;
using Portico.Finance;

namespace Portico.Data;

/// <summary>Normalizes the four workbook tables into finance records.</summary>
internal static class WorkbookNormalizer
{
    private static readonly DateOnly EarliestSourceDate = new(1900, 1, 1);

    /// <summary>Normalizes parsed CSV tables into a portfolio snapshot.</summary>
    public static PortfolioSnapshot Normalize(IReadOnlyDictionary<string, CsvTable> tables)
    {
        ArgumentNullException.ThrowIfNull(tables);
        CsvTable transactions = tables["transactions"];
        CsvTable balances = tables["balance_history"];
        CsvTable categories = tables["categories"];
        CsvTable accounts = tables["accounts"];

        transactions.RequireHeaders("transactions", "Date", "Category", "Amount", "Account", "Full Description");
        balances.RequireHeaders("balance_history", "Date", "Time", "Account", "Account #", "Account ID", "Balance", "Class");
        categories.RequireHeaders("categories", "Category", "Group", "Type", "Hide From Reports");
        accounts.RequireHeaders("accounts", "Account", "Class Override", "Group", "Hide");

        IReadOnlyDictionary<string, CategoryRule> categoryRules = ReadCategories(categories);
        IReadOnlyList<AccountRule> accountRules = ReadAccounts(accounts);
        IReadOnlyList<FinancialTransaction> normalizedTransactions = ReadTransactions(transactions, categoryRules, accountRules);
        IReadOnlyList<BalanceObservation> normalizedBalances = ReadBalances(balances, accountRules);
        IReadOnlyList<BudgetEntry> budgets = ReadBudgets(categoryRules);
        return new PortfolioSnapshot(normalizedTransactions, normalizedBalances, budgets);
    }

    private static IReadOnlyDictionary<string, CategoryRule> ReadCategories(CsvTable table)
    {
        var result = new Dictionary<string, CategoryRule>(StringComparer.OrdinalIgnoreCase);
        for (int rowIndex = 0; rowIndex < table.Rows.Count; rowIndex++)
        {
            IReadOnlyDictionary<string, string> row = table.Rows[rowIndex];
            string category = RequiredText(row, "Category", "categories", rowIndex);
            if (!result.TryAdd(category, new CategoryRule(
                    category,
                    RequiredText(row, "Group", "categories", rowIndex),
                    ParseKind(RequiredText(row, "Type", "categories", rowIndex)),
                    ParseHidden(Value(row, "Hide From Reports"), "categories", rowIndex, "Hide From Reports"),
                    ReadBudgetValues(row, table.Headers, rowIndex))))
            {
                throw new DataContractException($"categories row {rowIndex + 2} duplicates a category.");
            }
        }

        return result;
    }

    private static IReadOnlyList<AccountRule> ReadAccounts(CsvTable table)
    {
        var result = new List<AccountRule>(table.Rows.Count);
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        for (int rowIndex = 0; rowIndex < table.Rows.Count; rowIndex++)
        {
            IReadOnlyDictionary<string, string> row = table.Rows[rowIndex];
            string account = RequiredText(row, "Account", "accounts", rowIndex);
            if (!names.Add(account))
                throw new DataContractException($"accounts row {rowIndex + 2} duplicates an account.");
            string? overrideText = EmptyToNull(Value(row, "Class Override"));
            AccountClass? overrideClass = overrideText is null ? null : ParseAccountClass(overrideText, "accounts", rowIndex);
            result.Add(new AccountRule(
                account,
                EmptyToNull(Value(row, "Group")) ?? string.Empty,
                overrideClass,
                ParseHidden(Value(row, "Hide"), "accounts", rowIndex, "Hide")));
        }

        return result;
    }

    private static IReadOnlyList<FinancialTransaction> ReadTransactions(
        CsvTable table,
        IReadOnlyDictionary<string, CategoryRule> categories,
        IReadOnlyList<AccountRule> accounts)
    {
        var result = new List<FinancialTransaction>(table.Rows.Count);
        for (int rowIndex = 0; rowIndex < table.Rows.Count; rowIndex++)
        {
            IReadOnlyDictionary<string, string> row = table.Rows[rowIndex];
            string category = RequiredText(row, "Category", "transactions", rowIndex);
            categories.TryGetValue(category, out CategoryRule? categoryRule);
            string account = RequiredText(row, "Account", "transactions", rowIndex);
            AccountRule? accountRule = FindTransactionAccount(accounts, account, Value(row, "Account #"));
            string id = EmptyToNull(Value(row, "Unnamed: 0")) ?? $"transaction-{rowIndex + 1}";
            result.Add(new FinancialTransaction(
                id,
                ParseDate(RequiredText(row, "Date", "transactions", rowIndex), "transactions", rowIndex, "Date"),
                category,
                categoryRule?.Group ?? "Uncategorized",
                account,
                EmptyToNull(Value(row, "Full Description")) ?? category,
                ParseMoney(RequiredText(row, "Amount", "transactions", rowIndex), "transactions", rowIndex, "Amount"),
                categoryRule?.Kind ?? TransactionKind.Unknown,
                categoryRule?.IsHidden == true || accountRule?.IsHidden == true));
        }

        return result;
    }

    private static IReadOnlyList<BalanceObservation> ReadBalances(CsvTable table, IReadOnlyList<AccountRule> accounts)
    {
        var result = new List<BalanceObservation>(table.Rows.Count);
        var identities = new Dictionary<string, (string Account, string Number)>(StringComparer.OrdinalIgnoreCase);
        for (int rowIndex = 0; rowIndex < table.Rows.Count; rowIndex++)
        {
            IReadOnlyDictionary<string, string> row = table.Rows[rowIndex];
            string account = RequiredText(row, "Account", "balance_history", rowIndex);
            string accountId = RequiredText(row, "Account ID", "balance_history", rowIndex);
            string accountNumber = Value(row, "Account #");
            if (identities.TryGetValue(accountId, out var prior)
                && (!string.Equals(prior.Account, account, StringComparison.OrdinalIgnoreCase)
                    || !string.Equals(prior.Number, accountNumber, StringComparison.OrdinalIgnoreCase)))
            {
                throw new DataContractException(
                    $"balance_history row {rowIndex + 2} uses an account ID for a different account.",
                    "data.inconsistent-account");
            }
            identities[accountId] = (account, accountNumber);
            AccountRule? accountRule = FindBalanceAccount(
                accounts,
                account,
                accountNumber,
                accountId);
            AccountClass sourceClass = ParseAccountClass(RequiredText(row, "Class", "balance_history", rowIndex), "balance_history", rowIndex);
            result.Add(new BalanceObservation(
                accountId,
                account,
                accountRule?.Group ?? string.Empty,
                ParseDate(RequiredText(row, "Date", "balance_history", rowIndex), "balance_history", rowIndex, "Date"),
                ParseTime(RequiredText(row, "Time", "balance_history", rowIndex), "balance_history", rowIndex),
                ParseMoney(RequiredText(row, "Balance", "balance_history", rowIndex), "balance_history", rowIndex, "Balance"),
                accountRule?.ClassOverride ?? sourceClass,
                accountRule?.IsHidden == true));
        }

        return result;
    }

    private static IReadOnlyList<BudgetEntry> ReadBudgets(IReadOnlyDictionary<string, CategoryRule> categories)
    {
        var result = new List<BudgetEntry>();
        foreach (CategoryRule category in categories.Values)
        {
            foreach ((YearMonth month, decimal amount) in category.Budgets)
                result.Add(new BudgetEntry(month, category.Category, category.Group, category.Kind, amount, category.IsHidden));
        }

        return result;
    }

    private static IReadOnlyDictionary<YearMonth, decimal> ReadBudgetValues(
        IReadOnlyDictionary<string, string> row,
        IReadOnlyList<string> headers,
        int rowIndex)
    {
        var result = new Dictionary<YearMonth, decimal>();
        foreach (string header in headers)
        {
            if (!DateOnly.TryParse(header, CultureInfo.InvariantCulture, DateTimeStyles.None, out DateOnly date))
                continue;
            string value = Value(row, header);
            if (string.IsNullOrWhiteSpace(value))
                continue;
            ValidateDate(date, "categories", rowIndex, "budget month");
            if (!result.TryAdd(
                    YearMonth.From(date),
                    ParseMoney(value, "categories", rowIndex, "budget amount")))
                throw new DataContractException($"categories row {rowIndex + 2} has duplicate budget months.");
        }

        return result;
    }

    private static AccountRule? FindTransactionAccount(IReadOnlyList<AccountRule> accounts, string account, string accountNumber)
    {
        string prefix = string.IsNullOrWhiteSpace(accountNumber) ? $"{account} -" : $"{account} - {accountNumber}";
        foreach (AccountRule candidate in accounts)
        {
            if (candidate.Account.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
                && (string.IsNullOrWhiteSpace(accountNumber)
                    || candidate.Account.Length == prefix.Length
                    || candidate.Account[prefix.Length] is ' ' or '('))
                return candidate;
        }

        return null;
    }

    private static AccountRule? FindBalanceAccount(IReadOnlyList<AccountRule> accounts, string account, string accountNumber, string accountId)
    {
        string suffix = accountId.Length >= 4 ? accountId[^4..] : accountId;
        string exact = $"{account} - {accountNumber} ({suffix})";
        foreach (AccountRule candidate in accounts)
        {
            if (string.Equals(candidate.Account, exact, StringComparison.OrdinalIgnoreCase))
                return candidate;
        }

        return FindTransactionAccount(accounts, account, accountNumber);
    }

    private static string Value(IReadOnlyDictionary<string, string> row, string column)
        => row.TryGetValue(column, out string? value) ? value : string.Empty;

    private static string RequiredText(IReadOnlyDictionary<string, string> row, string column, string source, int rowIndex)
    {
        string value = Value(row, column);
        if (!string.IsNullOrWhiteSpace(value))
            return value;
        throw new DataContractException($"{source} row {rowIndex + 2} has no value for '{column}'.");
    }

    private static string? EmptyToNull(string value) => string.IsNullOrWhiteSpace(value) ? null : value;

    private static bool ParseHidden(string value, string source, int rowIndex, string column)
        => value.Trim().ToLowerInvariant() switch
        {
            "" or "false" or "no" or "0" => false,
            "true" or "yes" or "1" => true,
            _ => throw new DataContractException($"{source} row {rowIndex + 2} has an invalid {column} value.")
        };

    private static TransactionKind ParseKind(string value)
        => value.Trim().ToLowerInvariant() switch
        {
            "income" => TransactionKind.Income,
            "expense" => TransactionKind.Expense,
            "transfer" => TransactionKind.Transfer,
            _ => TransactionKind.Unknown
        };

    private static AccountClass ParseAccountClass(string value, string source, int rowIndex)
        => value.Trim().ToLowerInvariant() switch
        {
            "asset" => AccountClass.Asset,
            "liability" => AccountClass.Liability,
            _ => throw new DataContractException($"{source} row {rowIndex + 2} has an unknown account class.")
        };

    private static DateOnly ParseDate(string value, string source, int rowIndex, string column)
    {
        string[] formats = ["M/d/yyyy", "MM/dd/yyyy", "yyyy-MM-dd", "yyyy-MM-ddTHH:mm:ss"];
        if (DateOnly.TryParseExact(value, formats, CultureInfo.InvariantCulture, DateTimeStyles.None, out DateOnly parsed)
            || DateOnly.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.None, out parsed))
        {
            ValidateDate(parsed, source, rowIndex, column);
            return parsed;
        }

        throw new DataContractException($"{source} row {rowIndex + 2} has an invalid {column} date.");
    }

    private static void ValidateDate(DateOnly date, string source, int rowIndex, string column)
    {
        if (date < EarliestSourceDate)
            throw new DataContractException(
                $"{source} row {rowIndex + 2} has a {column} date before 1900-01-01.",
                "data.date-out-of-range");
    }

    private static TimeOnly ParseTime(string value, string source, int rowIndex)
    {
        if (DateTime.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.None, out DateTime dateTime))
            return TimeOnly.FromDateTime(dateTime);
        if (TimeOnly.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.None, out TimeOnly time))
            return time;
        throw new DataContractException($"{source} row {rowIndex + 2} has an invalid Time.");
    }

    private static decimal ParseMoney(string value, string source, int rowIndex, string column)
    {
        NumberStyles styles = NumberStyles.AllowCurrencySymbol | NumberStyles.AllowDecimalPoint | NumberStyles.AllowThousands | NumberStyles.AllowLeadingSign | NumberStyles.AllowParentheses | NumberStyles.AllowLeadingWhite | NumberStyles.AllowTrailingWhite;
        if (decimal.TryParse(value, styles, CultureInfo.GetCultureInfo("en-US"), out decimal amount)
            || decimal.TryParse(value, NumberStyles.Number, CultureInfo.InvariantCulture, out amount))
        {
            return amount;
        }

        throw new DataContractException($"{source} row {rowIndex + 2} has an invalid {column} amount.");
    }

    private sealed record CategoryRule(
        string Category,
        string Group,
        TransactionKind Kind,
        bool IsHidden,
        IReadOnlyDictionary<YearMonth, decimal> Budgets);

    private sealed record AccountRule(string Account, string Group, AccountClass? ClassOverride, bool IsHidden);
}
