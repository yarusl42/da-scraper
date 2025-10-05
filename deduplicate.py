import argparse
import hashlib
from pathlib import Path
from typing import List, Dict, Any
import json as _json
import ast as _ast
import pandas as pd
from src.config.base import DEBUG

# Project paths (align with scraper.py)
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
MAPS_DIR = DATA_DIR / "maps"
COMBINED_DIR = DATA_DIR / "combined"


def safe_print(msg: str) -> None:
    print(msg, flush=True)


def read_map_file(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    # Normalize columns that we rely on
    # Ensure these columns exist even if missing
    required_cols = [
        "listing_link",
        "position",
        "name",
        "categories",
        "website",
        "phone",
        "address",
        "reviews_count",
        "rating",
        "status",
        "source_file",
        "search_volume",
    ]
    for col in required_cols:
        if col not in df.columns:
            df[col] = None
    return df


def _parse_categories_value(val) -> List[str]:
    """Normalize a categories cell into a list[str]. Supports:
    - already a list/tuple
    - JSON array string, e.g. "[\"A\", \"B\"]"
    - Python list literal string, e.g. "['A', 'B']"
    - pipe/comma-separated string, e.g. "A|B" or "A, B"
    """
    # None/NaN -> empty list
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    # If already list/tuple
    if isinstance(val, (list, tuple)):
        items = list(val)
    else:
        s = str(val).strip()
        if not s:
            return []
        # Try JSON first
        try:
            parsed = _json.loads(s)
            if isinstance(parsed, list):
                items = parsed
            else:
                items = [s]
        except Exception:
            # Try Python literal list
            try:
                parsed = _ast.literal_eval(s)
                if isinstance(parsed, (list, tuple)):
                    items = list(parsed)
                else:
                    items = [s]
            except Exception:
                # Fallback: split by separators
                sep = "|" if "|" in s else ","
                items = [p.strip() for p in s.split(sep)]

    # Clean, dedupe (case-insensitive), and keep order
    out: List[str] = []
    seen = set()
    for it in items:
        txt = str(it).strip()
        if not txt:
            continue
        key = txt.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(txt)
    return out


def _normalize_categories_series(series: pd.Series) -> pd.Series:
    return series.apply(_parse_categories_value)


def filter_min_rating(df: pd.DataFrame, min_rating: float) -> pd.DataFrame:
    # Coerce rating to float; drop rows with rating < min_rating or NaN
    ratings = pd.to_numeric(df.get("rating"), errors="coerce")
    mask = ratings >= float(min_rating)
    return df[mask].copy()


def merge_rows_by_listing(rows: List[Dict[str, Any]], source_flags: Dict[str, int]) -> List[Dict[str, Any]]:
    """Deduplicate by listing_link and merge fields.

    - positions -> list of unique sorted ints
    - categories -> prefer first non-empty list; else empty
    - other scalar fields -> first non-null/non-empty
    - add query_filename{i} boolean flags based on presence in each input MAP file
    - add map_files -> list of MAP filenames where the listing appeared
    - carry 'source_file' -> first non-empty source from the original row (e.g. query filename)
    - set status = 'pending' in the merged output
    """
    by_link: Dict[str, Dict[str, Any]] = {}

    def first_non_empty(*vals):
        for v in vals:
            if v is None:
                continue
            if isinstance(v, float) and pd.isna(v):
                continue
            if isinstance(v, str) and not v.strip():
                continue
            return v
        return None

    for r in rows:
        link = r.get("listing_link")
        if not isinstance(link, str) or not link.strip():
            # skip items without a stable key
            continue
        if link not in by_link:
            by_link[link] = {
                "listing_link": link,
                "position": [],
                "name": r.get("name"),
                "categories": r.get("categories") if isinstance(r.get("categories"), list) else [],
                "website": r.get("website"),
                "phone": r.get("phone"),
                "address": r.get("address"),
                "reviews_count": r.get("reviews_count"),
                "rating": r.get("rating"),
                "source_file": r.get("source_file"),  # first seen source
                "search_volume": [],  # align 1:1 with map_files/position
                "map_files": [],  # will aggregate below
                "status": "pending",
            }
            # initialize flags
            for fname, idx in source_flags.items():
                by_link[link][f"query_filename{idx}"] = False

        agg = by_link[link]
        # merge positions together with map_files to preserve encounter order and alignment
        pos = r.get("position")
        map_name = r.get("map_file")
        sv = r.get("search_volume")
        if pd.notna(pos):
            try:
                p = int(pos)
                if isinstance(map_name, str) and map_name:
                    existing_pairs = set(zip(agg["map_files"], agg["position"]))
                    if (map_name, p) not in existing_pairs:
                        agg["position"].append(p)
                        agg["map_files"].append(map_name)
                        agg["search_volume"].append(sv)
                else:
                    # If no map_file, still append position (rare), but alignment may be off
                    # We skip appending search_volume here to preserve alignment with map_files
                    if p not in agg["position"]:
                        agg["position"].append(p)
            except Exception:
                pass

        # merge categories (prefer first non-empty; if current empty and r has list, set)
        cats = r.get("categories")
        if isinstance(cats, list) and cats and not agg["categories"]:
            agg["categories"] = cats

        # scalar fields: keep first non-empty (search_volume handled as per-map list above)
        for key in ("name", "website", "phone", "address", "reviews_count", "rating", "source_file"):
            agg[key] = first_non_empty(agg.get(key), r.get(key))

        # mark source flag using the MAP filename, not source_file
        if isinstance(map_name, str) and map_name in source_flags:
            agg[f"query_filename{source_flags[map_name]}"] = True

    # DO NOT sort positions; keep encounter order to align with map_files

    return list(by_link.values())


def update_input_files_status(input_paths: List[Path], included_links: set[str]) -> None:
    """Update status column in each input map file deterministically.

    - Only consider non-empty listing_link values for matching.
    - Mark rows whose normalized listing_link is in included_links as 'success'.
    - Set all other rows to 'pending'.
    - Force status to be string values to avoid random Excel coercions.
    """
    for p in input_paths:
        try:
            df = pd.read_excel(p)
        except Exception as e:
            safe_print(f"[!] Failed to read {p.name} for status update: {e}")
            continue
        # Ensure status column exists and is string-typed
        if "status" not in df.columns:
            df["status"] = "pending"
        df["status"] = df["status"].astype(str)
        df.loc[df["status"].isna() | (df["status"].str.strip() == "") | (df["status"].str.lower() == "nan"), "status"] = "pending"

        # Normalize listing_link for robust matching
        series = df.get("listing_link")
        if series is None:
            # Nothing to match on in this file
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                df.to_excel(p, index=False)
            except Exception as e:
                safe_print(f"[!] Failed to write updated statuses for {p.name}: {e}")
            continue

        norm_links = series.astype(str).str.strip()
        valid = norm_links.notna() & (norm_links != "") & (norm_links.str.lower() != "nan")
        in_combined = valid & norm_links.isin(included_links)

        # Set 'success' where included; everything else -> 'pending'
        df.loc[in_combined, "status"] = "success"
        df.loc[~in_combined, "status"] = "pending"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            df.to_excel(p, index=False)
        except Exception as e:
            safe_print(f"[!] Failed to write updated statuses for {p.name}: {e}")


def run(files_arg: str, min_rating: float = 4.2) -> int:
    files = [f.strip() for f in files_arg.split(",") if f.strip()]
    if not files:
        safe_print("No input files provided. Nothing to do.")
        return 1

    input_paths: List[Path] = []
    for name in files:
        path = MAPS_DIR / name
        if not path.exists():
            safe_print(f"[!] Not found in {MAPS_DIR}: {name}")
            return 1
        input_paths.append(path)

    # Assign a stable index for source flags
    source_flags = {name: i + 1 for i, name in enumerate(files)}

    # Load and filter
    frames: List[pd.DataFrame] = []
    total_before = 0
    total_after_rating = 0
    for path in input_paths:
        df = read_map_file(path)
        # Preserve original source_file from the map rows if present (e.g., query filename)
        # Do NOT overwrite it with the map filename. Instead, record the map filename separately.
        if "source_file" not in df.columns:
            df["source_file"] = None
        df["map_file"] = path.name
        total_before += len(df)
        # Normalize categories before merging to ensure lists come through
        if "categories" in df.columns:
            df["categories"] = _normalize_categories_series(df["categories"])
        df = filter_min_rating(df, min_rating)
        total_after_rating += len(df)
        frames.append(df)

    if not frames:
        safe_print("No rows after filtering.")
        return 1

    all_rows_df = pd.concat(frames, ignore_index=True)

    # Convert rows to dicts for custom merge
    rows = all_rows_df.to_dict(orient="records")
    merged = merge_rows_by_listing(rows, source_flags)

    # Build final DataFrame in a consistent column order
    # Include query_filename{i} columns in order of input
    flag_cols = [f"query_filename{i+1}" for i in range(len(files))]
    base_cols = [
        "listing_link",
        "position",
        "name",
        "categories",
        "website",
        "phone",
        "address",
        "reviews_count",
        "rating",
        "source_file",
        "search_volume",
        "map_files",
        "status",
    ] + flag_cols

    out_df = pd.DataFrame(merged)
    # add any missing flag columns
    for c in flag_cols:
        if c not in out_df.columns:
            out_df[c] = False
    # ensure column order
    ordered_cols = [c for c in base_cols if c in out_df.columns] + [
        c for c in out_df.columns if c not in base_cols
    ]
    out_df = out_df[ordered_cols]

    # Calculate summary metrics
    before_total = total_before
    after_rating_total = total_after_rating
    removed_by_rating = before_total - after_rating_total

    # Deduplication summary is based on valid (non-empty) listing_link values
    links_series = all_rows_df["listing_link"].astype(str).str.strip()
    valid_mask = links_series.notna() & (links_series != "") & (links_series.str.lower() != "nan")
    valid_count = int(valid_mask.sum())
    unique_links = int(links_series[valid_mask].nunique())
    removed_no_link = int(len(all_rows_df) - valid_count)
    removed_by_dedup = int(valid_count - unique_links)
    added_to_target = int(len(out_df))  # should equal unique_links

    # Output filename (short, Windows-safe)
    def build_combined_filename(file_names: List[str]) -> str:
        # Determine extension from first file
        ext = (file_names[0].split(".")[-1] if "." in file_names[0] else "xlsx")
        joined = "__".join([fn.rsplit(".", 1)[0] for fn in file_names])
        # If too long, fall back to hashed name to avoid MAX_PATH issues on Windows
        if len(joined) > 120:
            digest = hashlib.md5("__".join(file_names).encode("utf-8")).hexdigest()[:10]
            return f"combined_{len(file_names)}_{digest}.{ext}"
        return f"{joined}.{ext}"

    out_name = build_combined_filename(files)
    out_path = COMBINED_DIR / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write combined
    out_df.to_excel(out_path, index=False)
    safe_print(f"[✓] Combined written: {out_path}")

    # Update input files statuses
    included_links = set(
        s for s in out_df["listing_link"].dropna().astype(str).str.strip().tolist()
        if s and s.lower() != "nan"
    )
    update_input_files_status(input_paths, included_links)

    safe_print(f"[✓] Updated status in {len(input_paths)} source files")
    safe_print(f"[i] Rows before: {before_total}")
    safe_print(f"[i] Removed by rating (< {min_rating}): {removed_by_rating}")
    safe_print(f"[i] Removed by deduplication: {removed_by_dedup}")
    safe_print(f"[i] Removed due to missing listing_link: {removed_no_link}")
    safe_print(f"[i] Rows in combined (added to target): {added_to_target}")
    return 0


def main() -> int:
    if not DEBUG:
        parser = argparse.ArgumentParser(description="Deduplicate & merge map files")
        parser.add_argument("files", type=str, help="Comma-separated list of .xlsx filenames located in ./data/maps/")
        parser.add_argument(
            "--min-rating",
            type=float,
            default=4.2,
            help="Minimum rating threshold (inclusive). Rows with lower rating are filtered out.",
        )
        args = parser.parse_args()
        files = args.files
        min_rating = args.min_rating
    else:
        files = "attic_insulation_denver_@39_7400428_-105_0508011_11z.xlsx,insulation_companies_denver_@39_7400428_-105_0508011_11z.xlsx,insulation_denver_colorado_@39_7400428_-105_0508011_11z.xlsx,spray_foam_insulation_denver_@39_7400428_-105_0508011_11z.xlsx"
        min_rating = 4.2
    return run(files, min_rating)


if __name__ == "__main__":
    main()
