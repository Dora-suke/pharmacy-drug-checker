from __future__ import annotations

import sys
from datetime import datetime

from app.mhlw_downloader import MHLWDownloader


def main() -> int:
    downloader = MHLWDownloader()
    result = downloader.check_and_update(force=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {result.get('message', '')}")

    # Always record the check time so the app can display last check
    downloader.meta["checked_at"] = datetime.now().isoformat()
    downloader._save_meta()

    if not result.get("success"):
        print("Update failed; keeping cache if available.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
