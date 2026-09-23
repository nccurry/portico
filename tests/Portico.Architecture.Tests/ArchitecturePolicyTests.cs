using System.Reflection;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;

namespace Portico.Architecture.Tests;

public sealed class ArchitecturePolicyTests
{
    private static readonly StringComparer PathComparer = OperatingSystem.IsWindows()
        ? StringComparer.OrdinalIgnoreCase
        : StringComparer.Ordinal;

    private static readonly string[] ProductionProjectNames =
    [
        "Portico.Adapters",
        "Portico.App",
        "Portico.Application",
        "Portico.Cli",
        "Portico.Configuration",
        "Portico.Dashboard",
        "Portico.Data",
        "Portico.Desktop",
        "Portico.Finance"
    ];
    private static readonly string[] Configurations = ["Debug", "Release"];

    private static readonly IReadOnlyDictionary<string, ProjectReferencePolicy> ProjectPolicies =
        new Dictionary<string, ProjectReferencePolicy>(StringComparer.Ordinal)
        {
            ["Portico.Finance"] = Policy([], []),
            ["Portico.Application"] = Policy(["Portico.Finance"], []),
            ["Portico.Configuration"] = Policy(["Portico.Application", "Portico.Finance"], []),
            ["Portico.Data"] = Policy(["Portico.Application", "Portico.Finance"], []),
            ["Portico.Cli"] = Policy(["Portico.Application"], []),
            ["Portico.Desktop"] = Policy(["Portico.Application"], ["Roci.Core"]),
            ["Portico.Dashboard"] = Policy(["Portico.Finance"], []),
            ["Portico.Adapters"] = Policy(["Portico.Dashboard", "Portico.Finance"], []),
            ["Portico.App"] = Policy(
            [
                "Portico.Adapters",
                "Portico.Application",
                "Portico.Cli",
                "Portico.Configuration",
                "Portico.Data",
                "Portico.Dashboard",
                "Portico.Desktop",
                "Portico.Finance"
            ],
            [
                "Roci.Core",
                "Roci.Hosting.MonoGame",
                "Roci.Input",
                "Roci.Input.Automation",
                "Roci.Input.Automation.Launch",
                "Roci.Input.MonoGame",
                "Roci.Launch",
                "Roci.Rendering",
                "Roci.Rendering.FontStashSharp",
                "Roci.Rendering.MonoGame",
                "Roci.Ui",
                "Roci.Ui.Charts",
                "Roci.Ui.Charts.Rendering",
                "Roci.Ui.Input",
                "Roci.Ui.Rendering"
            ])
        };

    private static readonly Lazy<RepositoryContext> CurrentRepository = new(RepositoryContext.Create);
    private static readonly Lazy<Task<IReadOnlyDictionary<string, IReadOnlyDictionary<string, EvaluatedProject>>>> ProductionProjects =
        new(LoadProductionProjectsAsync);

    [Fact]
    public async Task ProductionProjectPolicy_StaysWithinPhaseOneRules()
    {
        foreach ((string configuration, IReadOnlyDictionary<string, EvaluatedProject> projects) in await ProductionProjects.Value)
        {
            foreach ((string projectName, ProjectReferencePolicy policy) in ProjectPolicies)
                AssertNoReferenceViolations(projectName, projects[projectName], policy, configuration);
        }
    }

    [Fact]
    public async Task OnlyApp_MayComposeAllTargetOuterModules()
    {
        string[] outerModules = ["Portico.Cli", "Portico.Desktop", "Portico.Configuration", "Portico.Data"];
        foreach (IReadOnlyDictionary<string, EvaluatedProject> projects in (await ProductionProjects.Value).Values)
        {
            string[] composers = projects
                .Where(pair => outerModules.All(module => ClassifyReferences(pair.Value).Portico.Contains(module)))
                .Select(pair => pair.Key)
                .Order(StringComparer.Ordinal)
                .ToArray();

            Assert.Equal(["Portico.App"], composers);
        }
    }

    [Fact]
    public async Task DirectForbiddenReferenceFixture_IsRejected()
    {
        using TemporaryProjectFixture fixture = TemporaryProjectFixture.CreateDirect(CurrentRepository.Value, ActiveTargetFramework);

        EvaluatedProject project = await CurrentRepository.Value.Evaluator.EvaluateAsync(
            fixture.ProjectPath,
            TestContext.Current.CancellationToken);
        IReadOnlyList<string> violations = FindReferenceViolations(
            "Portico.Application",
            project,
            ProjectPolicies["Portico.Application"]);

        Assert.Contains(
            "Portico.Application has an unexpected Portico project reference 'Portico.Cli'.",
            violations);
    }

