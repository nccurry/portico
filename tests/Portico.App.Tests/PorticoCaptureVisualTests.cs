using System.Diagnostics;
using Portico.CaptureHost;
using Roci.Testing;

namespace Portico.App.Tests;

[CollectionDefinition(nameof(PorticoCaptureCollection), DisableParallelization = true)]
public sealed class PorticoCaptureCollection
{
}

[Collection(nameof(PorticoCaptureCollection))]
public sealed class PorticoCaptureVisualTests
{
#if DEBUG
    private const string BuildConfiguration = "Debug";
#else
    private const string BuildConfiguration = "Release";
#endif

    private const string CaptureHostProjectPath =
        "tests/Portico.CaptureHost/Portico.CaptureHost.csproj";

    [Fact]
    [Trait("Category", "VisualCapture")]
    public async Task CaptureRun_WritesAVerifiedPngForEveryCase()
    {
        foreach (CaptureCase captureCase in PorticoCaptureCatalog.CaptureCatalog.CaptureCases)
            await CaptureAndVerify(captureCase);
    }

    private static async Task CaptureAndVerify(CaptureCase captureCase)
    {
        string root = FindRepositoryRoot();
        string capturePath = ResolveCapturePath(root, captureCase);
        string? captureDirectory = Path.GetDirectoryName(capturePath);
        if (!string.IsNullOrWhiteSpace(captureDirectory))
            Directory.CreateDirectory(captureDirectory);

        using Process process = StartCaptureProcess(root, captureCase, capturePath);
        Task<string> outputTask = process.StandardOutput.ReadToEndAsync(TestContext.Current.CancellationToken);
        Task<string> errorTask = process.StandardError.ReadToEndAsync(TestContext.Current.CancellationToken);
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(90));
        using var cancellation = CancellationTokenSource.CreateLinkedTokenSource(
            TestContext.Current.CancellationToken,
            timeout.Token);

        try
        {
            await process.WaitForExitAsync(cancellation.Token);
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested)
        {
            if (!process.HasExited)
                process.Kill(entireProcessTree: true);

            await process.WaitForExitAsync(CancellationToken.None);
            throw;
        }

        string output = await outputTask;
        string error = await errorTask;
        Assert.True(
            process.ExitCode == 0,
            $"Capture case '{captureCase.Name}' failed with exit code {process.ExitCode}.{Environment.NewLine}{output}{error}");

        PngCaptureVerificationResult verification = CaptureCaseVerifier.Verify(captureCase, capturePath);
        Assert.True(verification.Success, verification.Error);

        if (!ShouldRetainCaptures())
            File.Delete(capturePath);
    }

    private static Process StartCaptureProcess(string root, CaptureCase captureCase, string capturePath)
    {
        string dotNetPath = Environment.GetEnvironmentVariable("DOTNET_HOST_PATH") ?? "dotnet";
        var startInfo = new ProcessStartInfo(dotNetPath)
        {
            WorkingDirectory = root,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false
        };
        startInfo.ArgumentList.Add("run");
        startInfo.ArgumentList.Add("--no-build");
        startInfo.ArgumentList.Add("--configuration");
        startInfo.ArgumentList.Add(BuildConfiguration);
        startInfo.ArgumentList.Add("--project");
        startInfo.ArgumentList.Add(CaptureHostProjectPath);
        startInfo.ArgumentList.Add("--");
        startInfo.ArgumentList.Add("--start-state");
        startInfo.ArgumentList.Add(captureCase.LaunchStateId);
        if (captureCase.ScenarioId is not null)
        {
            startInfo.ArgumentList.Add("--scenario");
            startInfo.ArgumentList.Add(captureCase.ScenarioId);
        }
        if (captureCase.InputScriptId is not null)
        {
            startInfo.ArgumentList.Add("--input-script");
            startInfo.ArgumentList.Add(captureCase.InputScriptId);
        }
        if (captureCase.Seed is int seed)
        {
            startInfo.ArgumentList.Add("--seed");
            startInfo.ArgumentList.Add(seed.ToString());
        }
        if (captureCase.SettingsPath is not null)
        {
            startInfo.ArgumentList.Add("--settings");
            startInfo.ArgumentList.Add(captureCase.SettingsPath);
        }
        foreach ((string key, string value) in captureCase.Parameters)
        {
            startInfo.ArgumentList.Add("--param");
            startInfo.ArgumentList.Add($"{key}={value}");
        }
        if (captureCase.CaptureSize is { } captureSize)
        {
            startInfo.ArgumentList.Add("--capture-size");
            startInfo.ArgumentList.Add($"{captureSize.Width}x{captureSize.Height}");
        }
        startInfo.ArgumentList.Add("--capture-frame");
        startInfo.ArgumentList.Add(captureCase.CaptureFrame.ToString());
        startInfo.ArgumentList.Add("--capture");
        startInfo.ArgumentList.Add(capturePath);

        return Process.Start(startInfo)
            ?? throw new InvalidOperationException($"Could not start capture case '{captureCase.Name}'.");
    }

    private static string ResolveCapturePath(string root, CaptureCase captureCase)
    {
        string? configuredDirectory = Environment.GetEnvironmentVariable("PORTICO_CAPTURE_OUTPUT_DIR");
        string directory = string.IsNullOrWhiteSpace(configuredDirectory)
            ? Path.Combine(root, "artifacts", "test-captures")
            : Path.GetFullPath(configuredDirectory, root);
        string fileName = ShouldRetainCaptures()
            ? $"{captureCase.Name}.png"
            : $"{captureCase.Name}-{Guid.NewGuid():N}.png";
        return Path.Combine(directory, fileName);
    }

    private static bool ShouldRetainCaptures()
    {
        string? value = Environment.GetEnvironmentVariable("PORTICO_CAPTURE_RETAIN_OUTPUT");
        return value is "1" || bool.TryParse(value, out bool retain) && retain;
    }

    private static string FindRepositoryRoot()
    {
        var current = new DirectoryInfo(Path.GetFullPath(Directory.GetCurrentDirectory()));
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "Portico.Roci.slnx")))
                return current.FullName;

            current = current.Parent;
        }

        throw new DirectoryNotFoundException("Could not find the Portico repository root.");
    }
}
