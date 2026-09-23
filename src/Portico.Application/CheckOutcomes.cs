namespace Portico.Application;

/// <summary>Safe configuration-check summary.</summary>
public sealed record ConfigurationCheckSummary(SourceKind Source);

/// <summary>Safe data-check summary. Counts never include financial row values.</summary>
public sealed record DataCheckSummary(SourceKind Source, int Transactions, int Balances, int Budgets);

/// <summary>Successful configuration check.</summary>
public sealed record ConfigurationChecked(ConfigurationCheckSummary Summary);

/// <summary>Successful data check.</summary>
public sealed record DataChecked(DataCheckSummary Summary);

/// <summary>Result of checking configuration without loading data.</summary>
public union ConfigurationCheckOutcome(ConfigurationChecked, PorticoFailure);

/// <summary>Result of checking configuration and normalized data.</summary>
public union DataCheckOutcome(DataChecked, PorticoFailure);
