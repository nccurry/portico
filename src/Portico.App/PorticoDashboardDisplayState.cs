namespace Portico.App;

/// <summary>Describes the source state shown in the Portico application frame.</summary>
public enum PorticoDataLoadStatus
{
    /// <summary>Data is available for the current page.</summary>
    Loaded,

    /// <summary>A refresh request is waiting for the host boundary.</summary>
    Loading,

    /// <summary>The last refresh failed while prior data remains available.</summary>
    Failed,

    /// <summary>The current host cannot safely refresh its data source.</summary>
    Unavailable
}

/// <summary>Describes how an app-owned source check completed.</summary>
public enum PorticoRefreshResultKind
{
    /// <summary>The boundary completed a source check while the held report remains in use.</summary>
    SourceChecked,

    /// <summary>The source check could not complete.</summary>
    Failed,

    /// <summary>The current host cannot check its source.</summary>
    Unavailable
}

/// <summary>Returns one safe, user-facing outcome from an app-owned source check.</summary>
public sealed record PorticoRefreshResult(PorticoRefreshResultKind Kind, string Message)
{
    /// <summary>Creates a completed source check that retains the existing report.</summary>
    public static PorticoRefreshResult SourceChecked(string message = "Source check completed. Showing the loaded data.")
        => new(PorticoRefreshResultKind.SourceChecked, message);

    /// <summary>Creates a failed source check that preserves the last usable report.</summary>
    public static PorticoRefreshResult Failed(string message = "Refresh failed. Showing the last loaded data.")
        => new(PorticoRefreshResultKind.Failed, message);

    /// <summary>Creates an unavailable source check result without pretending to reload data.</summary>
    public static PorticoRefreshResult Unavailable(string message = "Refresh is unavailable in this desktop session.")
        => new(PorticoRefreshResultKind.Unavailable, message);
}

/// <summary>Owns an optional source check without moving loading code into the UI.</summary>
public interface IPorticoRefreshBoundary
{
    /// <summary>Checks source availability and returns a result without changing the held report.</summary>
    Task<PorticoRefreshResult> CheckSourceAsync();
}

/// <summary>Reports that the current host was started from an already loaded snapshot.</summary>
public sealed class UnavailablePorticoRefreshBoundary : IPorticoRefreshBoundary
{
    /// <inheritdoc />
    public Task<PorticoRefreshResult> CheckSourceAsync()
        => Task.FromResult(PorticoRefreshResult.Unavailable());
}

/// <summary>Holds the small presentation state shared by the rail and visible page.</summary>
public sealed class PorticoDashboardDisplayState
{
    /// <summary>Creates a loaded display state for normal or demo data.</summary>
    public PorticoDashboardDisplayState(bool isDemoData = false)
    {
        IsDemoData = isDemoData;
        LoadStatus = PorticoDataLoadStatus.Loaded;
        HasLastGoodData = true;
        StatusMessage = isDemoData ? "Demo data loaded." : "Data loaded.";
    }

    /// <summary>Gets whether the current source is the checked-in demo data.</summary>
    public bool IsDemoData { get; }

    /// <summary>Gets whether financial text is masked at the presentation boundary.</summary>
    public bool HideValues { get; private set; }

    /// <summary>Gets the source status shown in the rail.</summary>
    public PorticoDataLoadStatus LoadStatus { get; private set; }

    /// <summary>Gets whether a prior report remains usable after a refresh result.</summary>
    public bool HasLastGoodData { get; private set; }

    /// <summary>Gets the safe text shown beside the current source status.</summary>
    public string StatusMessage { get; private set; }

    /// <summary>Changes the privacy presentation without changing report values.</summary>
    public void ToggleHideValues() => HideValues = !HideValues;

    /// <summary>Moves the visible status into its loading state when no refresh is already pending.</summary>
    public bool BeginRefresh()
    {
        if (LoadStatus == PorticoDataLoadStatus.Loading)
            return false;

        LoadStatus = PorticoDataLoadStatus.Loading;
        StatusMessage = "Checking the source. Showing the loaded data.";
        return true;
    }

    /// <summary>Applies a completed source check while keeping the last good report available.</summary>
    public void CompleteRefresh(PorticoRefreshResult result)
    {
        ArgumentNullException.ThrowIfNull(result);
        if (string.IsNullOrWhiteSpace(result.Message))
            throw new ArgumentException("A refresh result needs a user-facing message.", nameof(result));

        switch (result.Kind)
        {
            case PorticoRefreshResultKind.SourceChecked:
                LoadStatus = PorticoDataLoadStatus.Loaded;
                HasLastGoodData = true;
                break;
            case PorticoRefreshResultKind.Failed:
                LoadStatus = PorticoDataLoadStatus.Failed;
                break;
            case PorticoRefreshResultKind.Unavailable:
                LoadStatus = PorticoDataLoadStatus.Unavailable;
                break;
            default:
                throw new ArgumentOutOfRangeException(nameof(result));
        }

        StatusMessage = result.Message;
    }
}
