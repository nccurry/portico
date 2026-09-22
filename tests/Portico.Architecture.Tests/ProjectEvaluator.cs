using System.Diagnostics;
using System.Text.Json;

namespace Portico.Architecture.Tests;

internal sealed class ProjectEvaluator(string repositoryRoot, string configuration, string targetFramework)
{
    private static readonly TimeSpan EvaluationTimeout = TimeSpan.FromSeconds(30);
    private static readonly StringComparer PathComparer = OperatingSystem.IsWindows()
        ? StringComparer.OrdinalIgnoreCase
        : StringComparer.Ordinal;

    public Task<EvaluatedProject> EvaluateAsync(string projectPath, CancellationToken cancellationToken)
        => EvaluateAsync(projectPath, targetFramework, configuration, cancellationToken);

    public async Task<EvaluatedProject> EvaluateAsync(
        string projectPath,
        string evaluationTargetFramework,
        string evaluationConfiguration,
        CancellationToken cancellationToken)
    {
        string fullProjectPath = Path.GetFullPath(projectPath);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(EvaluationTimeout);

        var startInfo = new ProcessStartInfo("dotnet")
        {
            WorkingDirectory = repositoryRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        startInfo.ArgumentList.Add("msbuild");
        startInfo.ArgumentList.Add(fullProjectPath);
        startInfo.ArgumentList.Add("-nologo");
        startInfo.ArgumentList.Add("-nodeReuse:false");
        startInfo.ArgumentList.Add("-getItem:ProjectReference;PackageReference;Compile");
        startInfo.ArgumentList.Add("-getProperty:RociSourceRoot");
        startInfo.ArgumentList.Add($"-property:Configuration={evaluationConfiguration}");
        startInfo.ArgumentList.Add($"-property:TargetFramework={evaluationTargetFramework}");

        using var process = new Process { StartInfo = startInfo };
        if (!process.Start())
            throw new InvalidOperationException($"Could not start MSBuild for '{fullProjectPath}'.");

        Task<string> standardOutput = process.StandardOutput.ReadToEndAsync();
        Task<string> standardError = process.StandardError.ReadToEndAsync();

        try
        {
            await process.WaitForExitAsync(timeout.Token);
        }
        catch (OperationCanceledException) when (timeout.IsCancellationRequested)
        {
            Stop(process);
            await Task.WhenAll(standardOutput, standardError);

            if (cancellationToken.IsCancellationRequested)
                throw;

            throw new TimeoutException($"MSBuild item evaluation exceeded {EvaluationTimeout.TotalSeconds:0} seconds for '{fullProjectPath}'.");
        }

        string output = await standardOutput;
        string error = await standardError;
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(
                $"MSBuild item evaluation failed for '{fullProjectPath}' with exit code {process.ExitCode}.{Environment.NewLine}{error}");
        }

        return ReadEvaluation(output);
    }

    private static EvaluatedProject ReadEvaluation(string output)
    {
        using JsonDocument document = JsonDocument.Parse(output);
        JsonElement root = document.RootElement;

        return new EvaluatedProject(
            ReadProperty(root, "RociSourceRoot"),
            ReadItems(root, "ProjectReference", paths: true),
            ReadItems(root, "PackageReference", paths: false),
            ReadItems(root, "Compile", paths: true));
    }

    private static string? ReadProperty(JsonElement root, string name)
    {
        if (!root.TryGetProperty("Properties", out JsonElement properties)
            || !properties.TryGetProperty(name, out JsonElement value))
        {
            return null;
        }

        string? text = value.GetString();
        return string.IsNullOrWhiteSpace(text) ? null : Path.GetFullPath(text);
    }

    private static IReadOnlyList<string> ReadItems(JsonElement root, string name, bool paths)
    {
        if (!root.TryGetProperty("Items", out JsonElement items)
            || !items.TryGetProperty(name, out JsonElement values))
        {
            return [];
        }

        return values
            .EnumerateArray()
            .Select(value => ReadItem(value, paths))
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value!)
            .Distinct(paths ? PathComparer : StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
    }

    private static string? ReadItem(JsonElement item, bool paths)
    {
        string property = paths ? "FullPath" : "Identity";
        if (!item.TryGetProperty(property, out JsonElement value))
            return null;

        string? text = value.GetString();
        return string.IsNullOrWhiteSpace(text) || !paths ? text : Path.GetFullPath(text);
    }

    private static void Stop(Process process)
    {
        try
        {
            if (!process.HasExited)
                process.Kill(entireProcessTree: true);
        }
        catch (InvalidOperationException)
        {
        }
    }
}
