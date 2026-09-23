using Portico.Application;
using Portico.Desktop;
using Portico.Configuration;
using Portico.Finance;

namespace Portico.Desktop.Tests;

public sealed class DashboardConfigurationReaderTests
{
    [Fact]
    public void ReadsTheCheckedInDashboardWithoutLoadingFinancialConfiguration()
    {
        string path = Path.Combine(FindRepositoryRoot(), "dashboard.toml");

        DashboardReadOutcome outcome = DashboardConfigurationReader.Read(path);

        DashboardReadSuccess success = outcome switch
        {
            DashboardReadSuccess value => value,
            _ => throw new InvalidOperationException("Expected a dashboard definition.")
        };
        Assert.Equal(10, success.Definition.Pages.Count);
        Assert.Equal(DashboardPageId.Home, success.Definition.FirstVisiblePage().Id);
    }

    [Fact]
    public void MissingFileDoesNotExposeItsPath()
    {
        string privatePath = Path.Combine(Path.GetTempPath(), "private-account-dashboard-does-not-exist.toml");

        DashboardReadOutcome outcome = DashboardConfigurationReader.Read(privatePath);

        PorticoFailure failure = outcome switch
        {
            PorticoFailure value => value,
            _ => throw new InvalidOperationException("Expected a dashboard failure.")
        };
        PorticoProblem problem = Assert.Single(failure.Problems);
        Assert.Equal("dashboard.invalid-value", problem.Code);
        Assert.Equal("dashboard", problem.Field);
        Assert.DoesNotContain(privatePath, problem.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void InvalidTomlDoesNotExposeItsContents()
    {
        string path = Path.GetTempFileName();
        try
        {
            File.WriteAllText(path, "secret = \"private-account-token\"\n[broken");

            DashboardReadOutcome outcome = DashboardConfigurationReader.Read(path);

            PorticoFailure failure = outcome switch
            {
                PorticoFailure value => value,
                _ => throw new InvalidOperationException("Expected a dashboard failure.")
            };
            PorticoProblem problem = Assert.Single(failure.Problems);
            Assert.Equal("dashboard.invalid-value", problem.Code);
            Assert.DoesNotContain("private-account-token", problem.Message, StringComparison.Ordinal);
            Assert.DoesNotContain(path, problem.Message, StringComparison.Ordinal);
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void UnknownWidgetReportIsRejectedWithoutEchoingItsName()
    {
        string original = File.ReadAllText(Path.Combine(FindRepositoryRoot(), "dashboard.toml"));
        string path = Path.GetTempFileName();
        try
        {
            File.WriteAllText(path, original.Replace(
                "report = \"home.net_worth\"",
                "report = \"private-account-token\"",
                StringComparison.Ordinal));

            DashboardReadOutcome outcome = DashboardConfigurationReader.Read(path);

            PorticoFailure failure = outcome switch
            {
                PorticoFailure value => value,
                _ => throw new InvalidOperationException("Expected a dashboard failure.")
            };
            Assert.Contains(failure.Problems, problem => problem.Field == "dashboard.pages[0].widgets[0].report");
            Assert.DoesNotContain("private-account-token", string.Join(" ", failure.Problems.Select(problem => problem.Message)));
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public async Task DashboardChoicesMatchTheCheckedInWorkspace()
    {
        string root = FindRepositoryRoot();
        var application = new PorticoApplication(
            new TomlConfigurationReader(Path.GetTempPath()),
            new EmptyPortfolioReader());
        OpenWorkspaceOutcome opened = await application.OpenWorkspaceAsync(
            new ConfigurationSelection(Path.Combine(root, "portico.toml")),
            cancellationToken: TestContext.Current.CancellationToken);
        Workspace workspace = opened switch
        {
            WorkspaceOpened value => value.GetWorkspace(),
            _ => throw new InvalidOperationException("Expected the checked-in workspace.")
        };

        DashboardReadOutcome outcome = DashboardConfigurationReader.Read(
            Path.Combine(root, "dashboard.toml"),
            workspace.ReportChoices);

        Assert.True(outcome is DashboardReadSuccess);
    }

    [Theory]
    [InlineData("app_title = \"Portico\"", "dashboard")]
    [InlineData("[[pages.widgets]]", "dashboard.pages[0].widgets[0]")]
    public void UnknownKeysAreRejectedAtTheirSafeTablePath(string anchor, string expectedField)
    {
        string original = File.ReadAllText(Path.Combine(FindRepositoryRoot(), "dashboard.toml"));
        string path = Path.GetTempFileName();
        try
        {
            File.WriteAllText(path, original.Replace(
                anchor,
                anchor + Environment.NewLine + "private-account-token = true",
                StringComparison.Ordinal));

            DashboardReadOutcome outcome = DashboardConfigurationReader.Read(path);

            PorticoFailure failure = outcome switch
            {
                PorticoFailure value => value,
                _ => throw new InvalidOperationException("Expected a dashboard failure.")
            };
            Assert.Contains(failure.Problems, problem => problem.Field == expectedField);
            Assert.DoesNotContain("private-account-token", string.Join(" ", failure.Problems.Select(problem => problem.Message)));
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public async Task DashboardRejectsUnconfiguredLookbackWithoutEchoingItsValue()
    {
        string root = FindRepositoryRoot();
        var application = new PorticoApplication(
            new TomlConfigurationReader(Path.GetTempPath()),
            new EmptyPortfolioReader());
        OpenWorkspaceOutcome opened = await application.OpenWorkspaceAsync(
            new ConfigurationSelection(Path.Combine(root, "portico.toml")),
            cancellationToken: TestContext.Current.CancellationToken);
        Workspace workspace = opened switch
        {
            WorkspaceOpened value => value.GetWorkspace(),
            _ => throw new InvalidOperationException("Expected the checked-in workspace.")
        };
        string original = File.ReadAllText(Path.Combine(root, "dashboard.toml"));
        string path = Path.GetTempFileName();
        try
        {
            File.WriteAllText(path, original.Replace(
                "options = [\"3\", \"6\", \"12\", \"24\"]",
                "options = [\"3\", \"6\", \"12\", \"999999-private\"]",
                StringComparison.Ordinal));

            DashboardReadOutcome outcome = DashboardConfigurationReader.Read(path, workspace.ReportChoices);

            PorticoFailure failure = outcome switch
            {
                PorticoFailure value => value,
                _ => throw new InvalidOperationException("Expected a dashboard failure.")
            };
            Assert.Contains(failure.Problems, problem => problem.Code == "dashboard.unsupported-choice");
            Assert.Contains(failure.Problems, problem => problem.Field?.EndsWith(".options[3]", StringComparison.Ordinal) == true);
            Assert.DoesNotContain("999999-private", string.Join(" ", failure.Problems.Select(problem => problem.Message)));
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Theory]
    [InlineData("3m", HomePeriod.ThreeMonths)]
    [InlineData("6m", HomePeriod.SixMonths)]
    [InlineData("1y", HomePeriod.OneYear)]
    [InlineData("2y", HomePeriod.TwoYears)]
    [InlineData("5y", HomePeriod.FiveYears)]
    [InlineData("all", HomePeriod.All)]
    public void HomeControlValuesMapToApplicationPeriods(string value, HomePeriod expected)
    {
        Assert.True(HomeTimeFrameOptions.TryParse(value, out HomePeriod period));
        Assert.Equal(expected, period);
    }

    private static string FindRepositoryRoot()
    {
        for (DirectoryInfo? directory = new(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            if (File.Exists(Path.Combine(directory.FullName, "dashboard.toml")))
                return directory.FullName;
        }

        throw new InvalidOperationException("The dashboard fixture was not found.");
    }

    private sealed class EmptyPortfolioReader : IPortfolioReader
    {
        public Task<PortfolioReadOutcome> ReadAsync(SourceRequest source, CancellationToken cancellationToken)
            => Task.FromResult<PortfolioReadOutcome>(new PortfolioReadSuccess(new PortfolioSnapshot([], [], [])));
    }
}
