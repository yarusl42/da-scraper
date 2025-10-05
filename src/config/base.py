from pathlib import Path

DEBUG = True
HEADLESS = False

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
QUERIES_DIR = DATA_DIR / "queries"
MAPS_DIR = DATA_DIR / "maps"
PROFILE_DIR = PROJECT_ROOT / "browser_profile"
EXTENSIONS_DIR = PROJECT_ROOT / "extensions"
GBP_EVERYWHERE_DIR = EXTENSIONS_DIR / "gbp-everywhere"
PLEPER_DIR = EXTENSIONS_DIR / "PlePer"
DEBUG_DIR = DATA_DIR / "debug"
COMBINED_DIR = DATA_DIR / "combined"
RESULTS_DIR = DATA_DIR / "results"
