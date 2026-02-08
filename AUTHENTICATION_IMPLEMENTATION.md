# PIN認証 + クラウドデプロイ実装完了レポート

## 実装完了日
2026年2月8日

## 実装概要
薬局向け医薬品供給状況チェッカーを外部からアクセス可能にするため、シンプルな4桁PIN認証とクラウドデプロイ対応を実装しました。

---

## 実装内容

### ✅ 1. `pyproject.toml` 更新
- `itsdangerous>=2.1.0` を追加（SessionMiddlewareの署名に必要）
- `python-dotenv>=1.0.0` を追加（環境変数読み込み）

```toml
dependencies = [
    ...
    "itsdangerous>=2.1.0",
    "python-dotenv>=1.0.0",
]
```

### ✅ 2. `app/config.py` 更新
- `dotenv.load_dotenv()` で .env ファイルを読み込み
- `APP_PIN` 環境変数から4桁のPINを取得
- `SESSION_SECRET_KEY` 環境変数からセッション署名キーを取得

```python
import os
from dotenv import load_dotenv

load_dotenv()

APP_PIN = os.environ.get("APP_PIN", "")
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "change-this-secret-key")
```

### ✅ 3. `templates/login.html` 新規作成
Bootstrap 5.3ベースの洗練されたログインページ

**特徴:**
- グラデーション背景（紫系）
- 4桁PIN入力フォーム（パスワード形式）
- `maxlength="4"`, `pattern="[0-9]{4}"` による入力制限
- 4桁入力時の自動サブミット機能
- エラーメッセージ表示対応
- モバイル対応デザイン

### ✅ 4. `main.py` 大幅更新

#### インポート追加
```python
from fastapi import Form
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from app.config import APP_PIN, SESSION_SECRET_KEY
```

#### SessionMiddleware追加
```python
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="pharmacy_session",
    max_age=None,       # ブラウザを閉じるまで有効
    https_only=False,   # ローカル開発とRender両対応
    same_site="lax",
)
```

#### 認証ヘルパー関数
```python
def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated."""
    return request.session.get("authenticated") is True
```

#### 新規ルート実装

**GET /login** - ログインページ表示
- 既認証の場合は / にリダイレクト
- 未認証の場合は login.html を表示

**POST /login** - PIN検証
- PINが正しい → `session["authenticated"] = True` → `/` へリダイレクト
- PINが間違い → エラーメッセージ表示

**GET /logout** - ログアウト
- セッションをクリア
- `/login` へリダイレクト

**GET /health** - ヘルスチェック（認証不要）
- Renderのヘルスチェック用
- 常に `{"status": "ok"}` を返す

#### 既存ルートへの認証チェック追加

全エンドポイントに認証チェックを追加：
- `/` (GET) - HTML ページ → 未認証なら /login へリダイレクト
- `/test` (GET) - HTML ページ → 未認証なら /login へリダイレクト
- `/check` (POST) - API → 未認証なら 401 JSON を返す
- `/refresh` (POST) - API → 未認証なら 401 JSON を返す
- `/status` (GET) - API → 未認証なら 401 JSON を返す
- `/preview-supply` (GET) - API → 未認証なら 401 JSON を返す

### ✅ 5. `.env.example` 新規作成
環境変数のテンプレートファイル

```env
# Application PIN for authentication (required)
APP_PIN=1234

# Session secret key for signing session cookies
SESSION_SECRET_KEY=your-secret-key-here-change-in-production
```

### ✅ 6. `.gitignore` 新規作成
以下を除外：
- `.env`, `.env.local`, `.env.*.local` - 機密情報
- `cache/*.xlsx`, `cache/*.json` - キャッシュファイル
- `.venv`, `env/`, `venv/` - 仮想環境
- `__pycache__/`, `*.pyc` - Python キャッシュ
- IDE設定（.vscode/, .idea/）
- テスト結果（.pytest_cache/, .coverage）
- PDMビルド（.pdm-build/）

### ✅ 7. `Dockerfile` 新規作成
Docker コンテナ実行用設定

**特徴:**
- Python 3.12-slim ベースイメージ
- libxml2-dev, libxslt-dev インストール（lxml対応）
- 全依存パッケージをインストール
- `/app/cache` ディレクトリを作成
- ポート 8000 を公開
- uvicorn で起動

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*
# ... 依存インストール
COPY . .
RUN mkdir -p /app/cache
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### ✅ 8. `render.yaml` 新規作成
Render デプロイ設定ファイル

