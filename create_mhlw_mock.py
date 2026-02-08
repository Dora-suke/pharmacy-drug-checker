"""Create mock MHLW Excel file for testing without network access."""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Create mock MHLW data with multiple specifications for some drugs
mock_data = {
    "YJコード": [
        "1234567890", "1234567890",  # アスピリン - 2規格
        "9876543210",                  # イブプロフェン - 1規格
        "1111111111", "1111111111", "1111111111",  # ウルソデオキシコール - 3規格
        "2222222222",                  # エピネフリン - 1規格
        "3333333333"                   # オメプラゾール - 1規格
    ],
    "③成分名": [
        "アスピリン", "アスピリン",
        "イブプロフェン",
        "ウルソデオキシコール酸", "ウルソデオキシコール酸", "ウルソデオキシコール酸",
        "エピネフリン",
        "オメプラゾール"
    ],
    "④規格単位※全角": [
        "５００ｍｇ錠", "１０００ｍｇ錠",
        "１００ｍｇ/５ｍｌ液",
        "１００ｍｇ", "２５０ｍｇ", "５００ｍｇ",
        "１ｍｇ/ｍｌ注",
        "２０ｍｇ錠"
    ],
    "医薬品名": [
        "アスピリン錠", "アスピリン錠",
        "イブプロフェン液",
        "ウルソデオキシコール酸", "ウルソデオキシコール酸", "ウルソデオキシコール酸",
        "エピネフリン注射液",
        "オメプラゾール錠"
    ],
    "製造販売業者": [
        "ファイザー", "ファイザー",
        "大正製薬",
        "科研製薬", "科研製薬", "科研製薬",
        "武田薬品工業",
        "第一三共"
    ],
    "供給状況": [
        "通常供給", "通常供給",
        "通常供給",
        "通常供給", "通常供給", "入手困難",
        "通常供給",
        "通常供給"
    ],
    "⑳当該品目の⑫以外の情報を更新した日": [
        (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),   # 2日前
        (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),   # 2日前
        (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),   # 5日前
        (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d"),   # 8日前
        (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d"),   # 8日前
        (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d"),   # 8日前
        (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d"),  # 15日前（フィルタ対象外）
        (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),   # 3日前
    ]
}

df = pd.DataFrame(mock_data)

# Save to cache directory
cache_path = Path(__file__).parent / "cache" / "mhlw_latest.xlsx"
cache_path.parent.mkdir(parents=True, exist_ok=True)
df.to_excel(cache_path, sheet_name="医薬品供給状況", index=False)

# Save mock metadata
import json
meta_path = Path(__file__).parent / "cache" / "mhlw_meta.json"
meta = {
    "etag": "mock-etag",
    "last_modified": "Mon, 08 Feb 2026 00:00:00 GMT",
    "content_length": "5000",
    "downloaded_at": datetime.now().isoformat(),
    "url": "mock://internal-test",
    "is_mock": True,
    "note": "This is a mock file for testing without network access"
}
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

print(f"✅ Mock MHLW Excel created: {cache_path}")
print(f"✅ Mock metadata created: {meta_path}")
print(f"\nMock Data ({len(df)} rows):")
print(df.to_string())
print(f"\nUpdate dates:")
for idx, row in df.iterrows():
    print(f"  {row['医薬品名']}: {row['⑳当該品目の⑫以外の情報を更新した日']}")
