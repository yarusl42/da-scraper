import argparse
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Any
from src.config.base import DEBUG
import pandas as pd
import json
import ast
from playwright.sync_api import sync_playwright, BrowserContext, Page
from src.config.base import COMBINED_DIR, RESULTS_DIR, PROJECT_ROOT
from src.evaluator_gui import (
    build_gui,
    set_status_dot,
    set_notes,
    get_notes,
    show_missing_file,
    show_info_no_website,
    show_nav_error,
)
from src.io_helpers import safe_print

@dataclass
class EvalRowRef:
    file_index: int
    row_index: int
    file_path: Path
    data: Dict[str, Any]


class EvaluatorApp:
    def __init__(self, files: List[str], filter_status: Optional[str] = None):
        self.files = files
        self.filter_status = (filter_status or "").strip().lower() or None
        self.file_paths: List[Path] = [COMBINED_DIR / f for f in files]
        self.results_paths: List[Path] = [RESULTS_DIR / f for f in files]
        self.frames: List[pd.DataFrame] = []
        self.rows: List[EvalRowRef] = []
        self.current_idx: int = 0

        # GUI
        self.root = build_gui(self, "520x1000")

        # Browser
        self.pw = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # Load data
        self._load_inputs()
        self._ensure_results_dirs()
        self._init_browser()
        self._show_current()

    # ---------------- GUI (moved to src/evaluator_gui.py) -----------------

    # ---------------- Data & Browser -----------------
    def _load_inputs(self) -> None:
        self.rows.clear()
        for i, p in enumerate(self.file_paths):
            if not p.exists():
                show_missing_file(p)
                continue
            df = pd.read_excel(p)
            # Optional filtering by status (pending|good|bad|okay) applied to the parent combined file
            if self.filter_status and "status" in df.columns:
                mask = df["status"].astype(str).str.strip().str.lower() == self.filter_status
                df = df[mask]
            self.frames.append(df)
            for idx, row in df.iterrows():
                self.rows.append(EvalRowRef(i, idx, p, row.to_dict()))
        safe_print(f"Loaded {len(self.rows)} rows from {len(self.frames)} file(s)")

    def _ensure_results_dirs(self) -> None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    def _init_browser(self) -> None:
        try:
            self.pw = sync_playwright().start()
            # viewport=None allows the page to resize with the window natively
            self.context = self.pw.chromium.launch_persistent_context(
                user_data_dir=str((PROJECT_ROOT / "browser_profile").resolve()),
                headless=False,
                viewport=None,
                args=[
                    "--window-size=1400,900",
                ],
            )
            self.page = self.context.new_page()
            try:
                # Ensure the window reflects the desired size
                self.page.set_viewport_size({"width": 1400, "height": 900})
            except Exception:
                pass
        except Exception as e:
            safe_print(f"[!] Failed to start browser: {e}")
            self.context = None
            self.page = None

    # ---------------- Helpers -----------------
    def _current_row(self) -> Optional[EvalRowRef]:
        if 0 <= self.current_idx < len(self.rows):
            return self.rows[self.current_idx]
        return None

    def _format_map_details(self, d: Dict[str, Any]) -> str:
        """Return bullet lines combining map_file + position + search_volume aligned by index.
        Format: "- {map_file} (#pos {x}, sv {y})" per line.
        Tolerates missing lists or scalar values.
        """
        def _to_list(v):
            # Already a list
            if isinstance(v, list):
                return v
            # None/NaN -> []
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return []
            # Try parse from string as JSON, then Python literal; else wrap
            if isinstance(v, str):
                s = v.strip()
                if not s:
                    return []
                try:
                    parsed = json.loads(s)
                    return parsed if isinstance(parsed, list) else [parsed]
                except Exception:
                    try:
                        parsed = ast.literal_eval(s)
                        return list(parsed) if isinstance(parsed, (list, tuple)) else [parsed]
                    except Exception:
                        return [s]
            # Fallback: wrap scalar
            return [v]

        map_files = _to_list(d.get("map_files"))
        positions = _to_list(d.get("position"))
        search_vols = _to_list(d.get("search_volume"))

        n = len(map_files)
        lines = []
        for i in range(n):
            f = str(map_files[i].split("_@")[0]) if i < len(map_files) else ""
            # pick matching position and search_volume if present
            pos = positions[i] if i < len(positions) else None
            sv = search_vols[i] if i < len(search_vols) else None
            pos_txt = "" if (pos is None or (isinstance(pos, float) and pd.isna(pos))) else str(pos)
            sv_txt = "" if (sv is None or (isinstance(sv, float) and pd.isna(sv))) else str(sv)
            lines.append(f"- {f} (#pos {pos_txt}, sv {sv_txt})")
        return "\n".join(lines)

    def _show_current(self) -> None:
        ref = self._current_row()
        if ref is None:
            self.title_var.set("All done!")
            for v in self.fields.values():
                v.set("")
            if hasattr(self, "status_dot"):
                self.status_dot.configure(foreground="grey")
            return

        d = ref.data
        title = f"[{self.current_idx + 1}/{len(self.rows)}] {d.get('name') or ''}"
        self.title_var.set(title)

        # Pretty display conversions
        categories = d.get("categories")
        if isinstance(categories, list):
            categories_str = " | ".join(categories)
        else:
            categories_str = str(categories) if categories is not None else ""

        position = d.get("position")
        if isinstance(position, list):
            position_str = ", ".join(str(x) for x in position)
        else:
            position_str = str(position) if position is not None else ""

        # Build a bullet list for map files with aligned position and search_volume
        map_files_str = self._format_map_details(d)

        # Fill fields
        self.fields["name"].set(str(d.get("name") or ""))
        self.fields["address"].set(str(d.get("address") or ""))
        self.fields["website"].set(str(d.get("website") or ""))
        self.fields["phone"].set(str(d.get("phone") or ""))
        self.fields["reviews_count"].set(str(d.get("reviews_count") or ""))
        self.fields["rating"].set(str(d.get("rating") or ""))
        self.fields["listing_link"].set(str(d.get("listing_link") or ""))
        self.fields["status"].set(str(d.get("status") or ""))
        self.fields["source_file"].set(str(d.get("source_file") or ""))
        self.fields["categories"].set(categories_str)
        self.fields["map_files"].set(map_files_str)

        # Load previous eval (notes + eval_rating) if available
        prev = self._load_existing_eval(ref)
        if prev is not None:
            # Notes
            prev_notes = str(prev.get("notes") or "")
            set_notes(self, prev_notes)
        else:
            set_notes(self, "")

        # Update status dot color (by saved eval_rating, else by current status)
        rating_tag = None
        if prev is not None:
            rating_tag = str(prev.get("eval_rating") or "").strip().lower()
        if not rating_tag:
            rating_tag = str(d.get("status") or "").strip().lower()
        set_status_dot(self.status_dot, rating_tag)

        # Auto-open website if available
        self._open_current_website(auto=True)

    def _open_current_website(self, auto: bool = False) -> None:
        if not self.page:
            return
        ref = self._current_row()
        if ref is None:
            return
        url = (ref.data.get("website") or "").strip()
        if not url:
            if not auto:
                show_info_no_website()
            return
        try:
            self.page.goto(url, timeout=30000)
        except Exception as e:
            safe_print(f"[!] Failed to open website: {e}")
            if not auto:
                show_nav_error(e)

    def _rate_and_next(self, rating: str) -> None:
        self._save_current_result(rating)
        # Update parent combined file status for this row
        self._update_parent_status(rating)
        self._next()

    def _skip(self) -> None:
        # Do not save or update status; just move to next
        self._next()

    def _next(self) -> None:
        self.current_idx += 1
        self._show_current()

    def _save_current_result(self, rating: str) -> None:
        ref = self._current_row()
        if ref is None:
            return
        notes_text = get_notes(self)
        eval_time = dt.datetime.now().isoformat(timespec="seconds")

        # Append to results file for the corresponding input file
        out_path = self.results_paths[ref.file_index]
        out_path.parent.mkdir(parents=True, exist_ok=True)

        new_row = dict(ref.data)
        new_row["eval_rating"] = rating
        new_row["eval_time"] = eval_time
        new_row["notes"] = notes_text

        try:
            if out_path.exists():
                df_old = pd.read_excel(out_path)
                df_new = pd.concat([df_old, pd.DataFrame([new_row])], ignore_index=True)
            else:
                df_new = pd.DataFrame([new_row])
            df_new.to_excel(out_path, index=False)
        except Exception as e:
            safe_print(f"[!] Failed to save result to {out_path.name}: {e}")

    def _load_existing_eval(self, ref) -> Optional[Dict[str, Any]]:
        """Return the most recent saved evaluation row for this listing_link, if any."""
        out_path = self.results_paths[ref.file_index]
        if not out_path.exists():
            return None
        try:
            df = pd.read_excel(out_path)
        except Exception:
            return None
        listing_link = str(ref.data.get("listing_link") or "").strip()
        if not listing_link or "listing_link" not in df.columns:
            return None
        matches = df[df["listing_link"].astype(str).str.strip() == listing_link]
        if matches.empty:
            return None
        # Return the last (most recent) match
        return matches.iloc[-1].to_dict()

    # _set_status_dot, _copy_field, _refresh_title moved to evaluator_gui helpers

    def _update_parent_status(self, rating: str) -> None:
        ref = self._current_row()
        if ref is None:
            return
        p = ref.file_path
        try:
            df = pd.read_excel(p)
        except Exception as e:
            safe_print(f"[!] Could not read parent combined file for status update: {e}")
            return

        # Identify row by listing_link; fallback by index if necessary
        listing_link = str(ref.data.get("listing_link") or "").strip()
        if listing_link and "listing_link" in df.columns:
            mask = df["listing_link"].astype(str).str.strip() == listing_link
            if mask.any():
                df.loc[mask, "status"] = rating
            else:
                # fallback by positional index within file
                try:
                    df.loc[ref.row_index, "status"] = rating
                except Exception:
                    pass
        else:
            try:
                df.loc[ref.row_index, "status"] = rating
            except Exception:
                pass
        try:
            df.to_excel(p, index=False)
        except Exception as e:
            safe_print(f"[!] Failed to write parent combined file: {e}")

    def run(self) -> None:
        self.root.mainloop()
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        try:
            if self.pw:
                self.pw.stop()
        except Exception:
            pass


def run(files_arg: str, filter_status: Optional[str] = None) -> int:
    files = [f.strip() for f in files_arg.split(",") if f.strip()]
    if not files:
        safe_print("No input files provided. Nothing to do.")
        return 1

    app = EvaluatorApp(files, filter_status=filter_status)
    app.run()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    if not DEBUG:
        parser = argparse.ArgumentParser(description="Evaluate combined map results with a GUI")
        parser.add_argument(
            "files",
            type=str,
            help="Comma-separated list of .xlsx filenames located in ./data/combined/",
        )
        parser.add_argument(
            "--filter",
            type=str,
            choices=["pending", "good", "bad", "okay"],
            help="Filter rows by status in the combined file (pending|good|bad|okay)",
        )
        args = parser.parse_args(argv)
        files = args.files
        filter_status = args.filter
    else:
        files = "combined_4_25c77f6ea7.xlsx"
        filter_status = None
    return run(files, filter_status)


if __name__ == "__main__":
    raise SystemExit(main())
