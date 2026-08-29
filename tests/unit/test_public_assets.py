from pathlib import Path
from xml.etree import ElementTree


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SVG_NAMESPACE = {"svg": "http://www.w3.org/2000/svg"}


def test_logo_has_accessible_metadata() -> None:
    logo = ElementTree.parse(PROJECT_ROOT / "assets" / "brand" / "logo.svg").getroot()

    title = logo.find("svg:title", SVG_NAMESPACE)
    description = logo.find("svg:desc", SVG_NAMESPACE)

    assert logo.attrib["role"] == "img"
    assert logo.attrib["aria-labelledby"] == "title desc"
    assert title is not None and title.attrib["id"] == "title" and title.text == "Portico logo"
    assert description is not None and description.attrib["id"] == "desc" and description.text
