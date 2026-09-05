using Portico.App;
using Portico.Finance;

namespace Portico.App.Tests;

public sealed class PorticoCliTests
{
    [Fact]
    public void Parser_AcceptsRepeatableGoogleSheetOverrides()
    {
        PorticoCommand command = PorticoCommandLine.Parse(
        [
            "doctor", "--source", "google-sheets", "--secrets", "secret.toml",
            "--sheet", "transactions=https://docs.google.com/spreadsheets/d/a/edit#gid=1",
            "--sheet", "accounts=https://docs.google.com/spreadsheets/d/a/edit#gid=2",
            "--output", "json"
        ]);

        Assert.Equal(PorticoCommandKind.Doctor, command.Kind);
        Assert.Equal(WorkbookSourceKind.GoogleSheets, command.SourceOverride);
        Assert.Equal(DoctorOutput.Json, command.Output);
        Assert.Equal(2, command.SheetOverrides.Count);
    }

    [Theory]
    [InlineData("--source", "spreadsheet")]
    [InlineData("--sheet", "not-a-sheet=https://example.com")]
    [InlineData("--output", "yaml")]
    public void Parser_RejectsInvalidNonInteractiveArguments(string option, string value)
    {
        CommandLineException error = Assert.Throws<CommandLineException>(() => PorticoCommandLine.Parse(["doctor", option, value]));

        Assert.NotEmpty(error.Message);
    }

