# PR #15 レビュー記録

- 対象: gensukeSpp/light_token_server PR #15「feat #260928: Issue #40 milestone events API（group_name 付与・閲覧権限緩和）」
- 状態: OPEN / base: main (05a9acb) / head: feature/milestone-events/40
- 比較基準: `main`（ローカルにも存在し、origin/main と同一 05a9acb）
- 関連: PR 42（gensukeSpp/time-table-to-line、フロント側。本記録ではバックエンド節のみ照合）
- 権限緩和（open/waiting 用 GET を require_token のみに）はユーザー同意済みのため、判断対象外。
- レビュー日: 2026-10-15

## 参照資料の確認

確認できたもの:
- PR 本文・コミット・変更ファイル: `gh pr view 15`（2 コミット: ab5127f, e599666）
- PR 42 本文（バックエンド節）: `gh pr view 42 --repo gensukeSpp/time-table-to-line`
- Issue #40: time-table-to-line 側に存在（`gh issue view 40 --repo gensukeSpp/time-table-to-line`）。light_token_server 側に Issue #40 は存在しない（GraphQL エラー）。PR 本文の `Closes gensukeSpp/time-table-to-line#40` はクロスリポジトリ参照であり、整合する。
- 仕様: `specs/2026-10-13-milestone-event-retrieval-spec.md`（改訂済み）、`specs/2026-10-15-milestone-events-group-name-auth-spec.md`（新規）
- アーキテクチャ: `docs/architecture/2026-10-15-1-architecture.md`、`docs/architecture/2026-10-15-2-architecture.md`
- ルール: `.hermes/rules/milestones.md`
- 関連タスク: `tasks/task-03/`、`tasks/task-11/`、`tasks/task-12/`（re-open 時の completed 復帰。今回差分には無関係だが、同じ API を参照）
- テスト実行: `uv run pytest -q` → 72 passed（PR 本文の記載と一致）

存在しなかった/対象外のもの:
- `tasks/issue-40/`: light_token_server には存在しない（フロント PR 42 側にのみ存在）。このため PR 15 について task 対応関係は確認できず。
- `specs/README.md`: light_token_server には存在しない（PR 42 側の追加ファイル）。
- Issue #40 の light_token_server 側の本体: 存在しない（上記のとおり、参照先は time-table-to-line）。

注意（ローカルとリモートの差）:
- ローカルブランチは origin より 1 コミット先行（d863d2c「docs #15: 仕様・構造ファイルを新規作成」）。このコミットは PR 15 のコミット一覧に含まれていない。つまり、以下の新規仕様・アーキテクチャ文書は PR としてはまだ提出されていない状態。

## 総評

PR 15 は、Issue #40 の要件のうち「非 admin でも open/waiting のイベントを閲覧可」「レスポンスに group_name を付与」を実装し、closed 用 API の admin gate は維持している。差分は `timetable.py` の数行と既存テストの追随で、最小限にまとまっている。`_get_milestone_events` の共通化により closed 側にも group_name が付くが、この点は仕様（§2.1）で明示されている。ローカルで pytest 72 件の通過を再現した。

主な懸念は、実装ではなく文書とテストにある。権限契約を変えたにもかかわらず、ルールファイルとアーキテクチャ文書の一部が旧契約（admin のみ）のまま残っており、矛盾する。また、仕様に検証観点として挙げた「Team 未登録時の null」と「closed 側の group_name」のテストが無い。

## 良い点

- admin gate 撤去の範囲が open/waiting 用のみに限定され、closed 用（`timetable.py` の `get_closed_milestone_events`）は変更されていない。
- `_get_milestone_events` に共通化し、open/waiting と closed の両方で group_name の付与ロジックを一本化した。
- 403/404 の優先順位（非 admin + 欠番: open/waiting=404、closed=403）を仕様に明記し、テスト `test_non_admin_missing_milestone_returns_404_vs_403` で分化を検証している。
- DB スキーマ変更なし（応答時に M_TEAM を解決）。マイグレーション不要な点は妥当。
- PR 42 のバックエンド節（group_name 付与、require_token のみ、closed は admin 限定、pytest 72 passed）と本 PR の内容は一致している。

## 指摘事項

### [High] 指摘 1: ルール文書が新契約と矛盾（旧契約のまま）
- 場所: `.hermes/rules/milestones.md` 37-38 行、51 行
- 内容: 「`GET /milestone/{milestone_id}/events` は admin のみ参照可能」と記載されたまま。本 PR の仕様（specs/2026-10-15-...）は §8 の「残件」でこの未更新を自認している。
- 影響: 今後の実装・レビューが旧契約（admin 限定）を正として判断するおそれがある。AGENTS.md がこのファイルを正として参照するため影響が大きい。
- 期待する修正: 37-38 行と 51 行を「open/waiting は require_token のみ、closed は admin のみ」に更新。40 行・52 行（closed 側）は現状のままで正しい。

### [Medium] 指摘 2: 旧版アーキテクチャ文書が新契約と矛盾
- 場所: `docs/architecture/2026-10-15-1-architecture.md` 10 行
- 内容: 「いずれのエンドポイントも管理者権限 (`admin` claim) を必須とし、非管理者の場合は 403」と記載。同日付の `2026-10-15-2-architecture.md` がこれを覆すが、1 の方には「旧版」「置換」の注記がない。
- 影響: 同日付の 2 ファイルが並ぶため、どちらが現行か判別しにくい。
- 期待する修正: 1 のファイル冒頭に「本ファイルは 2 により置換（Issue #40 で open/waiting 用の認可を緩和）」と注記するか、10 行を現契約に合わせる。

