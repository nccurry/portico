using System.Net;
using System.Net.Http;
using Portico.Adapters;
using Portico.Dashboard;
using Portico.Finance;

namespace Portico.Adapters.Tests;

public sealed class AdapterTests
{
    [Fact]
    public void CsvTable_ParsesQuotedCommasQuotesAndNewlines()
    {
        CsvTable table = CsvTable.Parse("Name,Note\r\nAda,\"one, two\"\r\nGrace,\"a \"\"quote\"\"\nand a line\"\r\n", "fixture");

        Assert.Equal(["Name", "Note"], table.Headers);
        Assert.Equal("one, two", table.Rows[0]["Note"]);
        Assert.Equal("a \"quote\"\nand a line", table.Rows[1]["Note"]);
    }

    [Theory]
    [InlineData("https://docs.google.com/spreadsheets/d/document-123/edit#gid=456", "document-123", 456)]
    [InlineData("https://docs.google.com/spreadsheets/d/document-123/view?gid=0", "document-123", 0)]
    public void GoogleSheetExportUrl_ParsesPublicPageUrl(string input, string expectedDocument, long expectedGid)
    {
        GoogleSheetExportUrl result = GoogleSheetExportUrl.Parse(input);

        Assert.Equal(expectedDocument, result.DocumentId);
        Assert.Equal(expectedGid, result.Gid);
        Assert.Equal($"https://docs.google.com/spreadsheets/d/{expectedDocument}/export?format=csv&gid={expectedGid}", result.ExportUri.AbsoluteUri);
    }

