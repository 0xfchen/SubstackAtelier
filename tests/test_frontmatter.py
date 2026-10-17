"""Tests for YAML frontmatter generation and extraction."""

from scraper.frontmatter import combine_metadata_and_content, extract_metadata_from_md


def test_mdx_frontmatter_includes_source_url():
    """Verify the post URL is emitted as canonical_url in YAML frontmatter."""
    result = combine_metadata_and_content(
        title="Title",
        subtitle="Subtitle",
        date="2024-01-01",
        author="Author",
        cover_image="",
        content="Body",
        canonical_url="https://example.substack.com/p/test-post",
    )

    assert 'canonical_url: "https://example.substack.com/p/test-post"' in result
    assert result.index('author: "Author"') < result.index("canonical_url:")


def test_combine_metadata_and_content_includes_post_id():
    markdown_output = combine_metadata_and_content(
        title="Codex Post",
        subtitle="Inside OpenAI",
        date="2026-09-09",
        author="Gergely",
        cover_image="",
        content="Post body",
        source_url="https://example.substack.com/p/codex",
        post_id=214748970,
    )
    assert "post_id: 214748970" in markdown_output
    assert 'title: "Codex Post"' in markdown_output


def test_extract_metadata_from_md_mdx_format(tmp_path):
    md_file = tmp_path / "post.md"
    md_file.write_text(
        '---\ntitle: "Codex Post"\npost_id: 214748970\ndate: "2026-09-09"\nauthor: "Gergely"\n---\n\nBody',
        encoding="utf-8",
    )
    metadata = extract_metadata_from_md(str(md_file))
    assert metadata is not None
    assert metadata["title"] == "Codex Post"
    assert metadata["post_id"] == 214748970
    assert metadata["date"] == "2026-09-09"
    assert metadata["author"] == "Gergely"


def test_combine_metadata_and_content_trailing_newline():
    """Verify combine_metadata_and_content always terminates with a newline character."""
    output = combine_metadata_and_content(
        title="Sample Post",
        subtitle="",
        date="2026-09-26",
        author="Author",
        cover_image="",
        content="Hello world",
    )
    assert output.endswith("\n")
    assert not output.endswith("\n\n\n")
