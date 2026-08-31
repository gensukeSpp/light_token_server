# v0.07 修正: M_MILESTONE.guidline_end_date -> guideline_end_date へのリネーム (スペル修正)
#
# Issue #9 で guidline のスペルミスを guideline に統一した。
# 列名をリネームする(データ保持のため create+drop ではなく rename)。
#
# 注意: このマイグレーションの実行(upgrade)は利用者本人が実施する。
# 本ファイルは差分準備のみ。

"""v0.07

Revision ID: e0fbbca5c733
Revises: 3be6e8d10186
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0fbbca5c733'
down_revision: Union[str, Sequence[str], None] = '3be6e8d10186'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # v0.06 で Boolean -> String(10) に型変更した際、既存行はリテラル
    # 'true'/'false' のまま残っている (PostgreSQL の暗黙キャスト)。
    # 新 API の status 契約 ('open'/'waiting'/'closed' の完全一致) を満たすため、
    # 旧値を正規化してから新 API を有効化する (PR #10 レビュー P1)。
    op.execute("UPDATE \"M_MILESTONE\" SET \"status\" = 'open' WHERE \"status\" = 'true'")
    op.execute("UPDATE \"M_MILESTONE\" SET \"status\" = 'closed' WHERE \"status\" = 'false'")

    # 列名リネーム(データ保持)
    op.alter_column(
        'M_MILESTONE',
        'guidline_end_date',
        new_column_name='guideline_end_date',
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 正規化した 'open'/'closed' を旧 boolean リテラルへ戻す
    # (waiting は v0.06 以前に存在しない値のため、旧値への変換対象外)。
    op.execute("UPDATE \"M_MILESTONE\" SET \"status\" = 'true' WHERE \"status\" = 'open'")
    op.execute("UPDATE \"M_MILESTONE\" SET \"status\" = 'false' WHERE \"status\" = 'closed'")
    op.alter_column(
        'M_MILESTONE',
        'guideline_end_date',
        new_column_name='guidline_end_date',
    )