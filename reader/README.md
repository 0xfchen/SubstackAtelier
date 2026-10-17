# SubstackAtelier Reader

Local static reader for scraped Substack essays, based on [Astro Tone](https://github.com/hanityx/astro-tone).

## Getting Started

Make sure Node.js (v22+) and pnpm are installed:

```bash
# In reader/
nvs use lts      # If using NVS
pnpm install
pnpm dev
```

Open [http://localhost:4321](http://localhost:4321) to browse scraped articles with full-text search (`Cmd`/`Ctrl` + `K`), category and tag filtering, syntax highlighting, and dark mode.

## Content Ingestion

The reader automatically discovers and loads all Markdown posts from the root `content/` directory (`../content/**/posts/*.md`). New scraped posts appear immediately upon refreshing.

## Building for Production

```bash
pnpm build
pnpm preview
```
