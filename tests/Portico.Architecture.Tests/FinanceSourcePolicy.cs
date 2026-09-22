using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace Portico.Architecture.Tests;

internal static class FinanceSourcePolicy
{
    private static readonly string[] ForbiddenNamespacePrefixes =
    [
        "Tomlyn",
        "Google",
        "Roci",
        "System.IO",
        "System.Net",
        "System.CommandLine",
        "Spectre.Console"
    ];

    private static readonly string[] SourceSelectionNames = ["WorkbookSourceKind", "DataSourceSettings"];

    private static readonly StringComparer PathComparer = OperatingSystem.IsWindows()
        ? StringComparer.OrdinalIgnoreCase
        : StringComparer.Ordinal;

    public static IReadOnlyList<string> FindForbiddenNamespaceUses(IEnumerable<string> sourceFiles)
    {
        var violations = new List<string>();
        foreach (string sourceFile in sourceFiles.Order(StringComparer.Ordinal))
        {
            SyntaxTree tree = CSharpSyntaxTree.ParseText(File.ReadAllText(sourceFile), path: sourceFile);
            violations.AddRange(FindForbiddenNamespaceUses(tree));
        }

        return violations;
    }

    public static IReadOnlyList<string> FindForbiddenNamespaceUses(SyntaxTree tree)
    {
        CompilationUnitSyntax root = tree.GetCompilationUnitRoot();
        var violations = new List<string>();

        foreach (UsingDirectiveSyntax directive in root.DescendantNodes().OfType<UsingDirectiveSyntax>())
        {
            string? name = directive.Name?.ToString();
            if (string.IsNullOrWhiteSpace(name))
                continue;

            if (IsForbiddenNamespace(name))
                violations.Add($"{tree.FilePath}: using {name}");
        }

        foreach (BaseNamespaceDeclarationSyntax declaration in root.DescendantNodes().OfType<BaseNamespaceDeclarationSyntax>())
        {
            string name = declaration.Name.ToString();
            if (IsForbiddenNamespace(name))
                violations.Add($"{tree.FilePath}: namespace {name}");
        }

        return violations;
    }

    public static IReadOnlyList<string> FindSourceSelectionDeclarations(string sourceFile)
    {
        SyntaxTree tree = CSharpSyntaxTree.ParseText(File.ReadAllText(sourceFile), path: sourceFile);
        return tree.GetRoot()
            .DescendantNodes()
            .OfType<BaseTypeDeclarationSyntax>()
            .Select(declaration => declaration.Identifier.ValueText)
            .Where(name => SourceSelectionNames.Contains(name, StringComparer.Ordinal))
            .Order(StringComparer.Ordinal)
            .ToArray();
    }

    public static IReadOnlyList<string> FindSourceSelectionUsesOutsideFinanceSettings(
        IEnumerable<string> sourceFiles,
        string financeSettingsFile)
    {
        var violations = new List<string>();
        string allowedSourceFile = Path.GetFullPath(financeSettingsFile);
        foreach (string sourceFile in sourceFiles.Order(StringComparer.Ordinal))
        {
            if (PathComparer.Equals(Path.GetFullPath(sourceFile), allowedSourceFile))
                continue;

            SyntaxTree tree = CSharpSyntaxTree.ParseText(File.ReadAllText(sourceFile), path: sourceFile);
            foreach (IdentifierNameSyntax identifier in tree.GetRoot().DescendantNodes().OfType<IdentifierNameSyntax>())
            {
                if (SourceSelectionNames.Contains(identifier.Identifier.ValueText, StringComparer.Ordinal))
                    violations.Add($"{sourceFile}: {identifier.Identifier.ValueText}");
            }

            foreach (BaseTypeDeclarationSyntax declaration in tree.GetRoot().DescendantNodes().OfType<BaseTypeDeclarationSyntax>())
            {
                if (SourceSelectionNames.Contains(declaration.Identifier.ValueText, StringComparer.Ordinal))
                    violations.Add($"{sourceFile}: {declaration.Identifier.ValueText}");
            }
        }

        return violations;
    }

    private static bool IsForbiddenNamespace(string name)
    {
        if ((string.Equals(name, "Portico", StringComparison.Ordinal)
             || name.StartsWith("Portico.", StringComparison.Ordinal))
            && !string.Equals(name, "Portico.Finance", StringComparison.Ordinal)
            && !name.StartsWith("Portico.Finance.", StringComparison.Ordinal))
        {
            return true;
        }

        return ForbiddenNamespacePrefixes.Any(prefix => IsNamespaceOrChild(name, prefix));
    }

    private static bool IsNamespaceOrChild(string name, string prefix)
        => string.Equals(name, prefix, StringComparison.Ordinal)
           || name.StartsWith($"{prefix}.", StringComparison.Ordinal);

}
