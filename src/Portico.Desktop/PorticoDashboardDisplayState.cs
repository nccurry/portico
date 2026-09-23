using Portico.Application;

namespace Portico.Desktop;

/// <summary>Source state shown in the desktop navigation rail.</summary>
public enum PorticoDataLoadStatus
{
    Loaded,
    Loading,
    Failed,
    Unavailable
}

/// <summary>Result of checking the source while keeping the loaded report.</summary>
public enum PorticoRefreshResultKind
{
    SourceChecked,
    Failed,
    Unavailable
}

/// <summary>A safe message and status for the desktop refresh action.</summary>
public sealed record PorticoRefreshResult(PorticoRefreshResultKind Kind, string Message)
{
    public static PorticoRefreshResult SourceChecked(string message = "Source check completed. Showing the loaded data.")
        => new(PorticoRefreshResultKind.SourceChecked, message);

    public static PorticoRefreshResult Failed(string message = "Refresh failed. Showing the last loaded data.")
        => new(PorticoRefreshResultKind.Failed, message);

    public static PorticoRefreshResult Unavailable(string message = "Refresh is unavailable in this desktop session.")
        => new(PorticoRefreshResultKind.Unavailable, message);

    /// <summary>Converts a safe Application failure into the existing desktop state.</summary>
    public static PorticoRefreshResult FromFailure(PorticoFailure failure)
    {
        ArgumentNullException.ThrowIfNull(failure);
        return Failed(failure.Problems[0].Message);
    }
}

/// <summary>Checks source availability without putting data loading in the UI.</summary>
public interface IPorticoRefreshBoundary
{
    Task<PorticoRefreshResult> CheckSourceAsync();
}

/// <summary>Used when no source check has been connected to this desktop session.</summary>
public sealed class UnavailablePorticoRefreshBoundary : IPorticoRefreshBoundary
{
    public Task<PorticoRefreshResult> CheckSourceAsync()
        => Task.FromResult(PorticoRefreshResult.Unavailable());
}

/// <summary>Holds the small display state shared by the rail and visible page.</summary>
public sealed class PorticoDashboardDisplayState
{
    public PorticoDashboardDisplayState(bool isDemoData = false)
    {
        IsDemoData = isDemoData;
        LoadStatus = PorticoDataLoadStatus.Loaded;
        HasLastGoodData = true;
        StatusMessage = isDemoData ? "Demo data loaded." : "Data loaded.";
    }

    public bool IsDemoData { get; }

    public bool HideValues { get; private set; }

    public PorticoDataLoadStatus LoadStatus { get; private set; }

    public bool HasLastGoodData { get; private set; }

    public string StatusMessage { get; private set; }

    public void ToggleHideValues() => HideValues = !HideValues;

    public bool BeginRefresh()
    {
        if (LoadStatus == PorticoDataLoadStatus.Loading)
            return false;

        LoadStatus = PorticoDataLoadStatus.Loading;
        StatusMessage = "Checking the source. Showing the loaded data.";
        return true;
    }

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
