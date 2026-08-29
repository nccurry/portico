from pathlib import Path

import pytest

from scripts import build_pages_demo


def test_build_gallery_uses_canonical_screenshots(tmp_path: Path) -> None:
    output = tmp_path / "pages"
    output.mkdir()

    build_pages_demo.build_gallery(output, "abc123")

    index = (output / "index.html").read_text(encoding="utf-8")
    assert "abc123" in index
    assert "not available" in index
    assert (output / "logo.svg").is_file()
    assert (output / ".nojekyll").is_file()
    for name in build_pages_demo.SCREENSHOTS:
        assert (output / "images" / name).read_bytes() == (
            build_pages_demo.PROJECT_ROOT / "docs" / "images" / name
        ).read_bytes()


def test_clean_output_rejects_repository_root() -> None:
    with pytest.raises(ValueError):
        build_pages_demo.clean_output(build_pages_demo.PROJECT_ROOT)


def test_build_gallery_rejects_unsafe_revision(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Revision"):
        build_pages_demo.build_gallery(tmp_path, "<script>")
