using Portico.Desktop;
using Portico.Finance;

namespace Portico.Desktop.Tests;

public sealed class DashboardPresentationStateTests
{
    [Fact]
    public void HomeAccountExpansion_IsRetainedPerGroup()
    {
        var state = new DashboardPresentationState();

        state.SetHomeAccountGroupExpanded("Cash", true);
        state.SetHomeAccountGroupExpanded("Debt", true);
        state.SetHomeAccountGroupExpanded("Cash", false);

        Assert.False(state.IsHomeAccountGroupExpanded("Cash"));
        Assert.True(state.IsHomeAccountGroupExpanded("Debt"));
    }

    [Fact]
    public void IncomeDefaults_AreSuppliedAsTypedInputsRatherThanFinanceSettings()
    {
        var regular = new IncomeSavingsAdjustments(["Salary"], [], [], [], [], false, 0m, false, 0m, 20m);
        var actual = new IncomeSavingsAdjustments([], [], [], [], [], false, 0m, false, 0m, 10m);
        var state = new DashboardPresentationState();

        state.InitializeIncomeSavings(regular, actual);
        state.SetIncomeDetailTab("Excluded");

        Assert.Same(regular, state.IncomeSavingsAdjustments(regular: true));
        Assert.Same(actual, state.IncomeSavingsAdjustments(regular: false));
        Assert.Equal("Excluded", state.IncomeSavings.DetailTab);
    }

    [Fact]
    public void DataHealthSelectionAndSettingsStayInDesktopState()
    {
        var state = new DashboardPresentationState();

        state.SetDataHealthSelectedCheck("duplicates");
        state.SetDataHealthStaleThreshold(14m);
        state.SetDataHealthIncludeInactive(true);

        Assert.Equal("duplicates", state.DataHealth.SelectedCheckId);
        Assert.Equal(14m, state.DataHealth.StaleThreshold);
        Assert.True(state.DataHealth.IncludeInactive);
    }
}
