from src.config.base import PROFILE_DIR
from playwright.sync_api import sync_playwright,  BrowserContext
from src.extentions import build_extension_args
from typing import Tuple

def launch_persistent_context(headless: bool) -> Tuple[BrowserContext, any]:
    """Launch a persistent Chromium context that saves cookies/profile under PROFILE_DIR.
    If the GBP Everywhere extension is present (unpacked) under GBP_EVERYWHERE_DIR,
    load it. Returns (context, pw_controller) so the caller can close both.
    """
    pw = sync_playwright().start()
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    args = []
    # Load supported unpacked extensions if present (GBP Everywhere, PlePer)
    try:
        args.extend(build_extension_args())
    except Exception:
        pass

    context = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR.resolve()),
        headless=headless,
        viewport={"width": 1280, "height": 900},
        args=args,
    )
    # Set a default timeout for all pages in this context
    context.set_default_timeout(30000)
    return context, pw

