# マイルストーン機能 設計すり合わせメモ

> **目的:** requirement-03.md の設計を既存コードベースとすり合わせ、不明確点を解消する。

**ステータス:** 未確定 — ユーザーの確認待ち

---

## 1. ユーザーからの提案

### 1-1. `group_id` カラムは不要
- マイルストーンはグループ間で共有する（要件本文「グループ間で共有する場合も考慮し」）
- ERDも `MILESTONE ||--o{ T_TIMELINE_EVENT` でグループを介さない
- **提案:** `group_id` は削除し、権限も「admin=True のユーザー全員」に変更

### 1-2. `status` は Boolean で良い
- `status=True` (open) / `False` (closed)
- `accomplished_date` があれば closed という2重表現
- Booleanの方がクエリが単純化される（`WHERE status=True`）
- **提案:** Booleanで維持（APIレイヤで closed→open 拒否）

---

## 2. 不明確点（要確認）

### 2-1. テーブル名の命名規則
- 要件: `MILESTONE`
- 既存: `M_STAFFINFO`, `M_TEAM`, `M_LOGGININFO`, `T_TIMELINE_EVENT`
- **提案:** `M_MILESTONE` に合わせる

### 2-2. `created_at` の型
- 要件: `Date()`
- 既存 `EventORM`: `DateTime()`
- **提案:** `DateTime()` に合わせる（時刻も記録すべき）

### 2-3. `staff_id` の外部キー参照
- 要件: `ForeignKey("M_LOGGININFO.STAFFID")`
- 作成者名表示には `M_STAFFINFO` が必要
- **確認が必要:** `M_LOGGININFO` のみで十分か

### 2-4. 権限モデルの矛盾
- グループ共有リソースなのに「そのグループの管理者のみ」が作成
- **提案:** 「admin=True のユーザー全員」が作成可能に変更

### 2-5. イベントの `completed` フィールド
- 手動か自動か不明
- AGENTS.md memoryには「自動導出しない」とある

### 2-6. `/milestone/remove` の UI 有無
- APIは定義されているが、操作フローに削除手順がない

### 2-7. カラーパターンの被り対策
- 10パターンしか準備しない
- 大量作成時のアルゴリズム

### 2-8. Calendar 側の `milestone_id` 追加
- 既存の `/event/add` スキーマに追加するか、別APIか

---

## 3. 既存コードとの整合性（確認済み）

### app/models.py 追加予定
- EventORM に `milestone_id` (FK), `completed` (Boolean) を追加
- `to_dict()` に milestone 関連情報を追加
- 新規 `MilestoneORM` モデルを追加

### app/schemas.py 追加予定
- `MilestoneCreate`, `MilestoneUpdate`, `MilestoneResponse` を追加
- `EventCreate` に `milestone_id` を optional で追加

### app/routers/timetable.py 追加予定
- `/milestone/add` (POST) — admin のみ
- `/milestone/all` (GET) — すべてのmilestone（全グループ表示用）
- `/milestone/update` (POST) — accomplished_date のみ更新、admin のみ
- `/milestone/remove` (DELETE) — admin のみ

---

**ステータス:** 未確定 — ユーザーの確認待ち