    [Fact]
    public async Task ImportedConditionalForbiddenReferenceFixture_IsRejected()
    {
        using TemporaryProjectFixture fixture = TemporaryProjectFixture.CreateImportedConditional(CurrentRepository.Value, ActiveTargetFramework);

        EvaluatedProject debug = await CurrentRepository.Value.Evaluator.EvaluateAsync(
            fixture.ProjectPath,
            ActiveTargetFramework,
            "Debug",
            TestContext.Current.CancellationToken);
        EvaluatedProject release = await CurrentRepository.Value.Evaluator.EvaluateAsync(
            fixture.ProjectPath,
            ActiveTargetFramework,
            "Release",
            TestContext.Current.CancellationToken);

        Assert.Empty(FindReferenceViolations("Portico.Application", debug, ProjectPolicies["Portico.Application"]));
        Assert.DoesNotContain(debug.ProjectReferences, reference => Path.GetFileNameWithoutExtension(reference) == "Portico.Cli");

        IReadOnlyList<string> releaseViolations = FindReferenceViolations(
            "Portico.Application",
            release,
            ProjectPolicies["Portico.Application"]);
        Assert.Contains(release.ProjectReferences, reference => Path.GetFileNameWithoutExtension(reference) == "Portico.Cli");
        Assert.Contains(
            "Portico.Application has an unexpected Portico project reference 'Portico.Cli'.",
            releaseViolations);
    }

    [Fact]
    public async Task NonCanonicalRociReferenceFixture_IsRejected()
    {
        string rociSourceRoot = CurrentRepository.Value.ExpectedRociSourceRoot;
        using TemporaryProjectFixture fixture = TemporaryProjectFixture.CreateNonCanonicalRoci(
            CurrentRepository.Value,
            ActiveTargetFramework,
            rociSourceRoot);

        EvaluatedProject project = await CurrentRepository.Value.Evaluator.EvaluateAsync(
            fixture.ProjectPath,
            TestContext.Current.CancellationToken);
        IReadOnlyList<string> violations = FindReferenceViolations(
            "Portico.Application",
            project,
            ProjectPolicies["Portico.Application"]);

        string nonCanonicalRociCore = Path.Combine(
            rociSourceRoot,
            "src",
            "nested",
            "Roci.Core",
            "Roci.Core.csproj");
        Assert.Contains(
            $"Portico.Application has an unapproved external project reference '{nonCanonicalRociCore}'.",
            violations);
    }

    [Fact]
    public async Task ProjectControlledRociRootFixture_IsRejected()
    {
        RepositoryContext repository = CurrentRepository.Value;
        using TemporaryProjectFixture fixture = TemporaryProjectFixture.CreateOverriddenRociRoot(
            repository,
            ActiveTargetFramework);

        EvaluatedProject project = await repository.Evaluator.EvaluateAsync(
            fixture.ProjectPath,
            TestContext.Current.CancellationToken);
        IReadOnlyList<string> violations = FindReferenceViolations(
            "Portico.Desktop",
            project,
            ProjectPolicies["Portico.Desktop"]);

        Assert.Contains(violations, violation => violation.Contains("unapproved external project reference", StringComparison.Ordinal));
        Assert.Contains(violations, violation => violation.Contains("unexpected RociSourceRoot", StringComparison.Ordinal));
    }

    [Fact]
    public async Task Finance_HasNoForbiddenInfrastructure()
    {
        foreach ((string configuration, IReadOnlyDictionary<string, EvaluatedProject> projects) in await ProductionProjects.Value)
        {
            EvaluatedProject finance = projects["Portico.Finance"];
            Assert.Empty(finance.ProjectReferences);
            Assert.Empty(finance.PackageReferences);

            IReadOnlyList<string> violations = FinanceSourcePolicy.FindForbiddenNamespaceUses(
                finance.CompileItems,
                FinanceSourcePolicy.ParseOptions(finance));
            Assert.True(violations.Count == 0, $"{configuration}:{Environment.NewLine}{string.Join(Environment.NewLine, violations)}");
        }
    }

