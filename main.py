"""FastAPI main application for pharmacy drug checker."""

from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import pandas as pd
import io
import time
import asyncio
import uuid
from pathlib import Path
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

from app.config import TEMPLATES_DIR, STATIC_DIR, MHLW_EXCEL_PATH, APP_PIN, SESSION_SECRET_KEY
from app.mhlw_downloader import MHLWDownloader
from app.excel_matcher import ExcelMatcher, find_column, normalize_text
from app.config import (
    MAX_UPLOAD_MB,
    MAX_PROCESS_SECONDS,
    DRUG_CODE_COLUMN_PATTERNS,
    DRUG_NAME_COLUMN_PATTERNS,
)

# In-memory job store (single instance only)
JOBS = {}

def _process_excel_content(content: bytes) -> dict:
    """Process Excel content and return match result."""
    header_df = pd.read_excel(io.BytesIO(content), sheet_name=0, nrows=0)
    code_col = find_column(header_df, DRUG_CODE_COLUMN_PATTERNS)
    name_col = find_column(header_df, DRUG_NAME_COLUMN_PATTERNS)
    usecols = None
    if code_col and name_col:
        usecols = [code_col, name_col]
    elif code_col:
        usecols = [code_col]
    elif name_col:
        usecols = [name_col]

    pharmacy_df = pd.read_excel(io.BytesIO(content), sheet_name=0, usecols=usecols)

    # Handle files where the first row contains headers
    if len(pharmacy_df) > 0:
        first_row = [str(v) if pd.notna(v) else "" for v in pharmacy_df.iloc[0].tolist()]
        joined = " ".join(first_row)
        if any(p in joined for p in ["YJコード", "⑤YJコード", "⑥品名", "品名"]):
            pharmacy_df.columns = pharmacy_df.iloc[0]
            pharmacy_df = pharmacy_df.iloc[1:].reset_index(drop=True)

    # Drop completely empty rows
    pharmacy_df = pharmacy_df.dropna(how="all")

    # Drop rows where both code and name are empty after normalization
    if code_col in pharmacy_df.columns or name_col in pharmacy_df.columns:
        code_series = pharmacy_df[code_col] if code_col in pharmacy_df.columns else None
        name_series = pharmacy_df[name_col] if name_col in pharmacy_df.columns else None
        def _is_empty(v):
            if pd.isna(v):
                return True
            return normalize_text(str(v)) == ""
        mask = []
        for i in range(len(pharmacy_df)):
            c_empty = _is_empty(code_series.iloc[i]) if code_series is not None else True
            n_empty = _is_empty(name_series.iloc[i]) if name_series is not None else True
            mask.append(not (c_empty and n_empty))
        pharmacy_df = pharmacy_df.loc[mask].reset_index(drop=True)
    print(f"📄 pharmacy rows: {len(pharmacy_df)}")

    matcher = ExcelMatcher()
    return matcher.match_and_filter(pharmacy_df)

app = FastAPI(title="Pharmacy Drug Checker")

# Add SessionMiddleware for session management
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="pharmacy_session",
    max_age=None,  # Browser session only - expires when browser closes
    https_only=False,  # Allow both HTTP (local) and HTTPS (Render)
    same_site="lax",
)

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Global downloader instance
downloader = MHLWDownloader()


# Authentication helper
def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated."""
    return request.session.get("authenticated") is True


@app.on_event("startup")
async def startup_event():
    """Initialize supply data and background scheduler on startup."""
    # Initial check with cached data
    result = downloader.check_and_update(force=False)  # Use cache if available
    print(f"起動時チェック: {result['message']}")

    # Setup background scheduler for periodic updates (最高のエンジニア的改善)
    scheduler = BackgroundScheduler()

    def background_update_task():
        """Background task to update MHLW data (ユーザーを待たせない)"""
        print("🔄 バックグラウンド更新タスク開始...")
        try:
            result = downloader.check_and_update(force=True)
            print(f"✅ バックグラウンド更新完了: {result['message']}")
        except Exception as e:
            print(f"❌ バックグラウンド更新エラー（キャッシュを使用）: {e}")

    # Schedule update every 2 hours
    scheduler.add_job(background_update_task, 'interval', hours=2)
    scheduler.start()

    # Ensure scheduler shuts down when app exits
    atexit.register(lambda: scheduler.shutdown())


# ===== Authentication Routes =====

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Display login page."""
    # If already authenticated, redirect to home
    if is_authenticated(request):
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, pin: str = Form(...)):
    """Process login with PIN."""
    # Check PIN
    if not APP_PIN:
        # If no PIN is configured, deny access
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "PINが設定されていません。管理者に連絡してください。"},
        )

    if pin == APP_PIN:
        # Correct PIN - set session
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=302)
    else:
        # Wrong PIN
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "PINが正しくありません。もう一度入力してください。"},
        )


