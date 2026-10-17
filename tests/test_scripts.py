"""Tests for developer and maintenance helper scripts."""

import importlib.util
from pathlib import Path


def test_check_markdown_script_functions(tmp_path):
    """Verify check_markdown CLI utility formatting and violation parsing."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "check_markdown.py"
    spec = importlib.util.spec_from_file_location("check_markdown", script_path)
    assert spec is not None and spec.loader is not None
    check_md = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_md)

    # Test parser
    raw_lines = [
        "file.md:10:1: MD007: Unordered list indentation [Expected: 0, Actual=2] (ul-indent)",
        "file.md:20:1: MD045: Images should have alternate text (alt text) (no-alt-text)",
    ]
    violations = check_md._parse_violations(raw_lines)
    assert len(violations) == 2
    assert violations[0].rule == "MD007"
    assert violations[1].rule == "MD045"

    # Test file fixing with mdformat
    sample_file = tmp_path / "sample.md"
    sample_file.write_text(
        '---\ntitle: "Test"\n---\n\n* Unordered list item 1\n* Unordered list item 2\n\n',
        encoding="utf-8",
    )
    modified, unchanged = check_md._fix_markdown_files([sample_file])
    assert modified == 1
    assert unchanged == 0
    formatted_content = sample_file.read_text(encoding="utf-8")
    assert "- Unordered list item 1" in formatted_content
    assert formatted_content.endswith("\n")
