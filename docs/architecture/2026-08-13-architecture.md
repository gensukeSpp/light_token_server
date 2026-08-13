# 2026-08-13 Architecture Snapshot: Flask to FastAPI Migration

## Purpose
FlaskベースのレガシーコードからFastAPIへの移行を完了し、認証システムをJWTベースに刷新することで、システムの安定性とセキュリティを向上させる。

## Overview
FlaskからFastAPIへの完全移行と、JWTベースのハイブリッド認証システムの導入。

## Key Design Decisions
- **Framework**: FastAPI (APIRouter) への統一。
- **Authentication**: `httpOnly Cookie` と `Bearer Token` を組み合わせたJWT認証。
- **Security**: CORSの `allow_credentials=True` 設定によるフロントエンド接続の最適化。
- **Access Control**: FastAPIの依存性注入 (DI) を利用した認可フローの確立。

## Background & Rationale: Auth Contract Mismatch
移行中、バックエンドの新方式（httpOnly Cookie）とフロントエンドの旧方式（Bearer ヘッダー）の間で認証の契約不一致が発生しました。これにより認証ループ（401）と型エラーが誘発されました。
フロントエンドの大規模な改修を回避するため、以下の解消方針（案A）を採用しました：
- バックエンドが Authorization: Bearer ヘッダーにも対応。
- `/timetable/auth` はトークンをクエリに乗せてリダイレクト。
- `/refresh` はレスポンスボディにトークン文字列を返す方式を維持。
これにより、既存クライアントとの互換性を確保しました。

## Changed Files
- `app/main.py`
- `app/tokens.py`
- `app/routers/timetable.py`
- `app/config.py`
- `app/schemas.py`
- (Deleted) `app/routes.py`, `app/auth_middleware.py`

## Next Steps
- 追加のバリデーションルールの詳細化。
- モニタリング・ロギングの強化。
