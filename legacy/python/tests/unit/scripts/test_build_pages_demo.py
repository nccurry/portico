from scripts.build_pages_demo import ARCHIVE_HASH_PLACEHOLDER, _render_index


def test_render_index_uses_archive_hash_for_cache_key() -> None:
    rendered = _render_index("abc123")

    assert "./portico-demo.zip?v=abc123" in rendered
    assert ARCHIVE_HASH_PLACEHOLDER not in rendered
