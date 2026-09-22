namespace Portico.Architecture.Tests;

internal sealed record EvaluatedProject(
    string? RociSourceRoot,
    IReadOnlyList<string> ProjectReferences,
    IReadOnlyList<string> PackageReferences,
    IReadOnlyList<string> CompileItems);
