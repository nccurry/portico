using Roci.Core;
using Roci.Ui;
using Roci.Ui.Charts;

namespace Portico.App.Ui;

/// <summary>Defines the shared visual language for the Portico desktop dashboard.</summary>
internal static class PorticoSkin
{
    internal const string RailPanelStyle = "portico-rail";
    internal const string MainPanelStyle = "portico-main";
    internal const string HeaderPanelStyle = "portico-header";
    internal const string RaisedPanelStyle = "portico-raised";
    internal const string MutedPanelStyle = "portico-muted";
    internal const string TablePanelStyle = "portico-table";
    internal const string NavigationGroupPanelStyle = "portico-navigation-group";
    internal const string PositivePanelStyle = "portico-positive";
    internal const string NegativePanelStyle = "portico-negative";
    internal const string NeutralPanelStyle = "portico-neutral";
    internal const string WarningPanelStyle = "portico-warning";
    internal const string LoadingPanelStyle = "portico-loading";
    internal const string HiddenPanelStyle = "portico-hidden";
    internal const string PrimaryActionStyle = "portico-primary";
    internal const string SecondaryActionStyle = "portico-secondary";
    internal const string QuietActionStyle = "portico-quiet";
    internal const string DangerActionStyle = "portico-danger";
    internal const string SelectedActionStyle = "portico-selected";
    internal const string NavigationActionStyle = "portico-navigation";
    internal const string SelectedNavigationActionStyle = "portico-navigation-selected";

    internal const float NavigationRailWidth = 232f;
    internal const float ShellGap = 0f;
    internal const float ShellPadding = 0f;
    internal const float MainPadding = 28f;
    internal const float PageGap = 20f;
    internal const float SectionGap = 16f;
    internal const float CompactGap = 8f;
    internal const float HeadingGap = 4f;
    internal const float FilterGap = 5f;
    internal const float ControlBarPadding = 10f;
    internal const float ControlMinimumWidth = 188f;
    internal const float FullControlMinimumWidth = 440f;
    internal const float SectionPadding = 14f;
    internal const float SectionHeaderGap = 10f;
    internal const float MultiSelectMinimumWidth = 220f;
    internal const float MultiSelectPopoverWidth = 300f;
    internal const float MultiSelectPopoverMaximumHeight = 310f;
    internal const int MultiSelectSearchThreshold = 7;
    internal const float RailPadding = 20f;
    internal const float HeaderTopPadding = 24f;
    internal const float DividerHeight = 1f;
    internal const float NavigationItemHorizontalPadding = 10f;
    internal const float NavigationItemVerticalPadding = 7f;
    internal const float NavigationIconGap = 8f;
    internal const float NavigationIconWidth = 16f;
    internal const float StatusPadding = 8f;
    internal const float StatusIndicatorSize = 8f;
    internal const float DemoBannerVerticalPadding = 10f;
    internal const float WidgetPadding = 14f;
    internal const float MetricGap = 3f;
    internal const float MetricPadding = 10f;
    internal const float SparklineGap = 8f;
    internal const float SparklineLabelWidth = 120f;
    internal const float TableGap = 3f;
    internal const float TableRowGap = 6f;
    internal const float TableRowHorizontalPadding = 7f;
    internal const float TableRowVerticalPadding = 5f;
    internal const float CompactActionHorizontalPadding = 8f;
    internal const float CompactActionVerticalPadding = 4f;
    internal const float ActionHorizontalPadding = 12f;
    internal const float ActionVerticalPadding = 7f;
    internal const float CardCornerRadius = 10f;
    internal const float SmallCornerRadius = 6f;
    internal const float TableCornerRadius = 4f;
    internal const float WidgetMinimumWidth = 400f;
    internal const float MetricMinimumWidth = 148f;
    internal const float ChartStrokeWidth = 2f;
    internal const float ChartMarkerSize = 5f;
    internal const float AreaFillOpacity = 0.18f;
    internal const float TimelineFillOpacity = 0.72f;
    internal const float TimelineBandFillRatio = 0.62f;
    internal const float HeatmapCellGap = 2f;
    internal const float MetricWidgetHeight = 155f;
    internal const float TableWidgetHeight = 310f;
    internal const float SparklineWidgetHeight = 200f;
    internal const float ChartWidgetHeight = 290f;
    internal const float HomeNetWorthWidgetHeight = 470f;

    internal const int BodyTextSize = 14;
    internal const int HelperTextSize = 12;
    internal const int CompactTextSize = 11;
    internal const int RailTitleTextSize = 20;
    internal const int WidgetTitleTextSize = 16;
    internal const int MetricValueTextSize = 20;
    internal const int PageTitleTextSize = 28;

