namespace Portico.Application;

/// <summary>Opened portfolio for in-process semantic report requests.</summary>
public sealed class WorkspaceOpened(Workspace workspace)
{
    private readonly Workspace _workspace = workspace ?? throw new ArgumentNullException(nameof(workspace));

    public Workspace GetWorkspace() => _workspace;
}

/// <summary>Expected result of opening a workspace.</summary>
public union OpenWorkspaceOutcome(WorkspaceOpened, PorticoFailure);
