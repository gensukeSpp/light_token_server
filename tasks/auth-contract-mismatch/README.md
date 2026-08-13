# 認証契約の不一致を解消する実装プラン（案A）

- 日付: 2026-08-10
- 方針決定: 案A ＝ **backend を呼び出し側（time-table-to-line）の契約に合わせる**
- 根拠: docs/design/2026-08-10-auth-contract-mismatch.md の検討結果。
  AGENTS.md「match the token shape and link URL to how that app consumes them」に合致。
  フロント変更ゼロで即座に動き、backend 2 ファイルの変更に留まる。

## 背景（何を直すか）

呼び出し側 time-table-to-line は旧 Flask 時代の契約のまま。

1. **初期トークン**: URL の `?token=<access>` から取得（AuthParent.tsx:14）。
   → backend `/timetable/auth` は現在 Cookie セット + `?token` 無しで 303 を返す。
2. **送信**: `Authorization: Bearer <token>` ヘッダーで送る（AuthInfo.ts:12-18,
   AxiosClientProvider.tsx:46-59）。
   → backend の `get_token_claims` / `require_token` は Cookie しか読まない。
3. **リフレッシュ応答**: body に新しいアクセストークン文字列を期待（queries.ts:25-29,
   AxiosClientProvider.tsx:18-26）。
   → backend `/refresh` は 303 + 空 body を返す。

いずれも「backend が新方式（httpOnly Cookie）に寄せたがフロントは旧方式のまま」という
同じ根因から発生している。案Aでは backend 側を旧契約に合わせる。

## 対象ファイルと現状

| ファイル | 現状 | 変更 |
|---------|------|------|
| `light_token_server/app/tokens.py` | `get_token_claims` / `require_token` が Cookie のみ読み取り | `Authorization: Bearer` ヘッダーを優先（無ければ Cookie）で読む |
| `light_token_server/app/routers/timetable.py` | `/timetable/auth` が `?token` 無し 303、`/refresh` が 303 + 空 body | `?token=<access>` 付き 303、`/refresh` が body に access token 文字列を返す |
| `light_token_server/tests/test_timetable.py` | Cookie 前提のアサーション | Bearer ヘッダー経路のテストを追加・既存を維持 |
| `light_token_server/docs/design/2026-08-10-auth-contract-mismatch.md` | 検討メモ | 解決済みの記録を追記（任意） |

## 前提・制約

- **httpOnly Cookie は残す**（捨てない）。Cookie が無い前提の旧クライアントを壊さないため、
  ヘッダーを優先・Cookie をフォールバックとする「両対応」にする。
- **`Authorization` ヘッダーが無い・空の場合は Cookie にフォールバック**。
- 応答形式はフロント契約に合わせる:
  - `/timetable/auth`: `RedirectResponse(f"{APP_URL}/auth?token={access}", 303)`
  - `/refresh`: `JSONResponse` で body に access token 文字列を返す
    （フロントは `string` も `{access_token|accessToken}` も許容 — 文字列で返せば安全）。
- Flask 由来の Flask コードは再導入しない（AGENTS.md の表記に従い `app/` 配下は
  FastAPI のみ）。
- DB マイグレーション（PostgreSQL 化）はユーザー本人が実施。本変更が DB 化と干渉しない。

## 実装ステップ（TDD）

### Step 1: `app/tokens.py` に Bearer ヘッダー読み取りを追加

`get_token_claims(request, expected_type)` を改修:
- まず `request.headers.get("Authorization")` を確認。
  書式 `Bearer <token>`（case-insensitive の "bearer"）なら token を取り出す。
- `expected_type == "refresh"` のときは Bearer で来たトークンも許容（フロントの
  `/refresh` は Bearer ヘッダーで送るため）。
- Authorization ヘッダーが無い/不正なら Cookie へフォールバック（従来動作）。

`require_token(request, db)` は `get_token_claims(request, "access")` に委譲しているので
自動的に追随。追加の変更不要。

### Step 2: `app/routers/timetable.py` をフロント契約に合わせる

- `post_access_token`（/timetable/auth）:
  - Cookie セット（set_auth_cookies）は維持。
  - リダイレクト先を `f"{APP_URL}/auth?token={access}"` に変更。
- `refresh_token`（/refresh）:
  - claims 取得は `get_token_claims(request, "refresh")`（Step1 後は Bearer 対応）。
  - 新 access token を発行し、Cookie セット＋**body に access token 文字列を返す**。
  - `from fastapi.responses import JSONResponse` を追加し、
    `return JSONResponse(access)` で返す（string body）。

### Step 3: テスト追加

`tests/test_timetable.py` に以下を追加:
- Bearer ヘッダー（Authorization）のみで `/event/all` が 200 になる（Cookie 無し）。
- `/timetable/auth` の Location に `?token=` が含まれる。
- `/refresh` を Bearer ヘッダーで叩くと body がアクセストークン文字列になり 200。
- 既存テスト（Cookie 経路）が素通しすることを確認。

### Step 4: 全体検証

- `source .venv/bin/activate && uv run pytest` が全て green。
- `uvicorn app.main:app` を起動し、curl で `/timetable/auth` の Location と
  `/refresh` の body を確認（任意・DB が無いとエンドポイントが動かない場合は
  テスト=SQLite を以て検証とみなす）。

## 明示的にやらないこと

- フロント（time-table-to-line）の変更はしない。
- httpOnly Cookie の削除はしない（両対応を維持）。
- DB マイグレーションはしない。
- `/timetable/inquiry` 等の他のエンドポイントは require_token 経由なので
  自動的に Bearer 対応になる。追加改修不要。

## リスク

- **低**: 変更は backend のトークン読み取り/リダイレクト/refresh 応答のみで、
  他エンドポイントのロジックには触れない。
- Bearer と Cookie の両対応で 404/401 の挙動は保たれる（どちらも無ければ従来通り 401）。