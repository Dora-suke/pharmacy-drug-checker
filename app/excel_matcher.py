"""Excel matching logic for pharmacy and MHLW data."""

import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

from app.config import (
    MHLW_EXCEL_PATH,
    DAYS_BACK,
    UPDATE_DATE_COLUMN_PATTERN,
    DRUG_CODE_COLUMN_PATTERNS,
    DRUG_NAME_COLUMN_PATTERNS,
)


def normalize_text(text: str) -> str:
    """Normalize text: convert full-width to half-width, lowercase, strip whitespace."""
    if not isinstance(text, str):
        return ""
    # NFKC normalization converts full-width alphanumerics to half-width
    text = unicodedata.normalize("NFKC", text)
    return text.lower().strip()


def find_column(df: pd.DataFrame, patterns: List[str]) -> Optional[str]:
    """Find column name matching any of the patterns.

    Search order:
    1. Exact match (highest priority)
    2. Pattern contained in column name (case-insensitive)
    3. Normalized text matching
    4. Fallback: semantic matching for common names (コード, 名, etc.)
    """
    # 1. Exact match
    for col in df.columns:
        for pattern in patterns:
            if col == pattern:
                return col

    # 2. Pattern contained in column name (case-insensitive)
    for col in df.columns:
        col_lower = col.lower()
        for pattern in patterns:
            if pattern.lower() in col_lower:
                return col

    # 3. Normalized text matching
    for col in df.columns:
        col_normalized = normalize_text(col)
        for pattern in patterns:
            if normalize_text(pattern) in col_normalized:
                return col

    # 4. Fallback: semantic matching for common Japanese names
    # Check if looking for code-related column
    if any('code' in p.lower() or 'コード' in p for p in patterns):
        for col in df.columns:
            if 'コード' in col or 'code' in col.lower():
                return col

    # Check if looking for name-related column
    if any('name' in p.lower() or '名' in p for p in patterns):
        for col in df.columns:
            if '名' in col or 'name' in col.lower():
                return col

    return None


