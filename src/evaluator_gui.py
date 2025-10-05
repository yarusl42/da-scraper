from __future__ import annotations

from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import ttk, messagebox
import json
import ast
import pandas as pd


def build_gui(app, geometry: str) -> None:
    app.root = tk.Tk()
    app.root.title("Maps Evaluator")
    app.root.geometry(geometry)
    top = ttk.Frame(app.root)
    top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

    app.title_var = tk.StringVar(value="")
    ttk.Label(top, textvariable=app.title_var, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
    app.status_dot = ttk.Label(top, text="●")
    try:
        app.status_dot.configure(font=("Segoe UI", 20, "bold"))
    except Exception:
        app.status_dot.configure(font=(None, 20, "bold"))
    app.status_dot.pack(side=tk.LEFT, padx=(8, 0))

    mid = ttk.Frame(app.root)
    mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

    left = ttk.Frame(mid)
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    app.fields = {
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
        add_row(left, label, app.fields[key])

    notes_wrap = ttk.Frame(app.root)
    notes_wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=10, pady=(0, 6))
    ttk.Label(notes_wrap, text="Notes:").pack(anchor=tk.W)
    app.notes = tk.Text(notes_wrap, height=6)
    app.notes.pack(fill=tk.X)

    controls = ttk.Frame(app.root)
    controls.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
    ttk.Button(controls, text="Open Website", command=lambda: app._open_current_website()).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls, text="Good", command=lambda: app._rate_and_next("good")).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls, text="Okay", command=lambda: app._rate_and_next("okay")).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls, text="Bad", command=lambda: app._rate_and_next("bad")).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls, text="Skip", command=app._skip).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls, text="Next", command=app._next).pack(side=tk.LEFT, padx=5)

    copybar = ttk.Frame(app.root)
    copybar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 6))
    ttk.Button(copybar, text="Copy Link", command=lambda: copy_field(app, "listing_link")).pack(side=tk.LEFT, padx=4)
    ttk.Button(copybar, text="Copy Phone", command=lambda: copy_field(app, "phone")).pack(side=tk.LEFT, padx=4)
    ttk.Button(copybar, text="Copy Address", command=lambda: copy_field(app, "address")).pack(side=tk.LEFT, padx=4)
    ttk.Button(copybar, text="Copy Source", command=lambda: copy_field(app, "source_file")).pack(side=tk.LEFT, padx=4)
    ttk.Button(copybar, text="Copy Map Files", command=lambda: copy_field(app, "map_files")).pack(side=tk.LEFT, padx=4)

    return app.root

def set_status_dot(status_dot_widget: Any, rating_tag: str) -> None:
    color = "grey"
    if rating_tag == "good":
        color = "green"
    elif rating_tag == "okay":
        color = "orange"
    elif rating_tag == "bad":
        color = "red"
    status_dot_widget.configure(foreground=color)


def set_notes(app, text: str) -> None:
    app.notes.delete("1.0", tk.END)
    if text:
        app.notes.insert("1.0", text)


def get_notes(app) -> str:
    return app.notes.get("1.0", tk.END).strip()


def copy_field(app, key: str) -> None:
    ref = app._current_row()
    if ref is None:
        return
    val = ref.data.get(key)
    if key == "map_files":
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
        app.root.clipboard_clear()
        app.root.clipboard_append(text)
        app.title_var.set(f"Copied {key} to clipboard")
        app.root.after(1200, lambda: refresh_title(app))
    except Exception:
        pass


def refresh_title(app) -> None:
    ref = app._current_row()
    if ref is None:
        app.title_var.set("All done!")
        return
    d = ref.data
    title = f"[{app.current_idx + 1}/{len(app.rows)}] {d.get('name') or ''}"
    app.title_var.set(title)


def show_missing_file(p: Path) -> None:
    messagebox.showerror("Missing file", f"Not found: {p}")


def show_info_no_website() -> None:
    messagebox.showinfo("No Website", "This row has no website URL.")


def show_nav_error(e: Exception) -> None:
    messagebox.showerror("Navigation Error", str(e))
