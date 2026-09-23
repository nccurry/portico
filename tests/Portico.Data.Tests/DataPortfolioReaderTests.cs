using System.Net;
using Portico.Application;
using Portico.Data;
using Portico.Finance;

namespace Portico.Data.Tests;

public sealed class DataPortfolioReaderTests
{
    private static readonly HttpClient UnusedHttpClient = new();

    [Fact]
    public async Task CsvAndFakeGoogle_ProduceTheSameNormalizedSnapshot()
    {
        using var fixture = new WorkbookFixture();
        PortfolioSnapshot local = Success(await Local(fixture));
        using var client = new HttpClient(new WorkbookHandler(fixture.Documents));
        PortfolioSnapshot remote = Success(await new DataPortfolioReader(client).ReadAsync(
            Sheets(), TestContext.Current.CancellationToken));

        Assert.Equal(local.Transactions, remote.Transactions);
        Assert.Equal(local.Balances, remote.Balances);
        Assert.Equal(local.Budgets, remote.Budgets);
        Assert.Equal("Living", local.Transactions[0].Group);
        Assert.Equal(TransactionKind.Expense, local.Transactions[0].Kind);
        Assert.Equal(-12.50m, local.Transactions[0].Amount);
        Assert.Equal(AccountClass.Liability, local.Balances[1].AccountClass);
        Assert.Equal("Debt", local.Balances[1].Group);
        Assert.Equal(300m, Assert.Single(local.Budgets, value => value.Category == "Food").Amount);
    }

    [Fact]
    public async Task HeaderOnlyTables_ProduceAnEmptySnapshot()
    {
        using var fixture = new WorkbookFixture();
        foreach (string table in fixture.Documents.Keys.ToArray())
            fixture.Replace(table, fixture.Documents[table].Split('\n')[0] + "\n");

        PortfolioSnapshot snapshot = Success(await Local(fixture));

        Assert.Empty(snapshot.Transactions);
        Assert.Empty(snapshot.Balances);
        Assert.Empty(snapshot.Budgets);
    }

