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


def should_process_row(status_value: Optional[str], rescrape: bool) -> Tuple[bool, str]:
    """Return (should_process, reason)."""
    s = normalize_status(status_value)
    if rescrape:
        return True, "rescrape"
    if s == "success":
        return False, "already success"
    # empty, pending, error, or anything else -> process
    return True, "pending/error/empty"


def process_query(url: str, source_file: str, cfg: ScrapeConfig, context: BrowserContext) -> Tuple[str, List[Dict]]:
    """Navigate to the URL, scroll (stub), and extract real data.
    Returns (slug, rows)
    """
    page = context.new_page()
    page.set_default_timeout(30000)
    try:
        page.goto(url, timeout=cfg.navigation_timeout_ms)
        scroll_results_stub(page, cfg)

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
        rescrape = True
    return run(files, rescrape)


if __name__ == "__main__":
    sys.exit(main())
