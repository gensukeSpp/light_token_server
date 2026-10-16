# マイルストーン所属イベント取得 API 仕様

> **本ファイルは現行契約の正本です。** open/waiting 用 `GET /milestone/{milestone_id}/events` は一般ユーザー（非 admin 含む）が閲覧可（`require_token` のみ）、closed 用 `GET /milestone/closed/{milestone_id}/events` は管理者限定です。Issue #40 / PR #15 による差分の記録は `2026-10-15-milestone-events-group-name-auth-spec.md` を参照してください。
> 変更理由・動機・テスト変更などの詳細は、差分記録 `2026-10-15-milestone-events-group-name-auth-spec.md` を参照。
> フロント側仕様は `time-table-to-line/specs/2026-10-15-spec.md`。

## 1. 目的

マイルストーンに所属するイベントを取得できるようにする。マイルストーンはグループ横断で共有されるため、取得対象のイベントもグループを限定しない。open / waiting と closed は別の API で参照する。open / waiting の所属イベント一覧はグループメンバー（非 admin 含む）が閲覧するための機能（Issue #40）。

## 2. 共通要件

- すべてのエンドポイントで有効な認証トークンを必須とする。
- **open/waiting 用 `GET /milestone/{milestone_id}/events` は認証済みであれば誰でも閲覧可（`require_token` のみ）。**
- **closed 用 `GET /milestone/closed/{milestone_id}/events` はアクセストークンの `admin` claim が真である管理者に限る。管理者以外は `403 Forbidden`。**
- マイルストーンに所属するイベントは全グループから取得する。トークンの `group_id`、イベントの `group`、または操作者の所属グループによる絞り込みは行わない。
- イベントの所属は `milestone_id` が指定のマイルストーン ID と一致することで判定する。
- 成功時のレスポンスはイベントオブジェクトの JSON 配列とする。各要素は通常のイベント取得 API と同じ形式に加えて `group_name` を持つ。
- 対象イベントがない場合は `200 OK` と空配列 `[]` を返す。
- イベント配列の順序は仕様で保証しない。

## 3. イベントレスポンス

各イベントオブジェクトは次のキーを持つ。日時は既存イベント API と同じ形式 (`YYYY-MM-DDTHH:mm:ss.000Z`) とする。

| キー | 内容 |
|---|---|
| `id` | イベント ID |
| `staff_id` | イベント作成者 ID |
| `group` | 所属グループ ID |
| `group_name` | **所属グループ名（`Team.SHORTNAME`。Team 未登録なら `null`）※ Issue #40 で追加** |
| `start` | 開始日時 |
| `end` | 終了日時 |
| `title` | イベントタイトル |
| `summary` | イベント概要。未設定の場合は `null` |
| `progress` | 進捗。未設定の場合は `null` |
| `milestone_id` | 所属マイルストーン ID |
| `completed` | 完了状態 |

## 4. open / waiting マイルストーンのイベント取得

### `GET /milestone/{milestone_id}/events`

指定 ID のマイルストーンが `open` または `waiting` の場合、そのマイルストーンに所属するイベントを全グループから返す。

- 認証・認可: 有効なトークンがあれば誰でも閲覧可（**非 admin 含む**）。admin 判定は行わない。
- 存在しない ID、または `open` / `waiting` 以外の状態の ID: `404 Not Found`。
- closed マイルストーンの取得にはこの API を使用しない。

## 5. closed マイルストーンのイベント取得

### `GET /milestone/closed/{milestone_id}/events`

指定 ID のマイルストーンが `closed` の場合、そのマイルストーンに所属するイベントを全グループから返す。

- 認証・認可: **admin 限定**（管理者以外は `403 Forbidden`）。
- 存在しない ID、または `closed` 以外の状態の ID: `404 Not Found`。
- `closed` には、管理者による close と waiting からの自動 close の両方を含む。

## 6. エラーと境界

- 有効な認証情報がない、またはトークンが無効な場合の応答は、既存の認証依存 (`require_token`) の契約に従う。
- **open/waiting 用 `GET /milestone/{milestone_id}/events`**: 認証済みなら誰でも閲覧可（非 admin の 403 はない）。
- **closed 用 `GET /milestone/closed/{milestone_id}/events`**: 認証済みの非管理者による要求は `403 Forbidden`（admin gate を先に判定）。
- マイルストーンが存在しない場合、または各 API の対象状態と異なる場合は `404 Not Found` とし、イベント配列を返さない。open/waiting 用は admin gate がないため非 admin + 欠番でも `404` が優先される。
- ページネーション、絞り込み、更新、削除は本 API の対象外。
