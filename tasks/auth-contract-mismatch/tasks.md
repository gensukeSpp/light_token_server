# 実装タスク: 認証契約の不一致解消（案A）

- 作業リポジトリ: `light_token_server`
- 関連設計: tasks/auth-contract-mismatch/README.md
- 状態: 完了のタスクは冒頭に [x]、未着手は [ ]

## 前提

- 作業前に `source .venv/bin/activate` を実行（このプロジェクトの venv は
  プリアクティベートされていない）。
- 検証は `uv run pytest`（tests/ は SQLite StaticPool で DB 不要）。

## タスク

### T1: `app/tokens.py` を Bearer ヘッダー対応にする
- [x] `get_token_claims` でまず `Authorization: Bearer <token>` を確認し、
      存在すればそれを使う。無ければ Cookie にフォールバック。
- [x] `type`（access/refresh）検証は Bearer でも Cookie でも同じロジックを通す。

### T2: `app/routers/timetable.py` をフロント契約に合わせる
- [x] `/timetable/auth` のリダイレクト先に `?token=<access>` を付ける。
- [x] `/refresh` が body に新しい access token 文字列を返す（JSONResponse）。
- [x] `/refresh` の claims 取得が Bearer ヘッダーでも動くことを確認（T1 に依存）。

### T3: テストを追加する
- [x] Bearer ヘッダーのみで `/event/all` が 200 になるテスト。
- [x] `/timetable/auth` の Location に `?token=` が含まれるテスト。
- [x] `/refresh` を Bearer で叩くと body が access token 文字列（200）になるテスト。
- [x] 既存テストが全て pass することを確認。

### T4: 全体検証
- [x] `uv run pytest` が全 green。（23 passed）
- [x] （任意）uvicorn 起動 + curl で `/timetable/auth` の Location と
      `/refresh` の body を確認。

## やらないこと

- フロント（time-table-to-line）の変更
- httpOnly Cookie の削除
- DB マイグレーション