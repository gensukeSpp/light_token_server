# v0.06 修正: M_LOGGININFO -> M_LOGININFO への改名 (表記ミスの修正)
#
# 元の自動生成版は create_table(M_LOGININFO) + drop_index/drop_table(M_LOGGININFO)
# という「作り直し」で表現していたが、M_LOGGININFO の unique index
# ix_M_LOGGININFO_STAFFID は T_TIMELINE_EVENT / M_MILESTONE の FK から
# 依存されているため、その順序では PostgreSQL が
# "DependentObjectsStillExist" (DROP ... CASCADE を要求) で失敗した。
#
# ここではテーブルを rename で改名する:
#  - テーブル rename では参照側 FK (T_TIMELINE_EVENT / M_MILESTONE) が OID 経由で
#    自動的に新名 M_LOGININFO を参照する形になるため、FK は drop/recreate不要。
#  - データ (ログイン用 PASSWORD_HASH 等) は保持される (create+drop なら消える)。
#  - ただし PostgreSQL ではテーブル rename でインデックス名は追従しないため、
#    ix_M_LOGGININFO_* -> ix_M_LOGININFO_* に明示リネイムしてモデルに揃える。
"""v0.06

Revision ID: 3be6e8d10186
Revises: 04ad260cac90
Create Date: 2026-08-27 10:53:06.730167

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3be6e8d10186'
down_revision: Union[str, Sequence[str], None] = '04ad260cac90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # テーブル名の修正 (同一テーブル・データ保持のままリネーム)
    op.rename_table('M_LOGGININFO', 'M_LOGININFO')

    # インデックス名をモデル (M_LOGININFO) に合わせる。
    # FK 参照列 (STAFFID) の unique index を含め、rename で保つ。
    op.execute('ALTER INDEX "ix_M_LOGGININFO_STAFFID" RENAME TO "ix_M_LOGININFO_STAFFID"')
    op.execute('ALTER INDEX "ix_M_LOGGININFO_PASSWORD_HASH" RENAME TO "ix_M_LOGININFO_PASSWORD_HASH"')
    op.execute('ALTER INDEX "ix_M_LOGGININFO_ADMIN" RENAME TO "ix_M_LOGININFO_ADMIN"')

    # M_MILESTONE.status: Boolean -> String(10) 'open' (requirement-03)
    # 既存行はリテラル 'true'/'false' のまま残るが、新規行の server_default は
    # モデル (server_default=MILESTONE_OPEN) に合わせて 'open' に揃える。
    op.alter_column('M_MILESTONE', 'status',
               existing_type=sa.BOOLEAN(),
               type_=sa.String(length=10),
               existing_nullable=False,
               server_default=sa.text("'open'"),
               existing_server_default=sa.text('true'))


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('M_MILESTONE', 'status',
               existing_type=sa.String(length=10),
               type_=sa.BOOLEAN(),
               existing_nullable=False,
               existing_server_default=sa.text("'open'"),
               server_default=sa.text('true'))
    op.execute('ALTER INDEX "ix_M_LOGININFO_STAFFID" RENAME TO "ix_M_LOGGININFO_STAFFID"')
    op.execute('ALTER INDEX "ix_M_LOGININFO_PASSWORD_HASH" RENAME TO "ix_M_LOGGININFO_PASSWORD_HASH"')
    op.execute('ALTER INDEX "ix_M_LOGININFO_ADMIN" RENAME TO "ix_M_LOGGININFO_ADMIN"')
    op.rename_table('M_LOGININFO', 'M_LOGGININFO')