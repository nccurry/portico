from pathlib import Path

import pytest

from scripts import build_pages_demo


def test_build_gallery_uses_canonical_screenshots(tmp_path: Path) -> None:
    output = tmp_path / "pages"
    output.mkdir()

    build_pages_demo.build_gallery(output, "abc123")

    index = (output / "index.html").read_text(encoding="utf-8")
    readme = (build_pages_demo.PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "tree/abc123" in index
    assert "__REVISION__" not in index
    assert "not available" in index
    assert (output / "logo.svg").is_file()
    assert (output / ".nojekyll").is_file()
    for name in build_pages_demo.SCREENSHOTS:
        assert f"images/{name}" in index
        assert f"docs/images/{name}" in readme
        assert (output / "images" / name).read_bytes() == (
            build_pages_demo.PROJECT_ROOT / "docs" / "images" / name
        ).read_bytes()


def test_clean_output_rejects_repository_root() -> None:
    with pytest.raises(ValueError, match="inside the build directory"):
        build_pages_demo.clean_output(build_pages_demo.PROJECT_ROOT)


def test_clean_output_rejects_path_outside_build(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="inside the build directory"):
        build_pages_demo.clean_output(tmp_path / "pages")


def test_clean_output_replaces_existing_pages_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_pages_demo, "PROJECT_ROOT", tmp_path)
    output = tmp_path / "build" / "pages"
    output.mkdir(parents=True)
    stale = output / "stale.txt"
    stale.touch()

    build_pages_demo.clean_output(output)

    assert output.is_dir()
    assert not stale.exists()


def test_build_gallery_rejects_unsafe_revision(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Revision"):
        build_pages_demo.build_gallery(tmp_path, "<script>")
