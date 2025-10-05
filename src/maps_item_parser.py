from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any

from bs4 import BeautifulSoup


@dataclass
class MapsItem:
    name: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    listing_link: Optional[str] = None
    status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clean_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _extract_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = re.search(r"(\d[\d,]*)", s)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except Exception:
        return None

_NOISE_CATEGORIES = {
    "gmb cat.",
    "gmb cat",
    "find more",
    "basic ai teleport review post",
}

def _normalize_category(cat: str) -> str:
    c = _clean_text(cat) or ""
    # Remove a trailing colon and normalize spaces/case for comparison
    c = c.rstrip(": ")
    return c

def _is_noise_category(cat: str) -> bool:
    base = _normalize_category(cat).lower()
    return base in _NOISE_CATEGORIES


def _extract_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    m = re.search(r"\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def parse_maps_item_container(container_html: str) -> MapsItem:
    soup = BeautifulSoup(container_html, "html.parser")
    container = soup.select_one("div.Nv2PK") or soup
    return parse_maps_item_soup(container)


def parse_maps_item_soup(container) -> MapsItem:
    item = MapsItem()

    # Listing link and name
    a = container.select_one("a.hfpxzc")
    if a:
        href = a.get("href", "")
        if href.startswith("http"):
            item.listing_link = href
        # aria-label often equals the business name
        item.name = _clean_text(a.get("aria-label"))

    # Fallback name from headline div
    if not item.name:
        name_div = container.select_one("div.qBF1Pd")
        if name_div:
            item.name = _clean_text(name_div.get_text(" "))

    # Rating and reviews
    rating_wrap = container.select_one("span.ZkP5Je[aria-label]")
    if rating_wrap:
        rating_val = rating_wrap.select_one("span.MW4etd")
        if rating_val:
            item.rating = _extract_float(rating_val.get_text())
        reviews_val = rating_wrap.select_one("span.UY7F9")
        if reviews_val:
            item.reviews_count = _extract_int(reviews_val.get_text())

    # Categories (explicit list if present)
    # Example container: <div class="category-list-display btn-gmb-category-tool"> ... </div>
    explicit_cat_div = container.select_one("div.category-list-display")
    if explicit_cat_div:
        # Collect text from likely elements; skip empty/icon-only bits
        raw_parts = []
        for el in explicit_cat_div.find_all(["a", "span", "div"], recursive=True):
            txt = _clean_text(el.get_text(" "))
            if txt:
                raw_parts.append(txt)
        # Also split on common separators
        cats: list[str] = []
        for p in raw_parts:
            for piece in re.split(r"\s*[·,|/]\s*", p):
                piece = piece.strip()
                if piece and len(piece) > 1 and not _is_noise_category(piece):
                    cats.append(piece)
        # De-duplicate while preserving order
        seen = set()
        deduped = []
        for c in cats:
            norm = _normalize_category(c)
            key = norm.lower()
            if key and key not in seen and not _is_noise_category(norm):
                seen.add(key)
                deduped.append(norm)
        item.categories = deduped

    # Category, address, phone, and status lines live in W4Efsd blocks
    w_blocks = container.select("div.W4Efsd")

    # First block with category/address can be nested; flatten text segments
    category = None
    address = None
    for block in w_blocks:
        text = _clean_text(block.get_text(" "))
        if not text:
            continue
        # Identify phone line by known class
        phone_span = block.select_one("span.UsdlK")
        if phone_span:
            item.phone = _clean_text(phone_span.get_text())
        # A status line often contains "Closed"/"Open" or "Opens"/"Closes"
        if any(kw in text.lower() for kw in ("open", "closed", "closes", "opens")) and not item.status:
            item.status = text
        # Category/address line heuristic: contains dot separators
        if "·" in text and ("open" not in text.lower()) and ("closed" not in text.lower()):
            # Example: "Steel fabricator · [icon] · 1401 Umatilla St"
            parts = [p.strip() for p in text.split("·") if p.strip()]
            # Filter out icon placeholders like single characters from symbols
            parts = [p for p in parts if len(p) > 2]
            if parts:
                if not category:
                    category = parts[0]
                if not address and len(parts) >= 2:
                    # Prefer the last segment as address if it looks like one
                    address = parts[-1]
    # If explicit categories were not found above, fall back to a single inferred category
    if not item.categories and category and not _is_noise_category(category):
        item.categories = [_normalize_category(category)]
    item.address = _clean_text(address)

    # Website
    # Try by aria-label that starts with "Visit <Name>'s website"
    website_a = None
    for cand in container.select("a[aria-label]"):
        aria = (cand.get("aria-label") or "").lower()
        if "website" in aria:
            website_a = cand
            break
    # Fallback by data-value
    if not website_a:
        website_a = container.select_one("a[data-value=Website]")
    if website_a and website_a.get("href").startswith("http"):
        item.website = website_a.get("href")

    return item


def parse_item_file(path: Path) -> MapsItem:
    html = path.read_text(encoding="utf-8")
    # In the test sample the file contains a single item container
    return parse_maps_item_container(html)


if __name__ == "__main__":
    # Test against testing/item.html and print the parsed JSON
    project_root = Path(__file__).resolve().parent.parent
    sample_path = project_root / "testing" / "item.html"
    if not sample_path.exists():
        print(f"Sample not found: {sample_path}")
    else:
        item = parse_item_file(sample_path)
        print(json.dumps(item.to_dict(), ensure_ascii=False, indent=2))