    [Fact]
    public async Task Finance_HasNoSourceSelectionTypes()
    {
        foreach ((string configuration, IReadOnlyDictionary<string, EvaluatedProject> projects) in await ProductionProjects.Value)
        {
            EvaluatedProject finance = projects["Portico.Finance"];
            CSharpParseOptions parseOptions = FinanceSourcePolicy.ParseOptions(finance);
            IReadOnlyList<string> violations = FinanceSourcePolicy.FindSourceSelectionUses(finance.CompileItems, parseOptions);
            Assert.True(violations.Count == 0, $"{configuration}:{Environment.NewLine}{string.Join(Environment.NewLine, violations)}");
        }
    }

    [Fact]
    public void FinanceSourceSelectionScan_RejectsTypesButIgnoresComments()
    {
        SyntaxTree tree = CSharpSyntaxTree.ParseText(
            """
            namespace Portico.Finance;
            // DataSourceSettings is an old adapter type.
            public sealed record DataSourceSettings(WorkbookSourceKind Kind);
            """,
            path: "source-selection.cs",
            cancellationToken: TestContext.Current.CancellationToken);

        Assert.Equal(
            ["source-selection.cs: WorkbookSourceKind", "source-selection.cs: DataSourceSettings"],
            FinanceSourcePolicy.FindSourceSelectionUses(tree));

        SyntaxTree commentOnly = CSharpSyntaxTree.ParseText(
            "// DataSourceSettings and WorkbookSourceKind were moved out of Finance.",
            path: "comment-only.cs",
            cancellationToken: TestContext.Current.CancellationToken);
        Assert.Empty(FinanceSourcePolicy.FindSourceSelectionUses(commentOnly));
    }

    [Fact]
    public void FinanceInfrastructureScan_IgnoresCommentsAndStringLiterals()
    {
        SyntaxTree tree = CSharpSyntaxTree.ParseText(
            """
            namespace Portico.Finance;

            public static class Evidence
            {
                // using System.IO;
                private const string Text = "using Tomlyn; namespace Portico.Adapters;";
            }
            """,
            path: "evidence.cs",
            cancellationToken: TestContext.Current.CancellationToken);

        Assert.Empty(FinanceSourcePolicy.FindForbiddenNamespaceUses(tree));
    }

    [Fact]
    public void FinanceInfrastructureScan_RejectsQualifiedInfrastructure()
    {
        SyntaxTree tree = CSharpSyntaxTree.ParseText(
            """
            namespace Portico.Finance;

            public sealed class Evidence
            {
                private readonly System.Net.Http.HttpClient _client = null!;
                private readonly Roci.Core.Widget? _widget = null;

                public string Read() => global::System.IO.File.ReadAllText("evidence.csv");
                public void Load() => Roci.Core.Widget.Load();
            }
            """,
            path: "qualified-evidence.cs",
            cancellationToken: TestContext.Current.CancellationToken);

        IReadOnlyList<string> violations = FinanceSourcePolicy.FindForbiddenNamespaceUses(tree);

        Assert.Contains("qualified-evidence.cs: qualified name System.IO.File.ReadAllText", violations);
        Assert.Contains("qualified-evidence.cs: qualified name System.Net.Http.HttpClient", violations);
        Assert.Contains("qualified-evidence.cs: qualified name Roci.Core.Widget.Load", violations);
    }

    [Fact]
    public void FinanceInfrastructureScan_RejectsImplicitFrameworkInfrastructure()
    {
        SyntaxTree tree = CSharpSyntaxTree.ParseText(
            """
            namespace Portico.Finance;

            public sealed class Evidence
            {
                private readonly HttpClient _client = null!;

                public bool Exists() => File.Exists("evidence.csv");
            }
            """,
            path: "implicit-evidence.cs",
            cancellationToken: TestContext.Current.CancellationToken);

        IReadOnlyList<string> violations = FinanceSourcePolicy.FindForbiddenNamespaceUses(tree);

        Assert.Contains(violations, violation => violation.Contains("System.IO symbol 'File'", StringComparison.Ordinal));
        Assert.Contains(violations, violation => violation.Contains("System.Net.Http symbol 'HttpClient'", StringComparison.Ordinal));
    }

