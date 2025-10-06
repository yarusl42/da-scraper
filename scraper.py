import argparse
import sys

from typing import List, Dict, Optional, Tuple
from src.config.base import DEBUG, HEADLESS, QUERIES_DIR, MAPS_DIR
from src.scroller import scroll_results_stub
from src.types.scraper import ScrapeConfig
from src.io_helpers import safe_print, read_queries_xlsx, write_map_results_xlsx, update_queries_status, query_to_human_slug
from src.parse_gbp_listing import extract_businesses_from_html
from src.playwright_utils import launch_persistent_context
from playwright.sync_api import BrowserContext

def normalize_status(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()

def to_integer(s, default):
    try:
        return int(s)
    except ValueError:
        return default

def should_process_row(status_value: Optional[str], rescrape: bool) -> Tuple[bool, str]:
    """Return (should_process, reason)."""
    s = normalize_status(status_value)
    if rescrape:
        return True, "rescrape"
    if s == "success":
        return False, "already success"
    # empty, pending, error, or anything else -> process
    return True, "pending/error/empty"

def click_on_the_listing(item):
    # Click interactive child or container
    clickable = item.locator(".hfpxzc").first
    for _ in range(20):
        try:
            if clickable.get_attribute("jsaction"):
                clickable.click(timeout=5000)
                return True
        except Exception:
            pass
        try:
            item.click(timeout=5000)
            break
        except Exception:
            page.wait_for_timeout(250)
    return False


def check_listing_has_image(page):
    # Optional: grab listing image src safely //maps.gstatic.com/tactile/pane/default_geocode-1x.png
    try:
        image_wrapper = page.locator(".ZKCDEc")
        image_wrapper_first = image_wrapper.first
        img = image_wrapper_first.locator("img")
        img_first = img.first
        src = img_first.get_attribute("src")
        if "default_geocode" in src:
            return False
        else:
            return True
    except Exception:
        pass
    return False

def open_pleper_panel(page, lastId):
    panel = page.locator(".single_listing_info_window").first
    for _ in range(40):
        try:
            page.wait_for_timeout(250)
            cur_id = panel.get_attribute("id") or ""
            if cur_id != lastId:
                return panel, cur_id
        except Exception:
            pass
        page.wait_for_timeout(250)
    return None, lastId

def scrape_pleper_panel(panel):
    result = {}
    # Extract company name (first <strong>)
    try:
        company = (panel.locator("strong").first.text_content() or "").strip()
        if company:
            result["gbp_company"] = company
    except Exception:
        pass

    # Extract verification from <small>
    try:
        small_txt = (panel.locator("small").first.text_content() or "").strip().lower()
        if "not verified" in small_txt:
            result["gbp_is_verified"] = False
        elif "verified" in small_txt:
            result["gbp_is_verified"] = True
    except Exception:
        pass

    # Parse table rows using count()/nth()
    try:
        result["attributes"] = -1
        rows = panel.locator("tr")
        rc = rows.count()
        for idx in range(1, rc):  # skip header row at 0
            row = rows.nth(idx)
            tds = row.locator("td")
            if tds.count() < 2:
                continue
            key = (tds.nth(0).text_content() or "").strip()
            val_txt = (tds.nth(1).text_content() or "").strip()
            if key.startswith("Categories"):
                result["categories"] = [p.strip() for p in val_txt.split(",") if p.strip()]
            elif key.startswith("Place ID"):
                result["place_id"] = val_txt
            elif key.startswith("CID"):
                result["CID"] = val_txt
            elif key.startswith("Business Profile ID"):
                result["business_profile_id"] = val_txt
            elif key.startswith("Coordinates"):
                try:
                    parts = [p.strip() for p in val_txt.split(",")]
                    if len(parts) >= 2:
                        result["coordinates"] = [float(parts[0]), float(parts[1])]
                except Exception:
                    pass
            elif key.startswith("KG ID"):
                result["kg_id"] = "https://www.google.com/search?kgmid=" + val_txt
            elif key.startswith("Attributes"):
                try:
                    result["attributes"] = int(val_txt.split()[0])
                except Exception:
                    result["attributes"] = -1
    except Exception:
        pass

    return result


def scrape_listing(page, item, lastId):
    result = {}
    result["gbp_has_image"] = True
    if not click_on_the_listing(item): return result, lastId

    page.wait_for_timeout(1000)

    panel, lastId = open_pleper_panel(page, lastId)
    if not panel is None:
        result = {**scrape_pleper_panel(panel), **result}

    result["gbp_has_image"] = check_listing_has_image(page)

    return result, lastId
        
def process_query(url: str, source_file: str, cfg: ScrapeConfig, context: BrowserContext) -> Tuple[str, List[Dict]]:
    """Navigate to the URL, scroll (stub), and extract real data.
    Returns (slug, rows)
    """
    page = context.new_page()
    page.set_default_timeout(30000)
    lastId = None
    try:
        page.goto(url, timeout=cfg.navigation_timeout_ms)
        scroll_results_stub(page, cfg)

        html = page.content()
        rows = extract_businesses_from_html(html, source_file)

        try:
            locator = page.locator("div.Nv2PK")
            count = locator.count()

            for i in range(count):
                item = locator.nth(i)
                scraped_item, lastId = scrape_listing(page, item, lastId)
                rows[i] = {**rows[i], **scraped_item}
                
        except Exception:
            pass
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
        rescrape = True
    return run(files, rescrape)


if __name__ == "__main__":
    sys.exit(main())
