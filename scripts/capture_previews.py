#!/usr/bin/env python3
"""Capture high-resolution preview screenshots for the SubstackAtelier documentation.

This script connects to the local Astro reader dev server and uses Playwright
to generate crisp 2x Retina screenshots of the reader interfaces:
  - Library table view (`/`)
  - Article reading view with side rails (`/posts/...`)
  - 3D Knowledge Graph view (`/graph/`)
  - Search view (`/search/`)
  - 404 Origami Crane view (`/404.html`)

Usage:
    uv run python scripts/capture_previews.py
    uv run python scripts/capture_previews.py --only graph
    uv run python scripts/capture_previews.py --only search
    uv run python scripts/capture_previews.py --only 404
    uv run python scripts/capture_previews.py --theme both
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from playwright.sync_api import sync_playwright

from scraper.browser import BrowserManager

if TYPE_CHECKING:
    from playwright.sync_api import Page

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:4321"
DEFAULT_POST_PATH = "pragmaticengineer/posts/20-years-of-software-engineering"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUTPUT_DIR = os.path.join(REPO_ROOT, "reader", "public", "preview")
ALL_TARGETS = ("library", "post", "graph", "search", "404")


def _is_server_reachable(url: str, timeout_sec: float = 3.0) -> bool:
    """Check if the local dev server is active and returning HTTP 200."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SubstackScreenshotBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _resolve_post_path(slug_or_path: str) -> str:
    """Resolve an article route path (supporting collection ID or bare slug)."""
    if "/" in slug_or_path:
        return slug_or_path.strip("/")

    # Search content directory for author-nested path
    content_dir = os.path.join(REPO_ROOT, "content")
    if os.path.isdir(content_dir):
        for author in sorted(os.listdir(content_dir)):
            posts_dir = os.path.join(content_dir, author, "posts")
            if os.path.isdir(posts_dir):
                for file in sorted(os.listdir(posts_dir)):
                    base_name = os.path.splitext(file)[0]
                    if base_name == slug_or_path:
                        return f"{author}/posts/{base_name}"

    return slug_or_path


def _apply_theme(page: Page, theme: str) -> None:
    """Set data-theme attribute on documentElement and dispatch update."""
    if theme in ("light", "dark"):
        page.evaluate(
            f"""() => {{
                document.documentElement.setAttribute('data-theme', '{theme}');
                try {{ localStorage.setItem('theme', '{theme}'); }} catch {{}}
                window.dispatchEvent(new Event('theme-change'));
            }}"""
        )
        page.wait_for_timeout(250)


