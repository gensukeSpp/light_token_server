# Python 汎用レビューレポート (@app/)

- 対象: `light_token_server` の `app/` 配下すべてのソース（Python 11 ファイル + テンプレート 3 ファイル）
- チェック基準: `auto-skill-python-review-checklist`（汎用 Python 品質項目 30 件）
- 実施日: 2026-08-10
- 種別: 読み取り専用調査（ファイル変更なし）

## 発見された問題

| # | カテゴリ | 項目 | ファイル | 重要度 | 説明 |
|---|----------|------|----------|--------|------|
| 1 | D-4 | デッドコード・重複代入 | app/config.py:37-39 | High | **37 行**で開発用デフォルトを設定した `SECRET_KEY` を、**39 行**でデフォルトなしの再取得により上書きしている。開発環境で env 未設定の場合 `None` となり、SessionMiddleware / JWT 署名が失敗するおそれがある。本番の保護（40-41 行）は存在するが、デフォルト値自体が重複代入により死コード化している。 |
| 2 | C | 入力バリデーション不足（防御的プログラミング） | app/routers/timetable.py:31-34 | Medium | `convert_str_to_date()` は正規表現で `.123Z` を除去後、`%Y-%m-%d %H:%M:%S` で解析する。形式が異なる入力（例: `%Y-%m-%dT%H:%M:%S%z` や datetime-local 形式）で `ValueError` が発生し 500 になる。Pydantic 側のフォーマット検証や例外処理で堅牢化するのが望ましい。 |
| 3 | B-1 | 辞書の直接アクセス | app/tokens.py:84, app/routers/timetable.py:74-79,99,122,131 | Low | `claims["user_id"]` / `claims["group_id"]` の直接アクセス。自アプリで発行した JWT claims のため実害はないが、防御的プログラミングの観点では `claims.get(...)` → None ガードが望ましい。 |

## 該当コード

### 1. app/config.py:37-39

```python
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-change-me")  # ← 39行で上書きされ死コード化
ENV = os.getenv("ENV", "development")
SECRET_KEY = os.getenv("SECRET_KEY")  # ← デフォルトなしで再取得。env未設定時はNoneになる
if ENV == "production" and not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in production")
```

**推奨パターン**（代入は 1 回に統一）:

```python
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-change-me")
```

### 2. app/routers/timetable.py:31-34

```python
def convert_str_to_date(str_date: str) -> datetime:
    regex_data = re.sub(r"\.\d{3}Z", "", str_date)
    replaced = regex_data.replace("T", " ")
    return datetime.strptime(replaced, "%Y-%m-%d %H:%M:%S")
```

**推奨パターン**: Pydantic 側で `datetime` 型に制約するか、少なくとも `ValueError` を捕捉して HTTPException(422) に変換する。

### 3. app/tokens.py:84 ほか

```python
user = db.query(StaffLogin).filter(StaffLogin.STAFFID == claims["user_id"]).first()
```

**推奨パターン**: `claims.get("user_id")` → None ならガード（内部生成のため任意）。

## 問題なしと確認された項目

- A-1 ✅（sqlite3 不使用。`get_db` が finally で close（database_base.py:12-17））
- A-2 ✅（Session の close が全 DB アクセス経路で一貫して保証）
- A-3 ✅（`ThreadPoolExecutor` 不使用）
- B-2 ✅（`.first()` の戻り値はすべてガード済み: login.py:39 / security.py / tokens.py:85 / timetable.py:59,86,167）
- B-3 ✅
- C-1 ✅（ネストしたリスト/座標処理なし）
- C-2 ✅ / C-3 ✅
- D-1 ✅（ループ不変の処理なし） / D-2 ✅（重複チェックなし） / D-3 ✅（結果を捨てるだけの I/O なし）
- E-1 ✅（Event の id は自動採番主キー） / E-2 ✅
- F-1 ✅（`TemplateResponse(request, name, {...})` は request 優先の位置引数形式で、AGENTS.md が定める Starlette 1.4.1 の規約に一致）
- F-2 ✅（テンプレートに hx-* 属性なし） / F-3 ✅（JSON 返却は `require_token` の API エンドポイントのみで htmx 端点ではない） / F-4 ✅（`Path(__file__).resolve().parents[1] / "templates"` で絶対パス）
- G-1 / G-2 ✅（パスワード検証は werkzeug を使用し、不要な多重ロジックなし）
- H-1 ✅（import 漏れなし） / H-2 ✅（print() なし） / H-3 ✅（コメントと実装の乖離なし）
- I-1 ✅（デッドメソッドなし） / I-2 ✅（get_or_create 不使用） / I-3 ✅ / I-4 ✅（`convert_str_to_date` は add 経路で一貫して適用）

## 統計

- 発見: 3 件（Critical: 0, High: 1, Medium: 1, Low: 1）
- 問題なし: 26 項目
- 未確認（対象外）: 1 項目（I-5: スタイル設定の比較は `pyproject.toml` / `.vscode` / `.editorconfig` 間で行うため、`@app/` の範囲外）
