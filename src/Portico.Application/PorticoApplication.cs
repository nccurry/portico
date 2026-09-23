namespace Portico.Application;

/// <summary>Runs Portico's in-process operations through its input boundaries.</summary>
public sealed class PorticoApplication(IConfigurationReader configurationReader, IPortfolioReader portfolioReader)
{
    private readonly IConfigurationReader _configurationReader = configurationReader
        ?? throw new ArgumentNullException(nameof(configurationReader));
    private readonly IPortfolioReader _portfolioReader = portfolioReader
        ?? throw new ArgumentNullException(nameof(portfolioReader));

    public async Task<ConfigurationCheckOutcome> CheckConfigurationAsync(
        ConfigurationSelection selection,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(selection);
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            ConfigurationReadOutcome result = await _configurationReader.ReadAsync(selection, cancellationToken);
            cancellationToken.ThrowIfCancellationRequested();

            return result switch
            {
                ConfigurationReadSuccess read => new ConfigurationChecked(
                    new ConfigurationCheckSummary(read.GetConfiguration().Source.Kind)),
                PorticoFailure failure => failure,
                _ => throw new InvalidOperationException("The configuration reader returned no outcome.")
            };
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return Cancelled();
        }
    }

    public async Task<DataCheckOutcome> CheckDataAsync(
        ConfigurationSelection selection,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(selection);
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            ConfigurationReadOutcome configuration = await _configurationReader.ReadAsync(selection, cancellationToken);
            cancellationToken.ThrowIfCancellationRequested();

            if (configuration is PorticoFailure failure)
                return failure;
            if (configuration is not ConfigurationReadSuccess read)
                throw new InvalidOperationException("The configuration reader returned no outcome.");

            PortfolioReadOutcome portfolio = await _portfolioReader.ReadAsync(
                read.GetConfiguration().Source,
                cancellationToken);
            cancellationToken.ThrowIfCancellationRequested();

            if (portfolio is PorticoFailure dataFailure)
                return dataFailure;
            if (portfolio is not PortfolioReadSuccess loaded)
                throw new InvalidOperationException("The portfolio reader returned no outcome.");

            var snapshot = loaded.GetSnapshot();
            return new DataChecked(new DataCheckSummary(
                read.GetConfiguration().Source.Kind,
                snapshot.Transactions.Count,
                snapshot.Balances.Count,
                snapshot.Budgets.Count));
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return Cancelled();
        }
    }

    /// <summary>Loads one fixed portfolio and its financial policy for report requests.</summary>
    public async Task<OpenWorkspaceOutcome> OpenWorkspaceAsync(
        ConfigurationSelection selection,
        DateOnly? asOfDate = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(selection);
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            ConfigurationReadOutcome configuration = await _configurationReader.ReadAsync(selection, cancellationToken);
            cancellationToken.ThrowIfCancellationRequested();

            if (configuration is PorticoFailure failure)
                return failure;
            if (configuration is not ConfigurationReadSuccess read)
                throw new InvalidOperationException("The configuration reader returned no outcome.");

            WorkspaceConfiguration settings = read.GetConfiguration();
            PortfolioReadOutcome portfolio = await _portfolioReader.ReadAsync(settings.Source, cancellationToken);
            cancellationToken.ThrowIfCancellationRequested();

            if (portfolio is PorticoFailure dataFailure)
                return dataFailure;
            if (portfolio is not PortfolioReadSuccess loaded)
                throw new InvalidOperationException("The portfolio reader returned no outcome.");

            return new WorkspaceOpened(new Workspace(loaded.GetSnapshot(), settings.Settings, settings.ReportChoices, asOfDate));
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return Cancelled();
        }
    }

    private static PorticoFailure Cancelled()
        => new([new PorticoProblem("operation.cancelled", "The operation was cancelled.", retryable: true)]);
}