    [Fact]
    public async Task Doctor_EmitsOneRedactedJsonDocumentForTheDemo()
    {
        string root = FindRepositoryRoot();
        var output = new StringWriter();
        var error = new StringWriter();

        int exitCode = await PorticoCli.RunAsync(
        [
            "doctor", "--config", Path.Combine(root, "portico-demo.toml"),
            "--dashboard", Path.Combine(root, "dashboard.toml"), "--output", "json"
        ],
        output,
        error);

        string json = output.ToString();
        Assert.Equal(0, exitCode);
        Assert.True(string.IsNullOrWhiteSpace(error.ToString()));
        Assert.Contains("\"Ready\":true", json, StringComparison.Ordinal);
        Assert.Contains("\"PageCount\":10", json, StringComparison.Ordinal);
        Assert.DoesNotContain("demo/data", json, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Help_ExplainsTheMachineReadableDoctorContract()
    {
        var output = new StringWriter();
        var error = new StringWriter();

        int exitCode = await PorticoCli.RunAsync(["--help"], output, error);

        Assert.Equal(0, exitCode);
        Assert.True(string.IsNullOrWhiteSpace(error.ToString()));
        Assert.Contains("AI_CONTEXT:", output.ToString(), StringComparison.Ordinal);
        Assert.Contains("doctor --output json", output.ToString(), StringComparison.Ordinal);
        Assert.Contains("Exit codes: 0 ready", output.ToString(), StringComparison.Ordinal);
    }

    [Fact]
    public async Task Doctor_ReturnsConfigExitCodeForASecretLikeBadOption()
    {
        string root = FindRepositoryRoot();
        var output = new StringWriter();
        var error = new StringWriter();

        int exitCode = await PorticoCli.RunAsync(
        [
            "doctor", "--config", Path.Combine(root, "portico-demo.toml"),
            "--dashboard", Path.Combine(root, "dashboard.toml"),
            "--source", "google-sheets", "--sheet", "transactions=private-value"
        ],
        output,
        error);

        Assert.Equal(3, exitCode);
        Assert.DoesNotContain("private-value", error.ToString(), StringComparison.Ordinal);
    }

    [Fact]
    public async Task Doctor_RejectsDashboardFilterValuesMissingFromFinanceConfiguration()
    {
        string root = FindRepositoryRoot();
        string dashboard = Path.Combine(Path.GetTempPath(), $"portico-dashboard-{Guid.NewGuid():N}.toml");
        await File.WriteAllTextAsync(dashboard, """
            schema_version = 1
            app_title = "Portico"
            [[pages]]
            id = "home"
            title = "Home"
            icon = "home"
            description = "Overview"
            group = "standalone"
            order = 1
            rail_label = "Home"
            page_heading = "Accounts and net worth"
            [[pages.filters]]
            id = "lookback"
            label = "Lookback"
            kind = "select"
            source = "lookback"
            default = "99"
            options = ["99"]
            [[pages.widgets]]
            id = "net-worth"
            title = "Net worth"
            kind = "area_chart"
            report = "home.net_worth"
            """, TestContext.Current.CancellationToken);
        var output = new StringWriter();
        var error = new StringWriter();

        int exitCode = await PorticoCli.RunAsync(
            ["doctor", "--config", Path.Combine(root, "portico-demo.toml"), "--dashboard", dashboard],
            output,
            error);

        Assert.Equal(2, exitCode);
        Assert.Contains("not configured", error.ToString(), StringComparison.Ordinal);
    }

    [Fact]
    public async Task Doctor_RejectsReportInputControlValuesMissingFromFinanceConfiguration()
    {
        string root = FindRepositoryRoot();
        string dashboard = Path.Combine(Path.GetTempPath(), $"portico-dashboard-{Guid.NewGuid():N}.toml");
        await File.WriteAllTextAsync(dashboard, """
            schema_version = 1
            app_title = "Portico"
            [[pages]]
            id = "income_savings"
            title = "Income and savings"
            icon = "savings"
            description = "Overview"
            group = "analyze"
            order = 1
            rail_label = "Income and savings"
            page_heading = "Income and savings"
            [[pages.controls]]
            id = "income_view"
            label = "View"
            kind = "select"
            source = "income_view"
            default = "impossible"
            options = ["impossible"]
            [[pages.widgets]]
            id = "cash-flow"
            title = "Monthly cash flow"
            kind = "combo_chart"
            report = "income.cash_flow"
            bar_series = ["income", "spending"]
            """, TestContext.Current.CancellationToken);
        var output = new StringWriter();
        var error = new StringWriter();

        int exitCode = await PorticoCli.RunAsync(
            ["doctor", "--config", Path.Combine(root, "portico-demo.toml"), "--dashboard", dashboard],
            output,
            error);

        Assert.Equal(2, exitCode);
        Assert.Contains("report filter 'income_view'", error.ToString(), StringComparison.Ordinal);
    }

    [Fact]
    public async Task Doctor_RejectsUnsupportedDashboardReports()
    {
        string root = FindRepositoryRoot();
        string dashboard = Path.Combine(Path.GetTempPath(), $"portico-dashboard-{Guid.NewGuid():N}.toml");
        await File.WriteAllTextAsync(dashboard, """
            schema_version = 1
            app_title = "Portico"
            [[pages]]
            id = "home"
            title = "Home"
            icon = "home"
            description = "Overview"
            group = "standalone"
            order = 1
            rail_label = "Home"
            page_heading = "Accounts and net worth"
            [[pages.widgets]]
            id = "unknown"
            title = "Unknown"
            kind = "metric"
            report = "missing.report"
            """, TestContext.Current.CancellationToken);
        var output = new StringWriter();
        var error = new StringWriter();

        int exitCode = await PorticoCli.RunAsync(
            ["doctor", "--config", Path.Combine(root, "portico-demo.toml"), "--dashboard", dashboard],
            output,
            error);

        Assert.Equal(2, exitCode);
        Assert.Contains("supported report", error.ToString(), StringComparison.Ordinal);
    }

    private static string FindRepositoryRoot()
    {
        string[] startingPoints = [Directory.GetCurrentDirectory(), AppContext.BaseDirectory];
        foreach (string start in startingPoints)
        {
            var current = new DirectoryInfo(start);
            while (current is not null)
            {
                if (File.Exists(Path.Combine(current.FullName, "portico-demo.toml"))
                    && File.Exists(Path.Combine(current.FullName, "dashboard.toml")))
                {
                    return current.FullName;
                }

                current = current.Parent;
            }
        }

        throw new InvalidOperationException("Could not find the Portico repository root.");
    }
}