    [Fact]
    public void FinanceInfrastructureScan_RejectsConditionalSourceInRelease()
    {
        const string source = """
            namespace Portico.Finance;
            public static class Evidence
            {
            #if RELEASE
                public static void Print() => System.Console.WriteLine("release");
            #endif
            }
            """;
        CSharpParseOptions debugOptions = CSharpParseOptions.Default.WithPreprocessorSymbols("DEBUG");
        CSharpParseOptions releaseOptions = CSharpParseOptions.Default.WithPreprocessorSymbols("RELEASE");

        Assert.Empty(FinanceSourcePolicy.FindForbiddenNamespaceUses(CSharpSyntaxTree.ParseText(
            source,
            debugOptions,
            cancellationToken: TestContext.Current.CancellationToken)));
        Assert.Contains(
            FinanceSourcePolicy.FindForbiddenNamespaceUses(CSharpSyntaxTree.ParseText(
                source,
                releaseOptions,
                cancellationToken: TestContext.Current.CancellationToken)),
            violation => violation.Contains("System.Console", StringComparison.Ordinal));
    }

    [Fact]
    public void FinanceInfrastructureScan_RejectsConsoleWithImplicitUsing()
    {
        SyntaxTree tree = CSharpSyntaxTree.ParseText(
            """
            namespace Portico.Finance;
            public static class Evidence
            {
                public static void Print() => Console.WriteLine("evidence");
            }
            """,
            path: "console-evidence.cs",
            cancellationToken: TestContext.Current.CancellationToken);

        Assert.Contains(
            FinanceSourcePolicy.FindForbiddenNamespaceUses(tree),
            violation => violation.Contains("System.Console", StringComparison.Ordinal));
    }

    private static string ActiveTargetFramework => ReadAssemblyMetadata("Portico.ActiveTargetFramework");

    private static async Task<IReadOnlyDictionary<string, IReadOnlyDictionary<string, EvaluatedProject>>> LoadProductionProjectsAsync()
    {
        RepositoryContext repository = CurrentRepository.Value;
        AssertProductionProjectCatalog(repository);

        var byConfiguration = new Dictionary<string, IReadOnlyDictionary<string, EvaluatedProject>>(StringComparer.Ordinal);
        foreach (string configuration in Configurations)
        {
            var projects = new Dictionary<string, EvaluatedProject>(StringComparer.Ordinal);
            foreach (string projectName in ProductionProjectNames)
            {
                projects[projectName] = await repository.Evaluator.EvaluateAsync(
                    repository.ProjectPath(projectName),
                    ActiveTargetFramework,
                    configuration,
                    CancellationToken.None);
            }

            byConfiguration.Add(configuration, projects);
        }

        return byConfiguration;
    }

    private static void AssertNoReferenceViolations(
        string projectName,
        EvaluatedProject project,
        ProjectReferencePolicy policy,
        string configuration)
    {
        IReadOnlyList<string> violations = FindReferenceViolations(projectName, project, policy);
        Assert.True(violations.Count == 0, $"{configuration}:{Environment.NewLine}{string.Join(Environment.NewLine, violations)}");
    }

    private static IReadOnlyList<string> FindReferenceViolations(
        string projectName,
        EvaluatedProject project,
        ProjectReferencePolicy policy)
    {
        ReferenceSets actual = ClassifyReferences(project);
        var violations = new List<string>();
        AddSetViolations(violations, projectName, "Portico", policy.Portico, actual.Portico);
        AddSetViolations(violations, projectName, "Roci", policy.Roci, actual.Roci);

        string expectedRociRoot = CurrentRepository.Value.ExpectedRociSourceRoot;
        if (project.RociSourceRoot is not null
            && !PathComparer.Equals(
                Path.TrimEndingDirectorySeparator(project.RociSourceRoot),
                Path.TrimEndingDirectorySeparator(expectedRociRoot)))
            violations.Add($"{projectName} has an unexpected RociSourceRoot '{project.RociSourceRoot}'.");

        foreach (string reference in actual.Other)
            violations.Add($"{projectName} has an unapproved external project reference '{reference}'.");

        return violations;
    }

    private static ReferenceSets ClassifyReferences(EvaluatedProject project)
    {
        var portico = new HashSet<string>(StringComparer.Ordinal);
        var roci = new HashSet<string>(StringComparer.Ordinal);
        var other = new List<string>();

        RepositoryContext repository = CurrentRepository.Value;
        foreach (string reference in project.ProjectReferences)
        {
            string projectName = Path.GetFileNameWithoutExtension(reference);
            if (ProjectPolicies.ContainsKey(projectName)
                && PathComparer.Equals(reference, repository.ProjectPath(projectName)))
            {
                portico.Add(projectName);
            }
            else if (PathComparer.Equals(reference, RociProjectPath(repository.ExpectedRociSourceRoot, projectName)))
            {
                roci.Add(projectName);
            }
            else
            {
                other.Add(reference);
            }
        }

        return new ReferenceSets(portico, roci, other.Order(StringComparer.Ordinal).ToArray());
    }

