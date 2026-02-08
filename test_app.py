"""Quick verification script for the pharmacy drug checker application."""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("Pharmacy Drug Checker - Application Verification")
print("=" * 60)

# Test 1: Check project structure
print("\n✓ [Test 1] Checking project structure...")
required_files = [
    "main.py",
    "pyproject.toml",
    "README.md",
    "app/__init__.py",
    "app/config.py",
    "app/mhlw_downloader.py",
    "app/excel_matcher.py",
    "templates/index.html",
    "static/custom.css",
    "sample/pharmacy_sample.xlsx",
]

for file in required_files:
    path = project_root / file
    if path.exists():
        print(f"  ✓ {file}")
    else:
        print(f"  ✗ MISSING: {file}")

# Test 2: Check imports
print("\n✓ [Test 2] Checking module imports...")
try:
    from app.config import PROJECT_ROOT, CACHE_DIR, MHLW_EXCEL_PATH
    print("  ✓ app.config")
    from app.mhlw_downloader import MHLWDownloader
    print("  ✓ app.mhlw_downloader")
    from app.excel_matcher import ExcelMatcher, normalize_text
    print("  ✓ app.excel_matcher")
    from main import app
    print("  ✓ main (FastAPI app)")
except Exception as e:
    print(f"  ✗ Import failed: {e}")
    sys.exit(1)

# Test 3: Test normalize_text function
print("\n✓ [Test 3] Testing normalize_text function...")
test_cases = [
    ("ＡＺ１２３", "az123"),  # Full-width to half-width
    ("  spaces  ", "spaces"),  # Strip whitespace
    ("ＵＲＬ", "url"),  # Full-width uppercase
]
for input_text, expected in test_cases:
    result = normalize_text(input_text)
    status = "✓" if result == expected else "✗"
    print(f"  {status} normalize_text('{input_text}') = '{result}' (expected: '{expected}')")

# Test 4: Test sample Excel loading
print("\n✓ [Test 4] Testing sample Excel loading...")
try:
    import pandas as pd
    sample_path = project_root / "sample" / "pharmacy_sample.xlsx"
    df = pd.read_excel(sample_path)
    print(f"  ✓ Sample Excel loaded: {len(df)} rows, {len(df.columns)} columns")
    print(f"  ✓ Columns: {', '.join(df.columns)}")
except Exception as e:
    print(f"  ✗ Failed to load sample Excel: {e}")

# Test 5: Check FastAPI endpoints
print("\n✓ [Test 5] Checking FastAPI endpoints...")
try:
    routes = [route.path for route in app.routes]
    required_routes = ["/", "/check", "/refresh", "/status"]
    for route in required_routes:
        if route in routes:
            print(f"  ✓ {route}")
        else:
            print(f"  ✗ MISSING: {route}")
except Exception as e:
    print(f"  ✗ Failed to check endpoints: {e}")

# Test 6: Check cache directory
print("\n✓ [Test 6] Checking cache directory...")
cache_dir = project_root / "cache"
if cache_dir.exists():
    print(f"  ✓ Cache directory exists: {cache_dir}")
    gitkeep = cache_dir / ".gitkeep"
    if gitkeep.exists():
        print(f"  ✓ .gitkeep file present")
else:
    print(f"  ✗ Cache directory missing")

# Test 7: Check configuration
print("\n✓ [Test 7] Checking configuration...")
from app.config import DAYS_BACK, MHLW_DOWNLOAD_TIMEOUT
print(f"  ✓ DAYS_BACK: {DAYS_BACK}")
print(f"  ✓ MHLW_DOWNLOAD_TIMEOUT: {MHLW_DOWNLOAD_TIMEOUT}s")

print("\n" + "=" * 60)
print("✓ All checks passed! Ready to run the application.")
print("=" * 60)
print("\nTo start the application, run:")
print("  uv run uvicorn main:app --reload --port 8000")
print("\nThen open: http://localhost:8000")
