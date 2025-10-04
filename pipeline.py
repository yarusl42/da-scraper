from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import List

# Reuse modules from this project
from scraper import run as scraper_run, read_queries_xlsx, query_to_human_slug, QUERIES_DIR, MAPS_DIR
from deduplicate import run as dedup_run, COMBINED_DIR
from evaluator import run as evaluator_run


def safe_print(msg: str) -> None:
    print(msg, flush=True)


def _expected_map_filenames(query_file: Path) -> List[str]:
    """Return a list of expected MAP .xlsx filenames (slug.xlsx) for rows with status == 'success'.
    Uses scraper.read_queries_xlsx to ensure normalized columns.
    """
    df = read_queries_xlsx(query_file)
    if "query_url" not in df.columns:
        return []
    # Prefer rows that are marked success by the scraper
    # If status missing, fallback to all non-empty URLs
    mask_success = (df.get("status").astype(str).str.strip().str.lower() == "success") if "status" in df.columns else None
    if mask_success is None or not mask_success.any():
        mask = df["query_url"].astype(str).str.strip() != ""
        urls = df.loc[mask, "query_url"].astype(str).tolist()
    else:
        urls = df.loc[mask_success, "query_url"].astype(str).tolist()
    slugs = [query_to_human_slug(u) for u in urls]
    return [f"{slug}.xlsx" for slug in slugs]


def run_pipeline(query_filename: str, rescrape: bool = False, min_rating: float = 4.2) -> int:
    # 1) Validate query file exists under data/queries
    query_path = QUERIES_DIR / query_filename
    if not query_path.exists():
        safe_print(f"[!] Not found in {QUERIES_DIR}: {query_filename}")
        return 1

    # 2) Run scraper for that file
    safe_print(f"[→] Scraping from {query_filename}...")
    rc = scraper_run(query_filename, rescrape)
    if rc != 0:
        safe_print("[!] Scraper returned non-zero exit code; continuing best-effort.")

    # 3) Determine which map files to deduplicate
    candidates = _expected_map_filenames(query_path)
    existing = [name for name in candidates if (MAPS_DIR / name).exists()]
    if not existing:
        safe_print("[!] No map files found to combine after scraping.")
        return 1

    # 4) Run deduplication on those map files
    maps_arg = ",".join(existing)
    safe_print(f"[→] Combining {len(existing)} map file(s) with min_rating={min_rating}...")
    rc = dedup_run(maps_arg, min_rating)
    if rc != 0:
        safe_print("[!] Deduplicate returned non-zero exit code; attempting to locate combined file anyway.")

    # Reconstruct the combined filename (mirrors logic inside deduplicate.run)
    def build_combined_filename(file_names: List[str]) -> str:
        ext = (file_names[0].split(".")[-1] if "." in file_names[0] else "xlsx")
        joined = "__".join([fn.rsplit(".", 1)[0] for fn in file_names])
        if len(joined) > 120:
            digest = hashlib.md5("__".join(file_names).encode("utf-8")).hexdigest()[:10]
            return f"combined_{len(file_names)}_{digest}.{ext}"
        return f"{joined}.{ext}"

    combined_name = build_combined_filename(existing)
    combined_path = COMBINED_DIR / combined_name
    if not combined_path.exists():
        safe_print(f"[!] Combined file not found at {combined_path}. Aborting before evaluator.")
        return 1

    # 5) Launch evaluator for the combined file
    safe_print(f"[→] Launching evaluator for {combined_name}...")
    safe_print("[i] RUNNING: python evaluator.py " + combined_name)
    rc = evaluator_run(combined_name)
    return rc


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run full pipeline: scrape -> deduplicate -> evaluate")
    parser.add_argument(
        "query_file",
        type=str,
        help="Single .xlsx filename located in ./data/queries/",
    )
    parser.add_argument(
        "--rescrape",
        action="store_true",
        help="Force re-process all rows in the query file regardless of their current status.",
    )
    parser.add_argument(
        "--min-rating",
        type=float,
        default=4.2,
        help="Minimum rating threshold for deduplication (inclusive).",
    )
    args = parser.parse_args(argv)
    return run_pipeline(args.query_file, rescrape=args.rescrape, min_rating=args.min_rating)


if __name__ == "__main__":
    raise SystemExit(main())
