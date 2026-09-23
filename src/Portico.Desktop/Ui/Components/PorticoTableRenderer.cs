using Portico.Desktop.Ui;
using Roci.Core;
using Roci.Input;
using Roci.Ui;

namespace Portico.Desktop.Ui.Components;

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

    /// <summary>Builds a report table whose bounded rows can select a related detail view.</summary>
    public static void BuildSelectable(
        UiBuilder ui,
        string id,
        IReadOnlyList<string> columns,
        IReadOnlyList<ReportTableRow> rows,
        Func<string?, string> display,
        int? selectedRow,
        Action<int> selectRow,
        int maximumRows = 30)
    {
        ArgumentNullException.ThrowIfNull(ui);
        ArgumentException.ThrowIfNullOrWhiteSpace(id);
        ArgumentNullException.ThrowIfNull(columns);
        ArgumentNullException.ThrowIfNull(rows);
        ArgumentNullException.ThrowIfNull(display);
        ArgumentNullException.ThrowIfNull(selectRow);
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(maximumRows);

        ui.VStack(PorticoSkin.TableGap, $"Table:{id}")
            .SetFlexGrow(1f)
            .SetScrollable(vertical: true, horizontal: false);
        BuildRow(ui, $"TableHeader:{id}", columns, true, null, display);
        for (int index = 0; index < Math.Min(rows.Count, maximumRows); index++)
        {
            int capturedIndex = index;
            ReportTableRow row = rows[index];
            string name = $"TableRowSelection:{id}:{index}";
            ui.Button(name)
                .SetWidth(UiLength.ParentPercent(100))
                .SetPadding(PorticoSkin.TableRowHorizontalPadding, PorticoSkin.TableRowVerticalPadding)
                .SetCornerRadius(PorticoSkin.TableCornerRadius)
                .SetStyle(selectedRow == index ? PorticoSkin.SelectedActionStyle : PorticoSkin.QuietActionStyle)
                .SetCommandSurface(pointer: true, focus: true)
                .SetOnCommand(
                    _ =>
                    {
                        selectRow(capturedIndex);
                        return true;
                    },
                    (int)InputCommands.ClickLeft,
                    (int)InputCommands.Accept);
            ui.HStack(PorticoSkin.TableRowGap, $"{name}:Content")
                .SetFlexGrow(1f)
                .SetCrossAlign(CrossAlignment.Center);
            for (int columnIndex = 0; columnIndex < row.Values.Count; columnIndex++)
            {
                string value = row.Values[columnIndex];
                ui.Text(TrimCell(display(value)), $"{name}:Cell:{columnIndex}")
                    .SetFlexGrow(1f)
                    .SetTextStyle(PorticoSkin.HelperText.Overlay(PorticoSkin.ToneTextStyle(row.Tone)))
                .End();
            }
            ui.End();
            ui.EndButton();
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
            .SetWidth(UiLength.ParentPercent(100))
            .SetPadding(PorticoSkin.TableRowHorizontalPadding, PorticoSkin.TableRowVerticalPadding)
            .SetCornerRadius(PorticoSkin.TableCornerRadius)
            .SetCrossAlign(CrossAlignment.Center)
            .SetStyle(header ? PorticoSkin.MutedPanelStyle : PorticoSkin.TablePanelStyle);
        for (int columnIndex = 0; columnIndex < values.Count; columnIndex++)
        {
            string value = values[columnIndex];
            ui.Text(TrimCell(header ? value : display(value)), $"{name}:Cell:{columnIndex}")
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
