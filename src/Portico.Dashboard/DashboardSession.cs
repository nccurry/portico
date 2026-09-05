using Portico.Finance;

using System.Globalization;

namespace Portico.Dashboard;

/// <summary>Owns the small mutable view state that connects configured controls to rebuilt reports.</summary>
public sealed class DashboardSession
{
    private readonly PortfolioSnapshot _snapshot;
    private readonly FinanceSettings _settings;
    private readonly DateOnly? _asOfDate;

    /// <summary>Creates a session with the first visible configured page and default filter values.</summary>
    public DashboardSession(
        PortfolioSnapshot snapshot,
        FinanceSettings settings,
        DashboardDefinition definition,
        DateOnly? asOfDate = null)
    {
        ArgumentNullException.ThrowIfNull(snapshot);
        ArgumentNullException.ThrowIfNull(settings);
        ArgumentNullException.ThrowIfNull(definition);

        _snapshot = snapshot;
        _settings = settings;
        _asOfDate = asOfDate;
        Definition = definition;
        CurrentPage = definition.FirstVisiblePage().Id;
        Filters = DashboardFilters.From(settings);
        Presentation = new DashboardPresentationState();
        Presentation.InitializeIncomeSavings(settings);
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
        if (string.Equals(source, "year_over_year_view", StringComparison.Ordinal))
        {
            SetYearOverYearView(value);
            return;
        }

        DashboardFilters updated = ApplyFilter(Filters, source, value);
        if (updated == Filters)
            return;

        Filters = updated;
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
            || decimal.Remainder(value - control.Minimum.Value, control.Step.Value) != 0m)
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
                Presentation.ResetFinancialIndependence(ConfiguredNumberDefault(
                    DashboardPageId.FinancialIndependence,
                    "target_amount"));
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
                SetIncomeSavingsAdjustments(IncomeSavingsAdjustments.Default(_settings, Filters.RegularIncome));
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
            DashboardControlOptionSource.SpendingGroups => SpendingAdjustmentOptions(transaction => transaction.Group),
            DashboardControlOptionSource.SpendingCategories => SpendingAdjustmentOptions(transaction => transaction.Category),
            DashboardControlOptionSource.SpendingMonths => SpendingMonthOptions(),
            DashboardControlOptionSource.IncomeIncomeCategories => IncomeCategoryOptions(TransactionKind.Income),
            DashboardControlOptionSource.IncomeExpenseGroups => IncomeExpenseGroupOptions(),
            DashboardControlOptionSource.IncomeExpenseCategories => IncomeCategoryOptions(TransactionKind.Expense),
            DashboardControlOptionSource.IncomeMonths => IncomeMonthOptions(),
            DashboardControlOptionSource.YearOverYearPresetCategories => YearOverYearPresetCategoryOptions(),
            DashboardControlOptionSource.YearOverYearCategories => YearOverYearEntityOptions(YearOverYearDimension.Category),
            DashboardControlOptionSource.YearOverYearGroups => YearOverYearEntityOptions(YearOverYearDimension.Group),
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
            _ => Presentation.ValuesFor(mapping.Source)
        };
    }

    /// <summary>Gets a source-shaped label for the active named spending view.</summary>
    public string SpendingSetLabel(string key) => _settings.TransactionSet(key).Label;

    /// <summary>Gets the source-shaped label for one configured Year over year preset.</summary>
    public string YearOverYearSetLabel(string key) => _settings.TransactionSet(key).Label;

    /// <summary>Gets the configured defaults for the selected Income calculation view.</summary>
    public IncomeSavingsAdjustments IncomeSavingsDefaultAdjustments(bool regular)
        => IncomeSavingsAdjustments.Default(_settings, regular);

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

    /// <summary>Sets whether one Year over year card's details are visible.</summary>
    public void SetYearOverYearDetailsExpanded(string entity, bool expanded)
        => Presentation.SetYearOverYearDetailsExpanded(entity, expanded);

    private int ParseLookback(string value)
    {
        if (!int.TryParse(value, out int months) || !_settings.Lookback.Months.Contains(months))
            throw new ArgumentException($"Lookback '{value}' is not configured.", nameof(value));
        return months;
    }

    private string ValidateFilterSet(string filterSet, string value)
    {
        FilterSetDefinition definition = _settings.FilterSet(filterSet);
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

    private DashboardFilters ApplyFilter(DashboardFilters filters, string source, string value)
        => source switch
        {
            "lookback" => filters with { LookbackMonths = ParseLookback(value) },
            "income_lookback" => filters with { IncomeLookbackMonths = ParseLookback(value) },
            "home_time_frame" => filters with { HomeTimeFrame = HomeReportRange.Parse(value) },
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
                SetControlNumber(
                    pageId,
                    control.Id,
                    decimal.Parse(control.DefaultValue!, CultureInfo.InvariantCulture));
                break;
            case DashboardControlKind.Toggle:
                SetControlToggle(pageId, control.Id, bool.Parse(control.DefaultValue!));
                break;
            case DashboardControlKind.ActionReset:
            case DashboardControlKind.Popover:
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
            default:
                throw new ArgumentException($"Dashboard control source '{mapping.Source}' does not accept one choice value.", nameof(mapping));
        }
    }

    private SpendingAdjustments CurrentSpendingAdjustments
        => Filters.SpendingAdjustments ?? SpendingAdjustments.Default(ConfiguredSpendingExpenseLimit());

    private IncomeSavingsAdjustments CurrentIncomeAdjustments
        => Presentation.IncomeSavingsAdjustments(Filters.RegularIncome);

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

    private IReadOnlyList<string> SpendingAdjustmentOptions(Func<FinancialTransaction, string> selector)
        => _snapshot.Transactions
            .Where(transaction => !transaction.IsHidden && transaction.Kind == TransactionKind.Expense)
            .Select(selector)
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value.Trim())
            .Distinct(StringComparer.Ordinal)
            .OrderBy(value => value, StringComparer.Ordinal)
            .ToArray();

    private IReadOnlyList<string> SpendingMonthOptions()
    {
        IReadOnlyList<YearMonth> months = SpendingAnalysisCalculator.CurrentMonths(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden && transaction.Kind == TransactionKind.Expense),
            Filters.LookbackMonths);
        return ["all", .. months.Reverse().Select(month => month.ToString())];
    }

    private IReadOnlyList<string> IncomeCategoryOptions(TransactionKind kind)
        => IncomeSavingsAnalysisCalculator.Categories(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden),
            kind);

    private IReadOnlyList<string> IncomeExpenseGroupOptions()
        => IncomeSavingsAnalysisCalculator.ExpenseGroups(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden));

    private IReadOnlyList<string> IncomeMonthOptions()
    {
        IncomeSavingsAnalysisResult analysis = IncomeSavingsAnalysisCalculator.Build(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden),
            Filters.EffectiveIncomeLookbackMonths,
            CurrentIncomeAdjustments);
        return analysis.Period.CurrentMonths
            .Reverse()
            .Select(month => month.ToString())
            .ToArray();
    }

    private IReadOnlyList<string> YearOverYearPresetCategoryOptions()
        => YearOverYearAnalysisCalculator.PresetCategories(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden),
            _settings,
            Filters.YearOverYearSet);

    private IReadOnlyList<string> YearOverYearEntityOptions(YearOverYearDimension dimension)
        => YearOverYearAnalysisCalculator.Entities(
            _snapshot.Transactions.Where(transaction => !transaction.IsHidden),
            dimension);

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
            : _settings.Thresholds.Expense;
    }

    private void RebuildReport()
    {
        Report = DashboardReportBuilder.Build(_snapshot, _settings, Filters, Presentation, _asOfDate);
        NormalizeIncomePresentation();
        NormalizeSpendingPresentation();
        NormalizeYearOverYearPresentation();
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
            Report = DashboardReportBuilder.Build(_snapshot, _settings, Filters, Presentation, _asOfDate);
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
            Report = DashboardReportBuilder.Build(_snapshot, _settings, Filters, Presentation, _asOfDate);
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
            Report = DashboardReportBuilder.Build(_snapshot, _settings, Filters, Presentation, _asOfDate);
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
            "home_time_frame" => HomeReportRange.Format(Filters.HomeTimeFrame),
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
            _ => throw new ArgumentException($"Unsupported report filter source '{source}'.", nameof(source))
        };

    private decimal ConfiguredNumberDefault(DashboardPageId pageId, string controlId)
    {
        DashboardControlDefinition control = Control(pageId, controlId);
        return decimal.Parse(control.DefaultValue!, CultureInfo.InvariantCulture);
    }
}