    private static void AddSetViolations(
        ICollection<string> violations,
        string projectName,
        string referenceKind,
        IReadOnlySet<string> expected,
        IReadOnlySet<string> actual)
    {
        foreach (string unexpected in actual.Except(expected, StringComparer.Ordinal).Order(StringComparer.Ordinal))
            violations.Add($"{projectName} has an unexpected {referenceKind} project reference '{unexpected}'.");

        foreach (string missing in expected.Except(actual, StringComparer.Ordinal).Order(StringComparer.Ordinal))
            violations.Add($"{projectName} is missing required {referenceKind} project reference '{missing}'.");
    }

    private static void AssertProductionProjectCatalog(RepositoryContext repository)
    {
        string[] actual = Directory
            .EnumerateFiles(Path.Combine(repository.Root, "src"), "Portico.*.csproj", SearchOption.AllDirectories)
            .Select(Path.GetFileNameWithoutExtension)
            .Where(name => name is not null)
            .Select(name => name!)
            .Order(StringComparer.Ordinal)
            .ToArray();

        Assert.Equal(ProductionProjectNames.Order(StringComparer.Ordinal), actual);
    }

    private static string RociProjectPath(string rociSourceRoot, string projectName)
        => Path.Combine(rociSourceRoot, "src", projectName, $"{projectName}.csproj");

    private static ProjectReferencePolicy Policy(IEnumerable<string> portico, IEnumerable<string> roci)
        => new(
            new HashSet<string>(portico, StringComparer.Ordinal),
            new HashSet<string>(roci, StringComparer.Ordinal));

    private static string ReadAssemblyMetadata(string key)
    {
        string? value = typeof(ArchitecturePolicyTests)
            .Assembly
            .GetCustomAttributes<AssemblyMetadataAttribute>()
            .SingleOrDefault(attribute => string.Equals(attribute.Key, key, StringComparison.Ordinal))
            ?.Value;

        return string.IsNullOrWhiteSpace(value)
            ? throw new InvalidOperationException($"The test assembly is missing '{key}' metadata.")
            : value;
    }

    private sealed record ProjectReferencePolicy(IReadOnlySet<string> Portico, IReadOnlySet<string> Roci);

    private sealed record ReferenceSets(IReadOnlySet<string> Portico, IReadOnlySet<string> Roci, IReadOnlyList<string> Other);

    private sealed class RepositoryContext
    {
        private RepositoryContext(string root, string configuration, string targetFramework)
        {
            Root = root;
            Evaluator = new ProjectEvaluator(root, configuration, targetFramework);
            string? overrideRoot = Environment.GetEnvironmentVariable("ROCI_ROOT");
            ExpectedRociSourceRoot = Path.GetFullPath(
                string.IsNullOrWhiteSpace(overrideRoot) ? Path.Combine(root, "..", "roci") : overrideRoot,
                root);
        }

        public string Root { get; }

        public ProjectEvaluator Evaluator { get; }

        public string ExpectedRociSourceRoot { get; }

        public static RepositoryContext Create()
        {
            string root = FindRepositoryRoot();
            return new RepositoryContext(
                root,
                ReadAssemblyMetadata("Portico.ActiveConfiguration"),
                ReadAssemblyMetadata("Portico.ActiveTargetFramework"));
        }

        public string ProjectPath(string projectName)
            => Path.Combine(Root, "src", projectName, $"{projectName}.csproj");

        private static string FindRepositoryRoot()
        {
            for (DirectoryInfo? directory = new DirectoryInfo(AppContext.BaseDirectory);
                 directory is not null;
                 directory = directory.Parent)
            {
                if (File.Exists(Path.Combine(directory.FullName, "Portico.Roci.slnx")))
                    return directory.FullName;
            }

            throw new DirectoryNotFoundException("Could not find the Portico repository root from the test output directory.");
        }
    }

