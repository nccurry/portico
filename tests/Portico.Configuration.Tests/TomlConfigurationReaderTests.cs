using System.Text.Json;
using Portico.Application;
using Portico.Finance;

namespace Portico.Configuration.Tests;

public sealed class TomlConfigurationReaderTests
{
    private const string PrivateUrl = "https://docs.google.com/spreadsheets/d/secret-synthetic-token/edit#gid=1";

    [Fact]
    public async Task LocalFile_MapsAllPolicyGroups()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", ValidMain());

        WorkspaceConfiguration result = Success(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken));

        Assert.Equal(Path.Combine(files.Root, "data"),
            Assert.IsType<LocalCsvSourceRequest>(result.Source).GetDirectory());
        FinanceSettings policy = result.Settings;
        Assert.Equal([3, 6, 12, 24], policy.Lookback.Months);
        Assert.Equal(12, policy.Lookback.DefaultMonths);
        Assert.Equal(3000m, policy.Thresholds.Expense);
        Assert.Equal(20000m, policy.Thresholds.Income);
        Assert.Equal(10m, policy.Thresholds.DuplicateMinimum);
        Assert.Equal(1, policy.Thresholds.DuplicateDays);
        Assert.Equal(["Market"], policy.MerchantAliases["Grocer"]);
        Assert.Equal("All spending", policy.TransactionSet("all").Label);
        Assert.Equal(["all"], policy.FilterSet("spending").Options);
        Assert.Equal("all", policy.FilterSet("year_over_year").Default);
        Assert.Equal("regular", policy.IncomeSavings.DefaultView);
        Assert.Equal(20m, policy.IncomeSavings.TargetRate);
        Assert.Equal(["Refunds"], policy.IncomeSavings.ExcludeCategories);
        Assert.Equal(["Transfers"], policy.IncomeSavings.ExcludeGroups);
        Assert.Equal(["Bills"], policy.Subscriptions.KnownCategories);
        Assert.Equal(80, policy.Subscriptions.MinimumConfidence);
        Assert.Equal(45, policy.Subscriptions.StaleAfterDays);
        Assert.Equal(["One-off"], policy.Subscriptions.DefaultExcludeCategories);
        Assert.Equal(["Transfers"], policy.Subscriptions.DetectionExcludedCategories);
        Assert.Equal(12, policy.Budget.HistoryMonths);
        Assert.Equal(7, policy.DataHealth.StaleAccountDays);
        Assert.True(policy.DataHealth.DuplicateRequireSameAccount);
        Assert.False(policy.DataHealth.DuplicateRequireSameCategory);
        Assert.True(policy.DataHealth.DuplicateRequireSameDescription);
        Assert.Equal(6, policy.FinancialSafety.EmergencyFundTargetMonths);
        Assert.Equal(["Cash"], policy.FinancialSafety.EmergencyFundIncludedGroups);
        Assert.Equal(["Checking"], policy.FinancialSafety.EmergencyFundIncludedAccountPatterns);
        Assert.Equal(6, policy.FinancialSafety.EmergencyFundSpendingLookbackMonths);
        Assert.Equal(["Excluded"], policy.FinancialSafety.EmergencyFundExcludeCategories);
        Assert.Equal(["Transfer"], policy.FinancialSafety.EmergencyFundExcludeGroups);
        Assert.Equal(["Debt"], policy.FinancialSafety.DebtIncludedGroups);
        Assert.Equal(["Loan"], policy.FinancialSafety.DebtIncludedAccountPatterns);
        Assert.Equal(new DateOnly(2024, 1, 1), policy.FinancialSafety.DebtBaselineDate);
        Assert.Equal(7m, policy.FinancialIndependence.ExpectedReturnRate);
        Assert.Equal(4m, policy.FinancialIndependence.WithdrawalRate);
        Assert.Equal(1_000_000m, policy.FinancialIndependence.TargetAmount);
        Assert.Equal(12, policy.FinancialIndependence.SpendingLookbackMonths);
        Assert.Equal(50, policy.FinancialIndependence.ProjectionYears);
        Assert.Equal(["Brokerage"], policy.FinancialIndependence.IncludedAccountPatterns);
        Assert.Equal(["Investments"], policy.FinancialIndependence.IncludedGroups);
    }

    [Fact]
    public async Task ExplicitMain_ResolvesDataFromTheSelectedFile()
    {
        using var files = new TestFiles();
        files.Write(Path.Combine("nested", "chosen.toml"), ValidMain());

        WorkspaceConfiguration result = Success(await files.Reader.ReadAsync(
            new ConfigurationSelection(Path.Combine("nested", "chosen.toml")),
            TestContext.Current.CancellationToken));

        Assert.Equal(Path.Combine(files.Root, "nested", "data"),
            Assert.IsType<LocalCsvSourceRequest>(result.Source).GetDirectory());
        Assert.Equal("config.file-not-found", Assert.Single(Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken)).Problems).Code);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public async Task GoogleSource_UsesDefaultOrExplicitSecretsAndRedactsUrls(bool explicitFile)
    {
        using var files = new TestFiles();
        files.Write("portico.toml", GoogleMain());
        string name = explicitFile ? Path.Combine("other", "chosen.toml") : "portico.secrets.toml";
        files.Write(name, Secrets());

        ConfigurationReadOutcome outcome = await files.Reader.ReadAsync(
            new ConfigurationSelection(secretsPath: explicitFile ? name : null),
            TestContext.Current.CancellationToken);
        WorkspaceConfiguration result = Success(outcome);

        Assert.Equal(PrivateUrl, Assert.IsType<GoogleSheetsSourceRequest>(result.Source).UrlFor("transactions"));
        Assert.DoesNotContain(PrivateUrl, outcome.ToString(), StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateUrl, JsonSerializer.Serialize(outcome), StringComparison.Ordinal);
        Assert.DoesNotContain(PrivateUrl, JsonSerializer.Serialize(result), StringComparison.Ordinal);
    }

    [Fact]
    public async Task MissingSecrets_IdentifiesOnlyTheRequiredSetting()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", GoogleMain());
        files.Write("portico.secrets.toml", Secrets().Replace(
            $"transactions = \"{PrivateUrl}\"", "", StringComparison.Ordinal));

        PorticoFailure failure = Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken));

        PorticoProblem problem = Assert.Single(failure.Problems);
        Assert.Equal("config.missing-secret", problem.Code);
        Assert.Equal("sheets.transactions", problem.Field);
        Assert.DoesNotContain(PrivateUrl, JsonSerializer.Serialize(failure), StringComparison.Ordinal);
        Assert.DoesNotContain(files.Root, JsonSerializer.Serialize(failure), StringComparison.Ordinal);
    }

    [Fact]
    public async Task MissingSecretFile_ReturnsSafeField()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", GoogleMain());

        PorticoProblem problem = Assert.Single(Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken)).Problems);

        Assert.Equal("config.file-not-found", problem.Code);
        Assert.Equal("secrets", problem.Field);
        Assert.DoesNotContain(files.Root, problem.Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task SecretVersionAndUnknownKeys_AreReportedSeparatelyFromMainFile()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", GoogleMain());
        files.Write("portico.secrets.toml", Secrets()
            .Replace("schema_version = 1", "schema_version = 2", StringComparison.Ordinal)
            + "\n[unexpected]\nvalue = \"private\"\n");

        PorticoFailure failure = Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken));

        Assert.Contains(failure.Problems, problem =>
            problem.Code == "config.schema-version" && problem.Field == "secrets.schema_version");
        Assert.Contains(failure.Problems, problem =>
            problem.Code == "config.unknown-key" && problem.Field == "secrets");
        Assert.DoesNotContain("private", JsonSerializer.Serialize(failure), StringComparison.Ordinal);
    }

    [Fact]
    public async Task UnknownNestedKey_IsRejected()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", ValidMain().Replace(
            "source = \"local_csv\"",
            "source = \"local_csv\"\nsecret_url = \"do-not-print\"",
            StringComparison.Ordinal));

        PorticoProblem problem = Assert.Single(Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken)).Problems);

        Assert.Equal("config.unknown-key", problem.Code);
        Assert.Equal("data", problem.Field);
        Assert.DoesNotContain("do-not-print", JsonSerializer.Serialize(problem), StringComparison.Ordinal);
    }

    [Fact]
    public async Task UnknownKeysAndWeeklySummary_AreRejected()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", ValidMain() + """

            [weekly_summary]
            average_weeks = 8
            [extra]
            value = "not supported"
            """);

        PorticoFailure failure = Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken));

        Assert.Contains(failure.Problems, problem =>
            problem.Code == "config.unknown-key" && problem.Field == "weekly_summary");
        Assert.Contains(failure.Problems, problem =>
            problem.Code == "config.unknown-key" && problem.Field == "configuration");
    }

    [Fact]
    public async Task LegacyShape_IsRejectedEvenWithExplicitLegacyFilename()
    {
        using var files = new TestFiles();
        files.Write("config.toml", ValidMain()
            .Replace("schema_version = 1", "", StringComparison.Ordinal)
            .Replace("source = \"local_csv\"", "source = \"local\"", StringComparison.Ordinal));

        PorticoFailure failure = Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection("config.toml"), TestContext.Current.CancellationToken));

        Assert.Contains(failure.Problems, problem => problem.Code == "config.schema-version");
        Assert.Contains(failure.Problems, problem => problem.Code == "config.invalid-source");
    }

    [Fact]
    public async Task IndependentProblems_AreReportedInStableOrder()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", ValidMain()
            .Replace("default_lookback_months = 12", "default_lookback_months = 11", StringComparison.Ordinal)
            .Replace("target_rate = 20", "target_rate = 150", StringComparison.Ordinal)
            .Replace("projection_years = 50", "projection_years = 200", StringComparison.Ordinal));

        PorticoFailure failure = Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken));

        Assert.Equal(
            ["financial_independence.projection_years", "income_savings.target_rate", "lookback.default_lookback_months"],
            failure.Problems.Select(problem => problem.Field));
    }

    [Fact]
    public async Task BadSetReferences_FailBeforeFinanceUse()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", ValidMain().Replace("includes = []", "includes = [\"all\", \"missing\"]", StringComparison.Ordinal));

        PorticoFailure failure = Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken));

        Assert.Contains(failure.Problems, problem =>
            problem.Code == "config.invalid-reference" && problem.Field == "transaction_sets");
    }

    [Fact]
    public async Task EmptyDebtDateAndAbsoluteDirectory_AreSupported()
    {
        using var files = new TestFiles();
        string absoluteDirectory = Path.Combine(files.Root, "another-data-root").Replace("\\", "/", StringComparison.Ordinal);
        files.Write("portico.toml", ValidMain()
            .Replace("directory = \"data\"", $"directory = \"{absoluteDirectory}\"", StringComparison.Ordinal)
            .Replace("debt_baseline_date = \"2024-01-01\"", "debt_baseline_date = \"\"", StringComparison.Ordinal));

        WorkspaceConfiguration result = Success(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken));

        Assert.Equal(Path.GetFullPath(absoluteDirectory),
            Assert.IsType<LocalCsvSourceRequest>(result.Source).GetDirectory());
        Assert.Null(result.Settings.FinancialSafety.DebtBaselineDate);
    }

    [Fact]
    public async Task MissingNumericValue_ProducesOneProblemForItsField()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", ValidMain().Replace("expense = 3000", "", StringComparison.Ordinal));

        PorticoFailure failure = Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken));

        PorticoProblem problem = Assert.Single(failure.Problems);
        Assert.Equal("thresholds.expense", problem.Field);
        Assert.Equal("config.missing-field", problem.Code);
    }

    [Fact]
    public async Task InvalidToml_HasNoInputInItsProblem()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", "private_secret = \"do-not-print\"\n[data\n");

        PorticoProblem problem = Assert.Single(Failure(await files.Reader.ReadAsync(
            new ConfigurationSelection(), TestContext.Current.CancellationToken)).Problems);

        Assert.Equal("config.invalid-toml", problem.Code);
        Assert.DoesNotContain("do-not-print", problem.Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task PreCancelledRead_PreservesCancellationForApplication()
    {
        using var files = new TestFiles();
        files.Write("portico.toml", ValidMain());
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() =>
            files.Reader.ReadAsync(new ConfigurationSelection(), cancellation.Token));
    }

    private static WorkspaceConfiguration Success(ConfigurationReadOutcome result)
        => result switch
        {
            ConfigurationReadSuccess success => success.GetConfiguration(),
            PorticoFailure failure => throw new Xunit.Sdk.XunitException(
                "Unexpected config problems: " + string.Join(", ", failure.Problems.Select(problem => problem.Field))),
            _ => throw new Xunit.Sdk.XunitException("Expected configuration success.")
        };

    private static PorticoFailure Failure(ConfigurationReadOutcome result)
        => result switch
        {
            PorticoFailure failure => failure,
            _ => throw new Xunit.Sdk.XunitException("Expected configuration failure.")
        };

    private static string GoogleMain()
        => ValidMain()
            .Replace("source = \"local_csv\"", "source = \"google_sheets\"", StringComparison.Ordinal)
            .Replace("directory = \"data\"", "", StringComparison.Ordinal);

    private static string Secrets() => $"""
        schema_version = 1
        [sheets]
        transactions = "{PrivateUrl}"
        balance_history = "{PrivateUrl}"
        categories = "{PrivateUrl}"
        accounts = "{PrivateUrl}"
        """;

    private static string ValidMain() => """
        schema_version = 1
        [data]
        source = "local_csv"
        directory = "data"
        [lookback]
        lookback_months = [3, 6, 12, 24]
        default_lookback_months = 12
        [thresholds]
        expense = 3000
        income = 20000
        duplicate_minimum = 10
        duplicate_days = 1
        [merchants.aliases]
        Grocer = ["Market"]
        [transaction_sets.all]
        label = "All spending"
        groups = []
        categories = []
        accounts = []
        merchants = []
        transactions_like = []
        includes = []
        excludes = []
        [filter_sets.spending]
        options = ["all"]
        default = "all"
        [filter_sets.year_over_year]
        options = ["all"]
        default = "all"
        [income_savings]
        default_view = "regular"
        target_rate = 20
        exclude_categories = ["Refunds"]
        exclude_groups = ["Transfers"]
        [subscriptions]
        known_categories = ["Bills"]
        minimum_confidence = 80
        stale_after_days = 45
        default_exclude_categories = ["One-off"]
        detection_excluded_categories = ["Transfers"]
        [budget]
        history_months = 12
        [data_health]
        stale_account_days = 7
        duplicate_require_same_account = true
        duplicate_require_same_category = false
        duplicate_require_same_description = true
        [financial_safety]
        emergency_fund_target_months = 6
        emergency_fund_included_groups = ["Cash"]
        emergency_fund_included_account_patterns = ["Checking"]
        emergency_fund_spending_lookback_months = 6
        emergency_fund_exclude_categories = ["Excluded"]
        emergency_fund_exclude_groups = ["Transfer"]
        debt_included_groups = ["Debt"]
        debt_included_account_patterns = ["Loan"]
        debt_baseline_date = "2024-01-01"
        [financial_independence]
        expected_return_rate = 7
        withdrawal_rate = 4
        target_amount = 1000000
        spending_lookback_months = 12
        projection_years = 50
        included_account_patterns = ["Brokerage"]
        included_groups = ["Investments"]
        """;

    private sealed class TestFiles : IDisposable
    {
        public TestFiles()
        {
            Root = Path.Combine(Path.GetTempPath(), $"portico-config-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Root);
            Reader = new TomlConfigurationReader(Root);
        }

        public string Root { get; }
        public TomlConfigurationReader Reader { get; }

        public void Write(string name, string content)
        {
            string path = Path.Combine(Root, name);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, content);
        }

        public void Dispose()
        {
            if (Directory.Exists(Root))
                Directory.Delete(Root, recursive: true);
        }
    }
}
