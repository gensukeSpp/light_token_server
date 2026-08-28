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
    # 列名リネーム(データ保持)
    op.alter_column(
        'M_MILESTONE',
        'guidline_end_date',
        new_column_name='guideline_end_date',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'M_MILESTONE',
        'guideline_end_date',
        new_column_name='guidline_end_date',
    )