@app.get("/logout")
async def logout(request: Request):
    """Logout and clear session."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/health")
async def health_check():
    """Health check endpoint (no authentication required for Render)."""
    return JSONResponse({"status": "ok"})


# ===== Protected Routes =====

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render main page."""
    # Check authentication
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)

    status = downloader.get_status()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "status": status,
            "max_upload_mb": MAX_UPLOAD_MB,
            "max_process_seconds": MAX_PROCESS_SECONDS,
        },
    )


@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    """Debug test page."""
    # Check authentication
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("test.html", {"request": request})


@app.post("/check")
async def check(request: Request, file: UploadFile = File(...)):
    """Check uploaded Excel file against MHLW data."""
    # Check authentication
    if not is_authenticated(request):
        return JSONResponse(
            {
                "success": False,
                "message": "認証が必要です。",
            },
            status_code=401,
        )

    try:
        start_ts = time.perf_counter()
        print("🧪 /check start")
        # Read uploaded file with size limit to avoid long hangs
        max_bytes = MAX_UPLOAD_MB * 1024 * 1024
        size = 0
        chunks = []
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                return JSONResponse(
                    {
                        "success": False,
                        "message": f"ファイルサイズが大きすぎます（上限 {MAX_UPLOAD_MB}MB）",
                        "data": [],
                        "stats": {},
                    },
                    status_code=413,
                )
            chunks.append(chunk)

        content = b"".join(chunks)
        print(f"📦 upload bytes: {size}")

        # Debug: Log uploaded file info
        print(f"📤 アップロードされたファイル: {file.filename}")

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_process_excel_content, content),
                timeout=MAX_PROCESS_SECONDS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                {
                    "success": False,
                    "message": f"処理がタイムアウトしました（上限 {MAX_PROCESS_SECONDS} 秒）",
                    "data": [],
                    "stats": {},
                },
                status_code=504,
            )
        elapsed = time.perf_counter() - start_ts
        result["elapsed_sec"] = round(elapsed, 3)
        print(f"✅ /check done in {elapsed:.3f}s")

        return JSONResponse(result)
    except Exception as e:
        elapsed = time.perf_counter() - start_ts
        print(f"❌ /check failed in {elapsed:.3f}s: {e}")
        return JSONResponse(
            {
                "success": False,
                "message": f"Error processing file: {str(e)}",
                "data": [],
                "stats": {},
            },
            status_code=400,
        )


@app.post("/refresh")
async def refresh(request: Request):
    """Return current cache status (updates run via scheduled GitHub Actions)."""
    # Check authentication
    if not is_authenticated(request):
        return JSONResponse(
            {
                "success": False,
                "message": "認証が必要です。",
            },
            status_code=401,
        )

    # Get current status (use cache immediately)
    status = downloader.get_status()

    # Return immediately with current cache status
    return JSONResponse(
        {
            "success": True,
            "message": "✅ 最新状況を確認しました。更新は毎日 9:30 / 10:00（JST）に自動実行されます。",
            "cached": True,
            "last_checked": datetime.now().strftime("%Y-%m-%d"),
            "file_date": status.get("file_date", ""),
            "loading": False,
            "checked_at": status.get("checked_at"),
        }
    )


@app.get("/refresh-status")
async def refresh_status(request: Request):
    """Get background refresh status."""
    if not is_authenticated(request):
        return JSONResponse(
            {
                "success": False,
                "message": "認証が必要です。",
            },
            status_code=401,
        )

    return JSONResponse(downloader.get_status())


@app.get("/status")
async def status(request: Request):
    """Get current cache status."""
    # Check authentication
    if not is_authenticated(request):
        return JSONResponse(
            {
                "success": False,
                "message": "認証が必要です。",
            },
            status_code=401,
        )

    return JSONResponse(downloader.get_status())