def capture_screenshots(
    base_url: str = DEFAULT_BASE_URL,
    post_slug: str = DEFAULT_POST_PATH,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    browser_name: str = "edge",
    targets: tuple[str, ...] = ALL_TARGETS,
    theme: str = "light",
) -> None:
    """Capture reader interface preview screenshots using Playwright.

    Args:
        base_url: Base URL of running Astro reader server.
        post_slug: Relative post slug for article view.
        output_dir: Destination folder for output PNG files.
        browser_name: Preferred browser channel ('edge' or 'chrome').
        targets: Subset of ('library', 'post', 'graph', 'search', '404').
        theme: Theme mode ('light', 'dark', or 'both').
    """
    clean_base = base_url.rstrip("/")

    if not _is_server_reachable(clean_base):
        logger.error(
            "Local Astro reader server is not reachable at %s.\n"
            "Please start the dev server first:\n"
            "    cd reader && pnpm dev",
            clean_base,
        )
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    themes = ("light", "dark") if theme == "both" else (theme,)

    with sync_playwright() as playwright:
        channel = BrowserManager.resolve_channel(browser_name, playwright)
        if not channel:
            logger.error("Neither Chrome nor Edge could be found on this system.")
            sys.exit(1)

        logger.info("Launching %s browser for preview generation...", channel)
        browser = playwright.chromium.launch(channel=channel, headless=True)

        for active_theme in themes:
            logger.info("Generating screenshots for theme: %s", active_theme)
            theme_dir = os.path.join(output_dir, active_theme)
            os.makedirs(theme_dir, exist_ok=True)

            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                device_scale_factor=2,
                color_scheme="dark" if active_theme == "dark" else "light",
            )
            reading_state_file = os.path.join(REPO_ROOT, "content", "reading_state.json")
            if os.path.isfile(reading_state_file):
                try:
                    with open(reading_state_file, encoding="utf-8") as f:
                        raw_state = f.read().strip()
                    if raw_state:
                        context.add_init_script(
                            f"""(() => {{
                                try {{
                                    localStorage.setItem('substack_reading_state_cache_v1', {json.dumps(raw_state)});
                                }} catch (e) {{}}
                            }})();"""
                        )
                except Exception as exc:
                    logger.warning("Could not inject reading state cache: %s", exc)

            page = context.new_page()

            # 1. Capture Library Preview
            if "library" in targets:
                page.set_viewport_size({"width": 1280, "height": 800})
                library_url = f"{clean_base}/"
                library_out = os.path.join(theme_dir, "library.png")
                logger.info("Capturing Library view: %s -> %s", library_url, library_out)

                page.goto(library_url, wait_until="networkidle")
                _apply_theme(page, active_theme)
                page.wait_for_selector("[data-reading-table]", timeout=10000)
                page.wait_for_timeout(1000)  # Allow stats bar & font metrics to settle
                page.screenshot(path=library_out)
                logger.info("Saved %s", library_out)

            # 2. Capture Article Preview (with Left Reading Rail and Right TOC Rail)
            if "post" in targets:
                page.set_viewport_size({"width": 1440, "height": 900})
                resolved_path = _resolve_post_path(post_slug)
                post_url = f"{clean_base}/posts/{resolved_path}/"
                post_out = os.path.join(theme_dir, "post.png")
                logger.info("Capturing Article view: %s -> %s", post_url, post_out)

                page.goto(post_url, wait_until="networkidle")
                _apply_theme(page, active_theme)
                page.wait_for_selector("main", timeout=10000)
                try:
                    page.wait_for_selector(".rail-ticks", state="attached", timeout=4000)
                    page.wait_for_selector(".toc-rail", state="attached", timeout=4000)
                except Exception:
                    pass
                page.wait_for_timeout(1000)  # Allow reading rails and code blocks to hydrate
                page.screenshot(path=post_out)
                logger.info("Saved %s", post_out)

            # 3. Capture 3D Knowledge Graph View
            if "graph" in targets:
                page.set_viewport_size({"width": 1440, "height": 900})
                graph_url = f"{clean_base}/graph/"
                graph_out = os.path.join(theme_dir, "graph.png")
                logger.info("Capturing Knowledge Graph view: %s -> %s", graph_url, graph_out)

                page.goto(graph_url, wait_until="networkidle")
                _apply_theme(page, active_theme)
                page.wait_for_selector("[data-graph-container]", timeout=10000)
                page.wait_for_selector("[data-graph-canvas]", timeout=10000)
                page.wait_for_timeout(2000)  # Allow force simulation and clustering to relax
                page.screenshot(path=graph_out)
                logger.info("Saved %s", graph_out)

            # 4. Capture Search View
            if "search" in targets:
                page.set_viewport_size({"width": 1280, "height": 800})
                search_url = f"{clean_base}/search/"
                search_out = os.path.join(theme_dir, "search.png")
                logger.info("Capturing Search view: %s -> %s", search_url, search_out)

                page.goto(search_url, wait_until="networkidle")
                _apply_theme(page, active_theme)
                page.wait_for_selector(".search-main", timeout=10000)
                try:
                    search_input = page.wait_for_selector("input.pagefind-ui__search-input", timeout=5000)
                    if search_input:
                        search_input.fill("engineering")
                        page.wait_for_selector(".pagefind-ui__results-area", timeout=4000)
                except Exception:
                    pass
                page.wait_for_timeout(600)
                page.screenshot(path=search_out)
                logger.info("Saved %s", search_out)

            # 5. Capture 404 Origami Crane View
            if "404" in targets:
                page.set_viewport_size({"width": 1280, "height": 800})
                four_oh_four_url = f"{clean_base}/404.html"
                four_oh_four_out = os.path.join(theme_dir, "404.png")
                logger.info("Capturing 404 Origami Crane view: %s -> %s", four_oh_four_url, four_oh_four_out)

                page.goto(four_oh_four_url, wait_until="networkidle")
                _apply_theme(page, active_theme)
                page.wait_for_selector(".not-found-main", timeout=10000)
                try:
                    page.wait_for_selector("[data-three-canvas]", timeout=5000)
                except Exception:
                    pass
                page.wait_for_timeout(1800)  # Allow 3D aerospace scene to render and settle
                page.screenshot(path=four_oh_four_out)
                logger.info("Saved %s", four_oh_four_out)

            context.close()

        browser.close()
        logger.info("All requested preview screenshots captured successfully.")


def main() -> None:
    """Parse CLI arguments and run preview capture."""
    parser = argparse.ArgumentParser(description="Capture Astro reader documentation preview screenshots.")
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL of running Astro reader (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--post-slug",
        default=DEFAULT_POST_PATH,
        help=f"Post slug or collection path to screenshot for article view (default: {DEFAULT_POST_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Destination directory for screenshots (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--browser",
        choices=["edge", "chrome"],
        default="edge",
        help="Browser channel to use (default: edge)",
    )
    parser.add_argument(
        "--only",
        choices=["library", "post", "graph", "search", "404", "all"],
        default="all",
        help="Which screenshot to capture (default: all)",
    )
    parser.add_argument(
        "--theme",
        choices=["light", "dark", "both"],
        default="light",
        help="Color theme mode to screenshot (default: light)",
    )

    args = parser.parse_args()
    targets = ALL_TARGETS if args.only == "all" else (args.only,)

    capture_screenshots(
        base_url=args.url,
        post_slug=args.post_slug,
        output_dir=args.output_dir,
        browser_name=args.browser,
        targets=targets,
        theme=args.theme,
    )


if __name__ == "__main__":
    main()
