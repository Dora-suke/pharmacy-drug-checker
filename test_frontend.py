# -*- coding: utf-8 -*-
"""Test frontend API integration with real data."""

from fastapi.testclient import TestClient
from main import app
from pathlib import Path
import json

client = TestClient(app)

print("=" * 80)
print("フロントエンド - API 統合テスト")
print("=" * 80)

# Test 1: Check GET /
print("\n✅ Test 1: メインページのロード")
response = client.get("/")
print(f"   Status code: {response.status_code}")
print(f"   Response type: {type(response.content)}")
print(f"   HTML size: {len(response.content)} bytes")
html_content = response.text
if "薬局向け医薬品供給状況チェッカー" in html_content:
    print("   ✓ タイトルが含まれている")
if "照合実行" in html_content:
    print("   ✓ 「照合実行」ボタンが含まれている")
if "MHLW データプレビュー" in html_content:
    print("   ✓ 「MHLWデータプレビュー」ボタンが含まれている")

# Test 2: Test /check endpoint response format
print("\n✅ Test 2: /check エンドポイントのレスポンス形式")
sample_path = Path("sample/pharmacy_sample.xlsx")
with open(sample_path, 'rb') as f:
    response = client.post("/check", files={"file": f})

print(f"   Status code: {response.status_code}")
data = response.json()

print(f"   Required fields:")
print(f"     - success: {data.get('success')} ({type(data.get('success')).__name__})")
print(f"     - message: {data.get('message')}")
print(f"     - stats: {data.get('stats')}")
print(f"     - data: {len(data.get('data', []))} rows")

# Test 3: Validate data structure
print("\n✅ Test 3: レスポンスデータ構造の検証")
if data.get('data'):
    first_row = data['data'][0]
    print(f"   First row keys ({len(first_row)} fields):")

    required_keys = [
        'pharmacy_薬品コード',
        'mhlw_③成分名',
        'mhlw_④規格単位',
        'mhlw_製造販売業者',
        'mhlw_供給状況'
    ]

    for key in required_keys:
        if key in first_row:
            value = first_row[key]
            # Truncate long values
            display_value = str(value)[:50] + ('...' if len(str(value)) > 50 else '')
            print(f"     ✓ {key}: {display_value}")
        else:
            print(f"     ✗ MISSING: {key}")

# Test 4: Check for update date
print("\n✅ Test 4: 更新日フィールドの確認")
if data.get('data'):
    first_row = data['data'][0]
    update_date_key = None
    for key in first_row.keys():
        if '更新' in key and '日' in key:
            update_date_key = key
            print(f"   ✓ Found update date key: {key}")
            print(f"     Value: {first_row[key]}")
            break

    if not update_date_key:
        print(f"   ⚠ Warning: No update date field found")
        print(f"   Available keys: {list(first_row.keys())}")

# Test 5: Validate aggregated specifications
print("\n✅ Test 5: 複数規格の集約確認")
if data.get('data'):
    rows_with_newlines = 0
    for row in data['data']:
        spec_value = row.get('mhlw_④規格単位', '')
        if '\n' in str(spec_value):
            rows_with_newlines += 1
            print(f"   Found multiline spec in row:")
            print(f"     Specs: {repr(spec_value)}")

    if rows_with_newlines == 0:
        print("   ℹ No multiline specifications found (this might be expected)")
    else:
        print(f"   ✓ Found {rows_with_newlines} rows with multiline specs")

# Test 6: Test /preview-mhlw endpoint
print("\n✅ Test 6: /preview-mhlw エンドポイントのテスト")
response = client.get("/preview-mhlw")
print(f"   Status code: {response.status_code}")
preview_data = response.json()

print(f"   Response fields:")
print(f"     - success: {preview_data.get('success')}")
print(f"     - total_rows: {preview_data.get('total_rows')}")
print(f"     - preview rows: {len(preview_data.get('data', []))}")
print(f"     - columns: {len(preview_data.get('columns', []))} columns")

if preview_data.get('columns'):
    print(f"     - column names: {preview_data.get('columns')}")

# Test 7: Test /refresh endpoint
print("\n✅ Test 7: /refresh エンドポイントのテスト")
response = client.post("/refresh")
print(f"   Status code: {response.status_code}")
refresh_data = response.json()
print(f"   Response:")
print(f"     - success: {refresh_data.get('success')}")
print(f"     - message: {refresh_data.get('message')}")
print(f"     - cached: {refresh_data.get('cached')}")

# Test 8: Summary and recommendations
print("\n" + "=" * 80)
print("テスト完了 - 推奨事項")
print("=" * 80)

if data.get('success') and data.get('data'):
    print("✓ バックエンドは正常に動作しています")
    print("✓ フロントエンドテンプレートが正常に処理できるようにしました")
    print("\n📝 ブラウザで確認してください：")
    print("   1. サンプルExcelをアップロード")
    print("   2. 「照合実行」をクリック")
    print("   3. 以下の情報が表示されることを確認：")
    print(f"      - 照合結果: {len(data['data'])} 医薬品")
    print(f"      - 統計: {data['stats']}")
    print(f"      - テーブルに成分名・規格・供給状況が表示される")
else:
    print("✗ 何か問題があります")

print("\n🧪 フロントエンドデバッグ手順:")
print("   1. ブラウザで http://localhost:8000 を開く")
print("   2. F12 で開発者ツールを開く")
print("   3. コンソールタブでエラーを確認")
print("   4. Network タブで /check リクエストを確認")
