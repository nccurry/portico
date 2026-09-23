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
        "System.Console",
        "System.CommandLine",
        "Spectre.Console"
    ];

    private static readonly string[] SourceSelectionNames = ["WorkbookSourceKind", "DataSourceSettings"];

    private static readonly string[] ForbiddenNamespaceRoots = ["Google", "Portico", "Roci", "Spectre", "System", "Tomlyn"];

    private static readonly StringComparer PathComparer = OperatingSystem.IsWindows()
        ? StringComparer.OrdinalIgnoreCase
        : StringComparer.Ordinal;

    private static readonly Lazy<IReadOnlyList<MetadataReference>> TrustedPlatformReferences = new(CreateTrustedPlatformReferences);

    private const string ImplicitFrameworkUsings =
        """
        global using System;
        global using System.Collections.Generic;
        global using System.IO;
        global using System.Linq;
        global using System.Net.Http;
        global using System.Net.Http.Json;
        global using System.Threading;
        global using System.Threading.Tasks;
        """;

    public static CSharpParseOptions ParseOptions(EvaluatedProject project)
    {
        if (!LanguageVersionFacts.TryParse(project.LangVersion, out LanguageVersion languageVersion))
            throw new InvalidOperationException($"Unknown Finance language version '{project.LangVersion}'.");

        string[] symbols = project.DefineConstants
            .Split([';', ','], StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        return CSharpParseOptions.Default
            .WithLanguageVersion(languageVersion)
            .WithPreprocessorSymbols(symbols);
    }

    public static IReadOnlyList<string> FindForbiddenNamespaceUses(
        IEnumerable<string> sourceFiles,
        CSharpParseOptions parseOptions)
    {
        SyntaxTree[] trees = sourceFiles
            .Order(StringComparer.Ordinal)
            .Select(sourceFile => CSharpSyntaxTree.ParseText(File.ReadAllText(sourceFile), parseOptions, sourceFile))
            .ToArray();
        return FindForbiddenNamespaceUses(trees);
    }

    public static IReadOnlyList<string> FindForbiddenNamespaceUses(SyntaxTree tree)
        => FindForbiddenNamespaceUses([tree]);

    private static IReadOnlyList<string> FindForbiddenNamespaceUses(IEnumerable<SyntaxTree> sourceTrees)
    {
        SyntaxTree[] trees = sourceTrees.ToArray();
        CSharpParseOptions parseOptions = trees.FirstOrDefault()?.Options as CSharpParseOptions
            ?? CSharpParseOptions.Default;
        CSharpCompilation compilation = CSharpCompilation.Create(
            "Portico.Finance.ArchitecturePolicy",
            trees.Append(CSharpSyntaxTree.ParseText(ImplicitFrameworkUsings, parseOptions, "<implicit-framework-usings>")),
            TrustedPlatformReferences.Value,
            new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));
        var violations = new SortedSet<string>(StringComparer.Ordinal);

        foreach (SyntaxTree sourceTree in trees)
        {
            CompilationUnitSyntax root = sourceTree.GetCompilationUnitRoot();
            SemanticModel semanticModel = compilation.GetSemanticModel(sourceTree);
            AddForbiddenNamespaceUses(sourceTree, root, semanticModel, violations);
            AddForbiddenSymbolUses(sourceTree, root, semanticModel, violations);
        }

        return violations.ToArray();
    }

    private static void AddForbiddenNamespaceUses(
        SyntaxTree tree,
        CompilationUnitSyntax root,
        SemanticModel semanticModel,
        ISet<string> violations)
    {
        foreach (UsingDirectiveSyntax directive in root.DescendantNodes().OfType<UsingDirectiveSyntax>())
        {
            string? name = directive.Name is null ? null : GetNamePath(directive.Name);
            if (name is not null && IsForbiddenNamespace(name))
                violations.Add($"{tree.FilePath}: using {name}");
        }

        foreach (BaseNamespaceDeclarationSyntax declaration in root.DescendantNodes().OfType<BaseNamespaceDeclarationSyntax>())
        {
            string name = GetNamePath(declaration.Name);
            if (IsForbiddenNamespace(name))
                violations.Add($"{tree.FilePath}: namespace {name}");
        }

        foreach (AliasQualifiedNameSyntax name in root.DescendantNodes().OfType<AliasQualifiedNameSyntax>())
        {
            if (string.Equals(name.Alias.Identifier.ValueText, "global", StringComparison.Ordinal))
                AddForbiddenQualifiedName(tree, GetNamePath(name.Name), violations);
        }

        foreach (QualifiedNameSyntax name in root.DescendantNodes().OfType<QualifiedNameSyntax>())
        {
            if (name.Parent is not QualifiedNameSyntax and not AliasQualifiedNameSyntax)
                AddForbiddenQualifiedName(tree, GetNamePath(name), violations);
        }

        foreach (MemberAccessExpressionSyntax access in root.DescendantNodes().OfType<MemberAccessExpressionSyntax>())
        {
            string? name = GetForbiddenMemberAccessPath(access, semanticModel);
            if (name is not null)
                AddForbiddenQualifiedName(tree, name, violations);
        }
    }

    private static void AddForbiddenSymbolUses(
        SyntaxTree tree,
        CompilationUnitSyntax root,
        SemanticModel semanticModel,
        ISet<string> violations)
    {
        foreach (IdentifierNameSyntax identifier in root.DescendantNodes().OfType<IdentifierNameSyntax>())
        {
            if (IsPartOfUsingOrNamespaceName(identifier))
                continue;

            ISymbol? symbol = semanticModel.GetSymbolInfo(identifier).Symbol;
            if (symbol is null || symbol is INamespaceSymbol)
                continue;

            string? namespaceName = GetContainingNamespace(symbol);
            if (namespaceName is not null && IsForbiddenNamespace(namespaceName))
                violations.Add($"{tree.FilePath}: use {namespaceName} symbol '{identifier.Identifier.ValueText}'");

            if (string.Equals((symbol as INamedTypeSymbol)?.ToDisplayString(), "System.Console", StringComparison.Ordinal)
                || string.Equals(symbol.ContainingType?.ToDisplayString(), "System.Console", StringComparison.Ordinal))
            {
                violations.Add($"{tree.FilePath}: use System.Console symbol '{identifier.Identifier.ValueText}'");
            }
        }
    }

    private static void AddForbiddenQualifiedName(SyntaxTree tree, string name, ISet<string> violations)
    {
        if (IsForbiddenNamespace(name))
            violations.Add($"{tree.FilePath}: qualified name {name}");
    }

    public static IReadOnlyList<string> FindSourceSelectionDeclarations(string sourceFile, CSharpParseOptions parseOptions)
    {
        SyntaxTree tree = CSharpSyntaxTree.ParseText(File.ReadAllText(sourceFile), parseOptions, sourceFile);
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
        string financeSettingsFile,
        CSharpParseOptions parseOptions)
    {
        var violations = new List<string>();
        string allowedSourceFile = Path.GetFullPath(financeSettingsFile);
        foreach (string sourceFile in sourceFiles.Order(StringComparer.Ordinal))
        {
            if (PathComparer.Equals(Path.GetFullPath(sourceFile), allowedSourceFile))
                continue;

            SyntaxTree tree = CSharpSyntaxTree.ParseText(File.ReadAllText(sourceFile), parseOptions, sourceFile);
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

    private static string? GetContainingNamespace(ISymbol symbol)
    {
        ISymbol target = symbol is IAliasSymbol alias ? alias.Target : symbol;
        INamespaceSymbol? namespaceSymbol = target is INamespaceSymbol directNamespace
            ? directNamespace
            : target.ContainingNamespace;

        return namespaceSymbol is null || namespaceSymbol.IsGlobalNamespace
            ? null
            : namespaceSymbol.ToDisplayString();
    }

    private static string GetNamePath(NameSyntax name)
        => name switch
        {
            IdentifierNameSyntax identifier => identifier.Identifier.ValueText,
            GenericNameSyntax generic => generic.Identifier.ValueText,
            QualifiedNameSyntax qualified => $"{GetNamePath(qualified.Left)}.{GetNamePath(qualified.Right)}",
            AliasQualifiedNameSyntax alias => string.Equals(alias.Alias.Identifier.ValueText, "global", StringComparison.Ordinal)
                ? GetNamePath(alias.Name)
                : $"{alias.Alias.Identifier.ValueText}::{GetNamePath(alias.Name)}",
            _ => throw new InvalidOperationException($"Unexpected C# name syntax '{name.Kind()}'.")
        };

    private static string? GetForbiddenMemberAccessPath(ExpressionSyntax expression, SemanticModel semanticModel)
        => expression switch
        {
            AliasQualifiedNameSyntax alias when string.Equals(alias.Alias.Identifier.ValueText, "global", StringComparison.Ordinal)
                => GetNamePath(alias.Name),
            IdentifierNameSyntax identifier when IsForbiddenNamespaceRoot(identifier, semanticModel)
                => identifier.Identifier.ValueText,
            MemberAccessExpressionSyntax access => GetForbiddenMemberAccessPath(access.Expression, semanticModel) is { } parent
                ? $"{parent}.{GetNamePath(access.Name)}"
                : null,
            _ => null
        };

    private static bool IsForbiddenNamespaceRoot(IdentifierNameSyntax identifier, SemanticModel semanticModel)
    {
        if (!ForbiddenNamespaceRoots.Contains(identifier.Identifier.ValueText, StringComparer.Ordinal))
            return false;

        ISymbol? symbol = semanticModel.GetSymbolInfo(identifier).Symbol;
        return symbol is null or INamespaceSymbol;
    }

    private static bool IsPartOfUsingOrNamespaceName(IdentifierNameSyntax identifier)
        => identifier.Ancestors().OfType<UsingDirectiveSyntax>()
            .Any(directive => directive.Name?.Span.Contains(identifier.Span) == true)
           || identifier.Ancestors().OfType<BaseNamespaceDeclarationSyntax>()
               .Any(declaration => declaration.Name.Span.Contains(identifier.Span));

    private static IReadOnlyList<MetadataReference> CreateTrustedPlatformReferences()
    {
        string? assemblies = AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES") as string;
        if (string.IsNullOrWhiteSpace(assemblies))
            throw new InvalidOperationException("The runtime did not provide trusted platform assemblies for Finance source analysis.");

        return assemblies
            .Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries)
            .Select(path => MetadataReference.CreateFromFile(path))
            .Cast<MetadataReference>()
            .ToArray();
    }

}