@app.get("/preview-supply")
async def preview_supply(request: Request, limit: int = 20, offset: int = 0, search: str = ""):
    """Preview supply status data as JSON table with pagination and search (案2: Memory cache)."""
    # Check authentication
    if not is_authenticated(request):
        return JSONResponse(
            {
                "success": False,
                "message": "認証が必要です。",
            },
            status_code=401,
        )

    try:
        if not MHLW_EXCEL_PATH.exists():
            return JSONResponse(
                {
                    "success": False,
                    "message": "医薬品供給情報ファイルが見つかりません",
                    "data": [],
                },
                status_code=404,
            )

        # Use in-memory cache if available (案2: メモリキャッシュ)
        if downloader.cached_df is not None:
            print("Using cached DataFrame from memory")
            df = downloader.cached_df
        else:
            print("Loading DataFrame from Excel file")
            # Read Excel data
            df = pd.read_excel(MHLW_EXCEL_PATH, sheet_name=0)

            # Skip first row if it contains headers (①薬剤区分, etc.)
            if len(df) > 0 and df.iloc[0, 0] == "①薬剤区分":
                # First row contains header info, use it as column names
                df.columns = df.iloc[0]
                df = df.iloc[1:].reset_index(drop=True)

            # Remove completely empty rows
            df = df.dropna(how='all')

            # Cache in memory for future requests (案2)
            downloader.cached_df = df
            print("DataFrame cached in memory")
        # Convert to list of dicts
        all_records = []
        for _, row in df.iterrows():
            record = {}
            for col in df.columns:
                value = row[col]
                # Format datetime
                if isinstance(value, pd.Timestamp):
                    record[col] = value.strftime("%Y-%m-%d")
                elif pd.isna(value):
                    record[col] = ""
                else:
                    record[col] = str(value)
            all_records.append(record)

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            filtered_records = []
            for record in all_records:
                # Search across all columns
                for value in record.values():
                    if search_lower in str(value).lower():
                        filtered_records.append(record)
                        break
            all_records = filtered_records

        # Apply pagination
        total_rows = len(all_records)
        paginated_records = all_records[offset:offset + limit]

        return JSONResponse(
            {
                "success": True,
                "message": f"医薬品供給情報（全{total_rows}件）",
                "columns": list(df.columns),
                "data": paginated_records,
                "total_rows": total_rows,
                "returned_rows": len(paginated_records),
                "offset": offset,
                "limit": limit,
            }
        )
    except Exception as e:
        return JSONResponse(
            {
                "success": False,
                "message": f"医薬品供給情報の読み込みエラー: {str(e)}",
                "data": [],
            },
            status_code=400,
        )


@app.post("/check_async")
async def check_async(request: Request, file: UploadFile = File(...)):
    """Start async check job for uploaded Excel file."""
    if not is_authenticated(request):
        return JSONResponse(
            {
                "success": False,
                "message": "認証が必要です。",
            },
            status_code=401,
        )

    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    chunks = []
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            return JSONResponse(
                {
                    "success": False,
                    "message": f"ファイルサイズが大きすぎます（上限 {MAX_UPLOAD_MB}MB）",
                    "data": [],
                    "stats": {},
                },
                status_code=413,
            )
        chunks.append(chunk)

    content = b"".join(chunks)
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "running", "result": None, "error": None}
    print(f"🧵 async job start: {job_id}")

    async def _run_job():
        start_ts = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_process_excel_content, content),
                timeout=MAX_PROCESS_SECONDS,
            )
            elapsed = time.perf_counter() - start_ts
            result["elapsed_sec"] = round(elapsed, 3)
            JOBS[job_id] = {"status": "done", "result": result, "error": None}
            print(f"✅ async job done: {job_id} ({elapsed:.3f}s)")
        except asyncio.TimeoutError:
            JOBS[job_id] = {
                "status": "error",
                "result": None,
                "error": f"処理がタイムアウトしました（上限 {MAX_PROCESS_SECONDS} 秒）",
            }
            print(f"⏱️ async job timeout: {job_id}")
        except Exception as e:
            JOBS[job_id] = {"status": "error", "result": None, "error": str(e)}
            print(f"❌ async job error: {job_id}: {e}")

    asyncio.create_task(_run_job())

    return JSONResponse({"success": True, "job_id": job_id})


@app.get("/check_status/{job_id}")
async def check_status(request: Request, job_id: str):
    """Check async job status."""
    if not is_authenticated(request):
        return JSONResponse(
            {
                "success": False,
                "message": "認証が必要です。",
            },
            status_code=401,
        )

    job = JOBS.get(job_id)
    if not job:
        return JSONResponse(
            {"success": False, "message": "ジョブが見つかりません。"},
            status_code=404,
        )

    if job["status"] == "running":
        return JSONResponse({"success": True, "status": "running"})
    if job["status"] == "error":
        return JSONResponse(
            {"success": False, "status": "error", "message": job["error"]},
            status_code=500,
        )

    return JSONResponse(job["result"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
