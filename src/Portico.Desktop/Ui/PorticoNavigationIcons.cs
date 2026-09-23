namespace Portico.Desktop.Ui;

/// <summary>Maps source icon identifiers to compact ASCII tokens because Roci has no Material icon primitive.</summary>
internal static class PorticoNavigationIcons
{
    internal static string Glyph(DashboardNavigationIcon icon)
        => icon switch
        {
            DashboardNavigationIcon.None => "?",
            DashboardNavigationIcon.Home => "H",
            DashboardNavigationIcon.Savings => "$",
            DashboardNavigationIcon.Storefront => "M",
            DashboardNavigationIcon.Category => "C",
            DashboardNavigationIcon.CompareArrows => "Y",
            DashboardNavigationIcon.Subscriptions => "S",
            DashboardNavigationIcon.ReceiptLong => "T",
            DashboardNavigationIcon.AccountBalanceWallet => "B",
            DashboardNavigationIcon.Monitoring => "F",
            DashboardNavigationIcon.HealthAndSafety => "+",
            _ => throw new ArgumentOutOfRangeException(nameof(icon), icon, "A configured navigation icon needs a rail glyph.")
        };
}
