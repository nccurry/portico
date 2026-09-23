using Portico.Application;
using Portico.Finance;

using System.Globalization;

namespace Portico.Desktop;

/// <summary>Owns the small mutable view state that connects configured controls to rebuilt reports.</summary>
public sealed class DashboardSession
{
    private readonly Workspace _workspace;
    private bool _initializing;

    /// <summary>Creates a session with the first visible configured page and default filter values.</summary>
    public DashboardSession(
        Workspace workspace,
        DashboardDefinition definition)
    {
        ArgumentNullException.ThrowIfNull(workspace);
        ArgumentNullException.ThrowIfNull(definition);

        _workspace = workspace;
        _initializing = true;
        Definition = definition;
        CurrentPage = definition.FirstVisiblePage().Id;
        ReportFilterChoices spending = workspace.ReportChoices.FilterSets["spending"];
        ReportFilterChoices yearOverYear = workspace.ReportChoices.FilterSets["year_over_year"];
        Filters = new DashboardFilters(
            workspace.ReportChoices.DefaultLookbackMonths,
            spending.Default,
            yearOverYear.Default,
            workspace.DefaultIncomeIsRegular);
        Presentation = new DashboardPresentationState();
        Presentation.InitializeIncomeSavings(
            workspace.IncomeAdjustments(regular: true),
            workspace.IncomeAdjustments(regular: false));
        Presentation.SetIncomeSavingsAdjustments(regular: true, IncomeSavingsDefaultAdjustments(regular: true));
        InitializePlanFilters();
        InitializeDataHealthFilters();
        foreach (DashboardFilterDefinition filter in definition.Pages
                     .SelectMany(page => page.Filters)
                     .GroupBy(filter => filter.Source, StringComparer.Ordinal)
                     .Select(group => group.First()))
        {
            Filters = ApplyFilter(Filters, filter.Source, filter.DefaultValue);
        }
        foreach (DashboardPageDefinition page in definition.Pages)
        {
            foreach (DashboardControlDefinition control in page.Controls)
                ApplyConfiguredControlDefault(page.Id, control);
        }
        _initializing = false;
        RebuildReport();
    }

    /// <summary>Gets the configuration used to render pages and controls.</summary>
    public DashboardDefinition Definition { get; }

    /// <summary>Gets the page currently shown in the main content area.</summary>
    public DashboardPageId CurrentPage { get; private set; }

    /// <summary>Gets the current report filter values.</summary>
    public DashboardFilters Filters { get; private set; }

    /// <summary>Gets the typed per-page state used by configured presentation controls.</summary>
    public DashboardPresentationState Presentation { get; }

    /// <summary>Gets the report rebuilt after the most recent filter change.</summary>
    public DashboardReport Report { get; private set; } = null!;

    /// <summary>Selects a visible configured page.</summary>
    public void SelectPage(DashboardPageId pageId)
    {
        DashboardPageDefinition? page = Definition.Pages.FirstOrDefault(page => page.Id == pageId);
        if (page is null || !page.Visible)
            throw new ArgumentException($"Page '{pageId}' is not visible in the dashboard configuration.", nameof(pageId));
        CurrentPage = pageId;
    }

    /// <summary>Changes a control using its configuration source and rebuilds the report when needed.</summary>
    public void SetFilter(string source, string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(source);
        ArgumentNullException.ThrowIfNull(value);
        if (string.Equals(source, "fi_spending_lookback", StringComparison.Ordinal))
        {
            SetFinancialIndependenceSource(CurrentFinancialIndependenceSource with
            {
                SpendingLookbackMonths = int.Parse(value, CultureInfo.InvariantCulture)
            });
            return;
        }
        if (string.Equals(source, "year_over_year_view", StringComparison.Ordinal))
        {
            SetYearOverYearView(value);
            return;
        }

        DashboardFilters updated = ApplyFilter(Filters, source, value);
        if (updated == Filters)
            return;

        updated.Budget?.Validate();
        updated.FinancialIndependenceSource?.Validate();
        updated.FinancialIndependenceScenario?.Validate();
        updated.DataHealth?.Validate();
        Filters = updated;
        SyncDataHealthPresentation(source);
        RebuildReport();
    }

