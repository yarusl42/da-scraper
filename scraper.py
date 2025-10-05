DEBUG = False
HEADLESS = False
import argparse
import sys
import time
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs, unquote_plus

import pandas as pd
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup, FeatureNotFound
from parsers.maps_item_parser import parse_maps_item_container

# --- Constants for project structure (cross-platform via pathlib) ---
# Use pathlib throughout to ensure compatibility on Windows and *nix.
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
QUERIES_DIR = DATA_DIR / "queries"
MAPS_DIR = DATA_DIR / "maps"
PROFILE_DIR = PROJECT_ROOT / "browser_profile"
EXTENSIONS_DIR = PROJECT_ROOT / "extensions"
GBP_EVERYWHERE_DIR = EXTENSIONS_DIR / "gbp-everywhere"
PLEPER_DIR = EXTENSIONS_DIR / "PlePer"
DEBUG_DIR = DATA_DIR / "debug"


# --- Utility functions ---

def safe_print(msg: str) -> None:
    """Print to stdout with flush to ensure logs appear in order."""
    print(msg, flush=True)


def normalize_status(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def should_process_row(status_value: Optional[str], rescrape: bool) -> Tuple[bool, str]:
    """Return (should_process, reason)."""
    s = normalize_status(status_value)
    if rescrape:
        return True, "rescrape"
    if s == "success":
        return False, "already success"
    # empty, pending, error, or anything else -> process
    return True, "pending/error/empty"


slug_illegal_pattern = re.compile(r"[\\/:*?\"<>|]+")
collapse_spaces_pattern = re.compile(r"\s+")


def query_to_human_slug(url: str) -> str:
    """Derive a deterministic, human-readable filename base from a Google Maps URL.

    Rules:
    - Prefer the 'q' query parameter if present
    - Else, try to extract from the path segment after '/maps/search/'
    - Replace '+' with spaces and percent-decode
    - Lowercase, trim, collapse multiple spaces
    - Remove illegal filename characters
    """
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        # Prefer q param
        q_vals = qs.get("q") or qs.get("query")
        if q_vals and len(q_vals) > 0 and q_vals[0].strip():
            raw = q_vals[0]
        else:
            # Try path after /maps/search/
            path = parsed.path or ""
            raw = ""
            if "/maps/search/" in path:
                after = path.split("/maps/search/", 1)[1]
                raw = after
            else:
                # Fallback to entire path tail
                raw = path.strip("/").split("/")[-1]
        # Decode google-style pluses and percent-encoding
        decoded = unquote_plus(raw)
        # cleanup
        decoded = decoded.lower().strip()
        decoded = slug_illegal_pattern.sub(" ", decoded)
        decoded = collapse_spaces_pattern.sub(" ", decoded)
        decoded = decoded.strip()
        decoded = decoded.replace(" ", "_")
        decoded = decoded.replace(",", "_")
        decoded = decoded.replace(".", "_")
        # If empty, fallback generic name
        return decoded if decoded else "google maps query"
    except Exception:
        return "google maps query"


# --- IO helpers ---

def read_queries_xlsx(file_path: Path) -> pd.DataFrame:
    """Read the queries Excel. Expect columns: 'query_url', 'status'.
    Optionally accepts 'search_volume'. Columns matched case-insensitively.
    """
    df = pd.read_excel(file_path)
    # Normalize columns
    cols = {c.lower().strip(): c for c in df.columns}
    url_col = None
    status_col = None
    sv_col = None
    for key, orig in cols.items():
        if key in ("query_url", "url", "link") and url_col is None:
            url_col = orig
        if key == "status" and status_col is None:
            status_col = orig
        if key in ("search_volume", "search volume", "volume") and sv_col is None:
            sv_col = orig
    if url_col is None:
        raise ValueError(
            f"Input file '{file_path.name}' must contain a 'query_url' (or 'url'/'link') column."
        )
    if status_col is None:
        # if missing, create it
        df["status"] = ""
        status_col = "status"
    # If search_volume missing, create empty column to keep schema stable
    if sv_col is None:
        df["search_volume"] = None
        sv_col = "search_volume"
    return df.rename(columns={url_col: "query_url", status_col: "status", sv_col: "search_volume"})


def write_map_results_xlsx(file_path: Path, rows: List[Dict]) -> None:
    df = pd.DataFrame(rows)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(file_path, index=False)


def update_queries_status(file_path: Path, df: pd.DataFrame) -> None:
    # Simply write back the normalized df
    file_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(file_path, index=False)


# --- Playwright helpers (with stubs) ---
@dataclass
class ScrapeConfig:
    scroll_pause_sec: float = 0.5
    navigation_timeout_ms: int = 30000


def launch_persistent_context(headless: bool) -> Tuple[BrowserContext, any]:
    """Launch a persistent Chromium context that saves cookies/profile under PROFILE_DIR.
    If the GBP Everywhere extension is present (unpacked) under GBP_EVERYWHERE_DIR,
    load it. Returns (context, pw_controller) so the caller can close both.
    """
    pw = sync_playwright().start()
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    args = []
    if GBP_EVERYWHERE_DIR.exists():
        ext_path = str(GBP_EVERYWHERE_DIR.resolve())
        args.extend([
            f"--disable-extensions-except={ext_path}",
            f"--load-extension={ext_path}",
        ])

    context = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR.resolve()),
        headless=headless,
        viewport={"width": 1280, "height": 900},
        args=args,
    )
    # Set a default timeout for all pages in this context
    context.set_default_timeout(30000)
    return context, pw


def new_page_in_context(context: BrowserContext) -> Page:
    page = context.new_page()
    page.set_default_timeout(30000)
    return page


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


# --- Real extraction from page HTML using BeautifulSoup + item parser ---

