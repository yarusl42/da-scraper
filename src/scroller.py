from playwright.sync_api import Page
from src.types.scraper import ScrapeConfig
import time
from src.config.base import DEBUG

def scroll_results_stub(page: Page, cfg: ScrapeConfig) -> None:
    """Stub for scrolling the results pane until no new results.
    For now, just wait a bit to simulate activity.
    """
    # Scroll the Google Maps results FEED until we see the end-of-results marker,
    # then wait for 10 seconds as requested.
    end_selector = ".m6QErb.XiKgde.tLjsW.eKbjU"
    feed_locator = page.locator('[role="feed"]')

    # Ensure the feed is present/visible (best effort)
    try:
        feed_locator.wait_for(state="visible", timeout=cfg.navigation_timeout_ms)
    except Exception:
        pass

    # Break out if we cannot make progress for 60 seconds
    # Progress is defined as an increase in the number of result item containers on the page
    stuck_threshold_sec = 60
    last_progress_ts = time.time()
    # Initial listing count
    try:
        count_primary = page.locator("div.Nv2PK.tH5CWc.THOPZb").count()
        last_count = count_primary if count_primary > 0 else page.locator("div.Nv2PK").count()
    except Exception:
        last_count = 0

    while not DEBUG:
        try:
            if page.locator(end_selector).count() > 0:
                break
        except Exception:
            # If querying fails intermittently, keep trying
            pass

        # Prefer scrolling the FEED element specifically
        try:
            handle = feed_locator.element_handle(timeout=20000)
        except Exception:
            handle = None

        scrolled = False
        if handle:
            try:
                # Scroll by one viewport height of the feed
                page.evaluate("(el) => el.scrollBy(0, el.clientHeight)", handle)
                scrolled = True
            except Exception:
                scrolled = False

        if not scrolled:
            # Fallback: use mouse wheel to nudge the page
            try:
                page.mouse.wheel(0, 1200)
            except Exception:
                pass
        # Evaluate current listing count to determine progress
        try:
            curr_primary = page.locator("div.Nv2PK.tH5CWc.THOPZb").count()
            curr_count = curr_primary if curr_primary > 0 else page.locator("div.Nv2PK").count()
        except Exception:
            curr_count = last_count

        if curr_count > last_count:
            last_count = curr_count
            last_progress_ts = time.time()
        else:
            # If listing count hasn't increased for too long, assume we're stuck and stop gracefully
            if (time.time() - last_progress_ts) >= stuck_threshold_sec:
                break

        time.sleep(cfg.scroll_pause_sec)

    # Final wait for content to settle after reaching the end marker (or after attempts)
    try:
        page.wait_for_timeout(10_000)
    except Exception:
        pass