    [Theory]
    [InlineData("http://docs.google.com/spreadsheets/d/a/edit#gid=1")]
    [InlineData("https://example.com/spreadsheets/d/a/edit#gid=1")]
    [InlineData("https://docs.google.com/spreadsheets/d/a/edit")]
    public void GoogleSheetExportUrl_RejectsInvalidUrlsWithoutEchoingInput(string input)
    {
        DataLoadException error = Assert.Throws<DataLoadException>(() => GoogleSheetExportUrl.Parse(input));

        Assert.DoesNotContain(input, error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void WorkbookNormalizer_ClassifiesRowsAppliesAccountRulesAndBuildsBudgets()
    {
        IReadOnlyDictionary<string, CsvTable> tables = Tables();

        PortfolioSnapshot snapshot = WorkbookNormalizer.Normalize(tables);

        FinancialTransaction expense = Assert.Single(snapshot.Transactions, row => row.Id == "1");
        Assert.Equal(TransactionKind.Expense, expense.Kind);
        Assert.Equal("Living", expense.Group);
        Assert.False(expense.IsHidden);
        BalanceObservation liability = Assert.Single(snapshot.Balances, row => row.AccountId == "card");
        Assert.Equal(AccountClass.Liability, liability.AccountClass);
        Assert.Equal("Debt", liability.Group);
        BudgetEntry budget = Assert.Single(snapshot.Budgets, row => row.Category == "Food");
        Assert.Equal(new YearMonth(2024, 1), budget.Month);
        Assert.Equal(300m, budget.Amount);
    }

    [Fact]
    public async Task LocalAndGoogleSources_NormalizeTheSameWorkbook()
    {
        IReadOnlyDictionary<string, string> documents = Documents();
        string directory = Path.Combine(Path.GetTempPath(), $"portico-adapter-{Guid.NewGuid():N}");
        Directory.CreateDirectory(directory);
        foreach ((string name, string content) in documents)
            await File.WriteAllTextAsync(Path.Combine(directory, $"{name}.csv"), content, TestContext.Current.CancellationToken);

        PortfolioSnapshot local = await new LocalCsvSnapshotSource(directory).LoadAsync(TestContext.Current.CancellationToken);
        using var client = new HttpClient(new StaticResponseHandler(documents));
        var settings = new SheetUrlSettings(new Dictionary<string, string>
        {
            ["transactions"] = "https://docs.google.com/spreadsheets/d/demo/edit#gid=1",
            ["balance_history"] = "https://docs.google.com/spreadsheets/d/demo/edit#gid=2",
            ["categories"] = "https://docs.google.com/spreadsheets/d/demo/edit#gid=3",
            ["accounts"] = "https://docs.google.com/spreadsheets/d/demo/edit#gid=4"
        });

        PortfolioSnapshot remote = await new GoogleSheetsSnapshotSource(client, settings).LoadAsync(TestContext.Current.CancellationToken);

        Assert.Equal(local.Transactions, remote.Transactions);
        Assert.Equal(local.Balances, remote.Balances);
        Assert.Equal(local.Budgets, remote.Budgets);
    }

    [Fact]
    public async Task GoogleSource_ReportsHttpFailuresWithoutEchoingTheSheetUrl()
    {
        using var client = new HttpClient(new StatusResponseHandler(HttpStatusCode.Forbidden));
        var settings = new SheetUrlSettings(new Dictionary<string, string>
        {
            ["transactions"] = "https://docs.google.com/spreadsheets/d/private-document/edit#gid=1"
        });

        DataLoadException error = await Assert.ThrowsAsync<DataLoadException>(() =>
            new GoogleSheetsSnapshotSource(client, settings).LoadAsync(TestContext.Current.CancellationToken));

        Assert.Contains("transactions", error.Message, StringComparison.Ordinal);
        Assert.Contains("HTTP 403", error.Message, StringComparison.Ordinal);
        Assert.DoesNotContain("private-document", error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void ConfigurationLoader_ParsesExistingFinanceShapeAndDashboardGrammar()
    {
        string directory = Path.Combine(Path.GetTempPath(), $"portico-config-{Guid.NewGuid():N}");
        Directory.CreateDirectory(directory);
        string financePath = Path.Combine(directory, "finance.toml");
        string dashboardPath = Path.Combine(directory, "dashboard.toml");
        File.WriteAllText(financePath, FinanceToml());
        File.WriteAllText(dashboardPath, DashboardToml());

        FinanceSettings finance = TomlConfigurationLoader.LoadFinance(financePath);
        Portico.Dashboard.DashboardDefinition dashboard = TomlConfigurationLoader.LoadDashboard(dashboardPath);

        Assert.Equal(WorkbookSourceKind.LocalCsv, finance.Data.Kind);
        Assert.Equal(12, finance.Lookback.DefaultMonths);
        Assert.Equal("discretionary", finance.FilterSet("spending").Default);
        Assert.Single(dashboard.Pages);
        Assert.Equal("home.net_worth", dashboard.Pages[0].Widgets[0].Report);
        Assert.Equal(DashboardNavigationGroup.Standalone, dashboard.Pages[0].NavigationGroup);
        Assert.Equal(1, dashboard.Pages[0].NavigationOrder);
        Assert.Equal("Home", dashboard.Pages[0].RailLabel);
        Assert.Equal("Accounts and net worth", dashboard.Pages[0].PageHeading);
        Assert.Equal(DashboardNavigationIcon.Home, dashboard.Pages[0].Icon);
    }

    [Fact]
    public void ConfigurationLoader_RejectsUnknownNavigationMetadata()
    {
        string path = Path.Combine(Path.GetTempPath(), $"portico-dashboard-{Guid.NewGuid():N}.toml");
        File.WriteAllText(
            path,
            DashboardToml()
                .Replace("group = \"standalone\"", "group = \"unknown\"", StringComparison.Ordinal)
                .Replace("icon = \"home\"", "icon = \"unknown\"", StringComparison.Ordinal));

        ConfigurationException error = Assert.Throws<ConfigurationException>(() => TomlConfigurationLoader.LoadDashboard(path));

        Assert.Contains(error.Errors, item => item.Path.EndsWith(".group", StringComparison.Ordinal));
        Assert.Contains(error.Errors, item => item.Path.EndsWith(".icon", StringComparison.Ordinal));
    }

    [Fact]
    public void ConfigurationLoader_ReportsBadDashboardKind()
    {
        string path = Path.Combine(Path.GetTempPath(), $"portico-dashboard-{Guid.NewGuid():N}.toml");
        File.WriteAllText(path, "schema_version = 1\napp_title = 'Portico'\n[[pages]]\nid = 'home'\ntitle = 'Home'\ndescription = 'x'\n[[pages.widgets]]\nid = 'x'\ntitle = 'x'\nkind = 'impossible'\nreport = 'home.net_worth'\n");

        ConfigurationException error = Assert.Throws<ConfigurationException>(() => TomlConfigurationLoader.LoadDashboard(path));

        Assert.Contains(error.Errors, item => item.Path.Contains("kind", StringComparison.Ordinal));
    }

    [Fact]
    public void ConfigurationLoader_RequiresBarSeriesForAComboChart()
    {
        string path = Path.Combine(Path.GetTempPath(), $"portico-dashboard-{Guid.NewGuid():N}.toml");
        File.WriteAllText(path, "schema_version = 1\napp_title = 'Portico'\n[[pages]]\nid = 'home'\ntitle = 'Home'\ndescription = 'x'\n[[pages.widgets]]\nid = 'x'\ntitle = 'x'\nkind = 'combo_chart'\nreport = 'home.net_worth'\n");

        ConfigurationException error = Assert.Throws<ConfigurationException>(() => TomlConfigurationLoader.LoadDashboard(path));

        Assert.Contains(error.Errors, item => item.Message.Contains("bar_series", StringComparison.Ordinal));
    }

    [Fact]
    public void ConfigurationLoader_RejectsFinanceValuesOutsideTheExistingConfigRange()
    {
        string path = Path.Combine(Path.GetTempPath(), $"portico-finance-{Guid.NewGuid():N}.toml");
        File.WriteAllText(path, FinanceToml().Replace("expected_return_rate = 7", "expected_return_rate = 21", StringComparison.Ordinal));

        ConfigurationException error = Assert.Throws<ConfigurationException>(() => TomlConfigurationLoader.LoadFinance(path));

        Assert.Contains(error.Errors, item => item.Path == "financial_independence");
    }

    private static IReadOnlyDictionary<string, CsvTable> Tables()
        => Documents().ToDictionary(pair => pair.Key, pair => CsvTable.Parse(pair.Value, pair.Key), StringComparer.OrdinalIgnoreCase);

    private static IReadOnlyDictionary<string, string> Documents()
        => new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["transactions"] = "Unnamed: 0,Date,Category,Amount,Account,Account #,Full Description\n1,01/02/2024,Food,\"-$12.50\",Checking,xxxx1,Store\n2,01/03/2024,Salary,$1000,Checking,xxxx1,Pay\n",
            ["balance_history"] = "Date,Time,Account,Account #,Account ID,Balance,Class\n01/03/2024,2024-01-03 08:00:00,Checking,xxxx1,checking,$987.50,Asset\n01/03/2024,2024-01-03 08:00:00,Card,xxxx2,card,$50,Liability\n",
            ["categories"] = "Category,Group,Type,Hide From Reports,2024-01-01\nFood,Living,Expense,,300\nSalary,Income,Income,,0\n",
            ["accounts"] = "Account,Class Override,Group,Hide\nChecking - xxxx1 (king),,Cash,\nCard - xxxx2 (card),Liability,Debt,\n"
        };

    private static string FinanceToml() => """
        [data]
        source = "local"
        directory = "demo/data"
        [lookback]
        lookback_months = [3, 6, 12]
        default_lookback_months = 12
        [thresholds]
        expense = 1000
        income = 5000
        duplicate_minimum = 10
        duplicate_days = 1
        [merchants.aliases]
        [transaction_sets.all]
        label = "All"
        groups = []
        categories = []
        accounts = []
        merchants = []
        transactions_like = []
        includes = []
        excludes = []
        [transaction_sets.discretionary]
        label = "Discretionary"
        groups = []
        categories = []
        accounts = []
        merchants = []
        transactions_like = []
        includes = ["all"]
        excludes = []
        [filter_sets.spending]
        options = ["all", "discretionary"]
        default = "discretionary"
        [filter_sets.year_over_year]
        options = ["all"]
        default = "all"
        [income_savings]
        default_view = "regular"
        target_rate = 20
        exclude_categories = []
        exclude_groups = []
        [subscriptions]
        known_categories = []
        minimum_confidence = 80
        stale_after_days = 45
        default_exclude_categories = []
        detection_excluded_categories = []
        [budget]
        history_months = 12
        [data_health]
        stale_account_days = 7
        duplicate_require_same_account = true
        duplicate_require_same_category = false
        duplicate_require_same_description = true
        [financial_safety]
        emergency_fund_target_months = 6
        emergency_fund_included_groups = []
        emergency_fund_included_account_patterns = []
        emergency_fund_spending_lookback_months = 6
        emergency_fund_exclude_categories = []
        emergency_fund_exclude_groups = []
        debt_included_groups = []
        debt_included_account_patterns = []
        debt_baseline_date = ""
        [financial_independence]
        expected_return_rate = 7
        withdrawal_rate = 4
        target_amount = 1000000
        spending_lookback_months = 12
        projection_years = 30
        included_account_patterns = []
        included_groups = []
        """;

    private static string DashboardToml() => """
        schema_version = 1
        app_title = "Portico"
        [[pages]]
        id = "home"
        title = "Home"
        description = "Overview"
        group = "standalone"
        order = 1
        rail_label = "Home"
        page_heading = "Accounts and net worth"
        icon = "home"
        [[pages.widgets]]
        id = "net-worth"
        title = "Net worth"
        kind = "area_chart"
        report = "home.net_worth"
        """;

    private sealed class StaticResponseHandler : HttpMessageHandler
    {
        private readonly IReadOnlyDictionary<string, string> _documents;

        public StaticResponseHandler(IReadOnlyDictionary<string, string> documents) => _documents = documents;

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string gid = request.RequestUri!.Query.Split("gid=", StringSplitOptions.None)[1];
            string name = gid switch
            {
                "1" => "transactions",
                "2" => "balance_history",
                "3" => "categories",
                "4" => "accounts",
                _ => throw new InvalidOperationException("Unexpected gid.")
            };
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(_documents[name])
            });
        }
    }

    private sealed class StatusResponseHandler(HttpStatusCode statusCode) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            => Task.FromResult(new HttpResponseMessage(statusCode));
    }
}
