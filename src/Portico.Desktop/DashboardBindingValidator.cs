using Portico.Application;

namespace Portico.Desktop;

/// <summary>Checks dashboard choices against the opened workspace's supported report choices.</summary>
public static class DashboardBindingValidator
{
    public static IReadOnlyList<PorticoProblem> Validate(DashboardDefinition definition, ReportChoices choices)
    {
        ArgumentNullException.ThrowIfNull(definition);
        ArgumentNullException.ThrowIfNull(choices);
        var problems = new List<PorticoProblem>();

        for (int pageIndex = 0; pageIndex < definition.Pages.Count; pageIndex++)
        {
            DashboardPageDefinition page = definition.Pages[pageIndex];
            for (int filterIndex = 0; filterIndex < page.Filters.Count; filterIndex++)
            {
                DashboardFilterDefinition filter = page.Filters[filterIndex];
                for (int optionIndex = 0; optionIndex < filter.Options.Count; optionIndex++)
                {
                    if (!IsSupported(filter.Source, filter.Options[optionIndex], choices))
                        problems.Add(Invalid($"dashboard.pages[{pageIndex}].filters[{filterIndex}].options[{optionIndex}]"));
                }
            }

            for (int controlIndex = 0; controlIndex < page.Controls.Count; controlIndex++)
            {
                DashboardControlDefinition control = page.Controls[controlIndex];
                DashboardControlMapping mapping = DashboardControlMappings.Resolve(page.Id, control.Id);
                if (mapping.Behavior != DashboardControlBehavior.ReportInput
                    || control.OptionSource != DashboardControlOptionSource.Static)
                    continue;

                for (int optionIndex = 0; optionIndex < control.ChoiceOptions.Count; optionIndex++)
                {
                    if (!IsSupported(mapping.ReportFilterSource!, control.ChoiceOptions[optionIndex], choices))
                        problems.Add(Invalid($"dashboard.pages[{pageIndex}].controls[{controlIndex}].options[{optionIndex}]"));
                }
            }
        }

        return problems;
    }

    private static PorticoProblem Invalid(string field)
        => new("dashboard.unsupported-choice", "The dashboard has a choice that is not available in this workspace.", field);

    private static bool IsSupported(string source, string value, ReportChoices choices)
        => source switch
        {
            "lookback" or "income_lookback" or "merchant_lookback"
                => int.TryParse(value, out int months) && choices.LookbackMonths.Contains(months),
            "spending" or "merchant_spending" => FilterSetHas(choices, "spending", value),
            "year_over_year" => FilterSetHas(choices, "year_over_year", value),
            "year_over_year_view" => value is "single_category" or "single_group"
                || FilterSetHas(choices, "year_over_year", value),
            "income_view" or "income_calculation" => value is "regular" or "actual",
            "home_time_frame" => HomeTimeFrameOptions.TryParse(value, out _),
            "spending_comparison" or "merchant_comparison"
                => DashboardControlMappings.TryParseSpendingComparison(value, out _),
            "spending_breakdown" => DashboardControlMappings.TryParseSpendingBreakdown(value, out _),
            "transactions_lookback" => value is "3m" or "6m" or "1y" or "2y" or "all",
            "transactions_type" => value is "all" or "expenses" or "income" or "transfers",
            "transactions_focus" => value is "all" or "largest" or "one_off" or "unusual" or "reversals",
            "transactions_breakdown" => value is "group" or "category" or "merchant" or "account" or "type",
            "fi_spending_lookback" => int.TryParse(value, out int fiMonths) && fiMonths is 6 or 12 or 24 or 36,
            _ => false
        };

    private static bool FilterSetHas(ReportChoices choices, string key, string value)
        => choices.FilterSets.TryGetValue(key, out ReportFilterChoices? filter)
            && filter.Options.Contains(value, StringComparer.Ordinal);
}
