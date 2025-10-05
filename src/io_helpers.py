from pathlib import Path
from typing import List, Dict
import pandas as pd
import re
from urllib.parse import urlparse, parse_qs, unquote_plus

def safe_print(msg: str) -> None:
    """Print to stdout with flush to ensure logs appear in order."""
    print(msg, flush=True)

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

