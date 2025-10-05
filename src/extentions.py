from src.config.base import GBP_EVERYWHERE_DIR, PLEPER_DIR
from typing import List

def build_extension_args() -> List[str]:
    """Build Chromium launch arguments to load unpacked extensions when present.
    Supports multiple extensions at once (GBP Everywhere, PlePer).
    """
    ext_paths: List[str] = []
    try:
        if GBP_EVERYWHERE_DIR.exists():
            ext_paths.append(str(GBP_EVERYWHERE_DIR.resolve()))
    except Exception:
        pass
    try:
        if PLEPER_DIR.exists():
            ext_paths.append(str(PLEPER_DIR.resolve()))
    except Exception:
        pass

    if not ext_paths:
        return []

    # Playwright Chromium requires both flags; when multiple, join paths by comma
    joined = ",".join(ext_paths)
    return [
        f"--disable-extensions-except={joined}",
        f"--load-extension={joined}",
    ]