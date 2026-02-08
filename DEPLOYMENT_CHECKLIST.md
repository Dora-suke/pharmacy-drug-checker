# Render デプロイ チェックリスト

## 実装完了確認 ✅

### コード変更
- [x] `pyproject.toml` に依存関係追加
- [x] `app/config.py` に環境変数読み込み
- [x] `main.py` に SessionMiddleware + ルート + 認証チェック
- [x] `templates/login.html` 作成

### 設定ファイル
- [x] `.env.example` 作成
- [x] `.gitignore` 作成
- [x] `Dockerfile` 作成
- [x] `render.yaml` 作成

### ドキュメント
- [x] `AUTHENTICATION_IMPLEMENTATION.md` 作成

---

## Renderデプロイ手順

### 1. ローカル確認（完了済み ✅）
```bash
APP_PIN=1234 SESSION_SECRET_KEY=test-secret python -m uvicorn main:app --reload
```

### 2. GitHub プッシュ
```bash
git add .
git commit -m "実装: PIN認証 + クラウドデプロイ対応"
git push origin main
```

### 3. Render ダッシュボード設定

**Step 1: New Web Service**
- https://render.com にアクセス
- 「New」 → 「Web Service」

**Step 2: GitHub接続**
- GitHub リポジトリを選択
- 「Connect」

**Step 3: 設定確認**
- Name: `pharmacy-drug-checker`
- Runtime: `Docker` (自動検出)
- Plan: `Free`
- Region: 任意（例：Tokyo）

**Step 4: 環境変数設定**
| キー | 値 | タイプ |
|------|-----|--------|
| `APP_PIN` | `1234` または 任意の4桁 | Secure String |
| `SESSION_SECRET_KEY` | (自動生成) | Standard |

**Step 5: デプロイ実行**
- 「Create Web Service」をクリック
- ビルド・デプロイ開始

### 4. デプロイ確認

✅ ビルド成功の確認:
```
...
Application startup complete
Uvicorn running on http://0.0.0.0:8000
```

✅ アクセス確認:
- `https://<your-service>.onrender.com` にアクセス
- PIN ログイン画面が表示される
- 設定したPINでログイン可能

### 5. ヘルスチェック確認
```bash
curl https://<your-service>.onrender.com/health
# Response: {"status":"ok"}
```

---

## トラブルシューティング

### ビルド失敗: "itsdangerous not found"
✅ **解決**: `pyproject.toml` に itsdangerous が含まれていることを確認

### PIN ログイン後も画面が変わらない
✅ **確認**: APP_PIN 環境変数が設定されているか確認

### セッションクッキーが保存されない
✅ **確認**: ブラウザのクッキー設定が有効か確認

---

## Render 無料プランの仕様

- **スリープ**: 15分のアイドルで自動スリープ
- **起動時間**: 30～60秒
- **キャッシュ**: 再起動時に初期化（アプリで自動再ダウンロード対応）
- **ストレージ**: 100MB

---

## セキュリティ設定確認

- [x] APP_PIN は Secure String として設定
- [x] SESSION_SECRET_KEY は自動生成
- [x] .env ファイルは .gitignore で除外
- [x] HTTPS は自動適用
- [x] セッションクッキーは httponly + samesite=lax

---

**プリント日**: 2026-02-08
**ステータス**: デプロイ可能 ✅