    private sealed class TemporaryProjectFixture : IDisposable
    {
        private TemporaryProjectFixture(string root, string projectPath)
        {
            Root = root;
            ProjectPath = projectPath;
        }

        public string Root { get; }

        public string ProjectPath { get; }

        public static TemporaryProjectFixture CreateDirect(RepositoryContext repository, string targetFramework)
        {
            TemporaryProjectFixture fixture = Create();
            File.WriteAllText(
                fixture.ProjectPath,
                $$"""
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <TargetFramework>{{targetFramework}}</TargetFramework>
                  </PropertyGroup>
                  <ItemGroup>
                    <ProjectReference Include="{{EscapeXml(repository.ProjectPath("Portico.Finance"))}}" />
                    <ProjectReference Include="{{EscapeXml(repository.ProjectPath("Portico.Cli"))}}" />
                  </ItemGroup>
                </Project>
                """);
            return fixture;
        }

        public static TemporaryProjectFixture CreateImportedConditional(RepositoryContext repository, string targetFramework)
        {
            TemporaryProjectFixture fixture = Create();
            File.WriteAllText(
                fixture.ProjectPath,
                $$"""
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <TargetFramework>{{targetFramework}}</TargetFramework>
                  </PropertyGroup>
                  <ItemGroup>
                    <ProjectReference Include="{{EscapeXml(repository.ProjectPath("Portico.Finance"))}}" />
                  </ItemGroup>
                  <Import Project="conditional-reference.props" />
                </Project>
                """);
            File.WriteAllText(
                Path.Combine(fixture.Root, "conditional-reference.props"),
                $$"""
                <Project>
                  <ItemGroup Condition="'$(Configuration)' == 'Release'">
                    <ProjectReference Include="{{EscapeXml(repository.ProjectPath("Portico.Cli"))}}" />
                  </ItemGroup>
                </Project>
                """);
            return fixture;
        }

        public static TemporaryProjectFixture CreateNonCanonicalRoci(
            RepositoryContext repository,
            string targetFramework,
            string rociSourceRoot)
        {
            TemporaryProjectFixture fixture = Create();
            string nonCanonicalRociCore = Path.Combine(
                rociSourceRoot,
                "src",
                "nested",
                "Roci.Core",
                "Roci.Core.csproj");
            File.WriteAllText(
                fixture.ProjectPath,
                $$"""
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <TargetFramework>{{targetFramework}}</TargetFramework>
                    <RociSourceRoot>{{EscapeXml(rociSourceRoot)}}</RociSourceRoot>
                  </PropertyGroup>
                  <ItemGroup>
                    <ProjectReference Include="{{EscapeXml(repository.ProjectPath("Portico.Finance"))}}" />
                    <ProjectReference Include="{{EscapeXml(nonCanonicalRociCore)}}" />
                  </ItemGroup>
                </Project>
                """);
            return fixture;
        }

        public static TemporaryProjectFixture CreateOverriddenRociRoot(
            RepositoryContext repository,
            string targetFramework)
        {
            TemporaryProjectFixture fixture = Create();
            string fakeRociRoot = Path.Combine(fixture.Root, "fake-roci");
            File.WriteAllText(
                fixture.ProjectPath,
                $$"""
                <Project Sdk="Microsoft.NET.Sdk">
                  <PropertyGroup>
                    <TargetFramework>{{targetFramework}}</TargetFramework>
                    <RociSourceRoot>{{EscapeXml(fakeRociRoot)}}</RociSourceRoot>
                  </PropertyGroup>
                  <ItemGroup>
                    <ProjectReference Include="{{EscapeXml(repository.ProjectPath("Portico.Application"))}}" />
                    <ProjectReference Include="{{EscapeXml(RociProjectPath(fakeRociRoot, "Roci.Core"))}}" />
                  </ItemGroup>
                </Project>
                """);
            return fixture;
        }

        public void Dispose()
        {
            if (Directory.Exists(Root))
                Directory.Delete(Root, recursive: true);
        }

        private static TemporaryProjectFixture Create()
        {
            string root = Path.Combine(Path.GetTempPath(), $"portico-architecture-{Guid.NewGuid():N}");
            Directory.CreateDirectory(root);
            return new TemporaryProjectFixture(root, Path.Combine(root, "Fixture.csproj"));
        }

        private static string EscapeXml(string value)
            => System.Security.SecurityElement.Escape(value)
               ?? throw new InvalidOperationException("A project path cannot be null.");
    }
}