    [Fact]
    public async Task MissingDirectory_IsNonRetryableAndHidesPath()
    {
        using var fixture = new WorkbookFixture();
        PorticoFailure failure = Failure(await Reader().ReadAsync(
            new LocalCsvSourceRequest(Path.Combine(fixture.DirectoryPath, "missing")),
            TestContext.Current.CancellationToken));

        AssertProblem(failure, "data.missing-directory", false);
        Assert.DoesNotContain(fixture.DirectoryPath, failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData("transactions")]
    [InlineData("balance_history")]
    [InlineData("categories")]
    [InlineData("accounts")]
    public async Task MissingFile_IdentifiesItsSafeTableName(string table)
    {
        using var fixture = new WorkbookFixture();
        fixture.Remove(table);

        PorticoFailure failure = Failure(await Local(fixture));

        AssertProblem(failure, "data.missing-file", false);
        Assert.Contains(table, failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData("transactions", "Date")]
    [InlineData("transactions", "Category")]
    [InlineData("transactions", "Amount")]
    [InlineData("transactions", "Account")]
    [InlineData("transactions", "Full Description")]
    [InlineData("balance_history", "Date")]
    [InlineData("balance_history", "Time")]
    [InlineData("balance_history", "Account")]
    [InlineData("balance_history", "Account #")]
    [InlineData("balance_history", "Account ID")]
    [InlineData("balance_history", "Balance")]
    [InlineData("balance_history", "Class")]
    [InlineData("categories", "Category")]
    [InlineData("categories", "Group")]
    [InlineData("categories", "Type")]
    [InlineData("categories", "Hide From Reports")]
    [InlineData("accounts", "Account")]
    [InlineData("accounts", "Class Override")]
    [InlineData("accounts", "Group")]
    [InlineData("accounts", "Hide")]
    public async Task MissingRequiredColumn_IsADataProblem(string table, string column)
    {
        using var fixture = new WorkbookFixture();
        string document = fixture.Documents[table];
        int firstNewline = document.IndexOf('\n');
        string[] headers = document[..firstNewline].TrimEnd('\r').Split(',');
        int index = Array.IndexOf(headers, column);
        Assert.True(index >= 0, $"The fixture must contain the {column} header.");
        headers[index] = "Missing";
        fixture.Replace(table, string.Join(",", headers) + document[firstNewline..]);

        PorticoFailure failure = Failure(await Local(fixture));

        AssertProblem(failure, "data.invalid", false);
        Assert.Contains(column, failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData("transactions", "01/02/2024", "private-date")]
    [InlineData("transactions", "-$12.50", "private-money")]
    [InlineData("balance_history", "2024-01-03 08:00:00", "private-time")]
    [InlineData("balance_history", "Liability", "private-class")]
    public async Task MalformedValue_UsesSafeMessage(string table, string oldValue, string privateValue)
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace(table, fixture.Documents[table].Replace(oldValue, privateValue, StringComparison.Ordinal));

        PorticoFailure failure = Failure(await Local(fixture));

        AssertProblem(failure, "data.invalid", false);
        Assert.DoesNotContain(privateValue, failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ContradictoryAccountId_IsADataProblem()
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace("balance_history", fixture.Documents["balance_history"]
            .Replace("Card,xxxx2,card", "Card,xxxx2,checking", StringComparison.Ordinal));

        PorticoFailure failure = Failure(await Local(fixture));

        AssertProblem(failure, "data.inconsistent-account", false);
        Assert.DoesNotContain("checking", failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task DuplicateAccountRule_IsRejectedWithoutShowingItsName()
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace("accounts", fixture.Documents["accounts"]
            + "Checking - xxxx1 (king),,Other,\n");

        PorticoFailure failure = Failure(await Local(fixture));

        AssertProblem(failure, "data.invalid", false);
        Assert.DoesNotContain("Checking", failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task SimilarAccountNumbers_DoNotApplyTheWrongHideRule()
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace("accounts", fixture.Documents["accounts"]
            .Replace("Checking - xxxx1 (king),,Cash,",
                "Checking - xxxx10 (other),,Other,true\nChecking - xxxx1 (king),,Cash,",
                StringComparison.Ordinal));

        PortfolioSnapshot snapshot = Success(await Local(fixture));

        Assert.False(snapshot.Transactions[0].IsHidden);
        Assert.Equal("Cash", snapshot.Balances[0].Group);
    }

    [Fact]
    public async Task QuotedCsvFieldsKeepCommasQuotesAndNewlines()
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace("transactions", fixture.Documents["transactions"]
            .Replace("Store", "\"Store, \"\"North\"\"\nMain Street\"", StringComparison.Ordinal));

        FinancialTransaction transaction = Success(await Local(fixture)).Transactions[0];

        Assert.Equal("Store, \"North\"\nMain Street", transaction.Description);
    }

    [Fact]
    public async Task InvalidQuotePlacement_IsADataProblem()
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace("transactions", fixture.Documents["transactions"]
            .Replace("Store", "Store\"private", StringComparison.Ordinal));

        PorticoFailure failure = Failure(await Local(fixture));

        AssertProblem(failure, "data.invalid", false);
        Assert.DoesNotContain("private", failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData("categories", "Food,Living,Expense,,300", "Food,Living,Expense,private-hide,300")]
    [InlineData("accounts", "Card - xxxx2 (card),Liability,Debt,", "Card - xxxx2 (card),Liability,Debt,private-hide")]
    public async Task InvalidHideFlag_IsADataProblem(string table, string original, string invalid)
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace(table, fixture.Documents[table].Replace(original, invalid, StringComparison.Ordinal));

        PorticoFailure failure = Failure(await Local(fixture));

        AssertProblem(failure, "data.invalid", false);
        Assert.DoesNotContain("private-hide", failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task HideToken_HidesCategoryRows()
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace("categories", fixture.Documents["categories"]
            .Replace("Food,Living,Expense,,300", "Food,Living,Expense,Hide,300", StringComparison.Ordinal));

        PortfolioSnapshot snapshot = Success(await Local(fixture));

        Assert.True(snapshot.Transactions[0].IsHidden);
        Assert.True(Assert.Single(snapshot.Budgets, entry => entry.Category == "Food").IsHidden);
    }

    [Fact]
    public async Task UnknownCategory_RemainsForDataHealth()
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace("transactions", fixture.Documents["transactions"]
            .Replace("Food,-$12.50", "NotListed,-$12.50", StringComparison.Ordinal));

        FinancialTransaction transaction = Success(await Local(fixture)).Transactions[0];

        Assert.Equal("Uncategorized", transaction.Group);
        Assert.Equal(TransactionKind.Unknown, transaction.Kind);
    }

    [Theory]
    [InlineData("transactions", "01/02/2024", "12/31/1899")]
    [InlineData("balance_history", "01/03/2024", "12/31/1899")]
    [InlineData("categories", "2024-01-01", "1899-12-01")]
    public async Task DateBefore1900_IsRejectedBeforeReports(string table, string oldDate, string earlyDate)
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace(table, fixture.Documents[table].Replace(oldDate, earlyDate, StringComparison.Ordinal));

        PorticoFailure failure = Failure(await Local(fixture));

        AssertProblem(failure, "data.date-out-of-range", false);
        Assert.DoesNotContain(earlyDate, failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task DateAtFloor_AllowsLargestConfiguredPriorPeriod()
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace("transactions", fixture.Documents["transactions"]
            .Replace("01/02/2024", "01/01/1900", StringComparison.Ordinal)
            .Replace("01/03/2024", "01/02/1900", StringComparison.Ordinal));
        fixture.Replace("balance_history", fixture.Documents["balance_history"]
            .Replace("01/03/2024", "01/01/1900", StringComparison.Ordinal));
        fixture.Replace("categories", fixture.Documents["categories"]
            .Replace("2024-01-01", "1900-01-01", StringComparison.Ordinal));

        PortfolioSnapshot snapshot = Success(await Local(fixture));
        IncomeSavingsAnalysisResult income = IncomeSavingsAnalysisCalculator.Build(
            snapshot.Transactions,
            120,
            new IncomeSavingsAdjustments([], [], [], [], [], false, 0m, false, 0m, 0m));

        Assert.Equal(new DateOnly(1900, 1, 1), snapshot.Transactions[0].Date);
        Assert.Equal(new YearMonth(1900, 1), snapshot.Budgets[0].Month);
        Assert.Equal(120, income.Period.CurrentMonths.Count);
        Assert.Equal(120, income.Period.PreviousMonths.Count);
        Assert.Equal(new YearMonth(1880, 2), income.Period.PreviousMonths[0]);
    }

    [Fact]
    public async Task TwoBudgetHeadersForOneMonth_AreRejected()
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace("categories", fixture.Documents["categories"]
            .Replace("2024-01-01", "2024-01-01,2024-01-15", StringComparison.Ordinal)
            .Replace("Expense,,300", "Expense,,300,100", StringComparison.Ordinal)
            .Replace("Income,,0", "Income,,0,0", StringComparison.Ordinal));

        PorticoFailure failure = Failure(await Local(fixture));

        AssertProblem(failure, "data.invalid", false);
        Assert.Contains("duplicate budget months", failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData(HttpStatusCode.Forbidden, false)]
    [InlineData(HttpStatusCode.TooManyRequests, true)]
    [InlineData(HttpStatusCode.InternalServerError, true)]
    public async Task GoogleHttpFailure_HasSafeRetryPolicy(HttpStatusCode status, bool retryable)
    {
        using var client = new HttpClient(new ResponseHandler((_, _) =>
            Task.FromResult(new HttpResponseMessage(status))));

        PorticoFailure failure = Failure(await new DataPortfolioReader(client).ReadAsync(
            Sheets("private-document"), TestContext.Current.CancellationToken));

        AssertProblem(failure, "source.http-error", retryable);
        Assert.DoesNotContain("private-document", failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task GoogleTimeout_IsRetryable()
    {
        using var client = new HttpClient(new ResponseHandler((_, _) =>
            Task.FromException<HttpResponseMessage>(new TaskCanceledException())));

        PorticoFailure failure = Failure(await new DataPortfolioReader(client).ReadAsync(
            Sheets(), TestContext.Current.CancellationToken));

        AssertProblem(failure, "source.timeout", true);
    }

    [Fact]
    public async Task GoogleNetworkFailure_DoesNotExposeExceptionText()
    {
        using var client = new HttpClient(new ResponseHandler((_, _) =>
            Task.FromException<HttpResponseMessage>(
                new HttpRequestException("private URL and row value"))));

        PorticoFailure failure = Failure(await new DataPortfolioReader(client).ReadAsync(
            Sheets(), TestContext.Current.CancellationToken));

        AssertProblem(failure, "source.unavailable", true);
        Assert.DoesNotContain("private", failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task CanceledRead_ReturnsTypedCancellation()
    {
        using var canceled = new CancellationTokenSource();
        canceled.Cancel();

        PorticoFailure failure = Failure(await Reader().ReadAsync(Sheets(), canceled.Token));

        AssertProblem(failure, "operation.cancelled", true);
    }

    [Fact]
    public async Task CancellationDuringGoogleRequest_ReturnsTypedCancellation()
    {
        using var canceled = new CancellationTokenSource();
        using var client = new HttpClient(new ResponseHandler((_, token) =>
        {
            canceled.Cancel();
            return Task.FromCanceled<HttpResponseMessage>(token);
        }));

        PorticoFailure failure = Failure(await new DataPortfolioReader(client).ReadAsync(
            Sheets(), canceled.Token));

        AssertProblem(failure, "operation.cancelled", true);
    }

    [Theory]
    [InlineData("http://docs.google.com/spreadsheets/d/private/edit#gid=1")]
    [InlineData("https://example.com/spreadsheets/d/private/edit#gid=1")]
    [InlineData("https://docs.google.com/spreadsheets/d/private/edit")]
    [InlineData("https://docs.google.com/spreadsheets/d/private/edit#gid=bad")]
    public async Task InvalidGoogleUrl_IsSafe(string url)
    {
        var sheets = new GoogleSheetsSourceRequest(url, url, url, url);

        PorticoFailure failure = Failure(await Reader().ReadAsync(
            sheets, TestContext.Current.CancellationToken));

        AssertProblem(failure, "source.invalid-url", false);
        Assert.DoesNotContain("private", failure.Problems[0].Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task InvalidGoogleCsv_MatchesLocalDataProblem()
    {
        using var fixture = new WorkbookFixture();
        fixture.Replace("transactions", "Date,Category\n\"unterminated");
        PorticoFailure local = Failure(await Local(fixture));
        using var client = new HttpClient(new WorkbookHandler(fixture.Documents));
        PorticoFailure remote = Failure(await new DataPortfolioReader(client).ReadAsync(
            Sheets(), TestContext.Current.CancellationToken));

        Assert.Equal(local.Problems, remote.Problems);
        AssertProblem(remote, "data.invalid", false);
    }

    private static DataPortfolioReader Reader() => new(UnusedHttpClient);

    private static Task<PortfolioReadOutcome> Local(WorkbookFixture fixture)
        => Reader().ReadAsync(new LocalCsvSourceRequest(fixture.DirectoryPath), TestContext.Current.CancellationToken);

    private static GoogleSheetsSourceRequest Sheets(string document = "demo")
        => new(
            $"https://docs.google.com/spreadsheets/d/{document}/edit#gid=1",
            $"https://docs.google.com/spreadsheets/d/{document}/edit#gid=2",
            $"https://docs.google.com/spreadsheets/d/{document}/edit#gid=3",
            $"https://docs.google.com/spreadsheets/d/{document}/edit#gid=4");

    private static PortfolioSnapshot Success(PortfolioReadOutcome outcome) => outcome switch
    {
        PortfolioReadSuccess success => success.GetSnapshot(),
        PorticoFailure failure => throw new Xunit.Sdk.XunitException(
            $"Expected a snapshot, got {failure.Problems[0].Code}."),
        _ => throw new Xunit.Sdk.XunitException("The reader returned no outcome.")
    };

    private static PorticoFailure Failure(PortfolioReadOutcome outcome) => outcome switch
    {
        PorticoFailure failure => failure,
        _ => throw new Xunit.Sdk.XunitException("Expected a typed data failure.")
    };

    private static void AssertProblem(PorticoFailure failure, string code, bool retryable)
    {
        PorticoProblem problem = Assert.Single(failure.Problems);
        Assert.Equal(code, problem.Code);
        Assert.Equal(retryable, problem.Retryable);
    }

    private sealed class WorkbookFixture : IDisposable
    {
        public WorkbookFixture()
        {
            DirectoryPath = Path.Combine(Path.GetTempPath(), $"portico-data-{Guid.NewGuid():N}");
            Directory.CreateDirectory(DirectoryPath);
            Documents = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["transactions"] = "Unnamed: 0,Date,Category,Amount,Account,Account #,Full Description\n1,01/02/2024,Food,-$12.50,Checking,xxxx1,Store\n2,01/03/2024,Salary,$1000,Checking,xxxx1,Pay\n",
                ["balance_history"] = "Date,Time,Account,Account #,Account ID,Balance,Class\n01/03/2024,2024-01-03 08:00:00,Checking,xxxx1,checking,$987.50,Asset\n01/03/2024,2024-01-03 08:00:00,Card,xxxx2,card,$50,Liability\n",
                ["categories"] = "Category,Group,Type,Hide From Reports,2024-01-01\nFood,Living,Expense,,300\nSalary,Income,Income,,0\n",
                ["accounts"] = "Account,Class Override,Group,Hide\nChecking - xxxx1 (king),,Cash,\nCard - xxxx2 (card),Liability,Debt,\n"
            };
            foreach ((string name, string content) in Documents)
                File.WriteAllText(Path.Combine(DirectoryPath, name + ".csv"), content);
        }

        public string DirectoryPath { get; }

        public Dictionary<string, string> Documents { get; }

        public void Replace(string table, string content)
        {
            Documents[table] = content;
            File.WriteAllText(Path.Combine(DirectoryPath, table + ".csv"), content);
        }

        public void Remove(string table) => File.Delete(Path.Combine(DirectoryPath, table + ".csv"));

        public void Dispose() => Directory.Delete(DirectoryPath, recursive: true);
    }

    private sealed class WorkbookHandler(IReadOnlyDictionary<string, string> documents) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string tab = request.RequestUri!.Query[^1] switch
            {
                '1' => "transactions",
                '2' => "balance_history",
                '3' => "categories",
                '4' => "accounts",
                _ => throw new InvalidOperationException("Unexpected workbook tab.")
            };
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(documents[tab])
            });
        }
    }

    private sealed class ResponseHandler(
        Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> response) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
            => response(request, cancellationToken);
    }
}