    internal static readonly Color Window = new(16, 22, 30);
    internal static readonly Color Rail = new(20, 30, 40);
    internal static readonly Color Main = new(24, 34, 45);
    internal static readonly Color Raised = new(31, 44, 57);
    internal static readonly Color MutedSurface = new(39, 54, 68);
    internal static readonly Color Table = new(28, 40, 52);
    internal static readonly Color Border = new(63, 81, 96);
    internal static readonly Color Text = new(236, 241, 245);
    internal static readonly Color MutedText = new(169, 185, 197);
    internal static readonly Color Accent = new(93, 189, 174);
    internal static readonly Color AccentMuted = new(51, 108, 106);
    internal static readonly Color Positive = new(105, 205, 157);
    internal static readonly Color Negative = new(239, 129, 119);
    internal static readonly Color Warning = new(235, 188, 91);
    internal static readonly Color Loading = new(108, 165, 235);
    internal static readonly Color Hidden = new(169, 185, 197);
    internal static readonly Color Neutral = Text;
    internal static readonly Color QuietAction = new(44, 60, 74);
    internal static readonly Color HeatmapLow = new(214, 105, 104);
    internal static readonly Color HeatmapHigh = new(93, 189, 174);
    internal static readonly Color[] ChartPalette =
    [
        Accent,
        Warning,
        new Color(121, 170, 241),
        new Color(217, 142, 209),
        new Color(167, 141, 221)
    ];

    internal static readonly TextStyle BodyText = CreateTextStyle(BodyTextSize, Text);
    internal static readonly TextStyle PageTitleText = CreateTextStyle(PageTitleTextSize, Text);
    internal static readonly TextStyle SectionTitleText = CreateTextStyle(WidgetTitleTextSize, Text);
    internal static readonly TextStyle MetricLabelText = CreateTextStyle(HelperTextSize, MutedText);
    internal static readonly TextStyle MetricValueText = CreateTextStyle(MetricValueTextSize, Text);
    internal static readonly TextStyle HelperText = CreateTextStyle(HelperTextSize, MutedText);
    internal static readonly TextStyle NavigationGroupLabelText = CreateTextStyle(CompactTextSize, MutedText);
    internal static readonly TextStyle RailTitleText = CreateTextStyle(RailTitleTextSize, Text);
    internal static readonly TextStyle CompactActionText = CreateTextStyle(CompactTextSize, Text);
    internal static readonly TextStyle ActionText = CreateTextStyle(HelperTextSize, Text);
    internal static readonly TextStyle WarningText = new(textColor: Warning);
    internal static readonly TextStyle PositiveText = new(textColor: Positive);
    internal static readonly TextStyle NegativeText = new(textColor: Negative);
    internal static readonly TextStyle NeutralText = new(textColor: Neutral);
    internal static readonly TextStyle LoadingText = new(textColor: Loading);
    internal static readonly TextStyle HiddenValueText = new(textColor: Hidden);

