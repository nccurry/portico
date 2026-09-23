using Portico.Cli;

namespace Portico.Cli.Tests;

public sealed class CommandLineTests
{
    [Theory]
    [InlineData(new string[0], PorticoCommandKind.Run)]
    [InlineData(new[] { "run" }, PorticoCommandKind.Run)]
    [InlineData(new[] { "config", "check" }, PorticoCommandKind.ConfigCheck)]
    [InlineData(new[] { "data", "check" }, PorticoCommandKind.DataCheck)]
    [InlineData(new[] { "doctor" }, PorticoCommandKind.Doctor)]
    [InlineData(new[] { "help" }, PorticoCommandKind.Help)]
    [InlineData(new[] { "--help" }, PorticoCommandKind.Help)]
    [InlineData(new[] { "run", "--help" }, PorticoCommandKind.Help)]
    public void ParserRecognizesCommands(string[] arguments, PorticoCommandKind expected)
    {
        PorticoCommand command = PorticoCommandLine.Parse(arguments);

        Assert.Equal(expected, command.Kind);
        Assert.Null(command.Selection.ConfigurationPath);
        Assert.Null(command.Selection.SecretsPath);
        Assert.Null(command.DashboardPath);
        Assert.Equal(OutputFormat.Text, command.Output);
    }

    [Fact]
    public void ParserKeepsExplicitSelectionsWithoutResolvingPaths()
    {
        PorticoCommand command = PorticoCommandLine.Parse(
            ["run", "--secrets", "chosen.secrets.toml", "--dashboard", "chosen.dashboard.toml", "--config", "chosen.toml"]);

        Assert.Equal("chosen.toml", command.Selection.ConfigurationPath);
        Assert.Equal("chosen.secrets.toml", command.Selection.SecretsPath);
        Assert.Equal("chosen.dashboard.toml", command.DashboardPath);
    }

    [Theory]
    [InlineData("config", "check")]
    [InlineData("data", "check")]
    [InlineData("doctor", "")]
    public void ParserAllowsJsonOnlyOnChecks(string first, string second)
    {
        string[] command = second.Length == 0 ? [first, "--output", "json"] : [first, second, "--output", "json"];

        Assert.Equal(OutputFormat.Json, PorticoCommandLine.Parse(command).Output);
    }

    [Theory]
    [InlineData("run --output json")]
    [InlineData("doctor --dashboard dashboard.toml")]
    [InlineData("config check --dashboard dashboard.toml")]
    [InlineData("data check --dashboard dashboard.toml")]
    [InlineData("doctor --source google-sheets")]
    [InlineData("doctor --data-dir private")]
    [InlineData("doctor --sheet transactions=private-url")]
    [InlineData("doctor --output yaml")]
    [InlineData("doctor --config")]
    [InlineData("doctor --config one --config two")]
    [InlineData("doctor --secrets one --secrets two")]
    [InlineData("run --dashboard one --dashboard two")]
    [InlineData("doctor --output text --output json")]
    [InlineData("missing private-url")]
    [InlineData("config missing")]
    [InlineData("data")]
    public void ParserRejectsInvalidOrInapplicableOptionsWithoutEchoingValues(string commandLine)
    {
        CommandLineException error = Assert.Throws<CommandLineException>(
            () => PorticoCommandLine.Parse(commandLine.Split(' ', StringSplitOptions.RemoveEmptyEntries)));

        Assert.NotEmpty(error.Message);
        Assert.DoesNotContain("private", error.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void ParserRejectsBlankOptionValue()
        => Assert.Throws<CommandLineException>(() => PorticoCommandLine.Parse(["doctor", "--config", ""]));

    [Fact]
    public void HelpExplainsAutomationAndInteractiveBehavior()
    {
        var output = new StringWriter();

        Assert.Equal(0, PorticoCli.WriteHelp(output));
        Assert.Contains("AI_CONTEXT:", output.ToString(), StringComparison.Ordinal);
        Assert.Contains("--output json", output.ToString(), StringComparison.Ordinal);
        Assert.Contains("interactive desktop window", output.ToString(), StringComparison.Ordinal);
        Assert.Contains("Exit codes: 0", output.ToString(), StringComparison.Ordinal);
    }
}
