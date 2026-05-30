from hermes.ingestors.obsidian import read_vault


def test_read_vault_finds_markdown_files(tmp_path):
    (tmp_path / "note1.md").write_text("# My Note\n\nSome content about AI safety.")
    (tmp_path / "note2.md").write_text("No title but some text.")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.md").write_text("# Nested\nNested content.")
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / ".obsidian" / "config").write_text("ignore me")

    items = read_vault(str(tmp_path))
    assert len(items) == 3
    titles = {i.title for i in items}
    assert "My Note" in titles
    assert "note2" in titles
    assert "Nested" in titles


def test_read_vault_skips_empty_files(tmp_path):
    (tmp_path / "empty.md").write_text("")
    (tmp_path / "has_content.md").write_text("Content here.")
    items = read_vault(str(tmp_path))
    assert len(items) == 1
    assert items[0].title == "has_content"


def test_read_vault_handles_nonexistent_path(tmp_path):
    items = read_vault(str(tmp_path / "nonexistent"))
    assert items == []
