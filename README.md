# SubstackAtelier

SubstackAtelier is a Python tool for downloading free and premium Substack posts and saving them into clean, structured Markdown files organized by author (`content/<author>/posts/<slug>.md`). It extracts rich post metadata, sanitizes promotional clutter, and powers a modern local static reader.

Once you run the scraper, it saves markdown files into `content/<author>/posts/` and an author catalog into `content/<author>/metadata.json`. When image downloading is enabled (`--images`), post images are saved locally into `content/<author>/images/<post_slug>/` and rewritten with relative links.

<p align="center">
  <img src="reader/public/preview/light/library.png" alt="Substack Reader Library" width="850" />
</p>

## Features

### Scraping Engine
- **Free & Subscriber Content**: Archives public newsletters and paid subscriber-only posts (requires active subscription).
- **Clean Markdown & Frontmatter**: Converts posts to markdown with sanitized HTML, stripped promotional clutter (subscribe buttons, paywall banners, footers), and preserved code syntax blocks.
- **Rich Metadata Extraction**: Captures `post_id`, `tags`, `description`, `wordcount`, `audience`, and `canonical_url` with zero extra network overhead.
- **Local Asset Pipeline**: Downloads embedded images into `content/<author>/images/<slug>/` and rewrites markdown image links with `--images`.
- **Author-Centric Organization**: Cleanly arranges posts, images, and author catalog into `content/<author>/`.
- **Browser Automation & Session Reuse**: Launches desktop Chrome or Edge via Playwright with persistent profiles, storage state JSON, or CDP attach (solving CAPTCHAs interactively once and reusing sessions).
- **Flexible Scoping**: Scrapes entire publications, single posts by URL (e.g. `/p/slug`), or limits post count with `--number`.

### Modern Astro Reader (`reader/`)
- **Reading Progress & Tracker**: Todo-style status tracking (`pending`, `in-progress`, `completed`), read counters, completion progress bar, and persistence via local storage and `content/reading_state.json`.
- **Instant Back-Navigation & State Preservation**: Returns from articles with zero latency (BFCache), preserving loaded row batches, exact scroll coordinates, active filters, search queries, and pulse-highlighting the active post row.
- **3D Knowledge Graph**: Interactive Three.js force-directed universe with dual-theme shape taxonomy (cosmic ringed planets, nebula hubs, and asteroids in dark mode; architectural spheres, prismatic diamonds, and document folios in light mode), real-time physics, chronological timeline scrubber, and topic/reading status color modes.
- **Interactive 404 Origami Scene**: Procedural Three.js aerospace flight experience on missing routes, featuring a duo-tone origami paper plane (or SpaceX Starship in dark mode), matching origami paper "404" typography in light mode, continuous 3D banking flight path, twinkling starfield, and instant vessel switching.
- **Full-Text Search & Filtering**: Fast client-side search (Pagefind) with live snippet highlighting, keyboard shortcut launcher (`Cmd/Ctrl+K`), author filtering, and multi-column sorting.
- **Reading Experience**: Dark/light modes, image lightbox, syntax-highlighted code blocks, left reading progress rail, and right floating table-of-contents outline.

## Installation

Clone the repository and install dependencies using `uv` (recommended) or `pip`:

```bash
git clone https://github.com/0xfchen/SubstackAtelier.git
cd SubstackAtelier

# Install dependencies with uv (or pip install .)
uv sync
```

### Credentials Setup (For Premium Content)

To scrape subscriber-only posts, provide your Substack credentials using either of the following methods:

1. **`.env` file** in the project root (recommended, see `.env.example`):
   ```ini
   SUBSTACK_EMAIL=your-email@domain.com
   SUBSTACK_PASSWORD=your-password
   ```

2. **Environment variables**:
   ```bash
   export SUBSTACK_EMAIL="your-email@domain.com"
   export SUBSTACK_PASSWORD="your-password"
   ```

> The `.env` file is gitignored to ensure your credentials are never committed.

For premium scraping, you will also need either **Google Chrome** or **Microsoft Edge** installed.

## Usage

### Basic Scraping (Free Content)

Scrape an entire publication:
```bash
uv run scraper --url https://example.substack.com
# Or using python module:
python -m scraper --url https://example.substack.com
```

Scrape a single post directly:
```bash
uv run scraper --url https://example.substack.com/p/my-post
```