### [Medium] 指摘 3: 新規仕様・文書がリモートの PR に未反映
- 場所: ローカル d863d2c（未 push）。対象は `specs/2026-10-15-milestone-events-group-name-auth-spec.md`、`docs/architecture/2026-10-15-1/2-architecture.md`、`docs/architecture/README.md`（追加分）
- 内容: PR 15 のファイル一覧に上記が含まれていない（`app/routers/timetable.py`、`specs/2026-10-13-...`、`tests/test_milestone.py` の 3 件のみ）。
- 影響: レビュー対象（GitHub 上の PR）と、ユーザーが読む文書（ローカル）が食い違う。特に指摘 1・2 の矛盾はローカルにしか無い文書同士の話。
- 期待する修正: d863d2c を push して PR に含める。または文書の扱いを別 PR に分けると明記する。

### [Medium] 指摘 4: 仕様の検証観点に対応するテストが無い（Team 未登録ケース）
- 場所: `tests/test_milestone.py`、仕様 `specs/2026-10-15-...-spec.md` §9
- 内容: §9 の検証観点に「`group_name` が `null` になる Team 未登録ケース」を挙げているが、テストが無い。実装は `team.SHORTNAME if team else None`（`app/routers/timetable.py` 312-313 行付近）。
- 影響: 欠損時の null 応答や例外パスが未検証。
- 期待する修正: 存在しない group の event を作成し、`group_name is None` を検証するテストを追加。SQLite の外部キー強制が無効なら conftest の設定を確認した上で作成可能か判断すること（未確認）。

### [Medium] 指摘 5: closed 側の group_name 付与がテストされていない
- 場所: `tests/test_milestone.py` の `test_closed_milestone_events_returns_events_across_groups`（205 行付近）ほか closed 系テスト
- 内容: 仕様 §2.1 は「両 API に適用される」と明記しているが、closed 側のテストは group_name を検証していない。`test_milestone_events_response_keys_and_format` も open 側のみ。
- 影響: `_get_milestone_events` を将来変更した際に closed 側だけ壊れても検出できない。
- 期待する修正: closed 系の既存テストに `group_name` のアサーションを追加する。

### [Low] 指摘 6: 文書の破損（仕様 §3.1 の認証行）
- 場所: `specs/2026-10-15-milestone-events-group-name-auth-spec.md` 76 行
- 内容: `| 認証 | 有効なアクセストークン必須（`Authorization: Bearer *** 判定は行わない** |` — バッククォートが閉じておらず、太字も閉じていない。「admin 判定は行わない」などの語句が欠落している可能性がある（推測）。
- 影響: Markdown が崩れて表が壊れる。意味も欠落している可能性がある。
- 期待する修正: 原文を確認し、正しい文言に修正する（例: `Authorization: Bearer {token}` と「admin 判定は行わない」を明記）。

### [Low] 指摘 7: 同一エンドポイントの仕様が 2 文書に重複
- 場所: `specs/2026-10-13-milestone-event-retrieval-spec.md`（改訂済み）と `specs/2026-10-15-milestone-events-group-name-auth-spec.md`
- 内容: 両方が同じエンドポイント・同じ権限マトリクスを記述している。今後どちらかだけ更新されると、再び矛盾する。
- 期待する修正: 現行の正本を 1 つに決める（例: 10-13 を正本とし、10-15 は「変更履歴」として差分のみ記載）。

### [Low] 指摘 8: N+1 クエリ
- 場所: `app/routers/timetable.py` の `_get_milestone_events`（308-313 行付近）
- 内容: イベント件数ぶん `db.get(Team, ...)` を発行する。仕様 §8 でも認めている。
- 影響: 現状の規模では軽微。イベント数が増えると負荷が出る。
- 期待する修正: 一度に `db.query(Team).filter(Team.CODE.in_(group_ids))` で取得し、dict にまとめる。

### [Low] 指摘 9: PR 本文と仕様の参照の不整合（軽微）
- 場所: PR 15 本文
- 内容: 本文に「フロント PR 42 と併せて実施」と記載があるが、PR 42 側の本文からは PR 15 への URL 参照がない。両方の本文の相互リンクが無い。
- 期待する修正: PR 42 の本文に PR 15 の URL を追記する（フロント側の作業）。

### [Nit] 指摘 10: 未使用になった引数
- 場所: `app/routers/timetable.py` の `get_milestone_events`（321 行付近）
- 内容: `claims` は権限判定に使われなくなった。認証の依存として残すこと自体は正しい（require_token による 401 判定のため）。
- 期待する修正: 現状のままでも良い。linter が警告する場合のみ `_claims` 等にする。

## 改善提案

1. ルール文書（指摘 1）を先に直す。これが最も誤読を生みやすい。
2. d863d2c を push して PR 15 に含め、指摘 2・3 を解消する。
3. テストを追加する（指摘 4・5）。
   - Team 未登録で `group_name` が None になるケース
   - closed 側の `group_name` アサーション
4. 仕様文書を 1 本に整理し、もう一方は差分（変更履歴）に縮める（指摘 7）。
5. 文書の破損箇所（指摘 6）を直す。
6. 余力があれば N+1 を解消する（指摘 8）。

## 検証ログ

- `uv run pytest -q` → 72 passed, 1 warning（テストの警告は httpx 関連で本 PR とは無関係）
- 未実施: リモート PR の head（ab5127f + e599666）に対するテストは、ローカル（d863d2c 含む）と同一コード。d863d2c は文書のみのため、テスト結果は同一と判断。
