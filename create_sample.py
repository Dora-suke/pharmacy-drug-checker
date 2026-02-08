"""Create sample pharmacy Excel file."""

import pandas as pd
from pathlib import Path

# Create sample data
sample_data = {
    "薬品コード": ["1234567890", "9876543210", "1111111111", "2222222222", "3333333333"],
    "薬品名": ["アスピリン錠", "イブプロフェン液", "ウルソデオキシコール酸", "エピネフリン注射液", "オメプラゾール錠"],
    "規格": ["100錠", "100ml", "50カプセル", "1ml×10本", "30錠"],
    "メーカー": ["ファイザー", "大正製薬", "科研製薬", "武田薬品工業", "第一三共"],
    "採用区分": ["採用中", "採用中", "採用中", "削除予定", "採用中"],
}

df = pd.DataFrame(sample_data)

# Save to Excel
output_path = Path(__file__).parent / "sample" / "pharmacy_sample.xlsx"
output_path.parent.mkdir(parents=True, exist_ok=True)
df.to_excel(output_path, sheet_name="薬品一覧", index=False)

print(f"Sample Excel created: {output_path}")
print(f"Rows: {len(df)}")
print(df.to_string())
