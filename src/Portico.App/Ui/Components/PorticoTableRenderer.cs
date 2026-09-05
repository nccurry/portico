using Portico.App.Ui;
using Portico.Dashboard;
using Roci.Core;
using Roci.Ui;

namespace Portico.App.Ui.Components;

/// <summary>Builds the compact report tables shared by configured and Home-specific views.</summary>
internal static class PorticoTableRenderer
{
    /// <summary>Builds a bounded, vertically scrollable table from typed report rows.</summary>
    public static void Build(
        UiBuilder ui,
        string id,
        IReadOnlyList<string> columns,
        IReadOnlyList<ReportTableRow> rows,
        Func<string?, string> display,
        int maximumRows = 30)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentException.ThrowIfNullOrWhiteSpace(id);
        ArgumentNullException.ThrowIfNull(columns);
        ArgumentNullException.ThrowIfNull(rows);
        ArgumentNullException.ThrowIfNull(display);
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(maximumRows);

        ui.VStack(PorticoSkin.TableGap, $"Table:{id}")
            .SetFlexGrow(1f)
            .SetScrollable(vertical: true, horizontal: false);
        BuildRow(ui, $"TableHeader:{id}", columns, true, null, display);
        for (int index = 0; index < Math.Min(rows.Count, maximumRows); index++)
        {
            ReportTableRow row = rows[index];
            BuildRow(ui, $"TableRow:{id}:{index}", row.Values, false, row.Tone, display);
        }

        ui.End();
    }

    private static void BuildRow(
        UiBuilder ui,
        string name,
        IReadOnlyList<string> values,
        bool header,
        string? tone,
        Func<string?, string> display)
    {
        ui.HStack(PorticoSkin.TableRowGap, name)
            .SetPadding(PorticoSkin.TableRowHorizontalPadding, PorticoSkin.TableRowVerticalPadding)
            .SetCornerRadius(PorticoSkin.TableCornerRadius)
            .SetCrossAlign(CrossAlignment.Center)
            .SetStyle(header ? PorticoSkin.MutedPanelStyle : PorticoSkin.TablePanelStyle);
        foreach (string value in values)
        {
            ui.Text(TrimCell(header ? value : display(value)), $"{name}:{value}")
                .SetFlexGrow(1f)
                .SetTextStyle(header
                    ? PorticoSkin.NavigationGroupLabelText
                    : PorticoSkin.HelperText.Overlay(PorticoSkin.ToneTextStyle(tone)))
                .SetFontStyle(header ? FontStyle.Bold : FontStyle.Regular)
            .End();
        }

        ui.End();
    }

    private static string TrimCell(string value)
        => value.Length <= 28 ? value : $"{value[..25]}...";
}