class ExcelMatcher:
    """Match pharmacy drugs with MHLW supply status data."""

    def __init__(self, mhlw_excel_path: Path = MHLW_EXCEL_PATH):
        self.mhlw_excel_path = mhlw_excel_path
        self.mhlw_df: Optional[pd.DataFrame] = None
        self.update_date_column: Optional[str] = None
        self.drug_code_column: Optional[str] = None
        self.drug_name_column: Optional[str] = None
        self._load_mhlw_data()

    def _load_mhlw_data(self) -> None:
        """Load MHLW Excel data."""
        try:
            if not self.mhlw_excel_path.exists():
                raise FileNotFoundError(f"MHLW Excel not found: {self.mhlw_excel_path}")

            # Try to read the first sheet
            self.mhlw_df = pd.read_excel(self.mhlw_excel_path, sheet_name=0)

            # Skip first row if it contains headers (①薬剤区分, etc.)
            if len(self.mhlw_df) > 0 and str(self.mhlw_df.iloc[0, 0]) == "①薬剤区分":
                # First row contains header info, use it as column names
                self.mhlw_df.columns = self.mhlw_df.iloc[0]
                self.mhlw_df = self.mhlw_df.iloc[1:].reset_index(drop=True)

            # Remove completely empty rows
            self.mhlw_df = self.mhlw_df.dropna(how='all')

            # Find required columns
            self.update_date_column = find_column(
                self.mhlw_df, [UPDATE_DATE_COLUMN_PATTERN]
            )
            self.drug_code_column = find_column(
                self.mhlw_df, DRUG_CODE_COLUMN_PATTERNS
            )
            self.drug_name_column = find_column(
                self.mhlw_df, DRUG_NAME_COLUMN_PATTERNS
            )

            # Convert update date column to datetime
            if self.update_date_column:
                self.mhlw_df[self.update_date_column] = pd.to_datetime(
                    self.mhlw_df[self.update_date_column], errors="coerce"
                )

        except Exception as e:
            print(f"Failed to load MHLW data: {e}")
            self.mhlw_df = None

    def match_and_filter(
        self, pharmacy_df: pd.DataFrame, days_back: int = DAYS_BACK
    ) -> Dict[str, Any]:
        """
        Match pharmacy drugs with MHLW data and filter by recent updates.
        Groups multiple specifications of the same ingredient.

        Returns dict with:
        - success: bool
        - message: str
        - data: list of matched rows
        - stats: matching statistics
        """
        result = {
            "success": False,
            "message": "",
            "data": [],
            "stats": {
                "pharmacy_rows": len(pharmacy_df),
                "matched_rows": 0,
                "recent_updates": 0,
            },
        }

        if self.mhlw_df is None:
            result["message"] = "MHLW data not loaded"
            return result

        if self.mhlw_df.empty:
            result["message"] = "MHLW data is empty"
            return result

        # Find pharmacy columns
        pharmacy_code_column = find_column(pharmacy_df, DRUG_CODE_COLUMN_PATTERNS)
        pharmacy_name_column = find_column(pharmacy_df, DRUG_NAME_COLUMN_PATTERNS)
        # Fallback: if only one column exists, treat it as name
        if not pharmacy_name_column and len(pharmacy_df.columns) == 1:
            pharmacy_name_column = pharmacy_df.columns[0]

        # Find MHLW specific columns
        mhlw_ingredient_column = self._find_ingredient_column()
        mhlw_spec_column = self._find_spec_column()

        matched_rows = []
        matched_pharmacy_codes = set()  # Track which pharmacy codes have been matched
        cutoff_date = datetime.now() - timedelta(days=days_back)

        # Prebuild lookup maps for faster matching
        mhlw_cols = list(self.mhlw_df.columns)
        mhlw_col_index = {c: i for i, c in enumerate(mhlw_cols)}
        update_idx = mhlw_col_index.get(self.update_date_column)
        code_idx = mhlw_col_index.get(self.drug_code_column)
        name_idx = mhlw_col_index.get(self.drug_name_column)

        code_map: Dict[str, List[tuple]] = {}
        name_map: Dict[str, List[tuple]] = {}
        name_prefix_map: Dict[str, List[tuple]] = {}

        for row in self.mhlw_df.itertuples(index=False, name=None):
            if code_idx is not None:
                code_val = row[code_idx]
                code_norm = normalize_text(str(code_val)) if pd.notna(code_val) else ""
                if code_norm:
                    code_map.setdefault(code_norm, []).append(row)
            if name_idx is not None:
                name_val = row[name_idx]
                name_norm = normalize_text(str(name_val)) if pd.notna(name_val) else ""
                if name_norm:
                    name_map.setdefault(name_norm, []).append(row)
                    if len(name_norm) > 3:
                        prefix = name_norm[:5]
                        name_prefix_map.setdefault(prefix, []).append(row)

        ph_cols = list(pharmacy_df.columns)
        ph_code_idx = ph_cols.index(pharmacy_code_column) if pharmacy_code_column else None
        ph_name_idx = ph_cols.index(pharmacy_name_column) if pharmacy_name_column else None

        for pharmacy_row_tuple in pharmacy_df.itertuples(index=False, name=None):
            # Try to match by drug code first
            mhlw_matches = []

            if ph_code_idx is not None:
                raw_code = pharmacy_row_tuple[ph_code_idx]
                # Skip if code is NaN/None
                if pd.notna(raw_code):
                    code = normalize_text(str(raw_code))
                else:
                    code = ""
                if code and len(code) > 0:
                    mhlw_matches = code_map.get(code, [])

            # Fallback to drug name matching
            if not mhlw_matches and ph_name_idx is not None:
                raw_name = pharmacy_row_tuple[ph_name_idx]
                # Skip if name is NaN/None
                if pd.notna(raw_name):
                    name = normalize_text(str(raw_name))
                else:
                    name = ""
                if name and len(name) > 0:
                    mhlw_matches = name_map.get(name, [])
                    if not mhlw_matches and len(name) > 3:
                        mhlw_matches = name_prefix_map.get(name[:5], [])

            if not mhlw_matches:
                continue

            # Skip if pharmacy code already matched (only if code exists)
            pharmacy_row_series = pd.Series(dict(zip(ph_cols, pharmacy_row_tuple)))
            pharmacy_code = self._safe_str(pharmacy_row_series.get(pharmacy_code_column, ""))
            if pharmacy_code and pharmacy_code in matched_pharmacy_codes:
                continue
            # Only add to matched if code exists
            if pharmacy_code:
                matched_pharmacy_codes.add(pharmacy_code)

            result["stats"]["matched_rows"] += 1

            # Check if any match has recent update
            has_recent = False
            if self.update_date_column:
                for mhlw_match_tuple in mhlw_matches:
                    update_date = (
                        mhlw_match_tuple[update_idx] if update_idx is not None else None
                    )
                    if pd.notna(update_date) and update_date >= cutoff_date:
                        has_recent = True
                        break
            else:
                has_recent = True

            if has_recent or not self.update_date_column:
                result["stats"]["recent_updates"] += 1
                # Convert first match only to avoid duplicates
                if mhlw_matches:
                    mhlw_row = pd.Series(dict(zip(self.mhlw_df.columns, mhlw_matches[0])))
                    matched_rows.append(
                        self._format_result_row(pharmacy_row_series, mhlw_row)
                    )

        result["data"] = matched_rows
        result["success"] = True
        result["message"] = f"Matched {len(matched_rows)} drugs with recent updates"

        return result

    def _format_result_row(
        self, pharmacy_row: pd.Series, mhlw_row: pd.Series
    ) -> Dict[str, Any]:
        """Format a matched row for display."""
        result = {}

        # Add relevant pharmacy fields
        for col in pharmacy_row.index:
            if col and not col.startswith("_"):
                result[f"pharmacy_{col}"] = self._safe_str(pharmacy_row.get(col))

        # Add relevant MHLW fields
        for col in mhlw_row.index:
            if col and not col.startswith("_"):
                value = mhlw_row.get(col)
                if isinstance(value, datetime):
                    result[f"mhlw_{col}"] = value.strftime("%Y-%m-%d")
                else:
                    result[f"mhlw_{col}"] = self._safe_str(value)

        return result

    def _safe_str(self, value: Any) -> str:
        """Safely convert value to string."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        if isinstance(value, (int, float)):
            return str(value)
        return str(value)

    def _find_ingredient_column(self) -> Optional[str]:
        """Find column for ③成分名 (ingredient name)."""
        if self.mhlw_df is None:
            return None
        patterns = ["③成分名", "成分名", "③", "ingredient"]
        return find_column(self.mhlw_df, patterns)

    def _find_spec_column(self) -> Optional[str]:
        """Find column for ④規格単位 (specification/unit)."""
        if self.mhlw_df is None:
            return None
        patterns = ["④規格単位", "規格単位", "④", "specification"]
        return find_column(self.mhlw_df, patterns)

    def _format_result_row_grouped(
        self,
        pharmacy_row: pd.Series,
        mhlw_series_list: List[pd.Series],
        ingredient_column: Optional[str],
        spec_column: Optional[str],
    ) -> Dict[str, Any]:
        """
        Format multiple MHLW rows grouped by ingredient.
        Combines multiple specifications into one row with line breaks.
        """
        result = {}

        # Add pharmacy fields
        for col in pharmacy_row.index:
            if col and not col.startswith("_"):
                result[f"pharmacy_{col}"] = self._safe_str(pharmacy_row.get(col))

        # Group MHLW data by ingredient
        if mhlw_series_list:
            first_mhlw = mhlw_series_list[0]

            # Get ingredient name from first row (or from ③成分名 column if available)
            if ingredient_column and ingredient_column in first_mhlw.index:
                ingredient_name = self._safe_str(first_mhlw.get(ingredient_column))
            else:
                # Fallback to drug name
                ingredient_name = self._safe_str(
                    first_mhlw.get("医薬品名") or first_mhlw.get("薬品名", "")
                )

            # Combine specifications (remove duplicates while preserving order)
            specs = []
            specs_set = set()
            for mhlw_row in mhlw_series_list:
                if spec_column and spec_column in mhlw_row.index:
                    spec = self._safe_str(mhlw_row.get(spec_column))
                    if spec and spec not in specs_set:
                        specs.append(spec)
                        specs_set.add(spec)

            # Add aggregated fields with simplified keys
            result["mhlw_ingredient_name"] = ingredient_name
            result["mhlw_spec"] = "\n".join(specs) if specs else ""

            # Add other fields from first row
            for col in first_mhlw.index:
                if col and not col.startswith("_"):
                    # Skip ingredient and spec columns as they're already handled
                    if col == ingredient_column or col == spec_column:
                        continue
                    value = first_mhlw.get(col)
                    if isinstance(value, datetime):
                        result[f"mhlw_{col}"] = value.strftime("%Y-%m-%d")
                    else:
                        result[f"mhlw_{col}"] = self._safe_str(value)

        return result