def extract_businesses_from_html(html: str, source_file: str) -> List[Dict]:
    """Parse all visible result items from a Google Maps results page HTML.

    Targets containers with classes: Nv2PK tH5CWc THOPZb. Falls back to Nv2PK if none found.
    Uses parse_maps_item_container() to extract a MapsItem from each container's HTML.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        soup = BeautifulSoup(html, "lxml")  # fallback if available at runtime

    containers = soup.select("div.Nv2PK.tH5CWc.THOPZb")
    if not containers:
        containers = soup.select("div.Nv2PK")

    rows: List[Dict] = []
    for idx, el in enumerate(containers, start=1):
        try:
            item = parse_maps_item_container(str(el))
            data = item.to_dict()
        except Exception as e:
            # On parse failure, continue but record minimal info
            data = {"name": None, "categories": [], "rating": None, "reviews_count": None,
                    "address": None, "phone": None, "website": None, "listing_link": None,
                    "status": f"parse_error: {e}"}

        # Augment with position and source
        data["position"] = idx
        data["source_file"] = source_file
        rows.append(data)

    return rows


def process_query(url: str, source_file: str, cfg: ScrapeConfig, context: BrowserContext) -> Tuple[str, List[Dict]]:
    """Navigate to the URL, scroll (stub), and extract real data.
    Returns (slug, rows)
    """
    page = new_page_in_context(context)
    try:
        page.goto(url, timeout=cfg.navigation_timeout_ms)
        scroll_results_stub(page, cfg)
        # Get the full HTML after scrolling and parse results list
        html = page.content()
        rows = extract_businesses_from_html(html, source_file)
        slug = query_to_human_slug(url)
        return slug, rows
    finally:
        try:
            page.close()
        except Exception:
            pass


# --- CLI and orchestration ---

def run(files_arg: str, rescrape: bool) -> int:
    input_files = [f.strip() for f in files_arg.split(",") if f.strip()]
    if not input_files:
        safe_print("No input files provided. Nothing to do.")
        return 1

    # Validate input files exist in data/queries/
    for name in input_files:
        fp = QUERIES_DIR / name
        if not fp.exists():
            safe_print(f"[!] Error: Input file not found: {name} (looked in {QUERIES_DIR})")
            return 1

    cfg = ScrapeConfig()

    # One persistent context for the whole run to optimize performance and save profile/cookies
    context, pw_cm = launch_persistent_context(headless=HEADLESS)

    try:
        for file_name in input_files:
            file_path = QUERIES_DIR / file_name
            safe_print("")
            safe_print(f"Processing file: {file_name}")

            try:
                df = read_queries_xlsx(file_path)
            except Exception as e:
                safe_print(f"[!] Error reading {file_name}: {e}")
                continue

            # Counters for summary
            success_count = 0
            error_count = 0
            pending_count = 0
            skipped_count = 0

            # Ensure required columns
            if "query_url" not in df.columns:
                safe_print(f"[!] Error: '{file_name}' missing 'query_url' column.")
                continue
            if "status" not in df.columns:
                df["status"] = ""

            # Iterate rows
            for idx, row in df.iterrows():
                url = str(row.get("query_url", "")).strip()
                status_val = row.get("status", "")
                search_volume = row.get("search_volume", None)

                if not url:
                    # treat as skipped/pending
                    pending_count += 1
                    df.at[idx, "status"] = "pending"
                    safe_print("[⏸] Pending: (empty query_url)")
                    continue

                do_process, reason = should_process_row(status_val, rescrape)
                if not do_process:
                    skipped_count += 1
                    safe_print(f"[→] Skipped: {query_to_human_slug(url)} ({reason})")
                    continue

                # Process this query
                try:
                    slug, rows_out = process_query(url, file_name, cfg, context)
                    # Attach search_volume to each output row
                    if search_volume is not None:
                        try:
                            for r in rows_out:
                                r["search_volume"] = search_volume
                        except Exception:
                            pass
                    out_path = MAPS_DIR / f"{slug}.xlsx"
                    write_map_results_xlsx(out_path, rows_out)
                    df.at[idx, "status"] = "success"
                    success_count += 1
                    safe_print(f"[✓] Success: {slug} ({len(rows_out)} results)")
                except Exception as e:
                    df.at[idx, "status"] = "error"
                    error_count += 1
                    safe_print(f"[!] Error: {query_to_human_slug(url)} ({e})")

            # Write updated statuses back to the query file
            try:
                update_queries_status(file_path, df)
            except Exception as e:
                safe_print(f"[!] Error writing status updates for {file_name}: {e}")

            # Count remaining pendings
            pending_count += int((df["status"].str.lower() == "pending").sum())

            # Summary
            safe_print("")
            safe_print(f"Finished file {file_name}")
            safe_print(
                f"Success: {success_count} | Error: {error_count} | Pending: {pending_count} | Skipped: {skipped_count}"
            )

        return 0
    finally:
        try:
            context.close()
        except Exception:
            pass
        try:
            pw_cm.stop()
        except Exception:
            pass


def main(argv: Optional[List[str]] = None) -> int:
    if not DEBUG:
        parser = argparse.ArgumentParser(
            description="Scrape Google Maps businesses from query Excel files."
        )
        parser.add_argument(
            "files",
            type=str,
            help="Comma-separated list of .xlsx filenames located in ./data/queries/",
        )
        parser.add_argument(
            "--rescrape",
            action="store_true",
            help="Force re-process all rows regardless of their current status.",
        )

        args = parser.parse_args(argv)
        files = args.files
        rescrape = args.rescrape
    else:
        files = "example.xlsx"
        rescrape = False
    return run(files, rescrape)


if __name__ == "__main__":
    sys.exit(main())