    /// <summary>Changes a configured single-choice control.</summary>
    public void SetControlValue(DashboardPageId pageId, string controlId, string value)
    {
        ArgumentNullException.ThrowIfNull(value);
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind is not (DashboardControlKind.Select or DashboardControlKind.SegmentedChoice or DashboardControlKind.TabChoice))
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not accept one choice value.", nameof(controlId));
        if (!ControlOptions(pageId, controlId).Contains(value, StringComparer.Ordinal))
            throw new ArgumentException($"Value '{value}' is not configured for dashboard control '{pageId}.{controlId}'.", nameof(value));

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        ApplySingleValue(mapping, value);
    }

    /// <summary>Changes a configured free-text control.</summary>
    public void SetControlText(DashboardPageId pageId, string controlId, string value)
    {
        ArgumentNullException.ThrowIfNull(value);
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind != DashboardControlKind.TextInput)
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not a text input.", nameof(controlId));

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        if (mapping.Behavior == DashboardControlBehavior.ReportInput)
        {
            SetFilter(mapping.ReportFilterSource!, value);
            return;
        }

        if (mapping.Source == DashboardControlSource.MerchantSearch)
        {
            Presentation.SetMerchantSearch(value);
            return;
        }

        throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not accept text.", nameof(controlId));
    }

    /// <summary>Changes a configured multi-select control.</summary>
    public void SetControlValues(DashboardPageId pageId, string controlId, IEnumerable<string> values)
    {
        ArgumentNullException.ThrowIfNull(values);
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind is not (DashboardControlKind.MultiSelect or DashboardControlKind.TextMultiSelect))
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not a multi-select.", nameof(controlId));

        string[] selected = values
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value.Trim())
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        if (control.Kind == DashboardControlKind.MultiSelect
            && selected.Any(value => !ControlOptions(pageId, controlId).Contains(value, StringComparer.Ordinal)))
            throw new ArgumentException($"A selected value is not configured for dashboard control '{pageId}.{controlId}'.", nameof(values));

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        switch (mapping.Source)
        {
            case DashboardControlSource.IncomeExcludedCategories:
                Presentation.SetIncomeExcludedCategories(selected);
                return;
            case DashboardControlSource.IncomeExcludedIncomeCategories:
                SetIncomeSavingsAdjustments(CurrentIncomeAdjustments with { ExcludedIncomeCategories = selected });
                return;
            case DashboardControlSource.IncomeExcludedExpenseGroups:
                SetIncomeSavingsAdjustments(CurrentIncomeAdjustments with { ExcludedExpenseGroups = selected });
                return;
            case DashboardControlSource.IncomeExcludedExpenseCategories:
                SetIncomeSavingsAdjustments(CurrentIncomeAdjustments with { ExcludedExpenseCategories = selected });
                return;
            case DashboardControlSource.IncomeIncludedDescriptions:
                SetIncomeSavingsAdjustments(CurrentIncomeAdjustments with { IncludedDescriptions = selected });
                return;
            case DashboardControlSource.IncomeExcludedDescriptions:
                SetIncomeSavingsAdjustments(CurrentIncomeAdjustments with { ExcludedDescriptions = selected });
                return;
            case DashboardControlSource.YearOverYearPresetCategories:
                Presentation.SetYearOverYearPresetCategories(Filters.YearOverYearSet, selected);
                RebuildReport();
                return;
            case DashboardControlSource.SpendingExcludedGroups:
                SetSpendingAdjustments(CurrentSpendingAdjustments with { ExcludedGroups = selected });
                return;
            case DashboardControlSource.SpendingExcludedCategories:
                SetSpendingAdjustments(CurrentSpendingAdjustments with { ExcludedCategories = selected });
                return;
            case DashboardControlSource.SpendingIncludedDescriptions:
                SetSpendingAdjustments(CurrentSpendingAdjustments with { IncludedDescriptions = selected });
                return;
            case DashboardControlSource.SpendingExcludedDescriptions:
                SetSpendingAdjustments(CurrentSpendingAdjustments with { ExcludedDescriptions = selected });
                return;
            case DashboardControlSource.SubscriptionCategories:
                Filters = Filters with { SubscriptionCategories = selected };
                RebuildReport();
                return;
            case DashboardControlSource.SubscriptionDiscoveryExclusions:
                Filters = Filters with { SubscriptionDiscoveryExclusions = selected };
                RebuildReport();
                return;
            case DashboardControlSource.MerchantExcludedGroups:
                SetMerchantAdjustments(CurrentMerchantAdjustments with { ExcludedGroups = selected });
                return;
            case DashboardControlSource.MerchantExcludedCategories:
                SetMerchantAdjustments(CurrentMerchantAdjustments with { ExcludedCategories = selected });
                return;
            case DashboardControlSource.MerchantIncludedDescriptions:
                SetMerchantAdjustments(CurrentMerchantAdjustments with { IncludedDescriptions = selected });
                return;
            case DashboardControlSource.MerchantExcludedDescriptions:
                SetMerchantAdjustments(CurrentMerchantAdjustments with { ExcludedDescriptions = selected });
                return;
            case DashboardControlSource.TransactionsGroups:
                SetTransactionExplorer(CurrentTransactionExplorer with { Groups = selected });
                return;
            case DashboardControlSource.TransactionsCategories:
                SetTransactionExplorer(CurrentTransactionExplorer with { Categories = selected });
                return;
            case DashboardControlSource.TransactionsAccounts:
                SetTransactionExplorer(CurrentTransactionExplorer with { Accounts = selected });
                return;
            case DashboardControlSource.BudgetGroups:
                SetBudgetRequest(CurrentBudgetRequest with { Groups = selected });
                return;
            case DashboardControlSource.BudgetExcludedGroups:
                SetBudgetRequest(CurrentBudgetRequest with
                {
                    Adjustments = CurrentBudgetRequest.Adjustments with { ExcludedGroups = selected }
                });
                return;
            case DashboardControlSource.BudgetExcludedCategories:
                SetBudgetRequest(CurrentBudgetRequest with
                {
                    Adjustments = CurrentBudgetRequest.Adjustments with { ExcludedCategories = selected }
                });
                return;
            case DashboardControlSource.BudgetIncludedDescriptions:
                SetBudgetRequest(CurrentBudgetRequest with
                {
                    Adjustments = CurrentBudgetRequest.Adjustments with { IncludedDescriptions = selected }
                });
                return;
            case DashboardControlSource.BudgetExcludedDescriptions:
                SetBudgetRequest(CurrentBudgetRequest with
                {
                    Adjustments = CurrentBudgetRequest.Adjustments with { ExcludedDescriptions = selected }
                });
                return;
            case DashboardControlSource.FinancialIndependenceIncludedAccounts:
                SetFinancialIndependenceSource(CurrentFinancialIndependenceSource with { IncludedAccounts = selected });
                return;
            case DashboardControlSource.FinancialIndependenceExcludedGroups:
                SetFinancialIndependenceSource(CurrentFinancialIndependenceSource with
                {
                    Adjustments = CurrentFinancialIndependenceSource.Adjustments with { ExcludedGroups = selected }
                });
                return;
            case DashboardControlSource.FinancialIndependenceExcludedCategories:
                SetFinancialIndependenceSource(CurrentFinancialIndependenceSource with
                {
                    Adjustments = CurrentFinancialIndependenceSource.Adjustments with { ExcludedCategories = selected }
                });
                return;
            case DashboardControlSource.FinancialIndependenceIncludedDescriptions:
                SetFinancialIndependenceSource(CurrentFinancialIndependenceSource with
                {
                    Adjustments = CurrentFinancialIndependenceSource.Adjustments with { IncludedDescriptions = selected }
                });
                return;
            case DashboardControlSource.FinancialIndependenceExcludedDescriptions:
                SetFinancialIndependenceSource(CurrentFinancialIndependenceSource with
                {
                    Adjustments = CurrentFinancialIndependenceSource.Adjustments with { ExcludedDescriptions = selected }
                });
                return;
            default:
                throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not accept multiple values.", nameof(controlId));
        }
    }

    /// <summary>Changes a configured number input or slider.</summary>
    public void SetControlNumber(DashboardPageId pageId, string controlId, decimal value)
    {
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind is not (DashboardControlKind.NumberInput or DashboardControlKind.Slider))
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not numeric.", nameof(controlId));
        if (control.Minimum is null
            || control.Maximum is null
            || control.Step is null
            || value < control.Minimum
            || value > control.Maximum
            || !MatchesNumberStep(pageId, control, value))
        {
            throw new ArgumentOutOfRangeException(nameof(value), value, $"Value must use the configured range and step for '{pageId}.{controlId}'.");
        }

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        switch (mapping.Source)
        {
            case DashboardControlSource.FinancialIndependenceTargetAmount:
                Presentation.SetFinancialIndependenceTargetAmount(value);
                return;
            case DashboardControlSource.DataHealthStaleThreshold:
                Presentation.SetDataHealthStaleThreshold(value);
                if (UsesSourceDataHealthPage())
                    SetDataHealthOptions(CurrentDataHealthOptions with { StaleAccountDays = (int)value });
                return;
            case DashboardControlSource.DataHealthDuplicateDays:
                SetDataHealthOptions(CurrentDataHealthOptions with { DuplicateDays = (int)value });
                return;
            case DashboardControlSource.DataHealthDuplicateMinimum:
                SetDataHealthOptions(CurrentDataHealthOptions with { DuplicateMinimum = value });
                return;
            case DashboardControlSource.SpendingExpenseLimit:
                SetSpendingAdjustments(CurrentSpendingAdjustments with { ExpenseLimit = value });
                return;
            case DashboardControlSource.IncomeIncomeLimit:
                SetIncomeSavingsAdjustments(CurrentIncomeAdjustments with { IncomeLimit = value });
                return;
            case DashboardControlSource.IncomeExpenseLimit:
                SetIncomeSavingsAdjustments(CurrentIncomeAdjustments with { ExpenseLimit = value });
                return;
            case DashboardControlSource.IncomeTargetRate:
                SetIncomeSavingsAdjustments(CurrentIncomeAdjustments with { TargetRate = value });
                return;
            case DashboardControlSource.SubscriptionMinimumConfidence:
                Filters = Filters with { SubscriptionMinimumConfidence = (int)value };
                RebuildReport();
                return;
            case DashboardControlSource.MerchantExpenseLimit:
                SetMerchantAdjustments(CurrentMerchantAdjustments with { ExpenseLimit = value });
                return;
            case DashboardControlSource.TransactionsMinimumAmount:
                SetTransactionExplorer(CurrentTransactionExplorer with { MinimumMagnitude = value });
                return;
            case DashboardControlSource.TransactionsMaximumAmount:
                SetTransactionExplorer(CurrentTransactionExplorer with { MaximumMagnitude = value == 0m ? null : value });
                return;
            case DashboardControlSource.TransactionsLargestCount:
                SetTransactionExplorer(CurrentTransactionExplorer with { LargestCount = (int)value });
                return;
            case DashboardControlSource.BudgetExpenseLimit:
                SetBudgetRequest(CurrentBudgetRequest with
                {
                    Adjustments = CurrentBudgetRequest.Adjustments with { ExpenseLimit = value }
                });
                return;
            case DashboardControlSource.FinancialIndependenceAssets:
                SetFinancialIndependenceScenario(CurrentFinancialIndependenceScenario with { Assets = value });
                return;
            case DashboardControlSource.FinancialIndependenceSpending:
                SetFinancialIndependenceScenario(CurrentFinancialIndependenceScenario with { AnnualSpending = value });
                return;
            case DashboardControlSource.FinancialIndependenceIncome:
                SetFinancialIndependenceScenario(CurrentFinancialIndependenceScenario with { AnnualIncome = value });
                return;
            case DashboardControlSource.FinancialIndependenceReturnRate:
                SetFinancialIndependenceScenario(CurrentFinancialIndependenceScenario with { ExpectedReturnRate = value });
                return;
            case DashboardControlSource.FinancialIndependenceWithdrawalRate:
                SetFinancialIndependenceScenario(CurrentFinancialIndependenceScenario with { WithdrawalRate = value });
                return;
            case DashboardControlSource.FinancialIndependenceProjectionYears:
                SetFinancialIndependenceScenario(CurrentFinancialIndependenceScenario with { ProjectionYears = (int)value });
                return;
            case DashboardControlSource.FinancialIndependenceExpenseLimit:
                SetFinancialIndependenceSource(CurrentFinancialIndependenceSource with
                {
                    Adjustments = CurrentFinancialIndependenceSource.Adjustments with { ExpenseLimit = value }
                });
                return;
            default:
                throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not accept a number.", nameof(controlId));
        }
    }

    /// <summary>Changes a configured toggle.</summary>
    public void SetControlToggle(DashboardPageId pageId, string controlId, bool value)
    {
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind != DashboardControlKind.Toggle)
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not a toggle.", nameof(controlId));

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        switch (mapping.Source)
        {
            case DashboardControlSource.DataHealthIncludeInactive:
                Presentation.SetDataHealthIncludeInactive(value);
                if (UsesSourceDataHealthPage())
                    SetDataHealthOptions(CurrentDataHealthOptions with { IncludeInactive = value });
                return;
            case DashboardControlSource.DataHealthDuplicateSameAccount:
                SetDataHealthOptions(CurrentDataHealthOptions with { DuplicateRequireSameAccount = value });
                return;
            case DashboardControlSource.DataHealthDuplicateSameCategory:
                SetDataHealthOptions(CurrentDataHealthOptions with { DuplicateRequireSameCategory = value });
                return;
            case DashboardControlSource.DataHealthDuplicateSameDescription:
                SetDataHealthOptions(CurrentDataHealthOptions with { DuplicateRequireSameDescription = value });
                return;
            case DashboardControlSource.SpendingExcludeLargeExpenses:
                SetSpendingAdjustments(CurrentSpendingAdjustments with { ExcludeLargeExpenses = value });
                return;
            case DashboardControlSource.IncomeExcludeLargeIncome:
                SetIncomeSavingsAdjustments(CurrentIncomeAdjustments with { ExcludeLargeIncome = value });
                return;
            case DashboardControlSource.IncomeExcludeLargeExpenses:
                SetIncomeSavingsAdjustments(CurrentIncomeAdjustments with { ExcludeLargeExpenses = value });
                return;
            case DashboardControlSource.MerchantExcludeLargeExpenses:
                SetMerchantAdjustments(CurrentMerchantAdjustments with { ExcludeLargeExpenses = value });
                return;
            case DashboardControlSource.BudgetExcludeLargeExpenses:
                SetBudgetRequest(CurrentBudgetRequest with
                {
                    Adjustments = CurrentBudgetRequest.Adjustments with { ExcludeLargeExpenses = value }
                });
                return;
            case DashboardControlSource.FinancialIndependenceExcludeLargeExpenses:
                SetFinancialIndependenceSource(CurrentFinancialIndependenceSource with
                {
                    Adjustments = CurrentFinancialIndependenceSource.Adjustments with { ExcludeLargeExpenses = value }
                });
                return;
            default:
                throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not accept a toggle value.", nameof(controlId));
        }
    }

    /// <summary>Runs one configured reset action.</summary>
    public void InvokeControlAction(DashboardPageId pageId, string controlId)
    {
        DashboardControlDefinition control = Control(pageId, controlId);
        if (control.Kind != DashboardControlKind.ActionReset)
            throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not an action.", nameof(controlId));

        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        switch (mapping.Source)
        {
            case DashboardControlSource.FinancialIndependenceReset:
                if (!UsesSourceFinancialIndependencePage())
                {
                    Presentation.ResetFinancialIndependence(ConfiguredNumberDefault(
                        DashboardPageId.FinancialIndependence,
                        "target_amount"));
                    RebuildReport();
                    return;
                }

                FinancialIndependenceReport initial = _workspace.FinancialIndependence(
                    new FinancialIndependenceReportRequest(CurrentFinancialIndependenceSource));
                Filters = Filters with { FinancialIndependenceScenario = initial.Scenario };
                Presentation.ResetFinancialIndependence(_workspace.DefaultFinancialIndependenceTargetAmount);
                RebuildReport();
                return;
            case DashboardControlSource.SpendingReset:
                Filters = Filters with
                {
                    SpendingAdjustments = Portico.Finance.SpendingAdjustments.Default(ConfiguredNumberDefault(
                        DashboardPageId.Spending,
                        "expense_limit"))
                };
                RebuildReport();
                return;
            case DashboardControlSource.IncomeReset:
                SetIncomeSavingsAdjustments(IncomeSavingsDefaultAdjustments(Filters.RegularIncome));
                return;
            case DashboardControlSource.MerchantReset:
                Filters = Filters with
                {
                    MerchantAdjustments = SpendingAdjustments.Default(ConfiguredMerchantExpenseLimit())
                };
                RebuildReport();
                return;
            case DashboardControlSource.BudgetReset:
                SetBudgetRequest(CurrentBudgetRequest with
                {
                    Adjustments = SpendingAdjustments.Default(ConfiguredBudgetExpenseLimit())
                });
                return;
            default:
                throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' does not have a reset action.", nameof(controlId));
        }
    }

    /// <summary>Gets the visible value for a configured single-value control.</summary>
    public string ControlValue(DashboardPageId pageId, string controlId)
    {
        Control(pageId, controlId);
        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        return mapping.Behavior == DashboardControlBehavior.ReportInput
            ? FilterValue(mapping.ReportFilterSource!)
            : Presentation.ValueFor(mapping.Source);
    }

    /// <summary>Gets the current finite options for one configured control.</summary>
    public IReadOnlyList<string> ControlOptions(DashboardPageId pageId, string controlId)
    {
        DashboardControlDefinition control = Control(pageId, controlId);
        return control.OptionSource switch
        {
            DashboardControlOptionSource.Static => control.ChoiceOptions,
            DashboardControlOptionSource.SpendingGroups => _workspace.TransactionChoices(TransactionChoiceField.Group, expensesOnly: true),
            DashboardControlOptionSource.SpendingCategories => _workspace.TransactionChoices(TransactionChoiceField.Category, expensesOnly: true),
            DashboardControlOptionSource.SpendingMonths => SpendingMonthOptions(),
            DashboardControlOptionSource.IncomeIncomeCategories => IncomeCategoryOptions(TransactionKind.Income),
            DashboardControlOptionSource.IncomeExpenseGroups => IncomeExpenseGroupOptions(),
            DashboardControlOptionSource.IncomeExpenseCategories => IncomeCategoryOptions(TransactionKind.Expense),
            DashboardControlOptionSource.IncomeMonths => IncomeMonthOptions(),
            DashboardControlOptionSource.YearOverYearPresetCategories => YearOverYearPresetCategoryOptions(),
            DashboardControlOptionSource.YearOverYearCategories => YearOverYearEntityOptions(YearOverYearDimension.Category),
            DashboardControlOptionSource.YearOverYearGroups => YearOverYearEntityOptions(YearOverYearDimension.Group),
            DashboardControlOptionSource.AllCategories => _workspace.TransactionChoices(TransactionChoiceField.Category),
            DashboardControlOptionSource.AllGroups => _workspace.TransactionChoices(TransactionChoiceField.Group),
            DashboardControlOptionSource.AllAccounts => _workspace.TransactionChoices(TransactionChoiceField.Account),
            DashboardControlOptionSource.SubscriptionDiscoveryCategories => SubscriptionDiscoveryCategoryOptions(),
            DashboardControlOptionSource.MerchantMonths => MerchantMonthOptions(),
            DashboardControlOptionSource.BudgetMonths => BudgetMonthOptions(),
            DashboardControlOptionSource.BudgetGroups => BudgetGroupOptions(),
            DashboardControlOptionSource.BudgetTransactionCategories => BudgetTransactionCategoryOptions(),
            DashboardControlOptionSource.FinancialIndependenceAccounts => FinancialIndependenceAccountOptions(),
            DashboardControlOptionSource.DataHealthChecks => DataHealthCheckIds(),
            _ => throw new ArgumentOutOfRangeException(nameof(control.OptionSource))
        };
    }

    /// <summary>Gets the visible selected values for a configured multi-select.</summary>
    public IReadOnlySet<string> ControlValues(DashboardPageId pageId, string controlId)
    {
        Control(pageId, controlId);
        DashboardControlMapping mapping = DashboardControlMappings.Resolve(pageId, controlId);
        return mapping.Source switch
        {
            DashboardControlSource.SpendingExcludedGroups => CurrentSpendingAdjustments.ExcludedGroups.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.SpendingExcludedCategories => CurrentSpendingAdjustments.ExcludedCategories.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.SpendingIncludedDescriptions => CurrentSpendingAdjustments.IncludedDescriptions.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.SpendingExcludedDescriptions => CurrentSpendingAdjustments.ExcludedDescriptions.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.IncomeExcludedIncomeCategories => CurrentIncomeAdjustments.ExcludedIncomeCategories.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.IncomeExcludedExpenseGroups => CurrentIncomeAdjustments.ExcludedExpenseGroups.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.IncomeExcludedExpenseCategories => CurrentIncomeAdjustments.ExcludedExpenseCategories.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.IncomeIncludedDescriptions => CurrentIncomeAdjustments.IncludedDescriptions.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.IncomeExcludedDescriptions => CurrentIncomeAdjustments.ExcludedDescriptions.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.YearOverYearPresetCategories => Presentation.YearOverYear.PresetCategories,
            DashboardControlSource.SubscriptionCategories => (Filters.SubscriptionCategories ?? SubscriptionCategoryDefaults()).ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.SubscriptionDiscoveryExclusions => (Filters.SubscriptionDiscoveryExclusions ?? SubscriptionDiscoveryDefaults()).ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.MerchantExcludedGroups => CurrentMerchantAdjustments.ExcludedGroups.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.MerchantExcludedCategories => CurrentMerchantAdjustments.ExcludedCategories.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.MerchantIncludedDescriptions => CurrentMerchantAdjustments.IncludedDescriptions.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.MerchantExcludedDescriptions => CurrentMerchantAdjustments.ExcludedDescriptions.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.TransactionsGroups => CurrentTransactionExplorer.Groups.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.TransactionsCategories => CurrentTransactionExplorer.Categories.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.TransactionsAccounts => CurrentTransactionExplorer.Accounts.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.BudgetGroups => CurrentBudgetRequest.Groups.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.BudgetExcludedGroups => CurrentBudgetRequest.Adjustments.ExcludedGroups.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.BudgetExcludedCategories => CurrentBudgetRequest.Adjustments.ExcludedCategories.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.BudgetIncludedDescriptions => CurrentBudgetRequest.Adjustments.IncludedDescriptions.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.BudgetExcludedDescriptions => CurrentBudgetRequest.Adjustments.ExcludedDescriptions.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.FinancialIndependenceIncludedAccounts => CurrentFinancialIndependenceSource.IncludedAccounts.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.FinancialIndependenceExcludedGroups => CurrentFinancialIndependenceSource.Adjustments.ExcludedGroups.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.FinancialIndependenceExcludedCategories => CurrentFinancialIndependenceSource.Adjustments.ExcludedCategories.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.FinancialIndependenceIncludedDescriptions => CurrentFinancialIndependenceSource.Adjustments.IncludedDescriptions.ToHashSet(StringComparer.Ordinal),
            DashboardControlSource.FinancialIndependenceExcludedDescriptions => CurrentFinancialIndependenceSource.Adjustments.ExcludedDescriptions.ToHashSet(StringComparer.Ordinal),
            _ => Presentation.ValuesFor(mapping.Source)
        };
    }

    /// <summary>Gets a source-shaped label for the active named spending view.</summary>
    public string SpendingSetLabel(string key) => _workspace.ReportChoices.TransactionSetLabels[key];

    /// <summary>Gets the source-shaped label for one configured Year over year preset.</summary>
    public string YearOverYearSetLabel(string key) => _workspace.ReportChoices.TransactionSetLabels[key];

    /// <summary>Gets the configured defaults for the selected Income calculation view.</summary>
    public IncomeSavingsAdjustments IncomeSavingsDefaultAdjustments(bool regular)
    {
        IncomeSavingsAdjustments defaults = _workspace.IncomeAdjustments(regular);
        if (!regular)
            return defaults;

        return defaults with
        {
            ExcludedIncomeCategories = AvailableDefaults(
                defaults.ExcludedIncomeCategories,
                IncomeCategoryOptions(TransactionKind.Income)),
            ExcludedExpenseGroups = AvailableDefaults(
                defaults.ExcludedExpenseGroups,
                IncomeExpenseGroupOptions()),
            ExcludedExpenseCategories = AvailableDefaults(
                defaults.ExcludedExpenseCategories,
                IncomeCategoryOptions(TransactionKind.Expense))
        };
    }

    /// <summary>Sets the selected Spending entity and rebuilds selected detail reports.</summary>
    public void SetSpendingSelectedEntity(SpendingBreakdown breakdown, string? entity)
    {
        Presentation.SetSpendingSelectedEntity(breakdown, entity);
        RebuildReport();
    }

    /// <summary>Sets the active Spending detail tab.</summary>
    public void SetSpendingDetailTab(string tab) => Presentation.SetSpendingDetailTab(tab);

    /// <summary>Sets whether the Spending adjustment popover is open.</summary>
    public void SetSpendingAdjustViewOpen(bool open) => Presentation.SetSpendingAdjustViewOpen(open);

    /// <summary>Sets whether excluded Spending rows are expanded.</summary>
    public void SetSpendingExcludedRowsExpanded(bool expanded) => Presentation.SetSpendingExcludedRowsExpanded(expanded);

    /// <summary>Sets the selected subscription merchant and rebuilds its detail reports.</summary>
    public void SetSubscriptionSelectedMerchant(string? merchant)
    {
        Presentation.SetSubscriptionSelectedMerchant(merchant);
        RebuildReport();
    }

    /// <summary>Sets whether subscription settings are open.</summary>
    public void SetSubscriptionSettingsOpen(bool open) => Presentation.SetSubscriptionSettingsOpen(open);

    /// <summary>Sets the selected subscription history range.</summary>
    public void SetSubscriptionHistoryLookback(string value)
    {
        Presentation.SetSubscriptionHistoryLookback(value);
        RebuildReport();
    }

    /// <summary>Sets the subscription timeline scope.</summary>
    public void SetSubscriptionTimelineScope(string value)
    {
        Presentation.SetSubscriptionTimelineScope(value);
        RebuildReport();
    }

    /// <summary>Sets the selected merchant and rebuilds its detail reports.</summary>
    public void SetMerchantSelectedMerchant(string? merchant)
    {
        Presentation.SetMerchantSelectedMerchant(merchant);
        RebuildReport();
    }

    /// <summary>Sets the selected merchant detail month.</summary>
    public void SetMerchantDetailMonth(string month)
    {
        Presentation.SetMerchantDetailMonth(month);
        RebuildReport();
    }

    /// <summary>Sets the selected merchant detail tab.</summary>
    public void SetMerchantDetailTab(string tab) => Presentation.SetMerchantDetailTab(tab);

    /// <summary>Sets whether merchant adjustments are open.</summary>
    public void SetMerchantAdjustViewOpen(bool open) => Presentation.SetMerchantAdjustViewOpen(open);

    /// <summary>Sets whether transaction filters are open.</summary>
    public void SetTransactionsMoreFiltersOpen(bool open) => Presentation.SetTransactionsMoreFiltersOpen(open);

    /// <summary>Sets the selected Budget group and rebuilds selected detail reports.</summary>
    public void SetBudgetSelectedGroup(string? group)
    {
        Presentation.SetBudgetSelectedGroup(group);
        RebuildReport();
    }

    /// <summary>Sets the Budget transaction-category detail view.</summary>
    public void SetBudgetTransactionCategory(string category)
    {
        Presentation.SetBudgetTransactionCategory(category);
        RebuildReport();
    }

    /// <summary>Sets whether the Budget Adjust view is open.</summary>
    public void SetBudgetAdjustViewOpen(bool open) => Presentation.SetBudgetAdjustViewOpen(open);

    /// <summary>Sets whether the Budget year-to-date detail is expanded.</summary>
    public void SetBudgetYearToDateOpen(bool open) => Presentation.SetBudgetYearToDateOpen(open);

    /// <summary>Sets whether Financial Independence source controls are open.</summary>
    public void SetFinancialIndependenceAdjustSourceDataOpen(bool open)
        => Presentation.SetFinancialIndependenceAdjustSourceDataOpen(open);

    /// <summary>Sets whether Financial Independence source details are expanded.</summary>
    public void SetFinancialIndependenceSourceDetailsOpen(bool open)
        => Presentation.SetFinancialIndependenceSourceDetailsOpen(open);

    /// <summary>Sets the active Financial Independence source-details tab.</summary>
    public void SetFinancialIndependenceSourceDetailsTab(string tab)
        => Presentation.SetFinancialIndependenceSourceDetailsTab(tab);

    /// <summary>Sets whether the Data Health check-settings popover is open.</summary>
    public void SetDataHealthCheckSettingsOpen(bool open)
        => Presentation.SetDataHealthCheckSettingsOpen(open);

    /// <summary>Sets the selected Data Health check and rebuilds its detail report.</summary>
    public void SetDataHealthSelectedCheck(string checkId)
    {
        if (!DataHealthCheckIds().Contains(checkId, StringComparer.Ordinal))
            throw new ArgumentException($"Data Health check '{checkId}' is not available.", nameof(checkId));
        Presentation.SetDataHealthSelectedCheck(checkId);
        RebuildReport();
    }

    /// <summary>Sets whether one Year over year card's details are visible.</summary>
    public void SetYearOverYearDetailsExpanded(string entity, bool expanded)
        => Presentation.SetYearOverYearDetailsExpanded(entity, expanded);

    private int ParseLookback(string value)
    {
        if (!int.TryParse(value, out int months) || !_workspace.ReportChoices.LookbackMonths.Contains(months))
            throw new ArgumentException($"Lookback '{value}' is not configured.", nameof(value));
        return months;
    }

    private string ValidateFilterSet(string filterSet, string value)
    {
        ReportFilterChoices definition = _workspace.ReportChoices.FilterSets[filterSet];
        if (!definition.Options.Contains(value, StringComparer.Ordinal))
            throw new ArgumentException($"Value '{value}' is not an option for '{filterSet}'.", nameof(value));
        return value;
    }

    private static bool ParseIncomeView(string value)
        => value switch
        {
            "regular" => true,
            "actual" => false,
            _ => throw new ArgumentException("Income view must be 'regular' or 'actual'.", nameof(value))
        };

    private static int? ParseTransactionLookback(string value)
        => value switch
        {
            "3m" => 90,
            "6m" => 180,
            "1y" => 365,
            "2y" => 730,
            "all" => null,
            _ => throw new ArgumentException("Transaction lookback must be 3m, 6m, 1y, 2y, or all.", nameof(value))
        };

    private static string FormatTransactionLookback(int? days)
        => days switch
        {
            90 => "3m",
            180 => "6m",
            365 => "1y",
            730 => "2y",
            null => "all",
            _ => "all"
        };

    private static TransactionExplorerType ParseTransactionType(string value)
        => value switch
        {
            "all" => TransactionExplorerType.All,
            "expenses" => TransactionExplorerType.Expenses,
            "income" => TransactionExplorerType.Income,
            "transfers" => TransactionExplorerType.Transfers,
            _ => throw new ArgumentException("Transaction type must be all, expenses, income, or transfers.", nameof(value))
        };

    private static string FormatTransactionType(TransactionExplorerType value)
        => value switch
        {
            TransactionExplorerType.All => "all",
            TransactionExplorerType.Expenses => "expenses",
            TransactionExplorerType.Income => "income",
            TransactionExplorerType.Transfers => "transfers",
            _ => throw new ArgumentOutOfRangeException(nameof(value))
        };

    private static TransactionExplorerFocus ParseTransactionFocus(string value)
        => value switch
        {
            "all" => TransactionExplorerFocus.AllTransactions,
            "largest" => TransactionExplorerFocus.Largest,
            "one_off" => TransactionExplorerFocus.OneOffMerchants,
            "unusual" => TransactionExplorerFocus.UnusualAmounts,
            "reversals" => TransactionExplorerFocus.RefundsReversals,
            _ => throw new ArgumentException("Transaction focus must be all, largest, one_off, unusual, or reversals.", nameof(value))
        };

    private static string FormatTransactionFocus(TransactionExplorerFocus value)
        => value switch
        {
            TransactionExplorerFocus.AllTransactions => "all",
            TransactionExplorerFocus.Largest => "largest",
            TransactionExplorerFocus.OneOffMerchants => "one_off",
            TransactionExplorerFocus.UnusualAmounts => "unusual",
            TransactionExplorerFocus.RefundsReversals => "reversals",
            _ => throw new ArgumentOutOfRangeException(nameof(value))
        };

    private static TransactionExplorerBreakdown ParseTransactionBreakdown(string value)
        => value switch
        {
            "group" => TransactionExplorerBreakdown.Group,
            "category" => TransactionExplorerBreakdown.Category,
            "merchant" => TransactionExplorerBreakdown.Merchant,
            "account" => TransactionExplorerBreakdown.Account,
            "type" => TransactionExplorerBreakdown.Type,
            _ => throw new ArgumentException("Transaction breakdown must be group, category, merchant, account, or type.", nameof(value))
        };

    private static string FormatTransactionBreakdown(TransactionExplorerBreakdown value)
        => value switch
        {
            TransactionExplorerBreakdown.Group => "group",
            TransactionExplorerBreakdown.Category => "category",
            TransactionExplorerBreakdown.Merchant => "merchant",
            TransactionExplorerBreakdown.Account => "account",
            TransactionExplorerBreakdown.Type => "type",
            _ => throw new ArgumentOutOfRangeException(nameof(value))
        };

    private DashboardFilters ApplyFilter(DashboardFilters filters, string source, string value)
        => source switch
        {
            "lookback" => filters with { LookbackMonths = ParseLookback(value) },
            "income_lookback" => filters with { IncomeLookbackMonths = ParseLookback(value) },
            "home_time_frame" => HomeTimeFrameOptions.TryParse(value, out HomePeriod period)
                ? filters with { HomeTimeFrame = period }
                : throw new ArgumentException($"Home time frame '{value}' is not supported.", nameof(value)),
            "spending" => filters with { SpendingSet = ValidateFilterSet("spending", value) },
            "spending_comparison" => DashboardControlMappings.TryParseSpendingComparison(value, out SpendingComparison comparison)
                ? filters with { SpendingComparison = comparison }
                : throw new ArgumentException("Spending comparison must be 'previous_period' or 'last_year'.", nameof(value)),
            "spending_breakdown" => DashboardControlMappings.TryParseSpendingBreakdown(value, out SpendingBreakdown breakdown)
                ? filters with { SpendingBreakdown = breakdown }
                : throw new ArgumentException("Spending breakdown must be 'group' or 'category'.", nameof(value)),
            "year_over_year" => filters with { YearOverYearSet = ValidateFilterSet("year_over_year", value) },
            "income_view" => filters with { RegularIncome = ParseIncomeView(value) },
            "income_calculation" => filters with { RegularIncome = ParseIncomeView(value) },
            "merchant_lookback" => filters with { MerchantLookbackMonths = ParseLookback(value) },
            "merchant_spending" => filters with { MerchantSet = ValidateFilterSet("spending", value) },
            "merchant_comparison" => DashboardControlMappings.TryParseSpendingComparison(value, out SpendingComparison merchantComparison)
                ? filters with { MerchantComparison = merchantComparison }
                : throw new ArgumentException("Merchant comparison must be 'previous_period' or 'last_year'.", nameof(value)),
            "transactions_lookback" => filters with { TransactionExplorer = TransactionFilters(filters) with { LookbackDays = ParseTransactionLookback(value) } },
            "transactions_type" => filters with { TransactionExplorer = TransactionFilters(filters) with { Type = ParseTransactionType(value) } },
            "transactions_focus" => filters with { TransactionExplorer = TransactionFilters(filters) with { Focus = ParseTransactionFocus(value) } },
            "transactions_search" => filters with { TransactionExplorer = TransactionFilters(filters) with { Search = value } },
            "transactions_breakdown" => filters with { TransactionExplorer = TransactionFilters(filters) with { Breakdown = ParseTransactionBreakdown(value) } },
            "budget_month" => filters with { Budget = CurrentBudgetRequest with { SelectedMonth = YearMonth.Parse(value) } },
            "budget_exclude_large_expenses" => filters with
            {
                Budget = CurrentBudgetRequest with
                {
                    Adjustments = CurrentBudgetRequest.Adjustments with { ExcludeLargeExpenses = bool.Parse(value) }
                }
            },
            "budget_expense_limit" => filters with
            {
                Budget = CurrentBudgetRequest with
                {
                    Adjustments = CurrentBudgetRequest.Adjustments with { ExpenseLimit = decimal.Parse(value, CultureInfo.InvariantCulture) }
                }
            },
            "fi_assets" => filters with { FinancialIndependenceScenario = CurrentFinancialIndependenceScenario with { Assets = decimal.Parse(value, CultureInfo.InvariantCulture) } },
            "fi_spending" => filters with { FinancialIndependenceScenario = CurrentFinancialIndependenceScenario with { AnnualSpending = decimal.Parse(value, CultureInfo.InvariantCulture) } },
            "fi_income" => filters with { FinancialIndependenceScenario = CurrentFinancialIndependenceScenario with { AnnualIncome = decimal.Parse(value, CultureInfo.InvariantCulture) } },
            "fi_return_rate" => filters with { FinancialIndependenceScenario = CurrentFinancialIndependenceScenario with { ExpectedReturnRate = decimal.Parse(value, CultureInfo.InvariantCulture) } },
            "fi_withdrawal_rate" => filters with { FinancialIndependenceScenario = CurrentFinancialIndependenceScenario with { WithdrawalRate = decimal.Parse(value, CultureInfo.InvariantCulture) } },
            "fi_years" => filters with { FinancialIndependenceScenario = CurrentFinancialIndependenceScenario with { ProjectionYears = int.Parse(value, CultureInfo.InvariantCulture) } },
            "fi_spending_lookback" => filters with { FinancialIndependenceSource = CurrentFinancialIndependenceSource with { SpendingLookbackMonths = int.Parse(value, CultureInfo.InvariantCulture) } },
            "fi_exclude_large_expenses" => filters with
            {
                FinancialIndependenceSource = CurrentFinancialIndependenceSource with
                {
                    Adjustments = CurrentFinancialIndependenceSource.Adjustments with { ExcludeLargeExpenses = bool.Parse(value) }
                }
            },
            "fi_expense_limit" => filters with
            {
                FinancialIndependenceSource = CurrentFinancialIndependenceSource with
                {
                    Adjustments = CurrentFinancialIndependenceSource.Adjustments with { ExpenseLimit = decimal.Parse(value, CultureInfo.InvariantCulture) }
                }
            },
            "health_stale_days" => filters with
            {
                DataHealth = CurrentDataHealthOptions with { StaleAccountDays = int.Parse(value, CultureInfo.InvariantCulture) }
            },
            "health_duplicate_days" => filters with
            {
                DataHealth = CurrentDataHealthOptions with { DuplicateDays = int.Parse(value, CultureInfo.InvariantCulture) }
            },
            "health_duplicate_minimum" => filters with
            {
                DataHealth = CurrentDataHealthOptions with { DuplicateMinimum = decimal.Parse(value, CultureInfo.InvariantCulture) }
            },
            "health_same_account" => filters with
            {
                DataHealth = CurrentDataHealthOptions with { DuplicateRequireSameAccount = bool.Parse(value) }
            },
            "health_same_category" => filters with
            {
                DataHealth = CurrentDataHealthOptions with { DuplicateRequireSameCategory = bool.Parse(value) }
            },
            "health_same_description" => filters with
            {
                DataHealth = CurrentDataHealthOptions with { DuplicateRequireSameDescription = bool.Parse(value) }
            },
            "health_include_inactive" => filters with
            {
                DataHealth = CurrentDataHealthOptions with { IncludeInactive = bool.Parse(value) }
            },
            _ => throw new ArgumentException($"Unsupported dashboard filter source '{source}'.", nameof(source))
        };

    private void ApplyConfiguredControlDefault(DashboardPageId pageId, DashboardControlDefinition control)
    {
        switch (control.Kind)
        {
            case DashboardControlKind.Select:
            case DashboardControlKind.SegmentedChoice:
            case DashboardControlKind.TabChoice:
                if (control.DefaultValue is not null)
                    SetControlValue(pageId, control.Id, control.DefaultValue);
                break;
            case DashboardControlKind.MultiSelect:
            case DashboardControlKind.TextMultiSelect:
                if (control.MultiSelectDefaults.Count == 0)
                {
                    break;
                }
                SetControlValues(pageId, control.Id, control.MultiSelectDefaults);
                break;
            case DashboardControlKind.NumberInput:
            case DashboardControlKind.Slider:
                if (control.DefaultValue is not null)
                {
                    SetControlNumber(
                        pageId,
                        control.Id,
                        decimal.Parse(control.DefaultValue, CultureInfo.InvariantCulture));
                }
                break;
            case DashboardControlKind.Toggle:
                SetControlToggle(pageId, control.Id, bool.Parse(control.DefaultValue!));
                break;
            case DashboardControlKind.TextInput:
                if (control.DefaultValue is not null)
                    SetControlText(pageId, control.Id, control.DefaultValue);
                break;
            case DashboardControlKind.ActionReset:
            case DashboardControlKind.Popover:
            case DashboardControlKind.Collapsible:
                break;
            default:
                throw new ArgumentOutOfRangeException(nameof(control));
        }
    }

    private void ApplySingleValue(DashboardControlMapping mapping, string value)
    {
        if (mapping.Source == DashboardControlSource.YearOverYearView)
        {
            SetYearOverYearView(value);
            return;
        }
        if (mapping.Source == DashboardControlSource.YearOverYearSingleCategory)
        {
            Presentation.SetYearOverYearSingleCategory(value);
            RebuildReport();
            return;
        }
        if (mapping.Source == DashboardControlSource.YearOverYearSingleGroup)
        {
            Presentation.SetYearOverYearSingleGroup(value);
            RebuildReport();
            return;
        }
        if (mapping.Behavior == DashboardControlBehavior.ReportInput)
        {
            SetFilter(mapping.ReportFilterSource!, value);
            return;
        }

        switch (mapping.Source)
        {
            case DashboardControlSource.IncomeDetailTab:
                Presentation.SetIncomeDetailTab(value);
                return;
            case DashboardControlSource.IncomeDetailMonth:
                Presentation.SetIncomeDetailMonth(value);
                RebuildReport();
                return;
            case DashboardControlSource.SpendingDetailMonth:
                Presentation.SetSpendingDetailMonth(value);
                RebuildReport();
                return;
            case DashboardControlSource.SubscriptionHistoryLookback:
                SetSubscriptionHistoryLookback(value);
                return;
            case DashboardControlSource.SubscriptionTimelineScope:
                SetSubscriptionTimelineScope(value);
                return;
            case DashboardControlSource.MerchantDetailMonth:
                SetMerchantDetailMonth(value);
                return;
            case DashboardControlSource.MerchantDetailTab:
                SetMerchantDetailTab(value);
                return;
            case DashboardControlSource.BudgetTransactionCategory:
                SetBudgetTransactionCategory(value);
                return;
            case DashboardControlSource.FinancialIndependenceSourceDetailsTab:
                SetFinancialIndependenceSourceDetailsTab(value);
                return;
            case DashboardControlSource.DataHealthSelectedCheck:
                SetDataHealthSelectedCheck(value);
                return;
            default:
                throw new ArgumentException($"Dashboard control source '{mapping.Source}' does not accept one choice value.", nameof(mapping));
        }
    }

    private SpendingAdjustments CurrentSpendingAdjustments
        => Filters.SpendingAdjustments ?? SpendingAdjustments.Default(ConfiguredSpendingExpenseLimit());

    private IncomeSavingsAdjustments CurrentIncomeAdjustments
        => Presentation.IncomeSavingsAdjustments(Filters.RegularIncome);

    private SpendingAdjustments CurrentMerchantAdjustments
        => Filters.MerchantAdjustments ?? SpendingAdjustments.Default(ConfiguredMerchantExpenseLimit());

    private TransactionExplorerFilters CurrentTransactionExplorer
        => Filters.TransactionExplorer ?? TransactionExplorerFilters.Default;

    private BudgetRequest CurrentBudgetRequest
        => Filters.Budget ?? DefaultBudgetRequest();

    private FinancialIndependenceSourceFilters CurrentFinancialIndependenceSource
        => Filters.FinancialIndependenceSource
            ?? _workspace.FinancialIndependence().SourceFilters;

    private FinancialIndependenceScenario CurrentFinancialIndependenceScenario
    {
        get
        {
            if (Filters.FinancialIndependenceScenario is { } scenario)
                return scenario;
            return _workspace.FinancialIndependence(
                new FinancialIndependenceReportRequest(CurrentFinancialIndependenceSource)).Scenario;
        }
    }

    private DataHealthCheckOptions CurrentDataHealthOptions
        => Filters.DataHealth ?? _workspace.DefaultDataHealthOptions();

    private static TransactionExplorerFilters TransactionFilters(DashboardFilters filters)
        => filters.TransactionExplorer ?? TransactionExplorerFilters.Default;

    private void SetSpendingAdjustments(SpendingAdjustments adjustments)
    {
        Filters = Filters with { SpendingAdjustments = adjustments };
        RebuildReport();
    }

    private void SetIncomeSavingsAdjustments(IncomeSavingsAdjustments adjustments)
    {
        Presentation.SetIncomeSavingsAdjustments(Filters.RegularIncome, adjustments);
        RebuildReport();
    }

    private void SetMerchantAdjustments(SpendingAdjustments adjustments)
    {
        Filters = Filters with { MerchantAdjustments = adjustments };
        RebuildReport();
    }

    private void SetTransactionExplorer(TransactionExplorerFilters filters)
    {
        Filters = Filters with { TransactionExplorer = filters };
        RebuildReport();
    }

    private void InitializePlanFilters()
    {
        if (UsesSourceBudgetPage())
        {
            Filters = Filters with { Budget = DefaultBudgetRequest() };
        }

        if (!UsesSourceFinancialIndependencePage())
            return;

        FinancialIndependenceReport initial = _workspace.FinancialIndependence();
        Filters = Filters with
        {
            FinancialIndependenceSource = initial.SourceFilters,
            FinancialIndependenceScenario = initial.Scenario
        };
    }

    private void InitializeDataHealthFilters()
    {
        if (!UsesSourceDataHealthPage())
            return;

        DataHealthCheckOptions options = _workspace.DefaultDataHealthOptions();
        Filters = Filters with { DataHealth = options };
        Presentation.SetDataHealthStaleThreshold(options.StaleAccountDays);
        Presentation.SetDataHealthIncludeInactive(options.IncludeInactive);
    }

    private bool UsesSourceBudgetPage()
        => Definition.Pages.Any(page => page.Id == DashboardPageId.Budget
            && page.Controls.Any(control => control.Source == DashboardControlSource.BudgetMonth));

    private bool UsesSourceFinancialIndependencePage()
        => Definition.Pages.Any(page => page.Id == DashboardPageId.FinancialIndependence
            && page.Controls.Any(control => control.Source == DashboardControlSource.FinancialIndependenceAssets));

    private bool UsesSourceDataHealthPage()
        => Definition.Pages.Any(page => page.Id == DashboardPageId.DataHealth
            && page.Controls.Any(control => control.Source == DashboardControlSource.DataHealthDuplicateDays));

    private bool MatchesNumberStep(DashboardPageId pageId, DashboardControlDefinition control, decimal value)
    {
        decimal step = control.Step!.Value;
        if (decimal.Remainder(value - control.Minimum!.Value, step) == 0m)
            return true;

        if (pageId != DashboardPageId.FinancialIndependence
            || control.DefaultValue is not null
            || control.Source is not (DashboardControlSource.FinancialIndependenceAssets
                or DashboardControlSource.FinancialIndependenceSpending
                or DashboardControlSource.FinancialIndependenceIncome))
        {
            return false;
        }

        decimal current = decimal.Parse(ControlValue(pageId, control.Id), CultureInfo.InvariantCulture);
        return decimal.Remainder(value - current, step) == 0m;
    }

    private BudgetRequest DefaultBudgetRequest() => _workspace.DefaultBudgetRequest();
    private void SetBudgetRequest(BudgetRequest request)
    {
        request.Validate();
        Filters = Filters with { Budget = request };
        RebuildReport();
    }

    private void SetFinancialIndependenceScenario(FinancialIndependenceScenario scenario)
    {
        scenario.Validate();
        Filters = Filters with { FinancialIndependenceScenario = scenario };
        RebuildReport();
    }

    private void SetFinancialIndependenceSource(FinancialIndependenceSourceFilters filters)
    {
        filters.Validate();
        FinancialIndependenceSourceAnalysis previousSource = _workspace.FinancialIndependence(
            new FinancialIndependenceReportRequest(CurrentFinancialIndependenceSource)).Source;
        FinancialIndependenceScenario scenario = CurrentFinancialIndependenceScenario;
        bool followsSource = scenario.Assets == previousSource.PortfolioValue
            && scenario.AnnualSpending == previousSource.AnnualSpending;
        Filters = Filters with { FinancialIndependenceSource = filters };
        if (followsSource)
        {
            FinancialIndependenceReport next = _workspace.FinancialIndependence(
                new FinancialIndependenceReportRequest(filters));
            Filters = Filters with
            {
                FinancialIndependenceScenario = next.Scenario
            };
        }
        RebuildReport();
    }

    private void SetDataHealthOptions(DataHealthCheckOptions options)
    {
        options.Validate();
        Filters = Filters with { DataHealth = options };
        Presentation.SetDataHealthStaleThreshold(options.StaleAccountDays);
        Presentation.SetDataHealthIncludeInactive(options.IncludeInactive);
        RebuildReport();
    }

    private IReadOnlyList<string> SubscriptionCategoryOptions()
        => _workspace.TransactionChoices(TransactionChoiceField.Category);

    private IReadOnlyList<string> SubscriptionCategoryDefaults()
        => _workspace.SubscriptionCategoryDefaults();

    private IReadOnlyList<string> SubscriptionDiscoveryDefaults()
        => _workspace.SubscriptionDiscoveryDefaults(Filters.SubscriptionCategories ?? SubscriptionCategoryDefaults());

    private IReadOnlyList<string> SubscriptionDiscoveryCategoryOptions()
    {
        IReadOnlyList<string> selected = Filters.SubscriptionCategories ?? SubscriptionCategoryDefaults();
        return SubscriptionCategoryOptions()
            .Where(category => !selected.Contains(category, StringComparer.Ordinal))
            .ToArray();
    }

    private IReadOnlyList<string> MerchantMonthOptions()
    {
        MerchantsReport report = _workspace.Merchants(new MerchantsReportRequest(
            Filters.MerchantSet ?? Filters.SpendingSet,
            Filters.EffectiveMerchantLookbackMonths,
            Filters.MerchantComparison,
            CurrentMerchantAdjustments));
        return ["all", .. report.Analysis.Period.CurrentMonths.Reverse().Select(month => month.ToString())];
    }

    private IReadOnlyList<string> BudgetMonthOptions()
        => _workspace.BudgetMonths().Select(month => month.ToString()).ToArray();

    private IReadOnlyList<string> BudgetGroupOptions()
        => _workspace.BudgetGroups();

    private IReadOnlyList<string> BudgetTransactionCategoryOptions()
    {
        string? group = Presentation.Budget.SelectedGroup ?? CurrentBudgetRequest.Groups.FirstOrDefault();
        return group is null
            ? ["all"]
            : ["all", .. _workspace.BudgetCategories(group, CurrentBudgetRequest.SelectedMonth)];
    }

    private IReadOnlyList<string> FinancialIndependenceAccountOptions()
        => _workspace.FinancialIndependenceAccounts();

    private static IReadOnlyList<string> DataHealthCheckIds()
        => ["uncategorized", "incomplete", "account_mapping", "stale_accounts", "duplicates", "reversals"];

    private IReadOnlyList<string> SpendingMonthOptions()
    {
        SpendingReport report = _workspace.Spending(new SpendingReportRequest(
            Filters.SpendingSet,
            Filters.LookbackMonths,
            Filters.SpendingComparison,
            Filters.SpendingBreakdown,
            CurrentSpendingAdjustments));
        return ["all", .. report.Analysis.Period.CurrentMonths.Reverse().Select(month => month.ToString())];
    }

    private IReadOnlyList<string> IncomeCategoryOptions(TransactionKind kind)
        => _workspace.IncomeCategories(kind);

    private IReadOnlyList<string> IncomeExpenseGroupOptions()
        => _workspace.IncomeExpenseGroups();

    private static IReadOnlyList<string> AvailableDefaults(
        IEnumerable<string> configured,
        IReadOnlyList<string> available)
        => configured.Where(available.Contains).ToArray();

    private IReadOnlyList<string> IncomeMonthOptions()
    {
        IncomeReport report = _workspace.Income(new IncomeReportRequest(
            Filters.EffectiveIncomeLookbackMonths,
            Filters.RegularIncome,
            CurrentIncomeAdjustments));
        return report.Analysis.Period.CurrentMonths
            .Reverse()
            .Select(month => month.ToString())
            .ToArray();
    }

    private IReadOnlyList<string> YearOverYearPresetCategoryOptions()
        => _workspace.YearOverYear(new YearOverYearReportRequest(
            PresetSetKey: Filters.YearOverYearSet)).PresetCategories;

    private IReadOnlyList<string> YearOverYearEntityOptions(YearOverYearDimension dimension)
    {
        YearOverYearReport report = _workspace.YearOverYear();
        return dimension == YearOverYearDimension.Category ? report.Categories : report.Groups;
    }
    private void SetYearOverYearView(string value)
    {
        if (string.Equals(value, "single_category", StringComparison.Ordinal))
        {
            Presentation.SetYearOverYearViewMode(YearOverYearViewMode.SingleCategory);
        }
        else if (string.Equals(value, "single_group", StringComparison.Ordinal))
        {
            Presentation.SetYearOverYearViewMode(YearOverYearViewMode.SingleGroup);
        }
        else
        {
            Filters = Filters with { YearOverYearSet = ValidateFilterSet("year_over_year", value) };
            Presentation.SetYearOverYearViewMode(YearOverYearViewMode.Preset);
        }

        RebuildReport();
    }

    private decimal ConfiguredSpendingExpenseLimit()
    {
        DashboardPageDefinition? spending = Definition.Pages.FirstOrDefault(page => page.Id == DashboardPageId.Spending);
        DashboardControlDefinition? control = spending?.Controls.FirstOrDefault(candidate => candidate.Id == "expense_limit");
        return control?.DefaultValue is { } value
            ? decimal.Parse(value, CultureInfo.InvariantCulture)
            : _workspace.DefaultSpendingAdjustments().ExpenseLimit;
    }

    private decimal ConfiguredMerchantExpenseLimit()
    {
        DashboardPageDefinition? merchants = Definition.Pages.FirstOrDefault(page => page.Id == DashboardPageId.Merchants);
        DashboardControlDefinition? control = merchants?.Controls.FirstOrDefault(candidate => candidate.Id == "expense_limit");
        return control?.DefaultValue is { } value
            ? decimal.Parse(value, CultureInfo.InvariantCulture)
            : _workspace.DefaultSpendingAdjustments().ExpenseLimit;
    }

    private decimal ConfiguredBudgetExpenseLimit()
    {
        DashboardPageDefinition? budget = Definition.Pages.FirstOrDefault(page => page.Id == DashboardPageId.Budget);
        DashboardControlDefinition? control = budget?.Controls.FirstOrDefault(candidate => candidate.Id == "expense_limit");
        return control?.DefaultValue is { } value
            ? decimal.Parse(value, CultureInfo.InvariantCulture)
            : _workspace.DefaultSpendingAdjustments().ExpenseLimit;
    }

    private void RebuildReport()
    {
        if (_initializing)
            return;
        Report = BuildReport();
        NormalizeIncomePresentation();
        NormalizeSpendingPresentation();
        NormalizeYearOverYearPresentation();
        NormalizeSubscriptionsPresentation();
        NormalizeMerchantsPresentation();
        NormalizeBudgetPresentation();
        NormalizeFinancialIndependencePresentation();
        NormalizeDataHealthPresentation();
    }

    private DashboardReport BuildReport()
    {
        YearMonth? incomeMonth = YearMonth.TryParse(Presentation.IncomeSavings.DetailMonth, out YearMonth selectedIncomeMonth)
            ? selectedIncomeMonth : null;
        YearMonth? spendingMonth = YearMonth.TryParse(Presentation.Spending.DetailMonth, out YearMonth selectedSpendingMonth)
            ? selectedSpendingMonth : null;
        YearMonth? merchantMonth = YearMonth.TryParse(Presentation.Merchants.DetailMonth, out YearMonth selectedMerchantMonth)
            ? selectedMerchantMonth : null;
        YearOverYearPresentationState yearOverYear = Presentation.YearOverYear;
        YearOverYearReportRequest yearOverYearRequest = yearOverYear.ViewMode switch
        {
            YearOverYearViewMode.SingleCategory => new(
                YearOverYearSelection.Category, Filters.YearOverYearSet, Entity: yearOverYear.SingleCategory),
            YearOverYearViewMode.SingleGroup => new(
                YearOverYearSelection.Group, Filters.YearOverYearSet, Entity: yearOverYear.SingleGroup),
            _ => new(YearOverYearSelection.Preset, Filters.YearOverYearSet, yearOverYear.PresetCategories)
        };
        IReadOnlyList<DashboardPageReport> pages =
        [
            HomeDashboardReport.Build(_workspace.Home(new HomeReportRequest(
                Filters.HomeTimeFrame, Filters.LookbackMonths, Filters.RegularIncome))),
            IncomeSavingsDashboardReport.Build(_workspace.Income(new IncomeReportRequest(
                Filters.EffectiveIncomeLookbackMonths, Filters.RegularIncome,
                CurrentIncomeAdjustments, incomeMonth)), Filters.EffectiveIncomeLookbackMonths),
            SpendingDashboardReport.Build(_workspace.Spending(new SpendingReportRequest(
                Filters.SpendingSet, Filters.LookbackMonths, Filters.SpendingComparison,
                Filters.SpendingBreakdown, CurrentSpendingAdjustments,
                Presentation.Spending.SelectedEntity(Filters.SpendingBreakdown), spendingMonth)),
                Filters.LookbackMonths, Filters.SpendingComparison,
                _workspace.ReportChoices.TransactionSetLabels),
            YearOverYearDashboardReport.Build(_workspace.YearOverYear(yearOverYearRequest)),
            SubscriptionsDashboardReport.Build(_workspace.Subscriptions(new SubscriptionsReportRequest(
                Filters.SubscriptionCategories, Filters.SubscriptionDiscoveryExclusions,
                Filters.SubscriptionMinimumConfidence > 0 ? Filters.SubscriptionMinimumConfidence : null,
                Presentation.Subscriptions.SelectedMerchant))),
            MerchantsDashboardReport.Build(_workspace.Merchants(new MerchantsReportRequest(
                Filters.MerchantSet ?? Filters.SpendingSet, Filters.EffectiveMerchantLookbackMonths,
                Filters.MerchantComparison, CurrentMerchantAdjustments,
                Presentation.Merchants.SelectedMerchant, merchantMonth)), Filters.MerchantComparison,
                _workspace.ReportChoices.TransactionSetLabels),
            BudgetDashboardMapper.Build(_workspace.Budget(new BudgetReportRequest(
                CurrentBudgetRequest, Presentation.Budget.SelectedGroup,
                Presentation.Budget.TransactionCategory == "all" ? null : Presentation.Budget.TransactionCategory)),
                _workspace.AsOfDate, _workspace.HasVisibleTransactions),
            TransactionsDashboardReport.Build(_workspace.Transactions(CurrentTransactionExplorer)),
            FinancialIndependenceDashboardMapper.Build(_workspace.FinancialIndependence(
                new FinancialIndependenceReportRequest(
                    CurrentFinancialIndependenceSource, CurrentFinancialIndependenceScenario)),
                _workspace.AsOfDate),
            DataHealthDashboardMapper.Build(_workspace.DataHealth(new DataHealthReportRequest(
                CurrentDataHealthOptions, Presentation.DataHealth.SelectedCheckId)))
        ];
        return new DashboardReport(pages.ToDictionary(page => page.PageId));
    }

    private void NormalizeIncomePresentation()
    {
        IncomeSavingsPageView? income = Report.Page(DashboardPageId.IncomeSavings).IncomeSavingsView;
        if (income is null)
            return;

        bool needsRebuild = false;
        if (income.DetailMonths.Count > 0
            && !income.DetailMonths.Contains(Presentation.IncomeSavings.DetailMonth, StringComparer.Ordinal))
        {
            Presentation.SetIncomeDetailMonth(income.DetailMonths[0]);
            needsRebuild = true;
        }

        if (Presentation.IncomeSavings.DetailTab is not ("Included" or "Excluded"))
            Presentation.SetIncomeDetailTab("Included");

        if (needsRebuild)
            Report = BuildReport();
    }

    private void NormalizeSpendingPresentation()
    {
        DashboardWidgetReport overview = Report.Page(DashboardPageId.Spending).Widgets["spending.overview"];
        string? selected = Presentation.Spending.SelectedEntity(Filters.SpendingBreakdown);
        bool selectionExists = selected is not null
            && overview.Rows.Any(row => string.Equals(row.Values[0], selected, StringComparison.Ordinal));
        bool reportNeedsRebuild = false;

        if (selected is not null && !selectionExists)
            Presentation.SetSpendingSelectedEntity(Filters.SpendingBreakdown, null);

        IReadOnlyList<string> months = SpendingMonthOptions();
        if (!months.Contains(Presentation.Spending.DetailMonth, StringComparer.Ordinal))
        {
            Presentation.SetSpendingDetailMonth("all");
            reportNeedsRebuild = true;
        }

        IReadOnlyList<string> tabs = Filters.SpendingBreakdown == SpendingBreakdown.Group
            ? ["Categories", "Merchants", "Transactions"]
            : ["Merchants", "Transactions"];
        if (!tabs.Contains(Presentation.Spending.DetailTab, StringComparer.Ordinal))
            Presentation.SetSpendingDetailTab(tabs[0]);

        if (reportNeedsRebuild)
            Report = BuildReport();
    }

    private void NormalizeYearOverYearPresentation()
    {
        YearOverYearPageView? yearOverYear = Report.Page(DashboardPageId.YearOverYear).YearOverYearView;
        if (yearOverYear is null)
            return;

        bool needsRebuild = false;
        if (Presentation.YearOverYear.ViewMode == YearOverYearViewMode.Preset)
        {
            IReadOnlyList<string> available = yearOverYear.PresetCategories;
            if (!string.Equals(Presentation.YearOverYear.PresetSetKey, Filters.YearOverYearSet, StringComparison.Ordinal))
            {
                Presentation.SetYearOverYearPresetCategories(Filters.YearOverYearSet, available.Take(8));
                needsRebuild = true;
            }
            else
            {
                string[] retained = Presentation.YearOverYear.PresetCategories
                    .Where(available.Contains)
                    .ToArray();
                if (retained.Length != Presentation.YearOverYear.PresetCategories.Count)
                {
                    Presentation.SetYearOverYearPresetCategories(Filters.YearOverYearSet, retained);
                    needsRebuild = true;
                }
            }
        }
        else
        {
            YearOverYearDimension dimension = Presentation.YearOverYear.ViewMode == YearOverYearViewMode.SingleCategory
                ? YearOverYearDimension.Category
                : YearOverYearDimension.Group;
            IReadOnlyList<string> values = dimension == YearOverYearDimension.Category
                ? yearOverYear.Categories
                : yearOverYear.Groups;
            string? selected = dimension == YearOverYearDimension.Category
                ? Presentation.YearOverYear.SingleCategory
                : Presentation.YearOverYear.SingleGroup;
            if (!values.Contains(selected, StringComparer.Ordinal))
            {
                string? preferred = PreferredYearOverYearEntity(values, dimension);
                if (dimension == YearOverYearDimension.Category)
                    Presentation.SetYearOverYearSingleCategory(preferred);
                else
                    Presentation.SetYearOverYearSingleGroup(preferred);
                needsRebuild = true;
            }
        }

        if (needsRebuild)
            Report = BuildReport();
    }

    private void NormalizeSubscriptionsPresentation()
    {
        SubscriptionsPageView? subscriptions = Report.Page(DashboardPageId.Subscriptions).SubscriptionsView;
        if (subscriptions is null)
            return;

        bool needsRebuild = false;
        string? selected = Presentation.Subscriptions.SelectedMerchant;
        if (selected is not null
            && !subscriptions.Analysis.Inventory
                .Concat(subscriptions.Analysis.Candidates)
                .Concat(subscriptions.Analysis.Inactive)
                .Any(entry => string.Equals(entry.Merchant, selected, StringComparison.Ordinal)))
        {
            Presentation.SetSubscriptionSelectedMerchant(subscriptions.SelectedMerchant);
            needsRebuild = true;
        }

        IReadOnlyList<string> historyRanges = ["3m", "6m", "12m", "24m", "all"];
        if (!historyRanges.Contains(Presentation.Subscriptions.HistoryLookback, StringComparer.Ordinal))
        {
            Presentation.SetSubscriptionHistoryLookback("12m");
            needsRebuild = true;
        }

        if (Presentation.Subscriptions.TimelineScope is not ("active_recent" or "all"))
        {
            Presentation.SetSubscriptionTimelineScope("active_recent");
            needsRebuild = true;
        }

        if (needsRebuild)
            Report = BuildReport();
    }

    private void NormalizeMerchantsPresentation()
    {
        MerchantsPageView? merchants = Report.Page(DashboardPageId.Merchants).MerchantsView;
        if (merchants is null)
            return;

        bool needsRebuild = false;
        if (Presentation.Merchants.SelectedMerchant is not null
            && !merchants.Analysis.Overview.Any(entry => string.Equals(
                entry.Merchant,
                Presentation.Merchants.SelectedMerchant,
                StringComparison.Ordinal)))
        {
            Presentation.SetMerchantSelectedMerchant(merchants.SelectedMerchant);
            needsRebuild = true;
        }

        if (!MerchantMonthOptions().Contains(Presentation.Merchants.DetailMonth, StringComparer.Ordinal))
        {
            Presentation.SetMerchantDetailMonth("all");
            needsRebuild = true;
        }

        if (Presentation.Merchants.DetailTab is not ("Breakdown" or "Descriptions" or "Transactions"))
            Presentation.SetMerchantDetailTab("Breakdown");

        if (needsRebuild)
            Report = BuildReport();
    }

    private void NormalizeBudgetPresentation()
    {
        BudgetPageView? budget = Report.Page(DashboardPageId.Budget).BudgetView;
        if (budget is null)
            return;

        bool needsRebuild = false;
        if (!budget.Analysis.Groups.Any(entry => string.Equals(
                entry.Entity,
                Presentation.Budget.SelectedGroup,
                StringComparison.Ordinal)))
        {
            Presentation.SetBudgetSelectedGroup(budget.SelectedGroup);
            needsRebuild = true;
        }

        BudgetGroupDetail? detail = budget.SelectedGroup is not null
            && budget.Analysis.GroupDetails.TryGetValue(budget.SelectedGroup, out BudgetGroupDetail? value)
            ? value
            : null;
        if (Presentation.Budget.TransactionCategory != "all"
            && (detail is null || !detail.Categories.Any(entry => string.Equals(
                entry.Entity,
                Presentation.Budget.TransactionCategory,
                StringComparison.Ordinal))))
        {
            Presentation.SetBudgetTransactionCategory("all");
            needsRebuild = true;
        }

        if (needsRebuild)
            Report = BuildReport();
    }

    private void NormalizeFinancialIndependencePresentation()
    {
        if (Presentation.FinancialIndependence.SourceDetailsTab is not ("Accounts" or "Spending" or "Transactions"))
            Presentation.SetFinancialIndependenceSourceDetailsTab("Accounts");
    }

    private void NormalizeDataHealthPresentation()
    {
        DataHealthPageView? health = Report.Page(DashboardPageId.DataHealth).DataHealthView;
        if (health is null || health.Analysis.Checks.Count == 0)
            return;

        if (health.Analysis.Checks.Any(check => string.Equals(
                check.Id,
                Presentation.DataHealth.SelectedCheckId,
                StringComparison.Ordinal)))
        {
            return;
        }

        DataHealthCheckView preferred = health.Analysis.Checks.FirstOrDefault(check => check.FindingCount > 0)
            ?? health.Analysis.Checks[0];
        Presentation.SetDataHealthSelectedCheck(preferred.Id);
        Report = BuildReport();
    }

    private void SyncDataHealthPresentation(string source)
    {
        if (Filters.DataHealth is not { } options)
            return;

        switch (source)
        {
            case "health_stale_days":
                Presentation.SetDataHealthStaleThreshold(options.StaleAccountDays);
                break;
            case "health_include_inactive":
                Presentation.SetDataHealthIncludeInactive(options.IncludeInactive);
                break;
        }
    }

    private static string? PreferredYearOverYearEntity(
        IReadOnlyList<string> values,
        YearOverYearDimension dimension)
    {
        if (values.Count == 0)
            return null;
        if (dimension == YearOverYearDimension.Group
            && values.Contains("Bills", StringComparer.Ordinal))
        {
            return "Bills";
        }

        string[] priorities = ["electric", "electricity", "utilities", "water", "natural gas", "internet", "phone"];
        foreach (string priority in priorities)
        {
            string? match = values.FirstOrDefault(value => value.Contains(priority, StringComparison.OrdinalIgnoreCase));
            if (match is not null)
                return match;
        }

        return values[0];
    }

    private DashboardControlDefinition Control(DashboardPageId pageId, string controlId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(controlId);
        DashboardPageDefinition? page = Definition.Pages.FirstOrDefault(candidate => candidate.Id == pageId);
        DashboardControlDefinition? control = page?.Controls.FirstOrDefault(candidate => string.Equals(candidate.Id, controlId, StringComparison.Ordinal));
        return control ?? throw new ArgumentException($"Dashboard control '{pageId}.{controlId}' is not configured.", nameof(controlId));
    }

    private string FilterValue(string source)
        => source switch
        {
            "lookback" => Filters.LookbackMonths.ToString(CultureInfo.InvariantCulture),
            "home_time_frame" => Filters.HomeTimeFrame switch
            {
                HomePeriod.ThreeMonths => "3m",
                HomePeriod.SixMonths => "6m",
                HomePeriod.OneYear => "1y",
                HomePeriod.TwoYears => "2y",
                HomePeriod.FiveYears => "5y",
                HomePeriod.All => "all",
                _ => throw new ArgumentOutOfRangeException()
            },
            "spending" => Filters.SpendingSet,
            "spending_comparison" => Filters.SpendingComparison == SpendingComparison.PreviousPeriod ? "previous_period" : "last_year",
            "spending_breakdown" => Filters.SpendingBreakdown == SpendingBreakdown.Group ? "group" : "category",
            "spending_exclude_large_expenses" => CurrentSpendingAdjustments.ExcludeLargeExpenses.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            "spending_expense_limit" => CurrentSpendingAdjustments.ExpenseLimit.ToString(CultureInfo.InvariantCulture),
            "year_over_year" => Filters.YearOverYearSet,
            "year_over_year_view" => Presentation.YearOverYear.ViewMode switch
            {
                YearOverYearViewMode.Preset => Filters.YearOverYearSet,
                YearOverYearViewMode.SingleCategory => "single_category",
                YearOverYearViewMode.SingleGroup => "single_group",
                _ => throw new ArgumentOutOfRangeException()
            },
            "year_over_year_single_category" => Presentation.YearOverYear.SingleCategory ?? string.Empty,
            "year_over_year_single_group" => Presentation.YearOverYear.SingleGroup ?? string.Empty,
            "income_view" => Filters.RegularIncome ? "regular" : "actual",
            "income_lookback" => Filters.EffectiveIncomeLookbackMonths.ToString(CultureInfo.InvariantCulture),
            "income_calculation" => Filters.RegularIncome ? "regular" : "actual",
            "income_exclude_large_income" => CurrentIncomeAdjustments.ExcludeLargeIncome.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            "income_income_limit" => CurrentIncomeAdjustments.IncomeLimit.ToString(CultureInfo.InvariantCulture),
            "income_exclude_large_expenses" => CurrentIncomeAdjustments.ExcludeLargeExpenses.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            "income_expense_limit" => CurrentIncomeAdjustments.ExpenseLimit.ToString(CultureInfo.InvariantCulture),
            "income_target_rate" => CurrentIncomeAdjustments.TargetRate.ToString(CultureInfo.InvariantCulture),
            "subscription_minimum_confidence" => Filters.SubscriptionMinimumConfidence.ToString(CultureInfo.InvariantCulture),
            "merchant_lookback" => Filters.EffectiveMerchantLookbackMonths.ToString(CultureInfo.InvariantCulture),
            "merchant_spending" => Filters.MerchantSet ?? Filters.SpendingSet,
            "merchant_comparison" => Filters.MerchantComparison == SpendingComparison.PreviousPeriod ? "previous_period" : "last_year",
            "merchant_exclude_large_expenses" => CurrentMerchantAdjustments.ExcludeLargeExpenses.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            "merchant_expense_limit" => CurrentMerchantAdjustments.ExpenseLimit.ToString(CultureInfo.InvariantCulture),
            "transactions_lookback" => FormatTransactionLookback(CurrentTransactionExplorer.LookbackDays),
            "transactions_type" => FormatTransactionType(CurrentTransactionExplorer.Type),
            "transactions_focus" => FormatTransactionFocus(CurrentTransactionExplorer.Focus),
            "transactions_search" => CurrentTransactionExplorer.Search,
            "transactions_minimum_amount" => CurrentTransactionExplorer.MinimumMagnitude.ToString(CultureInfo.InvariantCulture),
            "transactions_maximum_amount" => (CurrentTransactionExplorer.MaximumMagnitude ?? 0m).ToString(CultureInfo.InvariantCulture),
            "transactions_largest_count" => CurrentTransactionExplorer.LargestCount.ToString(CultureInfo.InvariantCulture),
            "transactions_breakdown" => FormatTransactionBreakdown(CurrentTransactionExplorer.Breakdown),
            "budget_month" => CurrentBudgetRequest.SelectedMonth.ToString(),
            "budget_exclude_large_expenses" => CurrentBudgetRequest.Adjustments.ExcludeLargeExpenses.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            "budget_expense_limit" => CurrentBudgetRequest.Adjustments.ExpenseLimit.ToString(CultureInfo.InvariantCulture),
            "fi_assets" => CurrentFinancialIndependenceScenario.Assets.ToString(CultureInfo.InvariantCulture),
            "fi_spending" => CurrentFinancialIndependenceScenario.AnnualSpending.ToString(CultureInfo.InvariantCulture),
            "fi_income" => CurrentFinancialIndependenceScenario.AnnualIncome.ToString(CultureInfo.InvariantCulture),
            "fi_return_rate" => CurrentFinancialIndependenceScenario.ExpectedReturnRate.ToString(CultureInfo.InvariantCulture),
            "fi_withdrawal_rate" => CurrentFinancialIndependenceScenario.WithdrawalRate.ToString(CultureInfo.InvariantCulture),
            "fi_years" => CurrentFinancialIndependenceScenario.ProjectionYears.ToString(CultureInfo.InvariantCulture),
            "fi_spending_lookback" => CurrentFinancialIndependenceSource.SpendingLookbackMonths.ToString(CultureInfo.InvariantCulture),
            "fi_exclude_large_expenses" => CurrentFinancialIndependenceSource.Adjustments.ExcludeLargeExpenses.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            "fi_expense_limit" => CurrentFinancialIndependenceSource.Adjustments.ExpenseLimit.ToString(CultureInfo.InvariantCulture),
            "health_stale_days" => CurrentDataHealthOptions.StaleAccountDays.ToString(CultureInfo.InvariantCulture),
            "health_duplicate_days" => CurrentDataHealthOptions.DuplicateDays.ToString(CultureInfo.InvariantCulture),
            "health_duplicate_minimum" => CurrentDataHealthOptions.DuplicateMinimum.ToString(CultureInfo.InvariantCulture),
            "health_same_account" => CurrentDataHealthOptions.DuplicateRequireSameAccount.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            "health_same_category" => CurrentDataHealthOptions.DuplicateRequireSameCategory.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            "health_same_description" => CurrentDataHealthOptions.DuplicateRequireSameDescription.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            "health_include_inactive" => CurrentDataHealthOptions.IncludeInactive.ToString(CultureInfo.InvariantCulture).ToLowerInvariant(),
            _ => throw new ArgumentException($"Unsupported report filter source '{source}'.", nameof(source))
        };

    private decimal ConfiguredNumberDefault(DashboardPageId pageId, string controlId)
    {
        DashboardControlDefinition control = Control(pageId, controlId);
        return decimal.Parse(control.DefaultValue!, CultureInfo.InvariantCulture);
    }
}
