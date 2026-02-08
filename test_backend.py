"""Test backend components comprehensively."""

import sys
from pathlib import Path
import pandas as pd

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("薬局向けアプリ - バックエンド総合テスト")
print("=" * 80)

# Test 1: Check MHLW data file exists
print("\n✅ Test 1: MHLW データファイルの存在確認")
from app.config import MHLW_EXCEL_PATH, SAMPLE_DIR
print(f"   MHLW Excel path: {MHLW_EXCEL_PATH}")
print(f"   Exists: {MHLW_EXCEL_PATH.exists()}")

if MHLW_EXCEL_PATH.exists():
    mhlw_df = pd.read_excel(MHLW_EXCEL_PATH)
    print(f"   Rows: {len(mhlw_df)}")
    print(f"   Columns: {list(mhlw_df.columns)}")
    print(f"\n   Data preview:")
    print(mhlw_df.to_string())
else:
    print("   ❌ MHLW file not found!")
    sys.exit(1)

# Test 2: Check sample pharmacy file
print("\n✅ Test 2: サンプル薬局ファイルの確認")
sample_path = SAMPLE_DIR / "pharmacy_sample.xlsx"
print(f"   Sample path: {sample_path}")
print(f"   Exists: {sample_path.exists()}")

if sample_path.exists():
    pharmacy_df = pd.read_excel(sample_path)
    print(f"   Rows: {len(pharmacy_df)}")
    print(f"   Columns: {list(pharmacy_df.columns)}")
    print(f"\n   Data preview:")
    print(pharmacy_df.to_string())
else:
    print("   ❌ Sample file not found!")
    sys.exit(1)

# Test 3: Test ExcelMatcher
print("\n✅ Test 3: ExcelMatcher の動作確認")
from app.excel_matcher import ExcelMatcher, normalize_text

matcher = ExcelMatcher()
print(f"   MHLW loaded: {matcher.mhlw_df is not None}")
if matcher.mhlw_df is not None:
    print(f"   MHLW rows: {len(matcher.mhlw_df)}")
    print(f"   Update date column: {matcher.update_date_column}")
    print(f"   Drug code column: {matcher.drug_code_column}")
    print(f"   Drug name column: {matcher.drug_name_column}")

# Test 4: Test normalize_text
print("\n✅ Test 4: テキスト正規化の確認")
test_cases = [
    ("アスピリン錠", "アスピリン錠"),
    ("ＡＳＰ１２３", "asp123"),
    ("  spaces  ", "spaces"),
]
for input_text, expected in test_cases:
    result = normalize_text(input_text)
    status = "✓" if result == expected.lower() else "✗"
    print(f"   {status} normalize('{input_text}') = '{result}'")

# Test 5: Test matching
print("\n✅ Test 5: 照合ロジックのテスト")
print("   Input pharmacy data:")
print(f"   - 薬品コード: {pharmacy_df['薬品コード'].tolist()}")
print(f"   - 薬品名: {pharmacy_df['薬品名'].tolist()}")

result = matcher.match_and_filter(pharmacy_df, days_back=10)
print(f"\n   Matching results:")
print(f"   - Success: {result['success']}")
print(f"   - Message: {result['message']}")
print(f"   - Stats: {result['stats']}")
print(f"   - Data rows: {len(result['data'])}")

if result['data']:
    print(f"\n   Matched data (first 2 rows):")
    for i, row in enumerate(result['data'][:2]):
        print(f"\n   Row {i+1}:")
        for key, value in row.items():
            print(f"     {key}: {value}")
else:
    print("   ❌ No matches found!")

# Test 6: Test with different filter days
print("\n✅ Test 6: 異なる日数フィルタでのテスト")
for days in [0, 5, 10, 30]:
    result = matcher.match_and_filter(pharmacy_df, days_back=days)
    print(f"   Days back: {days:2d} → Matched: {result['stats']['recent_updates']} rows")

# Test 7: API endpoint test
print("\n✅ Test 7: API エンドポイントのテスト")
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Test /status endpoint
print("   Testing GET /status...")
response = client.get("/status")
print(f"   Status code: {response.status_code}")
print(f"   Response: {response.json()}")

# Test /preview-mhlw endpoint
print("\n   Testing GET /preview-mhlw...")
response = client.get("/preview-mhlw")
print(f"   Status code: {response.status_code}")
data = response.json()
print(f"   Success: {data.get('success')}")
print(f"   Rows in preview: {len(data.get('data', []))}")
print(f"   Total rows: {data.get('total_rows')}")

# Test /check endpoint
print("\n   Testing POST /check...")
with open(sample_path, 'rb') as f:
    response = client.post("/check", files={"file": f})
print(f"   Status code: {response.status_code}")
check_data = response.json()
print(f"   Success: {check_data.get('success')}")
print(f"   Message: {check_data.get('message')}")
print(f"   Stats: {check_data.get('stats')}")
print(f"   Data rows: {len(check_data.get('data', []))}")

if check_data.get('data'):
    print(f"\n   First matched row:")
    for key, value in list(check_data['data'][0].items())[:6]:
        print(f"     {key}: {value}")

# Test 8: Summary
print("\n" + "=" * 80)
print("✅ テスト完了")
print("=" * 80)

if result['success'] and result['data']:
    print("✓ バックエンドは正常に動作しています")
else:
    print("⚠ 何か問題があります。詳細を確認してください")
