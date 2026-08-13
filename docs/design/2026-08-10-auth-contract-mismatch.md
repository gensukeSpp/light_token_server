# 認証契約不一致の診断と設計案 (2026-08-10)

## 1. 症状

リンククリック後に `time-table-to-line` アプリから `/refresh`, `/event/all` を叩くと
`401` になる。同時にフロントエンド側で TypeScript の型エラーが複数出る。

## 2. 結論（型エラーと 401 は「同じ根因」の表裏）

**バグではなく認証の契約（トークンの受け渡し方式）が backend と 呼び出し側で食い違っている。**
401 と型エラーは別々の不具合ではなく、一つの原因（API 契約の不一致）から同時に発生している。

## 3. 現状の契約のズレ

### backend（light_token_server）＝ 新方式（httpOnly Cookie）
- `app/tokens.py:52-60` `get_token_claims()` は **Cookie だけ**を見る。
  `Authorization: Bearer *** ヘッダーは一切読まない。
- `require_token`（tokens.py:81）も Cookie の access_token を検証するだけ。
- `/timetable/auth` は Cookie をセットして `RedirectResponse(APP_URL/auth)` へ 303。
  **URL クエリに token を載せない。**
- `/refresh` は refresh Cookie を検証し、新しい access Cookie をセットして 303 を返す。
  **body は空（トークン文字列を返さない）。**

### 呼び出し側（time-table-to-line）＝ 旧方式（Bearer ヘッダー + URL クエリ）
- `src/lib/AuthInfo.ts:12-18` `postHeaders()` は `Authorization: Bearer <token>` を送る。
- `src/components/templates/AxiosClientProvider.tsx:46-59` インターセプターが
  各リクエストに `Authorization: Bearer` を付与（token は react-query の
  `/refresh` 結果 or localStorage）。
- `src/components/templates/AuthParent.tsx:13-27` 初期トークンを **URL の `?token=`** から取得。
- `src/lib/authPayload.ts:10-47` `normalizeAuthPayload()` は `/timetable/inquiry` の
  body（JSON）を期待。
- `src/resources/queries.ts:25-29` `useRefreshQuery()` は `/refresh` が
  **body にトークン文字列**を返すことを期待。

### ズレの要約

| 観点 | backend（新） | フロント（旧） | 結果 |
|------|--------------|---------------|------|
| トークン送信 | Cookie のみ読む | `Authorization: Bearer` ヘッダーで送る | ヘッダー無視 → 401 |
| 初期トークン供給 | クエリ無しで `/auth` へ 303 | `?token=` から読む | token が届かない → 全 API 401 |
| `/refresh` の応答 | 303 + Cookie（body 空） | body にトークン文字列を期待 | 型エラー + 認証継続不能 |
| CORS/クッキー | httpOnly Cookie （samesite=lax） | `GET /event/all` 等は `withCredentials` 未指定 | クロスオリジンで Cookie 不達 |

## 4. 発生メカニズム（リンククリック後の経路）

1. ユーザーが light_token_server の `/`（index.html）で「time-table-to-line へ」リンクをクリック。
   → 実際には先に `/timetable/auth` が叩かれる想定だが、現在の backend は Cookie セット + `/auth` へ 303。
2. フロント `AuthParent.tsx` は `?token=` を探す → backend が token をクエリに載せないため **空**。
   → accessToken 未取得。localStorage にも無ければ空。
3. `AxiosClientProvider` は `Authorization: Bearer ''`（または無付与）で API を呼ぶ。
4. backend は Cookie（もろもろの理由で到達しない）を探す → **401**。
5. 401 を受けたフロントは `/refresh` で再発行を試みるが、`/refresh` も同じく
   Bearer ヘッダー（旧）で送るため 401。→ 認証ループ。

## 5. 型エラーが「関連している」理由

`src/components/templates/AxiosClientProvider.tsx:14-17` のコメントに既に書かれている通り、
古い backend は `/refresh` が **アクセストークン文字列を body で返していた**。
新 backend は **303 リダイレクト + 空 body** を返すため、フロントの型
`AxiosResponse<AuthInfoProp>` と実体が合わず型エラーになる。
- `fetch.ts:29` `basicAxios.post<AuthInfoProp>('/refresh', await postHeaders(_prev))`
  → headers を body 引数に渡している等で型不一致。
- `AxiosClientProvider.tsx:18-26` `extractTokenFromRefresh()` は string / `{access_token|accessToken}`
  を想定 → 新 backend の応答（空）と不整合。

→ **401（認証失敗）と型エラー（応答形状不一致）は、同じ「トークン契約の変更」から導かれる。**

## 6. 解消方針（2 案）

### 案 A：backend を呼び出し側（旧契約）に合わせる ★推奨
- `get_token_claims()` / `require_token` に `Authorization: Bearer` ヘッダー読み取りを追加
  （Cookie を先に見て、なければヘッダー、の順で対応）。
- `/timetable/auth`：`?token=<access>` を付けて `APP_URL/auth` へ 303（旧実装と同一）。
- `/refresh`：**body に新しいアクセストークン文字列を返す**（`content-type: application/json`）。
- `set_auth_cookies` は維持（必要なら両対応）。
- **影響**：フロント変更なしで即座に動く。AGENTS.md「match the token shape and link URL to
  how that app consumes them」に合致。httpOnly Cookie 方式は実質破棄（要求書 requirement-02 の
  方針と要調整）。

### 案 B：呼び出し側（time-table-to-line）を新方式（Cookie）に合わせる
- フロントの `AuthParent.tsx`, `AuthInfo.ts`, `AxiosClientProvider.tsx`, `fetch.ts`,
  `queries.ts` を改修し、token をヘッダー/Cookie にしない方式へ。
- httpOnly Cookie は JS から読めないため、react-query の token 状態管理チェーンを
  Cookie 連動型に書き直す大改修。
- **影響**：backend は現行のまま。フロント改修範囲が広く、CORS (`withCredentials`)
  と samesite 設定の見直しも必要。

## 7. 推奨

**案 A**。理由:
- フロント（既存資産・既に動いているクライアント）を壊さない。
- backend 側の変更は `tokens.py` / `routers/timetable.py` の 2 ファイル程度に留まる。
- AGENTS.md の指針（呼び出し側に合わせる）と一致。
- db マイグレーション（ユーザー本人が実施）と独立して進められる。

## 8. 判断に必要な残調査（必要なら実施）
- requirement-02.md の明示的なトークン方針（Cookie vs Bearer）。
- CORS 実運用時のオリジン（CLOUD_TIMETABLE4 の実際値）。
- フロントの既存テスト（queries.spec.tsx 等）が想定する応答形状。