    /// <summary>Creates the app-owned dark Roci skin used by every Portico scene.</summary>
    internal static UiSkin CreateUiSkin()
    {
        UiSkin skin = UiSkin.Dark();
        skin.Name = "Portico Dark";
        skin.Text.Style = BodyText;
        skin.Controls.MinHeight = UiSkinLength.Px(32f);
        skin.Controls.TextStyle = ActionText;

        skin.Panel.Surface.Background = UiDrawable.Solid(Color.Transparent);
        skin.Panel.Surface.TextColor = Text;
        ConfigurePanel(skin.Panel.Style(RailPanelStyle), Rail, Border);
        ConfigurePanel(skin.Panel.Style(MainPanelStyle), Main, Color.Transparent);
        ConfigurePanel(skin.Panel.Style(HeaderPanelStyle), Main, Color.Transparent);
        ConfigurePanel(skin.Panel.Style(RaisedPanelStyle), Raised, Border);
        ConfigurePanel(skin.Panel.Style(MutedPanelStyle), MutedSurface, Color.Transparent);
        ConfigurePanel(skin.Panel.Style(TablePanelStyle), Table, Border);
        ConfigurePanel(skin.Panel.Style(NavigationGroupPanelStyle), Color.Transparent, Color.Transparent);
        ConfigurePanel(skin.Panel.Style(PositivePanelStyle), MutedSurface, Positive);
        ConfigurePanel(skin.Panel.Style(NegativePanelStyle), MutedSurface, Negative);
        ConfigurePanel(skin.Panel.Style(NeutralPanelStyle), MutedSurface, Neutral);
        ConfigurePanel(skin.Panel.Style(WarningPanelStyle), MutedSurface, Warning);
        ConfigurePanel(skin.Panel.Style(LoadingPanelStyle), MutedSurface, Loading);
        ConfigurePanel(skin.Panel.Style(HiddenPanelStyle), MutedSurface, Hidden);

        skin.Button.Surface.Background = UiDrawable.Solid(QuietAction);
        skin.Button.Surface.BorderColor = Border;
        skin.Button.Surface.BorderWidth = 1f;
        skin.Button.Surface.Padding = UiSkinSpacing.XY(10f, 6f);
        skin.Button.Surface.TextColor = Text;
        skin.Button.TextStyle = ActionText;
        ConfigureButton(skin.Button.Style(PrimaryActionStyle), Accent, Window, Accent);
        ConfigureButton(skin.Button.Style(SecondaryActionStyle), MutedSurface, Text, Border);
        ConfigureButton(skin.Button.Style(QuietActionStyle), QuietAction, Text);
        ConfigureButton(skin.Button.Style(DangerActionStyle), Negative, Window, Negative);
        ConfigureButton(skin.Button.Style(SelectedActionStyle), AccentMuted, Text);
        UiButtonSkin navigation = skin.Button.Style(NavigationActionStyle);
        ConfigureButton(navigation, Color.Transparent, Text, Color.Transparent);
        navigation.States[UiSkinState.Hovered] = new UiStateStyle { Background = UiDrawable.Solid(QuietAction) };
        navigation.States[UiSkinState.Focused] = new UiStateStyle
        {
            Background = UiDrawable.Solid(MutedSurface),
            BorderColor = Accent
        };
        ConfigureButton(skin.Button.Style(SelectedNavigationActionStyle), AccentMuted, Text);

        return skin;
    }

    /// <summary>Creates the chart skin that matches the app-owned desktop skin.</summary>
    internal static ChartSkin CreateChartSkin()
    {
        ChartSkin skin = ChartSkin.Dark();
        ChartCartesianSkin chart = skin.Cartesian;
        chart.Outer.Background = UiDrawable.Solid(Raised);
        chart.Outer.BorderColor = Border;
        chart.Outer.BorderWidth = 1f;
        chart.Outer.Padding = UiSkinSpacing.All(10f);
        chart.Plot.Background = UiDrawable.Solid(Main);
        chart.Plot.BorderColor = Border;
        chart.Plot.BorderWidth = 1f;
        chart.Plot.Padding = UiSkinSpacing.All(6f);
        chart.TickTextStyle = HelperText;
        chart.AxisTitleTextStyle = HelperText;
        chart.LegendTextStyle = ActionText;
        chart.AxisColor = Border;
        chart.MajorGridColor = MutedSurface;
        chart.Palette.Clear();
        foreach (Color color in ChartPalette)
            chart.Palette.Add(color);

        return skin;
    }

    /// <summary>Gets the named text style for a report tone.</summary>
    internal static TextStyle ToneTextStyle(string? tone)
        => tone switch
        {
            "positive" => PositiveText,
            "negative" => NegativeText,
            "warning" => WarningText,
            "loading" => LoadingText,
            "hidden" => HiddenValueText,
            _ => NeutralText
        };

    /// <summary>Gets the metric text style for a report tone.</summary>
    internal static TextStyle MetricToneTextStyle(string? tone)
        => MetricValueText.Overlay(ToneTextStyle(tone));

    /// <summary>Gets a deterministic chart color from the app palette.</summary>
    internal static Color SeriesColor(int index) => ChartPalette[index % ChartPalette.Length];

    private static void ConfigurePanel(UiPanelSkin panel, Color background, Color border)
    {
        panel.Surface.Background = UiDrawable.Solid(background);
        panel.Surface.BorderColor = border;
        panel.Surface.BorderWidth = border == Color.Transparent ? 0f : 1f;
        panel.Surface.TextColor = Text;
    }

    private static TextStyle CreateTextStyle(int size, Color color)
        => new(FontFamilies.Default, size, color);

    private static void ConfigureButton(UiButtonSkin button, Color background, Color text, Color? border = null)
    {
        button.Surface.Background = UiDrawable.Solid(background);
        button.Surface.BorderColor = border ?? Border;
        button.Surface.BorderWidth = button.Surface.BorderColor == Color.Transparent ? 0f : 1f;
        button.Surface.TextColor = text;
        button.TextStyle = new TextStyle(FontFamilies.Default, HelperTextSize, text);
    }
}
