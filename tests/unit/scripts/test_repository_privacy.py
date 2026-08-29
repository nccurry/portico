from __future__ import annotations

from scripts.check_repository_privacy import sensitive_text_patterns


def test_discord_webhook_pattern_rejects_realistic_tokens() -> None:
    webhook = (
        "https://discord.com/api/"
        + "webhooks/"
        + "123456789012345678"
        + "/"
        + "synthetic-token-value-that-is-not-secret"
    )

    assert sensitive_text_patterns()["Discord webhook token"].search(webhook)


def test_discord_webhook_pattern_allows_documentation_placeholder() -> None:
    placeholder = "https://discord.com/api/webhooks/<webhook-id>/<webhook-token>"

    assert not sensitive_text_patterns()["Discord webhook token"].search(placeholder)


def test_absolute_user_path_pattern_allows_portico_container_user() -> None:
    assert not sensitive_text_patterns()["absolute user path"].search("/home/portico")


def test_absolute_user_path_pattern_rejects_personal_user() -> None:
    personal_path = "/" + "home" + "/" + "alice"

    assert sensitive_text_patterns()["absolute user path"].search(personal_path)
