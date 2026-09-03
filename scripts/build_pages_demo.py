"""Build the static Portico demo for GitHub Pages."""

from __future__ import annotations

import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "build" / "pages"
ARCHIVE_PATH = OUTPUT_DIRECTORY / "portico-demo.zip"
DEMO_ENTRYPOINT = PROJECT_ROOT / "demo" / "pages" / "entry.py"
APPLICATION_ENTRYPOINT = PROJECT_ROOT / "Home.py"
SITE_FILES = (
    (PROJECT_ROOT / "demo" / "pages" / "index.html", OUTPUT_DIRECTORY / "index.html"),
    (PROJECT_ROOT / "assets" / "brand" / "logo.svg", OUTPUT_DIRECTORY / "logo.svg"),
)
APPLICATION_FILES = (
    Path(".streamlit/config.toml"),
    Path("config.toml"),
    Path("portico-demo.toml"),
    Path("demo/__init__.py"),
    Path("demo/pages/__init__.py"),
    Path("demo/pages/streamlit_compat.py"),
)
APPLICATION_DIRECTORIES = (Path("app_pages"), Path("src"))


def _app_files() -> tuple[Path, ...]:
    """Return the Portico app and synthetic data for the browser demo."""
    files = [PROJECT_ROOT / path for path in APPLICATION_FILES]
    for directory in APPLICATION_DIRECTORIES:
        files.extend(sorted((PROJECT_ROOT / directory).rglob("*.py")))
    files.extend(sorted((PROJECT_ROOT / "demo" / "data").glob("*.csv")))
    return tuple(files)


def _require_file(path: Path) -> None:
    """Stop the build when a required demo file is missing."""
    if not path.is_file():
        raise FileNotFoundError(path)


def _copy_site_files() -> None:
    """Copy the browser page and its logo to the publish directory."""
    for source, destination in SITE_FILES:
        _require_file(source)
        shutil.copy2(source, destination)
    (OUTPUT_DIRECTORY / ".nojekyll").touch()


def _write_archive(files: tuple[Path, ...]) -> None:
    """Write the source code and synthetic data for the browser runtime."""
    _require_file(DEMO_ENTRYPOINT)
    _require_file(APPLICATION_ENTRYPOINT)
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as archive:
        archive.write(DEMO_ENTRYPOINT, "Home.py")
        archive.write(APPLICATION_ENTRYPOINT, "portico_home.py")
        for source in files:
            _require_file(source)
            archive.write(source, source.relative_to(PROJECT_ROOT).as_posix())


def main() -> None:
    """Build the GitHub Pages files."""
    if OUTPUT_DIRECTORY.exists():
        shutil.rmtree(OUTPUT_DIRECTORY)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    _copy_site_files()
    _write_archive(_app_files())
    print(f"Built {ARCHIVE_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
