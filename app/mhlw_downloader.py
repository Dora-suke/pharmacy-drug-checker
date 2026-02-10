"""Download and cache MHLW drug supply status Excel."""

import json
import httpx
from pathlib import Path
from datetime import datetime
import threading
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

from app.config import (
    MHLW_MAIN_URL,
    MHLW_EXCEL_PATH,
    MHLW_META_PATH,
    MHLW_SCRAPE_TIMEOUT,
    MHLW_META_TIMEOUT,
    MHLW_DOWNLOAD_TIMEOUT,
)


class MHLWDownloader:
    """Handle downloading and caching MHLW Excel files."""

    def __init__(self):
        self.excel_url: Optional[str] = None
        self.meta: Dict[str, Any] = {}
        self.refresh_in_progress = False
        self.last_refresh_started_at: Optional[str] = None
        self.last_refresh_finished_at: Optional[str] = None
        self.last_refresh_error: Optional[str] = None
        self._refresh_lock = threading.Lock()
        self._load_meta()

    def _load_meta(self) -> None:
        """Load cached metadata if it exists."""
        if MHLW_META_PATH.exists():
            try:
                with open(MHLW_META_PATH, "r", encoding="utf-8") as f:
                    self.meta = json.load(f)
            except Exception as e:
                print(f"Failed to load meta: {e}")
                self.meta = {}

    def _save_meta(self) -> None:
        """Save metadata to cache."""
        try:
            with open(MHLW_META_PATH, "w", encoding="utf-8") as f:
                json.dump(self.meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save meta: {e}")

    def _find_excel_link(self) -> Optional[str]:
        """Scrape MHLW page to find Excel download link."""
        try:
            timeout = httpx.Timeout(MHLW_SCRAPE_TIMEOUT)
            with httpx.Client(timeout=timeout) as client:
                response = client.get(MHLW_MAIN_URL)
                response.raise_for_status()

            soup = BeautifulSoup(response.content, "lxml")

            # Look for links containing .xlsx
            for link in soup.find_all("a"):
                href = link.get("href", "")
                if ".xlsx" in href.lower():
                    # Convert relative URLs to absolute
                    if href.startswith("/"):
                        href = urljoin(MHLW_MAIN_URL, href)
                    elif not href.startswith("http"):
                        href = urljoin(MHLW_MAIN_URL, href)
                    return href

            return None
        except Exception as e:
            print(f"Failed to scrape MHLW page: {e}")
            return None

    def _get_remote_metadata(self, url: str) -> Optional[Dict[str, str]]:
        """Get ETag and Last-Modified from remote server."""
        try:
            timeout = httpx.Timeout(MHLW_META_TIMEOUT)
            with httpx.Client(timeout=timeout) as client:
                response = client.head(url, follow_redirects=True)
                response.raise_for_status()

                return {
                    "etag": response.headers.get("etag", ""),
                    "last_modified": response.headers.get("last-modified", ""),
                    "content_length": response.headers.get("content-length", ""),
                }
        except Exception as e:
            print(f"Failed to get remote metadata: {e}")
            return None

    def _download_excel(self, url: str) -> bool:
        """Download Excel file from URL."""
        try:
            timeout = httpx.Timeout(MHLW_DOWNLOAD_TIMEOUT)
            with httpx.Client(timeout=timeout) as client:
                with client.stream("GET", url, follow_redirects=True) as response:
                    response.raise_for_status()
                    with open(MHLW_EXCEL_PATH, "wb") as f:
                        for chunk in response.iter_bytes():
                            f.write(chunk)
                return True
        except Exception as e:
            print(f"Failed to download Excel: {e}")
            return False

    def _format_date(self, iso_string: str) -> str:
        """Format ISO datetime string to YYYY-MM-DD."""
        if not iso_string:
            return "不明"
        try:
            return iso_string.split("T")[0]
        except:
            return iso_string

    def _parse_http_date(self, http_date_str: str) -> str:
        """Parse HTTP Last-Modified date to YYYY-MM-DD format."""
        if not http_date_str:
            return "不明"
        try:
            # HTTP date format: "Mon, 08 Feb 2026 00:00:00 GMT"
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(http_date_str)
            return dt.strftime("%Y-%m-%d")
        except:
            return "不明"

    def _extract_filename(self, url_or_filename: str) -> str:
        """Extract just the filename from URL."""
        if not url_or_filename:
            return "不明"
        try:
            return url_or_filename.split('/')[-1]
        except:
            return "不明"

    def _extract_date_from_filename(self, url_or_filename: str) -> str:
        """Extract date from filename like '260206iyakuhinkyoukyu.xlsx' -> '2026-02-06'."""
        if not url_or_filename:
            return "不明"
        try:
            import re
            # Extract just the filename from URL if needed
            filename = url_or_filename.split('/')[-1]

            # Find 6 consecutive digits in the filename
            match = re.search(r'(\d{6})', filename)
            if match:
                date_str = match.group(1)
                # Format: YYMMDD -> YYYY-MM-DD
                year = int(date_str[:2])
                month = int(date_str[2:4])
                day = int(date_str[4:6])
                # Assume 20XX for year 00-99
                full_year = 2000 + year if year < 100 else year
                return f"{full_year:04d}-{month:02d}-{day:02d}"
        except Exception as e:
            print(f"Error extracting date from filename: {e}")
            pass
        return "不明"

    def check_and_update(self, force: bool = False) -> Dict[str, Any]:
        """
        Check for updates and download if necessary.
        Returns a dict with status and metadata.
        """
        result = {
            "success": False,
            "message": "",
            "cached": False,
            "last_checked": None,
            "file_exists": MHLW_EXCEL_PATH.exists(),
        }

        # Prefer cached URL for speed; fall back to scraping if needed
        cached_url = self.meta.get("url", "")
        if cached_url:
            self.excel_url = cached_url

        if not self.excel_url:
            self.excel_url = self._find_excel_link()

        if not self.excel_url:
            result["message"] = "Failed to find Excel download link"
            # Use cached file if available
            if result["file_exists"]:
                result["cached"] = True
                result["success"] = True
                # Try to extract date from filename first, then from HTTP header
                last_modified = self._extract_date_from_filename(self.meta.get("url", ""))
                if last_modified == "不明":
                    last_modified = self._parse_http_date(self.meta.get("last_modified", "不明"))
                result["last_checked"] = last_modified
                result["message"] = f"新しいデータが見つかりません。{last_modified}のデータを使用しています"
            return result

        # Get remote metadata
        remote_meta = self._get_remote_metadata(self.excel_url)
        if not remote_meta and cached_url and self.excel_url == cached_url:
            # If cached URL failed, try scraping a fresh URL once
            scraped_url = self._find_excel_link()
            if scraped_url and scraped_url != self.excel_url:
                self.excel_url = scraped_url
                remote_meta = self._get_remote_metadata(self.excel_url)
        if not remote_meta:
            result["message"] = "Failed to get remote metadata"
            if result["file_exists"]:
                result["cached"] = True
                result["success"] = True
                last_modified = self._extract_date_from_filename(self.meta.get("url", ""))
                if last_modified == "不明":
                    last_modified = self._parse_http_date(self.meta.get("last_modified", "不明"))
                result["last_checked"] = last_modified
                result["message"] = f"最新情報の確認に失敗しました。{last_modified}のデータを使用しています"
            return result

        # Check if cache needs update
        cache_needs_update = (
            force
            or not MHLW_EXCEL_PATH.exists()
            or self.meta.get("etag") != remote_meta["etag"]
            or self.meta.get("last_modified") != remote_meta["last_modified"]
            or self.meta.get("content_length") != remote_meta["content_length"]
            or self.meta.get("url") != self.excel_url
        )

        if cache_needs_update:
            if self._download_excel(self.excel_url):
                self.meta = {
                    "etag": remote_meta["etag"],
                    "last_modified": remote_meta["last_modified"],
                    "content_length": remote_meta["content_length"],
                    "downloaded_at": datetime.now().isoformat(),
                    "url": self.excel_url,
                }
                self._save_meta()
                result["success"] = True
                # Extract date and filename
                last_modified = self._extract_date_from_filename(self.excel_url)
                filename = self._extract_filename(self.excel_url)
                result["last_checked"] = last_modified
                result["message"] = f"✅ データが更新されました。{last_modified}（{filename}）"
            else:
                result["message"] = "Failed to download Excel"
                if result["file_exists"]:
                    result["cached"] = True
                    result["success"] = True
                    last_modified = self._extract_date_from_filename(self.meta.get("url", ""))
                    filename = self._extract_filename(self.meta.get("url", ""))
                    if last_modified == "不明":
                        last_modified = self._parse_http_date(self.meta.get("last_modified", "不明"))
                    result["last_checked"] = last_modified
                    result["message"] = f"ダウンロードに失敗しました。{last_modified}（{filename}）のデータを使用しています"
        else:
            result["success"] = True
            result["cached"] = True
            last_modified = self._extract_date_from_filename(self.excel_url)
            filename = self._extract_filename(self.excel_url)
            result["last_checked"] = last_modified
            result["message"] = f"✅ データは最新です。{last_modified}（{filename}）"

        return result

    def start_background_refresh(self, force: bool = True) -> bool:
        """Start background refresh in a dedicated thread if not already running."""
        with self._refresh_lock:
            if self.refresh_in_progress:
                return False
            self.refresh_in_progress = True
            self.last_refresh_started_at = datetime.now().isoformat()
            self.last_refresh_error = None

        def _run():
            try:
                self.check_and_update(force=force)
            except Exception as e:
                self.last_refresh_error = str(e)
            finally:
                self.last_refresh_finished_at = datetime.now().isoformat()
                self.refresh_in_progress = False

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get current cache status without checking for updates."""
        return {
            "file_exists": MHLW_EXCEL_PATH.exists(),
            "file_size": MHLW_EXCEL_PATH.stat().st_size if MHLW_EXCEL_PATH.exists() else 0,
            "last_checked": self.meta.get("downloaded_at"),
            "last_modified": self.meta.get("last_modified"),
            "url": self.meta.get("url", ""),
            "file_date": self._extract_date_from_filename(self.meta.get("url", "")),
            "refresh_in_progress": self.refresh_in_progress,
            "last_refresh_started_at": self.last_refresh_started_at,
            "last_refresh_finished_at": self.last_refresh_finished_at,
            "last_refresh_error": self.last_refresh_error,
        }
