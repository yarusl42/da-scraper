from __future__ import annotations

DEBUG = False

import argparse
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Any

import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
import json
import ast
from playwright.sync_api import sync_playwright, BrowserContext, Page

# --- Paths (aligned with other programs) ---
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
COMBINED_DIR = DATA_DIR / "combined"
RESULTS_DIR = DATA_DIR / "results"


def safe_print(msg: str) -> None:
    print(msg, flush=True)


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
        self.root = tk.Tk()
        self.root.title("Maps Evaluator")
        # Set Tkinter window to 520x1000 (WxH)
        self.root.geometry("520x1000")

        self._build_gui()

        # Browser
        self.pw = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # Load data
        self._load_inputs()
        self._ensure_results_dirs()
        self._init_browser()
        self._show_current()

    # ---------------- GUI -----------------
    def _build_gui(self) -> None:
        # Top: Title only
        top = ttk.Frame(self.root)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.title_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.title_var, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        # Colored status dot (●) next to title (make it bigger)
        self.status_dot = ttk.Label(top, text="●")
        try:
            self.status_dot.configure(font=("Segoe UI", 20, "bold"))
        except Exception:
            # Fallback if font family unavailable
            self.status_dot.configure(font=(None, 20, "bold"))
        self.status_dot.pack(side=tk.LEFT, padx=(8, 0))

        # Middle: details panel
        mid = ttk.Frame(self.root)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left column of labels/values
        left = ttk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.fields = {
            "name": tk.StringVar(),
            "address": tk.StringVar(),
            "website": tk.StringVar(),
            "phone": tk.StringVar(),
            "reviews_count": tk.StringVar(),
            "rating": tk.StringVar(),
            "listing_link": tk.StringVar(),
            "status": tk.StringVar(),
            "source_file": tk.StringVar(),
            "categories": tk.StringVar(),
            "map_files": tk.StringVar(),
        }

        def add_row(frame: ttk.Frame, label: str, var: tk.StringVar):
            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{label}:", width=16).pack(side=tk.LEFT)
            ttk.Label(row, textvariable=var, wraplength=450, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True)

        for label, key in [
            ("Address", "address"),
            ("Website", "website"),
            ("Phone", "phone"),
            ("Reviews", "reviews_count"),
            ("Rating", "rating"),
            ("Listing", "listing_link"),
            ("Status", "status"),
            ("Source", "source_file"),
            ("Categories", "categories"),
            
            ("Map files", "map_files"),
        ]:
            add_row(left, label, self.fields[key])

        # Notes directly under info (under mid)
        notes_wrap = ttk.Frame(self.root)
        notes_wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=10, pady=(0, 6))
        ttk.Label(notes_wrap, text="Notes:").pack(anchor=tk.W)
        self.notes = tk.Text(notes_wrap, height=6)
        self.notes.pack(fill=tk.X)

        # Controls directly after Notes
        controls = ttk.Frame(self.root)
        controls.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(controls, text="Open Website", command=self._open_current_website).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Good", command=lambda: self._rate_and_next("good")).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Okay", command=lambda: self._rate_and_next("okay")).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Bad", command=lambda: self._rate_and_next("bad")).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Skip", command=self._skip).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Next", command=self._next).pack(side=tk.LEFT, padx=5)

        # Copy controls for quick clipboard access
        copybar = ttk.Frame(self.root)
        copybar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 6))
        ttk.Button(copybar, text="Copy Link", command=lambda: self._copy_field("listing_link")).pack(side=tk.LEFT, padx=4)
        ttk.Button(copybar, text="Copy Phone", command=lambda: self._copy_field("phone")).pack(side=tk.LEFT, padx=4)
        ttk.Button(copybar, text="Copy Address", command=lambda: self._copy_field("address")).pack(side=tk.LEFT, padx=4)
        ttk.Button(copybar, text="Copy Source", command=lambda: self._copy_field("source_file")).pack(side=tk.LEFT, padx=4)
        ttk.Button(copybar, text="Copy Map Files", command=lambda: self._copy_field("map_files")).pack(side=tk.LEFT, padx=4)

        # No keyboard shortcuts for control or copy actions per request

    # ---------------- Data & Browser -----------------
    def _load_inputs(self) -> None:
        self.rows.clear()
        for i, p in enumerate(self.file_paths):
            if not p.exists():
                messagebox.showerror("Missing file", f"Not found: {p}")
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
            self.notes.delete("1.0", tk.END)
            prev_notes = str(prev.get("notes") or "")
            if prev_notes:
                self.notes.insert("1.0", prev_notes)
        else:
            # Clear notes when no previous
            self.notes.delete("1.0", tk.END)

        # Update status dot color (by saved eval_rating, else by current status)
        rating_tag = None
        if prev is not None:
            rating_tag = str(prev.get("eval_rating") or "").strip().lower()
        if not rating_tag:
            rating_tag = str(d.get("status") or "").strip().lower()
        self._set_status_dot(rating_tag)

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
                messagebox.showinfo("No Website", "This row has no website URL.")
            return
        try:
            self.page.goto(url, timeout=30000)
        except Exception as e:
            safe_print(f"[!] Failed to open website: {e}")
            if not auto:
                messagebox.showerror("Navigation Error", str(e))

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
        notes_text = self.notes.get("1.0", tk.END).strip()
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

    def _set_status_dot(self, rating_tag: str) -> None:
        color = "grey"
        if rating_tag == "good":
            color = "green"
        elif rating_tag == "okay":
            color = "orange"
        elif rating_tag == "bad":
            color = "red"
        self.status_dot.configure(foreground=color)

    def _copy_field(self, key: str) -> None:
        ref = self._current_row()
        if ref is None:
            return
        val = ref.data.get(key)
        if key == "map_files":
            # Copy the raw file map list (one per line), not the formatted display
            v = ref.data.get("map_files")
            files_list = []
            if isinstance(v, list):
                files_list = v
            elif isinstance(v, str):
                s = v.strip()
                if s:
                    try:
                        parsed = json.loads(s)
                        files_list = parsed if isinstance(parsed, list) else [s]
                    except Exception:
                        try:
                            parsed = ast.literal_eval(s)
                            files_list = list(parsed) if isinstance(parsed, (list, tuple)) else [s]
                        except Exception:
                            files_list = [s]
            elif v is not None:
                files_list = [v]
            text = "\n".join(str(x) for x in files_list)
        elif isinstance(val, list):
            text = ", ".join(str(x) for x in val)
        else:
            text = str(val or "")
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            # brief visual hint in title
            self.title_var.set(f"Copied {key} to clipboard")
            self.root.after(1200, lambda: self._refresh_title())
        except Exception:
            pass

    def _refresh_title(self) -> None:
        ref = self._current_row()
        if ref is None:
            self.title_var.set("All done!")
            return
        d = ref.data
        title = f"[{self.current_idx + 1}/{len(self.rows)}] {d.get('name') or ''}"
        self.title_var.set(title)

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
        files = "metal_fabrication_denver_@39_8801791_-105_2843769_10__welders_in_denver_@39_8801791_-105_2843769_10z.xlsx"
        filter_status = None
    return run(files, filter_status)


if __name__ == "__main__":
    raise SystemExit(main())
