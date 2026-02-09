"""FastAPI main application for pharmacy drug checker."""

from fastapi import FastAPI, UploadFile, File, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import pandas as pd
import io
from pathlib import Path
from datetime import datetime

from app.config import TEMPLATES_DIR, STATIC_DIR, MHLW_EXCEL_PATH, APP_PIN, SESSION_SECRET_KEY
from app.mhlw_downloader import MHLWDownloader
from app.excel_matcher import ExcelMatcher

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
    """Initialize supply data on startup."""
    result = downloader.check_and_update(force=True)
    print(f"起動時チェック: {result['message']}")


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
        # Read uploaded file
        content = await file.read()
        pharmacy_df = pd.read_excel(io.BytesIO(content), sheet_name=0)

        # Debug: Log uploaded file info
        print(f"📤 アップロードされたファイル: {file.filename}")
        print(f"   行数: {len(pharmacy_df)}")
        print(f"   最初の3行:")
        for idx, row in pharmacy_df.head(3).iterrows():
            code = row.get('コード', '')
            name = row.get('薬品名', '')
            print(f"     【{idx}】Code: {code}, Name: {name}")

        # Match and filter
        matcher = ExcelMatcher()
        result = matcher.match_and_filter(pharmacy_df)

        return JSONResponse(result)
    except Exception as e:
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
async def refresh(request: Request, background_tasks: BackgroundTasks):
    """Manually refresh supply data (non-blocking)."""
    # Check authentication
    if not is_authenticated(request):
        return JSONResponse(
            {
                "success": False,
                "message": "認証が必要です。",
            },
            status_code=401,
        )

    # Start background update task
    background_tasks.add_task(downloader.check_and_update)

    # Return immediately with loading message
    return JSONResponse(
        {
            "success": True,
            "message": "🔄 厚生労働省のデータを更新中です...（数秒かかる場合があります）",
            "cached": True,
            "last_checked": datetime.now().strftime("%Y-%m-%d"),
            "file_date": downloader.meta.get("last_checked", ""),
            "loading": True,
        }
    )


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
        else:
            # Skip first row if it contains headers (①薬剤区分, etc.)
            if len(df) > 0 and df.iloc[0, 0] == "①薬剤区分":
                # First row contains header info, use it as column names
                df.columns = df.iloc[0]
                df = df.iloc[1:].reset_index(drop=True)

            # Remove completely empty rows
            df = df.dropna(how='all')

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
