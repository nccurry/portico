using Portico.Application;
using Portico.Desktop;

namespace Portico.Desktop.Tests;

public sealed class DisplayStateTests
{
    [Fact]
    public void DemoStateCanHideValuesWithoutChangingItsLoadStatus()
    {
        var state = new PorticoDashboardDisplayState(isDemoData: true);

        state.ToggleHideValues();

        Assert.True(state.IsDemoData);
        Assert.True(state.HideValues);
        Assert.Equal(PorticoDataLoadStatus.Loaded, state.LoadStatus);
        Assert.Equal("Demo data loaded.", state.StatusMessage);
    }

    [Fact]
    public void FailedRefreshKeepsTheLastReportAvailable()
    {
        var state = new PorticoDashboardDisplayState();

        Assert.True(state.BeginRefresh());
        Assert.False(state.BeginRefresh());
        Assert.Equal(PorticoDataLoadStatus.Loading, state.LoadStatus);

        state.CompleteRefresh(PorticoRefreshResult.FromFailure(
            new PorticoFailure([new PorticoProblem("data.read-failed", "The selected source could not be read.")])));

        Assert.Equal(PorticoDataLoadStatus.Failed, state.LoadStatus);
        Assert.True(state.HasLastGoodData);
        Assert.Equal("The selected source could not be read.", state.StatusMessage);
    }

    [Fact]
    public async Task UnavailableRefreshKeepsTheLastReportAvailable()
    {
        var state = new PorticoDashboardDisplayState();

        state.BeginRefresh();
        state.CompleteRefresh(await new UnavailablePorticoRefreshBoundary().CheckSourceAsync());

        Assert.Equal(PorticoDataLoadStatus.Unavailable, state.LoadStatus);
        Assert.True(state.HasLastGoodData);
        Assert.Equal("Refresh is unavailable in this desktop session.", state.StatusMessage);
    }

    [Fact]
    public void SuccessfulRefreshRestoresTheLoadedStatus()
    {
        var state = new PorticoDashboardDisplayState();

        state.BeginRefresh();
        state.CompleteRefresh(PorticoRefreshResult.SourceChecked());

        Assert.Equal(PorticoDataLoadStatus.Loaded, state.LoadStatus);
        Assert.True(state.HasLastGoodData);
        Assert.Equal("Source check completed. Showing the loaded data.", state.StatusMessage);
    }
}
