# PR #21 レビュー: fix #261023: Issue #20 更新・削除の所有者チェック

- 対象: https://github.com/gensukeSpp/light_token_server/pull/21
- ブランチ: fix/front-review/45-m-2 → main（compare target: origin/main）
- レビュー日: 2026-10-23
- 前提: 実装意図（本人 or admin、admin は例外）は合致と判断済み。本記録は意図に対する実装の穴・周辺影響を見る。

## 参照資料

確認できたもの:
- PR 本文 / コミット 1751c31
- Issue #20 (OPEN): フロント PR #45 レビュー [Medium] 指摘 2、admin 例外の要件
- specs/2026-10-23-event-owner-permission-spec.md（差分記録）
- tasks/issue-20/plan.md, tasks.md, tasks2.md
- .hermes/rules/milestones.md（権限契約を追記済み）
- 周辺: app/routers/timetable.py, app/schemas.py, app/tokens.py

存在しない / 対象外:
- docs/architecture/ 配下に本変更に対応する文書はなし（実装後の docs PR 扱いのため、欠落は指摘対象外）
- Issue #20 に comments はなし

## 総評

`/event/update/{id}`、`/event/remove/{id}`、`/date/update` の 3 箇所に共通ヘルパー `_require_event_owner_or_admin` を適用し、本人 or admin 以外を 403 にする変更。判定順は 404 → 403 で統一されており、仕様・ルール・テストも揃っている。既存テスト 87 passed を再現確認した（`.venv/bin/python -m pytest -q`）。

差分は小さく、既存の本人・admin 操作は挙動を変えない。残課題は「作成時の所有者偽装」（後述の指摘 1）と、差分に混ざった無関係な pycache 削除のみ。

## 良い点

- 権限判定を 1 関数に集約し、3 エンドポイントで同一ポリシーを使う（DRY）。
- /date/update の既存チェックを置き換え、admin 例外を全エンドポイントで揃えた。
- 非 admin の「他人」テストを作るため conftest に staff 1002 を追加。テストは RED → GREEN の順で検証されている。
- 削除拒否時にイベントが残ることを `1 in remaining` で確認している。
- spec / milestones.md / tasks が差分まで整合している。
- /date/update は全件検証後に commit するため、途中で 403 になった場合は DB 反映されない（部分更新なし）。

## 指摘事項

### [Medium] 1. /event/add が body の staff_id を無検証で採用 — 所有者チェックの前提が崩れる
- 場所: app/routers/timetable.py `append_event_item`（170 行付近）、app/schemas.py `EventCreate.staff_id: int`
- 問題: 作成時の `staff_id` は request body から取り、claims と照合していない。認証済みの任意ユーザーが `staff_id=他人` でイベントを作成できる。
- 影響: 今回の所有者チェックは「作成者 = staff_id」を前提にしている。他人名義のイベントが作成されると、その持ち主本人が後から更新・削除する手段を得る一方、作成者は 403 で触れない。また、他人の `/event/user` 一覧に偽のイベントが混入する。更新・削除の穴は塞がれたが、「所有者の偽装」という同じ権限モデルの穴が残る。
- 本 PR のスコープ外の既存欠陥だが、「所有者」の定義に関わるため、本 PR で認識しておくべき。
- 修正方針: `append_event_item` で `body.staff_id != claims["user_id"]` かつ非 admin の場合は 403。admin は他人名義の作成を許す（要件に応じる）。別 Issue として登録し、PR 説明に「作成時の staff_id 検証は未対応」と明記することを推奨。

### [Low] 2. 差分に tests/__pycache__ の削除が混入
- 場所: PR の files に `tests/__pycache__/conftest.cpython-313-pytest-9.1.1.pyc` と `test_health...pyc` の DELETED が含まれる。
- 問題: 本 Issue と無関係のバイナリ変更。pycache は再生成されるため、ローカルでテストを回すたびに `M` が出る（issue-20 の差分記録 7 節にも記載あり）。
- 修正方針: これらを追跡対象から外すなら `.gitignore` 追加と `git rm --cached` を別コミットに分ける。本 PR からは削除を外す。

### [Low] 3. /date/update の 403 詳細文言を変更
- 場所: app/routers/timetable.py `_require_event_owner_or_admin`、`detail="not allowed to modify other member's event"`
- 問題: 旧 `/date/update` の文言は「...: {item.id}」を含んでいた。ID が落ちたため、フロントでエラーをログ・表示している場合に差異が出る可能性がある。テストは文言を固定していないため CI では検出されない。
- 修正方針: 必要ならヘルパーに event_id を渡して文言に含める。フロントが文言に依存していないことを確認しておく。

### [Low] 4. 周辺の print 残存（本 PR のスコープ外）
- 場所: app/tokens.py の `get_token_claims` 内 `print(f"Wrong token type: ...")` は残存。
- 問題: AGENTS.md の方針（トークン・シークレットの print 削除）に対して未完。今回は他の print は削除されている。
- 修正方針: 別タスクで整理。本 PR で必須ではない。

## 周辺ロジックへの影響（確認結果）

- マイルストーン所属: `update_event_item` の `milestone_id` 更新も本人 or admin に制限される。仕様「イベントからの所属選択は一般ユーザーも可能」は自分のイベントに対しては従来どおり成立する。
- 閉じ処理（remove_milestone / update_milestone）は admin 専用で、イベントの staff_id は見ないため影響なし。他人のイベントの completed を admin が書き換える点は従来どおり。
- `/group/all`、`/event/all`、`/event/user`、`/milestone/*/events`（to_dict / to_milestone_dict）は変更なし。
- DB スキーマ変更なし。追加クエリもなし（既取得の target を比較するのみ）。
- フロント（time-table-to-line）は UI 側で isOwnEvent 済みのため、実行時の振る舞いは変わらない見込み。ただし 403 が増えるため、非本人操作の UI 経路がないことは確認が必要。

## 改善提案

1. 指摘 1 を別 Issue として登録し、append_event_item の staff_id 検証を追加する（優先度 Medium）。
2. PR から tests/__pycache__ の削除を外す（または別コミットに分離する）。
3. 403 文言に event_id を含める（任意）。
4. 残存する print は backend 整理タスクで処理する。

## 判定

本 Issue #20 の範囲（更新・削除・日時移動の所有者チェック）は、意図どおり実装されており、マージ可能と判断する。ただし指摘 1 は同じ権限モデルの残穴のため、マージ後の別 Issue 化を強く推奨する。
