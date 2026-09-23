using System.Diagnostics;
using System.Text.Json;
using Xunit;

namespace Portico.EndToEnd.Tests;

public sealed class PublishedCommandTests
{
    [Fact]
    [Trait("Category", "PublishedProcess")]
    public async Task PublishedExecutable_ChecksCopiedSyntheticConfigurationAndData()
    {
        string repository = FindRepositoryRoot();
        using var fixture = new TemporaryDirectory();
        string executable = await PublishAsync(repository, fixture.Path);
        string scenario = Path.Combine(fixture.Path, "scenario");
        Directory.CreateDirectory(scenario);
        CopyDemo(repository, scenario);

        ProcessResult config = await RunAsync(executable, scenario, "config", "check", "--output", "json");
        Assert.Equal(0, config.ExitCode);
        Assert.Empty(config.Error);
        AssertResponse(config.Output, "config-check", "success", "local_csv");

        ProcessResult data = await RunAsync(executable, scenario, "data", "check", "--output", "json");
        Assert.Equal(0, data.ExitCode);
        Assert.Empty(data.Error);
        AssertResponse(data.Output, "data-check", "success", "local_csv", 986, 432, 1344);

        ProcessResult doctor = await RunAsync(executable, scenario, "doctor", "--output", "json");
        Assert.Equal(0, doctor.ExitCode);
        Assert.Empty(doctor.Error);
        AssertResponse(doctor.Output, "doctor", "success", "local_csv", 986, 432, 1344);

        ProcessResult textDoctor = await RunAsync(executable, scenario, "doctor");
        Assert.Equal(0, textDoctor.ExitCode);
        Assert.Empty(textDoctor.Error);
        Assert.Contains("ready", textDoctor.Output, StringComparison.OrdinalIgnoreCase);

        const string privateUrl = "https://private.example/account-token";
        ProcessResult rejectedOption = await RunAsync(executable, scenario, "doctor", "--sheet", privateUrl);
        Assert.Equal(2, rejectedOption.ExitCode);
        Assert.Empty(rejectedOption.Output);
        Assert.DoesNotContain(privateUrl, rejectedOption.Error, StringComparison.Ordinal);

        string mainFile = Path.Combine(scenario, "portico.toml");
        string valid = await File.ReadAllTextAsync(mainFile, TestContext.Current.CancellationToken);
        await File.WriteAllTextAsync(mainFile, "weekly_summary = true\n" + valid, TestContext.Current.CancellationToken);
        ProcessResult unknown = await RunAsync(executable, scenario, "config", "check", "--output", "json");
        Assert.Equal(3, unknown.ExitCode);
        Assert.Empty(unknown.Error);
        AssertResponse(unknown.Output, "config-check", "failure", problemCode: "config.unknown-key");

        await File.WriteAllTextAsync(mainFile, "[data]\nsource = \"local\"\n", TestContext.Current.CancellationToken);
        ProcessResult oldShape = await RunAsync(executable, scenario, "config", "check", "--output", "json");
        Assert.Equal(3, oldShape.ExitCode);
        Assert.Empty(oldShape.Error);
        AssertResponse(oldShape.Output, "config-check", "failure", problemCode: "config.missing-field");

        ProcessResult invalidDoctor = await RunAsync(executable, scenario, "doctor", "--output", "json");
        Assert.Equal(3, invalidDoctor.ExitCode);
        Assert.Empty(invalidDoctor.Error);
        AssertResponse(invalidDoctor.Output, "doctor", "failure", problemCode: "config.missing-field");

        await File.WriteAllTextAsync(mainFile, valid, TestContext.Current.CancellationToken);
        File.Delete(Path.Combine(scenario, "demo", "data", "accounts.csv"));
        ProcessResult missing = await RunAsync(executable, scenario, "doctor", "--output", "json");
        Assert.Equal(4, missing.ExitCode);
        Assert.Empty(missing.Error);
        AssertResponse(missing.Output, "doctor", "failure", problemCode: "data.missing-file");
        Assert.DoesNotContain(scenario, missing.Output, StringComparison.OrdinalIgnoreCase);

        ProcessResult missingDataCheck = await RunAsync(executable, scenario, "data", "check", "--output", "json");
        Assert.Equal(4, missingDataCheck.ExitCode);
        Assert.Empty(missingDataCheck.Error);
        AssertResponse(missingDataCheck.Output, "data-check", "failure", problemCode: "data.missing-file");
    }