```yaml
services:
  - type: web
    name: pharmacy-drug-checker
    runtime: docker
    plan: free
    envVars:
      - key: APP_PIN
        sync: false          # Renderダッシュボードで手動設定
      - key: SESSION_SECRET_KEY
        generateValue: true  # 自動生成
    healthCheckPath: /health
    autoDeploy: true
```

---

## 認証フロー

```
ユーザー → GET /
           ↓
      is_authenticated()?
           ↓ No
      → 302 リダイレクト → GET /login
           ↓
      login.html を表示（4桁PIN入力フォーム）
           ↓
      ユーザーが PIN を入力 → POST /login
           ↓
      PIN == APP_PIN?
           ├─ Yes → session["authenticated"] = True → 302 リダイレクト → GET /
           │                                             ↓
           │                                        is_authenticated() = True
           │                                             ↓
           │                                        index.html を表示 ✓
           │
           └─ No → エラーメッセージ表示 → login.html を再表示
```

**セッション特性:**
- `max_age=None` により、ブラウザを閉じるまでセッション有効
- クッキーは `httponly` + `samesite=lax` で保護
- ブラウザを閉じるとセッションクッキーが削除される

---

## ローカルテスト結果

### テスト環境
- Python 3.12
- FastAPI 0.104.0+
- Starlette SessionMiddleware

### テスト項目と結果

#### ✅ 認証なしでホームページアクセス
```bash
$ curl -i http://localhost:8000/
HTTP/1.1 302 Found
location: /login
```
→ `/login` へリダイレクト ✓

#### ✅ ログインページ表示
```bash
$ curl -s http://localhost:8000/login | grep "title"
<title>薬局供給チェッカー - ログイン</title>
```
→ ログインフォーム表示 ✓

#### ✅ 正しいPINでログイン
```bash
$ curl -c /tmp/cookies.txt -i -d "pin=1234" -X POST http://localhost:8000/login
HTTP/1.1 302 Found
location: /
set-cookie: pharmacy_session=...; path=/; httponly; samesite=lax
```
→ セッションクッキー設定 + `/` へリダイレクト ✓

#### ✅ 間違ったPINでログイン
```bash
$ curl -i -d "pin=9999" -X POST http://localhost:8000/login
HTTP/1.1 200 OK
...
PINが正しくありません。もう一度入力してください。
```
→ エラーメッセージ表示 ✓

#### ✅ セッションクッキーでホームページアクセス
```bash
$ curl -b /tmp/cookies.txt -s http://localhost:8000/ | grep "title"
<title>薬局向け医薬品供給状況チェッカー</title>
```
→ メインページ表示 ✓

#### ✅ ヘルスチェック（認証不要）
```bash
$ curl -s http://localhost:8000/health
{"status":"ok"}
```
→ 200 OK ✓

#### ✅ API認証（認証なし）
```bash
$ curl -s http://localhost:8000/preview-supply
{"success":false,"message":"認証が必要です。"}
```
→ 401 エラー ✓

#### ✅ API認証（認証あり）
```bash
$ curl -b /tmp/cookies.txt -s http://localhost:8000/preview-supply
{"success":true,"message":"医薬品供給情報（全...件）","columns":[...],...}
```
→ データ返却 ✓

#### ✅ ログアウト
```bash
$ curl -b /tmp/cookies.txt -i http://localhost:8000/logout
HTTP/1.1 302 Found
location: /login
```
→ セッション削除 + `/login` へリダイレクト ✓

---

## Renderデプロイ手順

### 前提条件
- GitHub アカウント
- render.com アカウント
- このリポジトリが GitHub に push されていること

### デプロイ手順

1. **ローカルで動作確認**
   ```bash
   APP_PIN=1234 SESSION_SECRET_KEY=test-secret uvicorn main:app --reload
   ```

2. **依存関係が正しく含まれていることを確認**
   ```bash
   cat pyproject.toml  # itsdangerous, python-dotenv が含まれていることを確認
   ```

3. **GitHub にコミット & プッシュ**
   ```bash
   git add .
   git commit -m "実装: PIN認証 + クラウドデプロイ対応"
   git push origin main
   ```

4. **Render ダッシュボードでデプロイ**
   - https://render.com にアクセス
   - 「New Web Service」をクリック
   - GitHub リポジトリを接続
   - 設定の確認：
     - Name: `pharmacy-drug-checker` (自動入力)
     - Runtime: `docker` (自動検出)
     - Build command: 自動
     - Start command: 自動

