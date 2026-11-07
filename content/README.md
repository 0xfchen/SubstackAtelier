# Content Directory

This directory contains scraped Substack newsletter posts, images, metadata, and local browser session state:

```text
content/
├── .browser_profiles/                # Persistent Playwright browser profiles (0o700)
│   └── <browser>/
├── storage_state.json                # Saved Playwright session cookies and localStorage (0o600)
└── <author>/
    ├── metadata.json                 # Publication metadata and essay catalog
    ├── posts/
    │   ├── <post-slug-1>.md          # Clean Markdown with YAML frontmatter
    │   └── <post-slug-2>.md
    └── images/                       # Downloaded post images (when --images is passed)
        └── <post-slug-1>/
            ├── image-1.png
            └── image-2.jpg
```

> **Security Note**: `storage_state.json` and `.browser_profiles/<browser>/` contain Substack session cookies and must never be committed or shared.
