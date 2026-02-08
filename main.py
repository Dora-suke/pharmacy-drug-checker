"""FastAPI main application for pharmacy drug checker."""

from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import pandas as pd
import io
from pathlib import Path

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
    result = downloader.check_and_update()
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
async def refresh(request: Request):
    """Manually refresh supply data."""
    # Check authentication
    if not is_authenticated(request):
        return JSONResponse(
            {
                "success": False,
                "message": "認証が必要です。",
            },
            status_code=401,
        )

    result = downloader.check_and_update()
    return JSONResponse(
        {
            "success": result["success"],
            "message": result["message"],
            "cached": result["cached"],
            "last_checked": result.get("last_checked"),
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
async def preview_supply(request: Request):
    """Preview supply status data as JSON table."""
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

        # Read Excel data
        df = pd.read_excel(MHLW_EXCEL_PATH, sheet_name=0)

        # Skip first row if it contains headers (①薬剤区分, etc.)
        if len(df) > 0 and df.iloc[0, 0] == "①薬剤区分":
            # First row contains header info, use it as column names
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)

        # Remove completely empty rows
        df = df.dropna(how='all')

        # Convert to list of dicts
        records = []
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
            records.append(record)

        return JSONResponse(
            {
                "success": True,
                "message": f"医薬品供給情報（全{len(records)}件）",
                "columns": list(df.columns),
                "data": records,  # Return all rows
                "total_rows": len(records),
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
