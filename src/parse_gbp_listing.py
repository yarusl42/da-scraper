from typing import List, Dict
from bs4 import BeautifulSoup
from src.maps_item_parser import parse_maps_item_container

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
