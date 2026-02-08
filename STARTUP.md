# 起動ガイド - 薬局向け医薬品供給状況チェッカー

## クイックスタート

### 前提条件

- Python 3.10 以上
- uv パッケージマネージャー（インストール済み）

### 1. 初回セットアップ（1回のみ）

```bash
cd /Users/nori3/Desktop/desktop/pharmacy-drug-checker
uv sync
```

このコマンドで、すべての依存パッケージが `.venv` に自動インストールされます。

### 2. アプリケーション起動

```bash
uv run uvicorn main:app --reload --port 8000
```

出力例：
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### 3. ブラウザでアクセス

```
http://localhost:8000
```

## 初回起動時の動作

アプリケーション起動時に以下の処理が自動実行されます：

1. **厚労省ページのスクレイピング**
   - `https://www.mhlw.go.jp/stf/.../` から Excel ダウンロードリンクを探索

2. **リモートメタデータ確認**
   - ETag / Last-Modified をサーバーから取得
   - キャッシュと比較

3. **ダウンロード判定**
   - 差異あり → 新しいデータをダウンロード
   - 差異なし → キャッシュを利用

4. **ステータス表示**
   - UI上に「最終更新: 2024-01-15 10:30:00」が表示

## キャッシュについて

### キャッシュの保存場所

```
cache/
├── mhlw_latest.xlsx      # 厚労省の最新 Excel
└── mhlw_meta.json        # メタ情報（ETag等）
```

### キャッシュをクリアする方法

以下のファイルを削除して再度アプリを起動してください：

```bash
rm -f /Users/nori3/Desktop/desktop/pharmacy-drug-checker/cache/mhlw_*
```

再起動時に自動的に新しいデータがダウンロードされます。

## 使用シナリオ

### シナリオ 1: サンプルで動作確認

1. アプリを起動
2. ファイル選択で `sample/pharmacy_sample.xlsx` を選択
3. 「照合実行」をクリック
4. 結果表を確認

### シナリオ 2: 実際の薬局データで使用

1. 薬局の Excel ファイルを準備
   - 列名: 「薬品コード」「薬品名」は必須
2. ファイル選択で薬局ファイルを選択
3. 「照合実行」をクリック
4. 10日以内に更新された医薬品が表示される

### シナリオ 3: 厚労省データを手動更新

1. UI ヘッダーの「🔄 更新確認」をクリック
2. ステータスに更新結果が表示される
3. 必要に応じてファイルを再度照合

## よくあるトラブル

### エラー: `ModuleNotFoundError: No module named 'fastapi'`

**原因**: 依存パッケージがインストールされていない

**解決方法**:
```bash
uv sync
```

### エラー: `Port 8000 is already in use`

**原因**: ポート 8000 が別のプロセスで使用されている

**解決方法**: 別のポートで起動
```bash
uv run uvicorn main:app --reload --port 8001
```

### ダウンロードが失敗する

**原因**: ネットワーク接続の問題または厚労省サーバーの負荷

**解決方法**:
- ネットワーク接続を確認
- しばらく待ってから「🔄 更新確認」を再度クリック
- キャッシュがあれば、それを使用（メッセージで "Using cached Excel" と表示）

### ファイルのアップロードがうまくいかない

**原因**: Excel フォーマットが異なる、または列名が一致していない

**確認方法**:
1. `sample/pharmacy_sample.xlsx` と列構成を比較
2. 必須列「薬品コード」「薬品名」が存在するか確認
3. ブラウザの開発者ツール（F12）でエラーメッセージを確認

## 設定のカスタマイズ

### 10日間の期間を変更したい場合

`app/config.py` を編集：

```python
# 変更前
DAYS_BACK = 10

# 変更後（例: 30日間に変更）
DAYS_BACK = 30
```

変更後、アプリを再起動してください。

### ポート番号を変更したい場合

起動時に指定：

```bash
uv run uvicorn main:app --reload --port 9000
```

### ホスト名を変更したい場合（ネットワークからアクセス可能にする）

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

⚠️ 注意: ネットワーク接続時はセキュリティに注意してください。

## 開発モードの無効化

本番環境では `--reload` を削除：

```bash
uv run uvicorn main:app --port 8000
```

## ログレベルの変更

詳細ログを表示：

```bash
uv run uvicorn main:app --reload --log-level debug
```

## 終了方法

ターミナルで `Ctrl+C` を入力してアプリケーションを停止してください。

```
KeyboardInterrupt
INFO:     Shutting down
INFO:     Waiting for background tasks to finish
INFO:     Application shutdown complete
```

---

**問題が発生した場合**: ターミナルのログメッセージを確認し、README.md の「トラブルシューティング」セクションを参照してください。