    private static void AssertResponse(
        string output,
        string command,
        string outcome,
        string? source = null,
        int? transactions = null,
        int? balances = null,
        int? budgets = null,
        string? problemCode = null)
    {
        Assert.Equal(1, output.Count(character => character == '\n'));
        using JsonDocument document = JsonDocument.Parse(output);
        JsonElement root = document.RootElement;
        Assert.Equal("portico.command-result.v1", root.GetProperty("schema").GetString());
        Assert.Equal(command, root.GetProperty("command").GetString());
        Assert.Equal(outcome, root.GetProperty("outcome").GetString());
        if (source is not null)
            Assert.Equal(source, root.GetProperty("details").GetProperty("source").GetString());
        if (transactions is int transactionCount)
            Assert.Equal(transactionCount, root.GetProperty("details").GetProperty("transactions").GetInt32());
        if (balances is int balanceCount)
            Assert.Equal(balanceCount, root.GetProperty("details").GetProperty("balances").GetInt32());
        if (budgets is int budgetCount)
            Assert.Equal(budgetCount, root.GetProperty("details").GetProperty("budgets").GetInt32());
        if (problemCode is not null)
        {
            Assert.Equal(JsonValueKind.Null, root.GetProperty("details").ValueKind);
            Assert.Contains(root.GetProperty("problems").EnumerateArray(), problem => problem.GetProperty("code").GetString() == problemCode);
        }
        else
        {
            Assert.Empty(root.GetProperty("problems").EnumerateArray());
        }
    }

    private static async Task<string> PublishAsync(string repository, string temporaryRoot)
    {
        string output = Path.Combine(temporaryRoot, "published");
        string configuration = new DirectoryInfo(AppContext.BaseDirectory).Parent?.Name
            ?? throw new InvalidOperationException("The test build configuration was not found.");
        ProcessResult result = await RunProcessAsync(
            "dotnet", repository,
            ["publish", "src/Portico.App/Portico.App.csproj", "--configuration", configuration, "--output", output, "--no-restore"],
            TimeSpan.FromMinutes(5));
        Assert.True(result.ExitCode == 0, $"Published-process setup failed: {result.Output}\n{result.Error}");
        string executable = Path.Combine(output, OperatingSystem.IsWindows() ? "portico.exe" : "portico");
        Assert.True(File.Exists(executable), "The published Portico executable was not found.");
        return executable;
    }

    private static Task<ProcessResult> RunAsync(string executable, string directory, params string[] arguments)
        => RunProcessAsync(executable, directory, arguments, TimeSpan.FromSeconds(30));

    private static async Task<ProcessResult> RunProcessAsync(
        string executable, string directory, IReadOnlyList<string> arguments, TimeSpan timeout)
    {
        using var process = new Process
        {
            StartInfo = new ProcessStartInfo(executable)
            {
                WorkingDirectory = directory,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false
            }
        };
        foreach (string argument in arguments)
            process.StartInfo.ArgumentList.Add(argument);
        process.Start();
        Task<string> output = process.StandardOutput.ReadToEndAsync(TestContext.Current.CancellationToken);
        Task<string> error = process.StandardError.ReadToEndAsync(TestContext.Current.CancellationToken);
        using var timeoutSource = CancellationTokenSource.CreateLinkedTokenSource(TestContext.Current.CancellationToken);
        timeoutSource.CancelAfter(timeout);
        try
        {
            await process.WaitForExitAsync(timeoutSource.Token);
        }
        catch (OperationCanceledException)
        {
            if (!process.HasExited)
                process.Kill(entireProcessTree: true);
            throw;
        }
        return new ProcessResult(process.ExitCode, await output, await error);
    }

    private static void CopyDemo(string repository, string destination)
    {
        File.Copy(Path.Combine(repository, "portico.toml"), Path.Combine(destination, "portico.toml"));
        string dataDirectory = Path.Combine(destination, "demo", "data");
        Directory.CreateDirectory(dataDirectory);
        foreach (string file in Directory.GetFiles(Path.Combine(repository, "demo", "data"), "*.csv"))
            File.Copy(file, Path.Combine(dataDirectory, Path.GetFileName(file)));
    }

    private static string FindRepositoryRoot()
    {
        for (DirectoryInfo? directory = new(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            if (File.Exists(Path.Combine(directory.FullName, "Portico.Roci.slnx")))
                return directory.FullName;
        }
        throw new InvalidOperationException("The Portico solution was not found.");
    }

    private sealed record ProcessResult(int ExitCode, string Output, string Error);

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"portico-e2e-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose() => Directory.Delete(Path, recursive: true);
    }
}