Limit the number of posts to scrape:
```bash
uv run scraper --url https://example.substack.com --number 5
```

Download images locally and rewrite markdown image links:
```bash
uv run scraper --url https://example.substack.com --images
```

Keep raw promotional widgets (disable cleaning):
```bash
uv run scraper --url https://example.substack.com --no-clean
```

Specify custom output base directory:
```bash
uv run scraper --url https://example.substack.com --directory /path/to/save/content
```

### Premium Scraping (Subscriber-Only Content)

Premium posts require subscriber access. Automation uses **Playwright** with zero driver setup, launching your desktop **Google Chrome** or **Microsoft Edge** directly.

Scrape premium content using Chrome or Edge:
```bash
uv run scraper --url https://example.substack.com --premium --browser chrome
```

#### Reusing Existing Sessions (No Repeated Logins)

**Option 1: Persistent Profile (Recommended)**
Saves your logged-in state to `~/.substack_scraper/<browser>_profile`:
```bash
# First run: logs in or solve CAPTCHA interactively once
uv run scraper --url https://example.substack.com --premium --persistent-profile

# Subsequent runs: reuse the session automatically
uv run scraper --url https://example.substack.com --premium --persistent-profile --skip-login
```

**Option 2: Storage State JSON**
Playwright automatically exports auth tokens and cookies to `~/.substack_scraper/storage_state.json` upon successful login:
```bash
# Run headlessly reusing saved cookies
uv run scraper --url https://example.substack.com --premium --headless --skip-login
# Or specify a custom state file:
uv run scraper --url https://example.substack.com --premium --storage-state path/to/state.json
```

**Option 3: Attach Directly to Active Browser (CDP)**
Connect directly to an already-open personal Chrome/Edge window without logging in again:
```bash
# 1. Start Chrome with remote debugging:
chrome.exe --remote-debugging-port=9222

# 2. Scrape directly using the active browser's tabs and cookies:
uv run scraper --url https://example.substack.com --premium --cdp-url http://localhost:9222
```

## Local Reader (Astro)

A modern static reader is provided in the `reader/` directory, built with Astro, Three.js, and Pagefind.

### Article Reading View
Distraction-free reading experience with a left reading-progress tick rail, right floating table-of-contents outline, code syntax highlighting, and responsive dark/light modes:

<p align="center">
  <img src="reader/public/preview/light/post.png" alt="Substack Reader Article View" width="850" />
</p>

### 3D Knowledge Graph (`/graph`)
Interactive 3D force-directed graph mapping your entire reading library. Distinct 3D geometric shapes identify entity types: in Dark Mode, publication hubs (**Ringed Planets**), topic hubs (**Nebula Spheres**), and articles (**Asteroids**); in Light Mode, publication hubs (**Solid Spheres**), topic hubs (**Prismatic Diamonds**), and articles (**Document Folios**). Features real-time physics, orbital camera navigation, topic/reading-status coloring, chronological timeline scrubbing, and instant node search:

<p align="center">
  <img src="reader/public/preview/light/graph.png" alt="Substack Reader 3D Knowledge Graph" width="850" />
</p>

### Instant Full-Text Search (`/search`)
Lightning-fast client-side search powered by Pagefind with keyword highlighting, snippet previews, and instant keyboard launcher (`Cmd/Ctrl + K` or `/`):

<p align="center">
  <img src="reader/public/preview/light/search.png" alt="Substack Reader Full-Text Search" width="850" />
</p>

### Interactive 404 Origami Scene (`/404`)
Playful 3D aerospace scene for missing routes featuring a duo-tone origami paper plane (cotton white top surface, slate craft gray underside) or SpaceX Starship gliding through a continuous 3D aerospace flight trajectory, complete with matching origami paper "404" typography in light mode, mouse parallax banking, starfield particles, and responsive dark/light theme duality:

<p align="center">
  <img src="reader/public/preview/light/404.png" alt="Substack Reader 404 Origami Scene" width="850" />
</p>

### Running the Reader

Start the local development server:
```bash
cd reader
pnpm install
pnpm dev
```
Open [http://localhost:4321](http://localhost:4321) in your browser to browse your library, search articles, and explore the 3D knowledge graph.

To build the static site and compile the Pagefind search index:
```bash
cd reader
pnpm build
pnpm preview
```
