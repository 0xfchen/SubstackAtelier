import os

USE_PREMIUM: bool = False
BASE_SUBSTACK_URL: str = "https://substack.com/"
BASE_CONTENT_DIR: str = "content"
NUM_POSTS_TO_SCRAPE: int = 0
DEFAULT_REQUEST_TIMEOUT: int = 30
MAX_IMAGE_WORKERS: int = 6
DEFAULT_API_POST_LIMIT: int = 25
MAX_API_SYNC_PAGES: int = 100
PLAYWRIGHT_NAVIGATION_TIMEOUT_MS: int = 15000
PLAYWRIGHT_CONTENT_RENDER_TIMEOUT_MS: int = 20000
PLAYWRIGHT_HYDRATION_TIMEOUT_MS: int = 5000
PLAYWRIGHT_SELECTOR_TIMEOUT_MS: int = 5000
PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS: int = 30
EXCLUDED_URL_KEYWORDS: tuple[str, ...] = ("about", "archive", "podcast")


def get_credentials() -> tuple[str, str]:
    """Retrieve Substack login credentials for premium scraping.

    The SUBSTACK_EMAIL and SUBSTACK_PASSWORD environment variables (or values
    from a .env file if present) are used.

    Returns:
        tuple[str, str]: A tuple of (email, password).
    """
    try:
        from dotenv import find_dotenv, load_dotenv

        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path)
    except ImportError:
        pass

    return (
        os.environ.get("SUBSTACK_EMAIL", ""),
        os.environ.get("SUBSTACK_PASSWORD", ""),
    )
