"""Start the browser demo with the full Portico app."""

import os
import runpy
from pathlib import Path

from demo.pages.streamlit_compat import install_streamlit_compatibility

PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    """Run Portico with the committed synthetic data."""
    os.chdir(PROJECT_ROOT)
    os.environ["PORTICO_CONFIG_PATH"] = "portico-demo.toml"

    # TODO(stlite-parity): Remove this call with demo/pages/streamlit_compat.py once
    # the removal conditions documented in that module are met.
    install_streamlit_compatibility()
    runpy.run_path(str(PROJECT_ROOT / "portico_home.py"), run_name="__main__")


if __name__ == "__main__":
    main()
