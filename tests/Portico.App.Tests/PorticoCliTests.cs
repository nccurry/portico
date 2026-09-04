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
