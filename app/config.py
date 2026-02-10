"""Configuration and constants for the pharmacy drug checker."""

from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR = PROJECT_ROOT / "cache"
SAMPLE_DIR = PROJECT_ROOT / "sample"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

# Ensure cache directory exists
CACHE_DIR.mkdir(exist_ok=True)

# Cache file paths
MHLW_EXCEL_PATH = CACHE_DIR / "mhlw_latest.xlsx"
MHLW_META_PATH = CACHE_DIR / "mhlw_meta.json"

# MHLW URLs and settings
MHLW_MAIN_URL = "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/kouhatu-iyaku/04_00003.html"
# Network timeouts (seconds)
# Keep these small to ensure the manual refresh finishes quickly.
MHLW_SCRAPE_TIMEOUT = 10
MHLW_META_TIMEOUT = 10
MHLW_DOWNLOAD_TIMEOUT = 25

# Drug information filtering
DAYS_BACK = 10  # Number of days back to check for updates

# Excel column search patterns
UPDATE_DATE_COLUMN_PATTERN = "⑳当該品目"  # Look for the specific update date column

# Drug code column patterns (具体的なパターンのみ、誤検知を避ける)
DRUG_CODE_COLUMN_PATTERNS = [
    # Official MHLW format
    "⑤YJコード",
    # YJ code variants (具体的)
    "YJコード", "YJ-コード", "YJコード番号",
    # Drug/Medicine code variants (具体的)
    "医薬品コード", "医薬品キー", "医薬品番号", "医薬品ID",
    "薬品コード", "薬品キー", "薬品番号", "薬品ID",
    # Product/Item code variants (具体的)
    "製品コード", "商品コード", "品目コード",
    # Database codes (具体的)
    "NDBコード", "HOTコード", "JAN",
]

# Drug name column patterns (具体的なパターンのみ、誤検知を避ける)
DRUG_NAME_COLUMN_PATTERNS = [
    # Official MHLW format
    "⑥品名",
    # Brand/Product name variants (具体的)
    "医薬品名", "医薬品正式名", "医薬品正式品名",
    "薬品名", "薬品正式名",
    "品名", "正式品名",
    "製品名", "商品名", "製品正式名",
    # Specific drug name variants (具体的)
    "販売名",
]

# UI Settings
ITEMS_PER_PAGE = 100

# Authentication settings
APP_PIN = os.environ.get("APP_PIN", "")
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "change-this-secret-key")
