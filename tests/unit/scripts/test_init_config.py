from pathlib import Path

from pytest import MonkeyPatch

from scripts import init_config


def test_init_config_creates_once(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "local.example.toml"
    target = tmp_path / "local.toml"
    source.write_text("[spending]\nexclude_groups = []\n", encoding="utf-8")
    monkeypatch.setattr(init_config, "SOURCE", source)
    monkeypatch.setattr(init_config, "TARGET", target)

    assert init_config.main() == 0
    assert target.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert init_config.main() == 1