5. **環境変数を設定**
   - Environment タブで以下を設定：
     - `APP_PIN`: 4桁の数字（例：`1234`）※**セキュア変数として設定**
     - `SESSION_SECRET_KEY`: 自動生成されるため設定不要（render.yaml で `generateValue: true` に設定）

6. **デプロイ実行**
   - 「Create Web Service」をクリック
   - ビルドとデプロイが自動開始
   - ログで `Application startup complete` が表示されたら完了

7. **アクセス確認**
   - `https://<your-service-name>.onrender.com` でアクセス
   - PIN ログイン画面が表示されることを確認
   - 設定したPINでログイン可能なことを確認

### Render 無料プランの注意事項

- **15分のアイドル時間**: アクセスがない場合、15分後にスリープします
- **起動時間**: スリープから起動までに30～60秒かかります
- **ストレージ**: 再起動時にキャッシュディレクトリが初期化されます（startup_event で自動再ダウンロード）

---

## セキュリティに関する注意

### 本番環境での設定

1. **SESSION_SECRET_KEY の生成**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   出力を Render の `SESSION_SECRET_KEY` に設定してください。

2. **APP_PIN の管理**
   - 強力な4桁を選択
   - GitHub には `.env` を push しないこと（`.gitignore` で除外済み）
   - Render ダッシュボードで「Secure」オプションで環境変数を保護

3. **HTTPS の確認**
   - Render は自動的に HTTPS を提供
   - `https_only=False` はローカル開発対応のため
   - 本番環境では自動的に HTTPS が使用されます

---

## ファイル一覧

| ファイル | 変更内容 | 説明 |
|---------|--------|------|
| `pyproject.toml` | 変更 | itsdangerous, python-dotenv を依存関係に追加 |
| `app/config.py` | 変更 | APP_PIN, SESSION_SECRET_KEY の環境変数読み込みを追加 |
| `main.py` | 変更 | SessionMiddleware, ログインルート, 認証チェックを追加 |
| `templates/login.html` | 新規 | Bootstrap 5.3 ベースのログインフォーム |
| `.env.example` | 新規 | 環境変数のサンプルファイル |
| `.gitignore` | 新規 | Git除外ファイル設定 |
| `Dockerfile` | 新規 | Docker コンテナ定義 |
| `render.yaml` | 新規 | Render デプロイ設定 |

---

## トラブルシューティング

### エラー: `ModuleNotFoundError: No module named 'itsdangerous'`

**解決方法:**
```bash
pip install itsdangerous python-dotenv
# または uv を使用している場合:
uv pip install 'itsdangerous>=2.1.0' 'python-dotenv>=1.0.0'
```

### エラー: `APP_PIN environment variable not set`

**解決方法:**
ローカルテスト時：
```bash
APP_PIN=1234 SESSION_SECRET_KEY=test python -m uvicorn main:app
```

Render デプロイ時：
- ダッシュボードの Environment で `APP_PIN` を設定

### PIN入力後もログインできない

**確認事項:**
1. `APP_PIN` 環境変数が設定されているか確認
2. セッションクッキーが有効になっているか確認
3. ブラウザのクッキーが有効になっているか確認

---

## 完了チェックリスト

- [x] pyproject.toml に依存関係を追加
- [x] app/config.py に環境変数読み込みを追加
- [x] templates/login.html を作成
- [x] main.py に SessionMiddleware を追加
- [x] main.py に /login, /logout, /health ルートを追加
- [x] 全エンドポイントに認証チェックを追加
- [x] .env.example を作成
- [x] .gitignore を作成
- [x] Dockerfile を作成
- [x] render.yaml を作成
- [x] ローカルでテスト実施
- [x] ドキュメント作成

---

## まとめ

PIN認証 + クラウドデプロイ対応が完全に実装され、以下の機能が動作確認されました：

✅ **認証機能**
- 4桁PIN入力フォーム
- PIN検証
- セッション管理（ブラウザ閉じるまで有効）
- ログアウト機能

✅ **API保護**
- 全エンドポイントへの認証チェック
- 未認証時は適切なエラーレスポンス

✅ **ヘルスチェック**
- 認証不要のヘルスチェック（Render対応）

✅ **デプロイ対応**
- Docker コンテナ化
- Render デプロイ設定
- 環境変数管理

これで Render 上での本番デプロイが可能です！

---

**実装日時**: 2026-02-08 19:00 JST
