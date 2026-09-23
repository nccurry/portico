using Portico.Application;
using Portico.Desktop;

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
}
